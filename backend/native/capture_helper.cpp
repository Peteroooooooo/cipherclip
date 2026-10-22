// Screen capture helper for the filtered live glass (see live_backdrop.cpp).
//
// The Magnification API can leave one window out of its capture. Run inside the app's own
// process it still sees the app's composition visuals (the filtered glass itself), so this tiny
// process grabs on request and hands the pixels over through shared memory.
//
// Usage: cipherclip_capture.exe <parent process id>. Exits when the parent goes away.

#define NOMINMAX
#include <windows.h>
#include <magnification.h>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <cwchar>

#include "capture_protocol.h"

namespace {

SharedCapture* g_shared = nullptr;

BOOL CALLBACK OnFrame(HWND, void* source, MAGIMAGEHEADER header, void*, MAGIMAGEHEADER, RECT, RECT, HRGN) {
    if (g_shared == nullptr || source == nullptr) {
        return TRUE;
    }
    size_t const bytes = static_cast<size_t>(header.stride) * header.height;
    if (bytes > kCapturePixelCapacity) {
        return TRUE;
    }
    std::memcpy(g_shared + 1, source, bytes);
    g_shared->width = header.width;
    g_shared->height = header.height;
    g_shared->stride = header.stride;
    g_shared->ok = 1;
    return TRUE;
}

}  // namespace

#pragma warning(push)
#pragma warning(disable : 4996)  // MagSetImageScalingCallback is marked deprecated but still works
int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR commandLine, int) {
    DWORD const parentId = static_cast<DWORD>(std::wcstoul(commandLine, nullptr, 10));
    HANDLE parent = OpenProcess(SYNCHRONIZE, FALSE, parentId);
    if (parent == nullptr) {
        return 1;
    }
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);

    wchar_t name[96];
    CaptureObjectName(name, parentId, L"Memory");
    HANDLE mapping = OpenFileMappingW(FILE_MAP_ALL_ACCESS, FALSE, name);
    CaptureObjectName(name, parentId, L"Request");
    HANDLE request = OpenEventW(SYNCHRONIZE | EVENT_MODIFY_STATE, FALSE, name);
    CaptureObjectName(name, parentId, L"Done");
    HANDLE done = OpenEventW(EVENT_MODIFY_STATE, FALSE, name);
    if (mapping == nullptr || request == nullptr || done == nullptr) {
        return 2;
    }
    g_shared = static_cast<SharedCapture*>(MapViewOfFile(mapping, FILE_MAP_ALL_ACCESS, 0, 0, 0));
    if (g_shared == nullptr || !MagInitialize()) {
        return 3;
    }

    HWND host = CreateWindowExW(WS_EX_LAYERED | WS_EX_TOOLWINDOW, L"Static", L"", WS_POPUP, 0, 0, 1, 1, nullptr, nullptr,
                                instance, nullptr);
    HWND magnifier =
        CreateWindowExW(0, WC_MAGNIFIERW, L"", WS_CHILD | WS_VISIBLE, 0, 0, 1, 1, host, nullptr, instance, nullptr);
    if (host == nullptr || magnifier == nullptr || !MagSetImageScalingCallback(magnifier, OnFrame)) {
        return 4;
    }

    HANDLE waits[] = {request, parent};
    for (;;) {
        DWORD const woke = MsgWaitForMultipleObjects(2, waits, FALSE, INFINITE, QS_ALLINPUT);
        if (woke == WAIT_OBJECT_0 + 1 || woke == WAIT_FAILED) {
            break;  // parent exited
        }
        if (woke == WAIT_OBJECT_0 + 2) {
            MSG message;
            while (PeekMessageW(&message, nullptr, 0, 0, PM_REMOVE)) {
                DispatchMessageW(&message);
            }
            continue;
        }

        // Set on every grab: an exclusion made while the window was hidden does not cover what the
        // window composes once it is shown, and the glass would then capture its own output.
        HWND list[] = {reinterpret_cast<HWND>(static_cast<intptr_t>(g_shared->exclude))};
        MagSetWindowFilterList(magnifier, MW_FILTERMODE_EXCLUDE, 1, list);
        RECT const area{g_shared->left, g_shared->top, g_shared->right, g_shared->bottom};
        int const width = area.right - area.left;
        int const height = area.bottom - area.top;
        RECT client{};
        GetClientRect(magnifier, &client);
        if (client.right != width || client.bottom != height) {
            SetWindowPos(host, nullptr, 0, 0, width, height, SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOMOVE);
            SetWindowPos(magnifier, nullptr, 0, 0, width, height, SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOMOVE);
        }
        g_shared->ok = 0;
        MagSetWindowSource(magnifier, area);  // runs OnFrame synchronously
        SetEvent(done);
    }

    MagUninitialize();
    return 0;
}
#pragma warning(pop)
