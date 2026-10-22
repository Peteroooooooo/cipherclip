// Live glass backdrop for a transparent Win32 window.
//
// The page inside WebView2 cannot read the desktop pixels behind the window, so it cannot blur
// them live. Two native ways are provided, both hung *under* the window content and clipped to
// an anti-aliased rounded rectangle of any radius, so the page draws on top:
//
// * Filtered glass (preferred): a capture thread grabs the screen area behind the panel through
//   the Magnification API, which can leave out one window (the panel itself) without hiding it
//   from screenshots. Direct2D then applies a real Gaussian blur and the CSS saturate() colour
//   maths, and the result is drawn into a composition surface. The surface
//   is pinned to the screen, not the window, so a frame that lags behind a moving window still
//   lines up with the desktop.
// * Host backdrop (fallback): the compositor's own blurred backdrop. Live and cheap, but its blur
//   strength is fixed; it can only be faded.
//
// It also drags the window (cc_window_drag_begin): the pointer is followed on a spring, paced by
// the display's frames, instead of the page sending every mouse move through the bridge.
//
// Exported C functions are called from Python (ctypes) on the window's UI thread.

#define NOMINMAX
#include <windows.h>
#include <dwmapi.h>
#include <d3d11.h>
#include <d2d1_1.h>
#include <d2d1effects.h>
#include <DispatcherQueue.h>
#include <windows.ui.composition.interop.h>

#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Foundation.Numerics.h>
#include <winrt/Windows.Graphics.DirectX.h>
#include <winrt/Windows.System.h>
#include <winrt/Windows.UI.h>
#include <winrt/Windows.UI.Composition.h>
#include <winrt/Windows.UI.Composition.Desktop.h>

#include "capture_protocol.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstring>
#include <mutex>
#include <thread>
#include <vector>

namespace wuc = winrt::Windows::UI::Composition;
namespace wucd = winrt::Windows::UI::Composition::Desktop;
namespace abicomp = ABI::Windows::UI::Composition;
using winrt::com_ptr;
using winrt::Windows::Foundation::Numerics::float2;
using winrt::Windows::Foundation::Numerics::float3;

namespace {

constexpr DWORD kUseHostBackdropBrush = 17;  // DWMWA_USE_HOSTBACKDROPBRUSH
constexpr auto kMovingFrame = std::chrono::milliseconds(16);  // as fast as it goes while the window moves
constexpr auto kActiveFrame = std::chrono::milliseconds(33);  // ~30 fps while the backdrop changes
constexpr auto kIdleFrame = std::chrono::milliseconds(100);   // after it has been still for a while
constexpr auto kDeepIdleFrame = std::chrono::milliseconds(250);  // still for several seconds
constexpr auto kMovingLinger = std::chrono::milliseconds(500);   // a move counts as ongoing this long
constexpr int kIdleAfterFrames = 15;
constexpr int kDeepIdleAfterFrames = 40;
constexpr int kGiveUpAfterEmptyGrabs = 30;
// Extra desktop captured around the glass while it moves, so the next frame is already there.
constexpr LONG kMotionMargin = 128;
// The drawn surface reaches this far past the captured area, filled with its clamped (smeared)
// edge, so a drag faster than the margin shows a blur streak rather than a hole.
constexpr int kEdgeBand = 96;

// Window drag spring: natural frequency (rad/s) and damping ratio (< 1 overshoots a little).
constexpr float kDragFrequency = 26.0f;
constexpr float kDragDamping = 0.62f;

struct FilterParams {
    float sigma = 0;  // Gaussian standard deviation in physical pixels (CSS blur() radius)
    float saturation = 1;

    bool Identity() const {
        return sigma < 0.5f && std::fabs(saturation - 1) < 0.005f;
    }
    bool operator!=(FilterParams const& other) const {
        return sigma != other.sigma || saturation != other.saturation;
    }
};

struct Frame {
    std::vector<uint8_t> pixels;
    UINT width = 0;
    UINT height = 0;
    // Always BGRA in memory (the magnifier labels it 32bppRGBA, but the bytes are B, G, R, A).
    UINT stride = 0;
    // Screen position of the captured area (physical px).
    LONG left = 0;
    LONG top = 0;
};

// Calls GetWindowRect / SetWindowPos in physical pixels whatever the calling thread's DPI mode.
class PhysicalPixels {
public:
    PhysicalPixels() : previous_(SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)) {}
    ~PhysicalPixels() {
        if (previous_ != nullptr) {
            SetThreadDpiAwarenessContext(previous_);
        }
    }

private:
    DPI_AWARENESS_CONTEXT previous_;
};

struct FilteredGlass {
    // Shared with the capture thread.
    std::mutex lock;
    FilterParams params;
    Frame pending;
    bool hasPending = false;
    std::atomic<bool> drawQueued{false};
    std::atomic<bool> offsetQueued{false};
    std::atomic<bool> paramsDirty{true};
    std::atomic<bool> enabled{true};
    std::atomic<bool> stop{false};
    std::atomic<int> status{0};  // 0 starting, 1 delivering frames, -1 unavailable
    std::condition_variable started;
    HWND panel = nullptr;
    int inset = 0;
    std::thread worker;

    // UI thread only.
    winrt::Windows::System::DispatcherQueue ui{nullptr};
    com_ptr<ID3D11Device> d3d;
    com_ptr<ID2D1Device> d2d;
    com_ptr<ID2D1DeviceContext> dc;
    wuc::CompositionGraphicsDevice graphics{nullptr};
    wuc::CompositionDrawingSurface surface{nullptr};
    // `visual` is fixed to the glass and clips; `content` holds the surface at its screen spot.
    wuc::ContainerVisual visual{nullptr};
    wuc::SpriteVisual content{nullptr};
    LONG surfaceLeft = 0;  // screen position of the surface's top-left pixel
    LONG surfaceTop = 0;
    com_ptr<ID2D1Bitmap1> bitmap;
    com_ptr<ID2D1Effect> border;
    com_ptr<ID2D1Effect> blur;
    com_ptr<ID2D1Effect> color;
    bool hasDrawn = false;
};

struct LiveBackdrop {
    winrt::Windows::System::DispatcherQueueController queue{nullptr};
    wuc::Compositor compositor{nullptr};
    wucd::DesktopWindowTarget target{nullptr};
    wuc::ContainerVisual root{nullptr};
    wuc::SpriteVisual glass{nullptr};
    wuc::CompositionRoundedRectangleGeometry shape{nullptr};
    float inset = 0;
    bool live = true;
    FilteredGlass* filtered = nullptr;
};

LiveBackdrop* g_backdrop = nullptr;
std::atomic<bool> g_dragging{false};

void EnsureDispatcherQueue(LiveBackdrop& state) {
    if (winrt::Windows::System::DispatcherQueue::GetForCurrentThread()) {
        return;
    }
    DispatcherQueueOptions options{sizeof(DispatcherQueueOptions), DQTYPE_THREAD_CURRENT, DQTAT_COM_STA};
    ABI::Windows::System::IDispatcherQueueController* controller = nullptr;
    winrt::check_hresult(CreateDispatcherQueueController(options, &controller));
    winrt::attach_abi(state.queue, controller);
}

// Which visual shows: the filtered glass when it works and has something to do, otherwise the
// host backdrop. With identity filters nothing shows, so the window is plainly transparent.
void ApplyVisibility() {
    auto& state = *g_backdrop;
    FilteredGlass* filtered = state.filtered;
    if (filtered != nullptr && filtered->status.load() == 1) {
        bool identity;
        {
            std::lock_guard guard(filtered->lock);
            identity = filtered->params.Identity();
        }
        bool const show = state.live && !identity;
        // Windows' own blur stays underneath the (opaque) filtered glass: it covers the moment
        // before the first frame and any edge a very fast drag uncovers.
        state.glass.IsVisible(show);
        filtered->visual.IsVisible(show && filtered->hasDrawn);
        return;
    }
    if (filtered != nullptr && filtered->visual) {
        filtered->visual.IsVisible(false);
    }
    state.glass.IsVisible(state.live);
}

// ---------------------------------------------------------------- rendering (UI thread)

void CreateRenderingDevice(FilteredGlass& glass) {
    UINT flags = D3D11_CREATE_DEVICE_BGRA_SUPPORT;
    HRESULT hr = D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, flags, nullptr, 0, D3D11_SDK_VERSION,
                                   glass.d3d.put(), nullptr, nullptr);
    if (FAILED(hr)) {
        winrt::check_hresult(D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_WARP, nullptr, flags, nullptr, 0,
                                               D3D11_SDK_VERSION, glass.d3d.put(), nullptr, nullptr));
    }
    com_ptr<ID2D1Factory1> factory;
    winrt::check_hresult(
        D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED, __uuidof(ID2D1Factory1), nullptr, factory.put_void()));
    winrt::check_hresult(factory->CreateDevice(glass.d3d.as<IDXGIDevice>().get(), glass.d2d.put()));
    winrt::check_hresult(glass.d2d->CreateDeviceContext(D2D1_DEVICE_CONTEXT_OPTIONS_NONE, glass.dc.put()));

    // Clamp the edges outwards so the blur never pulls in transparent black at a screen edge.
    winrt::check_hresult(glass.dc->CreateEffect(CLSID_D2D1Border, glass.border.put()));
    winrt::check_hresult(glass.border->SetValue(D2D1_BORDER_PROP_EDGE_MODE_X, D2D1_BORDER_EDGE_MODE_CLAMP));
    winrt::check_hresult(glass.border->SetValue(D2D1_BORDER_PROP_EDGE_MODE_Y, D2D1_BORDER_EDGE_MODE_CLAMP));
    winrt::check_hresult(glass.dc->CreateEffect(CLSID_D2D1GaussianBlur, glass.blur.put()));
    glass.blur->SetInputEffect(0, glass.border.get());
    winrt::check_hresult(glass.blur->SetValue(D2D1_GAUSSIANBLUR_PROP_OPTIMIZATION, D2D1_GAUSSIANBLUR_OPTIMIZATION_QUALITY));
    winrt::check_hresult(glass.dc->CreateEffect(CLSID_D2D1ColorMatrix, glass.color.put()));
    winrt::check_hresult(glass.color->SetValue(D2D1_COLORMATRIX_PROP_CLAMP_OUTPUT, TRUE));
    glass.bitmap = nullptr;
}

void RecoverRenderingDevice(FilteredGlass& glass) {
    glass.d3d = nullptr;
    glass.d2d = nullptr;
    glass.dc = nullptr;
    CreateRenderingDevice(glass);
    glass.graphics.as<abicomp::ICompositionGraphicsDeviceInterop>()->SetRenderingDevice(glass.d2d.get());
}

// CSS saturate(s) as a Direct2D colour matrix. Darkening is the page's tint, painted on top.
// Direct2D multiplies a row vector [r g b a 1] by the matrix, so m[input][output].
D2D1_MATRIX_5X4_F ColorMatrix(FilterParams const& p) {
    float const s = p.saturation;
    float const saturate[3][3] = {
        {0.213f + 0.787f * s, 0.715f - 0.715f * s, 0.072f - 0.072f * s},
        {0.213f - 0.213f * s, 0.715f + 0.285f * s, 0.072f - 0.072f * s},
        {0.213f - 0.213f * s, 0.715f - 0.715f * s, 0.072f + 0.928f * s},
    };
    D2D1_MATRIX_5X4_F m{};
    for (int out = 0; out < 3; ++out) {
        for (int in = 0; in < 3; ++in) {
            m.m[in][out] = saturate[out][in];
        }
    }
    m.m[3][3] = 1;
    return m;
}

// Places the surface where it was captured, relative to where the glass is now. Called after
// every draw and every move, so a moving window slides over a still desktop image.
void UpdateContentOffset(FilteredGlass& glass) {
    if (!glass.content) {
        return;
    }
    RECT window{};
    {
        PhysicalPixels physical;
        GetWindowRect(glass.panel, &window);
    }
    glass.content.Offset(float3{static_cast<float>(glass.surfaceLeft - (window.left + glass.inset)),
                                static_cast<float>(glass.surfaceTop - (window.top + glass.inset)), 0.0f});
}

void Render(FilteredGlass& glass, Frame const& frame, FilterParams const& params) {
    if (glass.bitmap) {
        D2D1_SIZE_U const size = glass.bitmap->GetPixelSize();
        if (size.width != frame.width || size.height != frame.height) {
            glass.bitmap = nullptr;
        }
    }
    if (!glass.bitmap) {
        D2D1_BITMAP_PROPERTIES1 props =
            D2D1::BitmapProperties1(D2D1_BITMAP_OPTIONS_NONE,
                                    D2D1::PixelFormat(DXGI_FORMAT_B8G8R8A8_UNORM, D2D1_ALPHA_MODE_IGNORE));
        winrt::check_hresult(
            glass.dc->CreateBitmap(D2D1::SizeU(frame.width, frame.height), nullptr, 0, props, glass.bitmap.put()));
        glass.border->SetInput(0, glass.bitmap.get());
    }
    winrt::check_hresult(glass.bitmap->CopyFromMemory(nullptr, frame.pixels.data(), frame.stride));

    bool const blurring = params.sigma >= 0.5f;
    if (blurring) {
        winrt::check_hresult(glass.blur->SetValue(D2D1_GAUSSIANBLUR_PROP_STANDARD_DEVIATION, params.sigma));
        glass.color->SetInputEffect(0, glass.blur.get());
    } else {
        glass.color->SetInputEffect(0, glass.border.get());
    }
    winrt::check_hresult(glass.color->SetValue(D2D1_COLORMATRIX_PROP_COLOR_MATRIX, ColorMatrix(params)));

    int const width = static_cast<int>(frame.width) + 2 * kEdgeBand;
    int const height = static_cast<int>(frame.height) + 2 * kEdgeBand;
    winrt::Windows::Foundation::Size const surfaceSize{static_cast<float>(width), static_cast<float>(height)};
    if (!glass.surface) {
        glass.surface = glass.graphics.CreateDrawingSurface(
            surfaceSize, winrt::Windows::Graphics::DirectX::DirectXPixelFormat::B8G8R8A8UIntNormalized,
            winrt::Windows::Graphics::DirectX::DirectXAlphaMode::Premultiplied);
        auto brush = g_backdrop->compositor.CreateSurfaceBrush(glass.surface);
        brush.Stretch(wuc::CompositionStretch::None);
        brush.HorizontalAlignmentRatio(0);
        brush.VerticalAlignmentRatio(0);
        glass.content.Brush(brush);
    }
    auto interop = glass.surface.as<abicomp::ICompositionDrawingSurfaceInterop>();
    auto const current = glass.surface.Size();
    if (current.Width != surfaceSize.Width || current.Height != surfaceSize.Height) {
        winrt::check_hresult(interop->Resize(SIZE{width, height}));
    }

    com_ptr<ID2D1DeviceContext> target;
    POINT offset{};
    winrt::check_hresult(interop->BeginDraw(nullptr, __uuidof(ID2D1DeviceContext), target.put_void(), &offset));
    target->SetDpi(96, 96);
    target->SetTransform(D2D1::Matrix3x2F::Translation(static_cast<float>(offset.x), static_cast<float>(offset.y)));
    target->Clear(D2D1::ColorF(0, 0, 0, 0));
    target->PushAxisAlignedClip(D2D1::RectF(0, 0, surfaceSize.Width, surfaceSize.Height), D2D1_ANTIALIAS_MODE_ALIASED);
    // The border effect clamps outwards, so the band around the captured area is its smeared edge.
    D2D1_POINT_2F const at{0.0f, 0.0f};
    D2D1_RECT_F const source{-static_cast<float>(kEdgeBand), -static_cast<float>(kEdgeBand),
                             static_cast<float>(frame.width + kEdgeBand), static_cast<float>(frame.height + kEdgeBand)};
    target->DrawImage(glass.color.get(), &at, &source);
    target->PopAxisAlignedClip();
    winrt::check_hresult(interop->EndDraw());

    glass.content.Size(float2{surfaceSize.Width, surfaceSize.Height});
    glass.surfaceLeft = frame.left - kEdgeBand;
    glass.surfaceTop = frame.top - kEdgeBand;
    UpdateContentOffset(glass);

    if (!glass.hasDrawn) {
        glass.hasDrawn = true;
        ApplyVisibility();
    }
}

void DrawPendingFrame() {
    if (g_backdrop == nullptr || g_backdrop->filtered == nullptr) {
        return;
    }
    FilteredGlass& glass = *g_backdrop->filtered;
    glass.drawQueued = false;
    Frame frame;
    FilterParams params;
    {
        std::lock_guard guard(glass.lock);
        if (!glass.hasPending) {
            return;
        }
        frame = std::move(glass.pending);
        glass.hasPending = false;
        params = glass.params;
    }
    try {
        Render(glass, frame, params);
    } catch (...) {
        // Most likely a lost GPU device (driver update, sleep). Rebuild it; the next frame redraws.
        try {
            RecoverRenderingDevice(glass);
        } catch (...) {
        }
        glass.paramsDirty = true;
    }
}

// ---------------------------------------------------------------- capture (worker thread)

// The capture runs in cipherclip_capture.exe (capture_helper.cpp): inside this process the
// Magnification API still sees this window's own composition visuals, so the glass would capture
// itself and blur and dim its own output again on every frame. Requests and pixels go through a
// named shared-memory block.
class CaptureClient {
public:
    ~CaptureClient() {
        if (view_ != nullptr) {
            UnmapViewOfFile(view_);
        }
        for (HANDLE handle : {mapping_, request_, done_, process_}) {
            if (handle != nullptr) {
                CloseHandle(handle);
            }
        }
    }

    bool Start() {
        DWORD const self = GetCurrentProcessId();
        wchar_t name[96];
        CaptureObjectName(name, self, L"Memory");
        ULONGLONG const size = sizeof(SharedCapture) + kCapturePixelCapacity;
        mapping_ = CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE | SEC_RESERVE,
                                      static_cast<DWORD>(size >> 32), static_cast<DWORD>(size), name);
        CaptureObjectName(name, self, L"Request");
        request_ = CreateEventW(nullptr, FALSE, FALSE, name);
        CaptureObjectName(name, self, L"Done");
        done_ = CreateEventW(nullptr, FALSE, FALSE, name);
        if (mapping_ == nullptr || request_ == nullptr || done_ == nullptr) {
            return false;
        }
        view_ = static_cast<SharedCapture*>(MapViewOfFile(mapping_, FILE_MAP_ALL_ACCESS, 0, 0, 0));
        if (view_ == nullptr || VirtualAlloc(view_, static_cast<SIZE_T>(size), MEM_COMMIT, PAGE_READWRITE) == nullptr) {
            return false;
        }

        // The helper sits next to this DLL.
        wchar_t path[MAX_PATH];
        HMODULE self_module = nullptr;
        GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           reinterpret_cast<LPCWSTR>(&CaptureObjectName), &self_module);
        DWORD const length = GetModuleFileNameW(self_module, path, MAX_PATH);
        if (length == 0 || length >= MAX_PATH) {
            return false;
        }
        wchar_t* slash = wcsrchr(path, L'\\');
        if (slash == nullptr) {
            return false;
        }
        wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - path), L"cipherclip_capture.exe");
        wchar_t commandLine[MAX_PATH + 32];
        swprintf(commandLine, MAX_PATH + 32, L"\"%ls\" %lu", path, static_cast<unsigned long>(self));
        STARTUPINFOW startup{sizeof(startup)};
        PROCESS_INFORMATION process{};
        if (!CreateProcessW(path, commandLine, nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr, nullptr, &startup,
                            &process)) {
            return false;
        }
        CloseHandle(process.hThread);
        process_ = process.hProcess;
        return true;
    }

    bool Grab(HWND exclude, RECT const& area, Frame& frame) {
        view_->left = area.left;
        view_->top = area.top;
        view_->right = area.right;
        view_->bottom = area.bottom;
        view_->exclude = static_cast<int64_t>(reinterpret_cast<intptr_t>(exclude));
        view_->ok = 0;
        SetEvent(request_);
        HANDLE waits[] = {done_, process_};
        if (WaitForMultipleObjects(2, waits, FALSE, 1000) != WAIT_OBJECT_0 || !view_->ok) {
            return false;
        }
        UINT const width = static_cast<UINT>(area.right - area.left);
        UINT const height = static_cast<UINT>(area.bottom - area.top);
        if (view_->width != width || view_->height != height) {
            return false;
        }
        auto const* pixels = reinterpret_cast<uint8_t const*>(view_ + 1);
        frame.pixels.assign(pixels, pixels + static_cast<size_t>(view_->stride) * view_->height);
        frame.width = view_->width;
        frame.height = view_->height;
        frame.stride = view_->stride;
        return true;
    }

private:
    HANDLE mapping_ = nullptr;
    HANDLE request_ = nullptr;
    HANDLE done_ = nullptr;
    HANDLE process_ = nullptr;
    SharedCapture* view_ = nullptr;
};

void QueueDraw(FilteredGlass& glass) {
    if (!glass.drawQueued.exchange(true)) {
        glass.ui.TryEnqueue([] { DrawPendingFrame(); });
    }
}

void CaptureLoop(FilteredGlass* glass) {
    SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    CaptureClient capture;
    bool ready = capture.Start();

    // Prove the helper actually delivers pixels on this system before reporting success.
    Frame frame;
    if (ready) {
        RECT probe{};
        GetWindowRect(glass->panel, &probe);
        ready = capture.Grab(glass->panel, RECT{probe.left, probe.top, probe.left + 8, probe.top + 8}, frame);
    }
    glass->status = ready ? 1 : -1;
    glass->started.notify_all();

    Frame previous;
    RECT previousArea{};
    RECT previousGlass{};
    auto lastMove = std::chrono::steady_clock::time_point{};
    bool wasShowing = false;
    int stillFrames = 0;
    int emptyGrabs = 0;
    while (ready && !glass->stop) {
        auto const begin = std::chrono::steady_clock::now();

        FilterParams params;
        {
            std::lock_guard guard(glass->lock);
            params = glass->params;
        }
        bool const showing = glass->enabled && IsWindowVisible(glass->panel) && !IsIconic(glass->panel);
        if (!showing || params.Identity()) {
            wasShowing = false;
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }

        RECT window{};
        GetWindowRect(glass->panel, &window);
        RECT const glassRect{window.left + glass->inset, window.top + glass->inset, window.right - glass->inset,
                             window.bottom - glass->inset};
        if (wasShowing && std::memcmp(&glassRect, &previousGlass, sizeof(RECT)) != 0) {
            lastMove = begin;
        }
        previousGlass = glassRect;
        bool const moving = g_dragging.load() || begin - lastMove < kMovingLinger;
        // Capture a margin around the glass so the blur near its edges sees real content, and
        // more while it moves, so the frame still covers the glass when it lands a little late.
        LONG const pad = static_cast<LONG>(std::ceil(params.sigma * 3)) + 2 + (moving ? kMotionMargin : 0);
        LONG const screenLeft = GetSystemMetrics(SM_XVIRTUALSCREEN);
        LONG const screenTop = GetSystemMetrics(SM_YVIRTUALSCREEN);
        RECT const area{
            std::max(glassRect.left - pad, screenLeft),
            std::max(glassRect.top - pad, screenTop),
            std::min(glassRect.right + pad, screenLeft + static_cast<LONG>(GetSystemMetrics(SM_CXVIRTUALSCREEN))),
            std::min(glassRect.bottom + pad, screenTop + static_cast<LONG>(GetSystemMetrics(SM_CYVIRTUALSCREEN))),
        };
        if (area.right <= area.left || area.bottom <= area.top || glassRect.right <= glassRect.left ||
            glassRect.bottom <= glassRect.top) {
            std::this_thread::sleep_for(kActiveFrame);
            continue;
        }

        if (!capture.Grab(glass->panel, area, frame)) {
            if (++emptyGrabs >= kGiveUpAfterEmptyGrabs) {
                // The API stopped delivering (a future Windows change?): fall back to the host backdrop.
                glass->status = -1;
                glass->ui.TryEnqueue([] { ApplyVisibility(); });
                break;
            }
            std::this_thread::sleep_for(kActiveFrame);
            continue;
        }
        emptyGrabs = 0;
        frame.left = area.left;
        frame.top = area.top;

        bool const moved = std::memcmp(&area, &previousArea, sizeof(RECT)) != 0;
        bool const changed = !wasShowing || moved || glass->paramsDirty.exchange(false) ||
                             frame.pixels.size() != previous.pixels.size() ||
                             std::memcmp(frame.pixels.data(), previous.pixels.data(), frame.pixels.size()) != 0;
        if (changed) {
            {
                std::lock_guard guard(glass->lock);
                glass->pending = frame;
                glass->hasPending = true;
            }
            QueueDraw(*glass);
            std::swap(previous, frame);
            previousArea = area;
            stillFrames = 0;
        } else {
            ++stillFrames;
        }
        wasShowing = true;

        auto const budget = moving                              ? kMovingFrame
                            : stillFrames > kDeepIdleAfterFrames ? kDeepIdleFrame
                            : stillFrames > kIdleAfterFrames     ? kIdleFrame
                                                                 : kActiveFrame;
        auto const spent = std::chrono::steady_clock::now() - begin;
        if (spent < budget) {
            std::this_thread::sleep_for(budget - spent);
        }
    }
}

// ---------------------------------------------------------------- window drag (drag thread)

void QueueOffsetUpdate() {
    if (g_backdrop == nullptr || g_backdrop->filtered == nullptr) {
        return;
    }
    FilteredGlass* glass = g_backdrop->filtered;
    if (!glass->offsetQueued.exchange(true)) {
        glass->ui.TryEnqueue(winrt::Windows::System::DispatcherQueuePriority::High, [glass] {
            glass->offsetQueued = false;
            UpdateContentOffset(*glass);
        });
    }
}

bool PrimaryButtonDown() {
    int const key = GetSystemMetrics(SM_SWAPBUTTON) ? VK_RBUTTON : VK_LBUTTON;
    return (GetAsyncKeyState(key) & 0x8000) != 0;
}

// Follows the pointer until the button is let go. Elastic: the window is pulled towards the
// pointer by a slightly under-damped spring, so it trails a fast drag and settles with a small
// overshoot when released. Paced by DWM's frames, so every displayed frame gets one move.
void DragLoop(HWND hwnd, LONG grabX, LONG grabY, bool elastic) {
    SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    RECT rect{};
    GetWindowRect(hwnd, &rect);
    if (grabX < 0 || grabY < 0 || grabX >= rect.right - rect.left || grabY >= rect.bottom - rect.top) {
        POINT cursor{};
        GetCursorPos(&cursor);
        grabX = cursor.x - rect.left;
        grabY = cursor.y - rect.top;
    }

    float x = static_cast<float>(rect.left), y = static_cast<float>(rect.top);
    float targetX = x, targetY = y, speedX = 0, speedY = 0;
    LONG shownX = rect.left, shownY = rect.top;
    bool held = true;
    auto previous = std::chrono::steady_clock::now();
    auto released = previous;
    while (IsWindow(hwnd) && IsWindowVisible(hwnd)) {
        if (FAILED(DwmFlush())) {
            std::this_thread::sleep_for(std::chrono::milliseconds(8));
        }
        auto const now = std::chrono::steady_clock::now();
        float const dt = std::min(std::chrono::duration<float>(now - previous).count(), 0.05f);
        previous = now;

        if (held && !PrimaryButtonDown()) {
            held = false;
            released = now;
        }
        if (held) {
            POINT cursor{};
            GetCursorPos(&cursor);
            targetX = static_cast<float>(cursor.x - grabX);
            targetY = static_cast<float>(cursor.y - grabY);
        }

        if (elastic) {
            // Small fixed steps keep the spring stable whatever the frame time.
            int const steps = std::max(1, static_cast<int>(std::ceil(dt / 0.002f)));
            float const h = dt / steps;
            float const stiffness = kDragFrequency * kDragFrequency;
            float const friction = 2 * kDragDamping * kDragFrequency;
            for (int i = 0; i < steps; ++i) {
                speedX += (stiffness * (targetX - x) - friction * speedX) * h;
                speedY += (stiffness * (targetY - y) - friction * speedY) * h;
                x += speedX * h;
                y += speedY * h;
            }
        } else {
            x = targetX;
            y = targetY;
        }

        bool settled = false;
        if (!held) {
            settled = !elastic || (std::fabs(targetX - x) < 0.5f && std::fabs(targetY - y) < 0.5f &&
                                   std::hypot(speedX, speedY) < 30.0f) ||
                      now - released > std::chrono::seconds(2);
            if (settled) {
                x = targetX;
                y = targetY;
            }
        }
        LONG const nextX = std::lround(x), nextY = std::lround(y);
        if (nextX != shownX || nextY != shownY) {
            SetWindowPos(hwnd, nullptr, nextX, nextY, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
            shownX = nextX;
            shownY = nextY;
            QueueOffsetUpdate();
        }
        if (settled) {
            break;
        }
    }
    g_dragging = false;
}

}  // namespace

// Attaches the live backdrop. `inset` keeps it inside the transparent shadow margin, `radius`
// is the corner radius; both in physical pixels. Returns 0 on success, an HRESULT otherwise.
extern "C" __declspec(dllexport) int cc_live_backdrop_attach(HWND hwnd, float inset, float radius) {
    try {
        if (g_backdrop != nullptr) {
            return 0;
        }
        auto state = new LiveBackdrop();
        state->inset = inset;
        EnsureDispatcherQueue(*state);

        BOOL enable = TRUE;
        DwmSetWindowAttribute(hwnd, kUseHostBackdropBrush, &enable, sizeof(enable));

        state->compositor = wuc::Compositor();
        auto interop = state->compositor.as<abicomp::Desktop::ICompositorDesktopInterop>();
        winrt::check_hresult(interop->CreateDesktopWindowTarget(
            hwnd, FALSE, reinterpret_cast<abicomp::Desktop::IDesktopWindowTarget**>(winrt::put_abi(state->target))));

        state->root = state->compositor.CreateContainerVisual();
        state->root.RelativeSizeAdjustment(float2{1.0f, 1.0f});
        state->target.Root(state->root);

        state->shape = state->compositor.CreateRoundedRectangleGeometry();
        state->shape.CornerRadius(float2{radius, radius});

        state->glass = state->compositor.CreateSpriteVisual();
        state->glass.Brush(state->compositor.CreateHostBackdropBrush());
        state->glass.Offset(float3{inset, inset, 0.0f});
        state->glass.RelativeSizeAdjustment(float2{1.0f, 1.0f});
        state->glass.Size(float2{-2.0f * inset, -2.0f * inset});
        state->glass.Clip(state->compositor.CreateGeometricClip(state->shape));
        state->root.Children().InsertAtTop(state->glass);

        g_backdrop = state;
        return 0;
    } catch (winrt::hresult_error const& error) {
        return static_cast<int>(error.code());
    } catch (...) {
        return static_cast<int>(E_FAIL);
    }
}

// Starts the filtered glass for `hwnd` (the window passed to attach). Returns 0 when the capture
// delivers frames, a non-zero code when this system cannot do it (the host backdrop stays).
extern "C" __declspec(dllexport) int cc_live_filter_start(HWND hwnd) {
    if (g_backdrop == nullptr) {
        return 1;
    }
    if (g_backdrop->filtered != nullptr) {
        return g_backdrop->filtered->status.load() == 1 ? 0 : 2;
    }
    try {
        auto glass = new FilteredGlass();
        glass->panel = hwnd;
        glass->inset = static_cast<int>(std::lround(g_backdrop->inset));
        glass->ui = winrt::Windows::System::DispatcherQueue::GetForCurrentThread();
        CreateRenderingDevice(*glass);
        winrt::check_hresult(g_backdrop->compositor.as<abicomp::ICompositorInterop>()->CreateGraphicsDevice(
            glass->d2d.get(), reinterpret_cast<abicomp::ICompositionGraphicsDevice**>(winrt::put_abi(glass->graphics))));

        glass->visual = g_backdrop->compositor.CreateContainerVisual();
        glass->visual.Offset(float3{g_backdrop->inset, g_backdrop->inset, 0.0f});
        glass->visual.RelativeSizeAdjustment(float2{1.0f, 1.0f});
        glass->visual.Size(float2{-2.0f * g_backdrop->inset, -2.0f * g_backdrop->inset});
        glass->visual.Clip(g_backdrop->compositor.CreateGeometricClip(g_backdrop->shape));
        glass->visual.IsVisible(false);
        glass->content = g_backdrop->compositor.CreateSpriteVisual();
        glass->visual.Children().InsertAtTop(glass->content);
        g_backdrop->root.Children().InsertAtTop(glass->visual);
        glass->enabled = g_backdrop->live;
        g_backdrop->filtered = glass;

        glass->worker = std::thread(CaptureLoop, glass);
        glass->worker.detach();
        {
            std::unique_lock guard(glass->lock);
            glass->started.wait_for(guard, std::chrono::milliseconds(1500), [glass] { return glass->status.load() != 0; });
        }
        ApplyVisibility();
        return glass->status.load() == 1 ? 0 : 3;
    } catch (winrt::hresult_error const& error) {
        return static_cast<int>(error.code());
    } catch (...) {
        return static_cast<int>(E_FAIL);
    }
}

// Filter values for the filtered glass: blur standard deviation in physical pixels, then CSS
// saturate factor (1 = unchanged).
extern "C" __declspec(dllexport) void cc_live_filter_set(float sigma, float saturation) {
    if (g_backdrop == nullptr || g_backdrop->filtered == nullptr) {
        return;
    }
    FilteredGlass& glass = *g_backdrop->filtered;
    {
        std::lock_guard guard(glass.lock);
        FilterParams next{std::max(0.0f, sigma), saturation};
        if (!(next != glass.params)) {
            return;
        }
        glass.params = next;
    }
    glass.paramsDirty = true;
    ApplyVisibility();
}

// 1 while the filtered glass delivers frames, 0 while starting, -1 when unavailable.
extern "C" __declspec(dllexport) int cc_live_filter_status() {
    if (g_backdrop == nullptr || g_backdrop->filtered == nullptr) {
        return -1;
    }
    return g_backdrop->filtered->status.load();
}

// The clip geometry is not relative, so it is resized with the window (physical pixels).
extern "C" __declspec(dllexport) void cc_live_backdrop_resize(float width, float height) {
    if (g_backdrop == nullptr) {
        return;
    }
    const float inset = g_backdrop->inset;
    g_backdrop->shape.Size(float2{width - 2.0f * inset, height - 2.0f * inset});
}

extern "C" __declspec(dllexport) void cc_live_backdrop_set_radius(float radius) {
    if (g_backdrop == nullptr) {
        return;
    }
    g_backdrop->shape.CornerRadius(float2{radius, radius});
}

// Live glass on or off (off: the page paints a desktop snapshot instead).
extern "C" __declspec(dllexport) void cc_live_backdrop_set_visible(int visible) {
    if (g_backdrop == nullptr) {
        return;
    }
    g_backdrop->live = visible != 0;
    if (g_backdrop->filtered != nullptr) {
        g_backdrop->filtered->enabled = g_backdrop->live;
        g_backdrop->filtered->paramsDirty = true;
    }
    ApplyVisibility();
}

// Starts dragging `hwnd` after a press on the page's drag region; the drag ends when the button
// is released. (grabX, grabY) is the pressed point inside the window in physical pixels, so the
// window catches up with any pointer movement made before this call arrived. Works with or
// without the live backdrop attached. Returns 0 when started, 1 when a drag is already running.
extern "C" __declspec(dllexport) int cc_window_drag_begin(HWND hwnd, int grabX, int grabY, int elastic) {
    if (g_dragging.exchange(true)) {
        return 1;
    }
    try {
        std::thread(DragLoop, hwnd, static_cast<LONG>(grabX), static_cast<LONG>(grabY), elastic != 0).detach();
    } catch (...) {
        g_dragging = false;
        return static_cast<int>(E_FAIL);
    }
    return 0;
}

// The host backdrop brush has one fixed blur strength. Fading the visual out (0..1) is the only
// way to get less: at 0 the transparent window shows the desktop unblurred. Fallback path only.
extern "C" __declspec(dllexport) void cc_live_backdrop_set_opacity(float opacity) {
    if (g_backdrop == nullptr) {
        return;
    }
    g_backdrop->glass.Opacity(opacity < 0.0f ? 0.0f : (opacity > 1.0f ? 1.0f : opacity));
}
