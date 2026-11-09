#include "jfg/runtime/win32_relative_mouse.hpp"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <atomic>
#include <thread>
#include <iostream>
static BOOL WINAPI denied(const RECT*) { SetLastError(ERROR_ACCESS_DENIED); return FALSE; }
static LRESULT CALLBACK procedure(HWND w,UINT m,WPARAM a,LPARAM b) { return DefWindowProcW(w,m,a,b); }
static void pump() { MSG m{};while(PeekMessageW(&m,nullptr,0,0,PM_REMOVE)){TranslateMessage(&m);DispatchMessageW(&m);} }
int main() {
    const HWND previous=GetForegroundWindow();POINT before{};GetCursorPos(&before);
    WNDCLASSW c{};c.lpfnWndProc=procedure;c.hInstance=GetModuleHandleW(nullptr);c.lpszClassName=L"JfgRelativeMouseRegression";
    assert(RegisterClassW(&c));
    HWND root=CreateWindowW(c.lpszClassName,L"JFG mouse regression",WS_OVERLAPPEDWINDOW|WS_VISIBLE,100,100,600,420,nullptr,nullptr,c.hInstance,nullptr);
    HWND child=CreateWindowW(c.lpszClassName,L"child",WS_CHILD|WS_VISIBLE,10,10,500,300,root,nullptr,c.hInstance,nullptr);
    assert(root && child);SetForegroundWindow(root);SetFocus(child);pump();
    assert(GetForegroundWindow()==root && GetFocus()==child);
    jfg::Win32RelativeMouse failed(denied);
    assert(!failed.update(child,true) && failed.state()[1]==0 && failed.state()[7]==ERROR_ACCESS_DENIED);
    jfg::Win32RelativeMouse capture;
    bool acquired=false;
    for(int i=0;i<40 && !acquired;++i){acquired=capture.update(child,true);pump();Sleep(10);}
    assert(acquired);
    RECT locked{};assert(GetClipCursor(&locked) && locked.right-locked.left==1 && locked.bottom-locked.top==1);
    POINT center{locked.left,locked.top};SetCursorPos(center.x+1000,center.y+1000);POINT actual{};assert(GetCursorPos(&actual) && PtInRect(&locked,actual));
    const auto attempts=capture.state()[6];assert(capture.update(child,true) && capture.state()[6]==attempts);
    SetWindowPos(child,nullptr,20,20,400,250,SWP_NOZORDER);pump();assert(capture.update(child,true));
    RECT resized{};assert(GetClipCursor(&resized) && !EqualRect(&locked,&resized));
    SetPropW(root,L"JfgSettingsOpen",reinterpret_cast<HANDLE>(1));assert(!capture.update(child,true));
    RECT released{};assert(GetClipCursor(&released) && !EqualRect(&released,&resized));
    RemovePropW(root,L"JfgSettingsOpen");SetFocus(child);assert(capture.update(child,true));
    capture.release();assert(capture.state()[1]==0);
    std::atomic<bool> worker_result{true};std::thread worker([&]{jfg::Win32RelativeMouse wrong_thread;worker_result=wrong_thread.update(child,true);});worker.join();assert(!worker_result);
    SetFocus(root);assert(!capture.update(child,true));SetFocus(child);assert(capture.update(child,true));
    assert(!capture.update(child,false));assert(!capture.update(nullptr,true));
    DestroyWindow(root);UnregisterClassW(c.lpszClassName,c.hInstance);
    if(previous && IsWindow(previous))SetForegroundWindow(previous);SetCursorPos(before.x,before.y);
    std::cout<<"Relative mouse: denied API, center confinement, resize, menu release, focus, owner thread and reacquisition passed.\n";
}
