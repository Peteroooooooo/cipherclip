// Shared-memory handshake between live_backdrop.cpp (in the app) and capture_helper.cpp.
#pragma once

#include <windows.h>

#include <cstdint>
#include <cwchar>

// Largest frame the helper hands over: the panel plus its blur margin, BGRA. 64 MB covers a
// 4000 x 4000 area; the mapping is page-file backed, so untouched pages cost nothing.
constexpr size_t kCapturePixelCapacity = 64ull * 1024 * 1024;

// Followed directly by the pixel bytes.
struct SharedCapture {
    // Request, written by the app before it signals "Request".
    LONG left;
    LONG top;
    LONG right;
    LONG bottom;
    int64_t exclude;  // HWND left out of the capture
    // Reply, written by the helper before it signals "Done".
    UINT width;
    UINT height;
    UINT stride;
    int ok;
};

inline void CaptureObjectName(wchar_t* out, DWORD appProcessId, wchar_t const* part) {
    swprintf(out, 96, L"Local\\ClipDeck.Capture.%lu.%ls", static_cast<unsigned long>(appProcessId), part);
}
