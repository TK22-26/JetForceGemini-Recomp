#pragma once
#include <windows.h>
#include <d3d11.h>
#include <dxgi1_2.h>
#include <wrl/client.h>
#include <stdexcept>

namespace jfg::frontend {
// An HWND swap chain cannot composite over the hosted game child. Present only
// the UI panel's pixels in an owned popup, keeping the game window visible.
// Both surfaces use the same device/context and the same RmlUi layout/input.
class FallbackOverlay {
    HWND window_ = nullptr;
    Microsoft::WRL::ComPtr<IDXGISwapChain1> swap_;
    int width_ = 0, height_ = 0;
    static void checked(HRESULT result) {
        if (FAILED(result)) throw std::runtime_error("Cannot present launcher overlay");
    }
    static LRESULT CALLBACK procedure(HWND window, UINT message, WPARAM w, LPARAM l) {
        if (message == WM_MOUSEACTIVATE) return MA_NOACTIVATE;
        if (message == WM_ERASEBKGND) return 1;
        if (message >= WM_MOUSEFIRST && message <= WM_MOUSELAST) {
            HWND owner = GetWindow(window, GW_OWNER);
            if (message != WM_MOUSEWHEEL && message != WM_MOUSEHWHEEL) {
                POINT point{static_cast<short>(LOWORD(l)), static_cast<short>(HIWORD(l))};
                MapWindowPoints(window, owner, &point, 1);
                l = MAKELPARAM(point.x, point.y);
            }
            return SendMessageW(owner, message, w, l);
        }
        return DefWindowProcW(window, message, w, l);
    }
public:
    FallbackOverlay() = default;
    FallbackOverlay(const FallbackOverlay&) = delete;
    FallbackOverlay& operator=(const FallbackOverlay&) = delete;
    ~FallbackOverlay() { if (window_) DestroyWindow(window_); }
    HWND window() const { return window_; }
    IDXGISwapChain1* swapChain() const { return swap_.Get(); }
    void hide() { if (window_ && IsWindowVisible(window_)) ShowWindow(window_, SW_HIDE); }
    void present(HWND owner, ID3D11Device* device, ID3D11DeviceContext* gpu,
                 ID3D11Resource* source, const RECT& bounds) {
        const int width = bounds.right - bounds.left, height = bounds.bottom - bounds.top;
        if (width <= 0 || height <= 0) { hide(); return; }
        if (!window_) {
            WNDCLASSW cls{};
            cls.hInstance = GetModuleHandleW(nullptr);
            cls.lpfnWndProc = procedure;
            cls.lpszClassName = L"JfgFallbackOverlay";
            cls.hCursor = LoadCursorW(nullptr, IDC_ARROW);
            if (!RegisterClassW(&cls) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
                throw std::runtime_error("Cannot register launcher overlay");
            window_ = CreateWindowExW(WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                cls.lpszClassName, L"JFG launcher panel", WS_POPUP,
                0, 0, width, height, owner, nullptr, cls.hInstance, nullptr);
            if (!window_) throw std::runtime_error("Cannot create launcher overlay");
            Microsoft::WRL::ComPtr<IDXGIDevice> dxgi;
            Microsoft::WRL::ComPtr<IDXGIAdapter> adapter;
            Microsoft::WRL::ComPtr<IDXGIFactory2> factory;
            checked(device->QueryInterface(IID_PPV_ARGS(&dxgi)));
            checked(dxgi->GetAdapter(&adapter));
            checked(adapter->GetParent(IID_PPV_ARGS(&factory)));
            DXGI_SWAP_CHAIN_DESC1 desc{};
            desc.Width = width; desc.Height = height;
            desc.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
            desc.SampleDesc.Count = 1;
            desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
            desc.BufferCount = 2;
            desc.SwapEffect = DXGI_SWAP_EFFECT_DISCARD;
            desc.AlphaMode = DXGI_ALPHA_MODE_IGNORE;
            checked(factory->CreateSwapChainForHwnd(device, window_, &desc, nullptr, nullptr, &swap_));
            checked(factory->MakeWindowAssociation(window_, DXGI_MWA_NO_ALT_ENTER));
            width_ = width; height_ = height;
        }
        if (width != width_ || height != height_) {
            checked(swap_->ResizeBuffers(0, width, height, DXGI_FORMAT_UNKNOWN, 0));
            width_ = width; height_ = height;
        }
        Microsoft::WRL::ComPtr<ID3D11Texture2D> destination;
        checked(swap_->GetBuffer(0, IID_PPV_ARGS(&destination)));
        const D3D11_BOX box{static_cast<UINT>(bounds.left), static_cast<UINT>(bounds.top), 0,
                           static_cast<UINT>(bounds.right), static_cast<UINT>(bounds.bottom), 1};
        gpu->CopySubresourceRegion(destination.Get(), 0, 0, 0, 0, source, 0, &box);
        POINT origin{bounds.left, bounds.top};
        ClientToScreen(owner, &origin);
        SetWindowPos(window_, nullptr, origin.x, origin.y, width, height,
                     SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW);
        checked(swap_->Present(0, 0));
    }
};
}
