// Offscreen native input routing check. No desktop input or gameplay.
#include "../native_ui.cpp"
#include <stdexcept>
static fs::path output;
static int checks=0;
static void require(bool ok,const char* message) { ++checks; if(!ok)throw std::runtime_error(message); }
static void frame() { for(int i=0;i<2;++i)FrontendUiFrame({}); }
static Rml::Element* item(const char* id) {auto* e=surface->ui.el(id);require(e!=nullptr,id);return e;}
static LPARAM point(const char* id) {
 auto* e=item(id);auto p=e->GetAbsoluteOffset(Rml::BoxArea::Border)+Rml::Vector2f(e->GetClientWidth()/2,e->GetClientHeight()/2);
 auto q=p;require(e->Project(q),"project target");p+=p-q;
 return MAKELPARAM(int(p.x),int(p.y));
}
static void input(HWND source,UINT m,WPARAM w=0,LPARAM l=0) {
 FrontendUiMessage(m,w,l,source);
}
static void press(HWND source,const char* id) {
 auto p=point(id);input(source,WM_MOUSEMOVE,0,p);input(source,WM_LBUTTONDOWN,MK_LBUTTON,p);input(source,WM_LBUTTONUP,0,p);frame();
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR,int) {
 HWND window=nullptr;bool ready=false;
 try {
  int argc=0;auto** argv=CommandLineToArgvW(GetCommandLineW(),&argc);
  if(argc!=2){LocalFree(argv);return 2;}output=argv[1];LocalFree(argv);
  if(fs::exists(output))return 3;fs::create_directories(output);
  WNDCLASSW cls{};cls.lpfnWndProc=DefWindowProcW;cls.hInstance=instance;cls.lpszClassName=L"JfgMenuInputTests";RegisterClassW(&cls);
  window=CreateWindowExW(WS_EX_TOOLWINDOW,cls.lpszClassName,L"Offscreen menu checks",WS_OVERLAPPEDWINDOW,-30000,-30000,1280,780,nullptr,nullptr,instance,nullptr);
  HWND shield=CreateWindowExW(0,L"STATIC",L"",WS_CHILD,0,24,1200,700,window,nullptr,instance,nullptr);
  std::string action;fs::create_directories(output/"profile");
  require(FrontendUiInit(window,output/"profile",[&](const std::string& a){action=a;}),"initialize");ready=true;FrontendUiInputChild(shield);
  surface->ui.sdlDiscovery=[] {return std::vector<jfg::ControllerDeviceInfo>{};};
  surface->ui.controllerState=[](DWORD,XINPUT_STATE*)->DWORD{return ERROR_DEVICE_NOT_CONNECTED;};
  ShowWindow(window,SW_SHOWNOACTIVATE);FrontendUiResize();surface->context->SetDensityIndependentPixelRatio(1);frame();
  input(window,WM_MOUSEMOVE,0,point("menu-controllers"));frame();
  require(item("menu-controllers")->IsPseudoClassSet("hover"),"top menu hover appears");
  input(window,WM_MOUSELEAVE);frame();
  require(!item("menu-controllers")->IsPseudoClassSet("hover"),"leaving UI clears idle hover");
  for(auto [menu,command,expected]:{std::tuple{"menu-video","action-video","video"},std::tuple{"menu-game","action-settings","settings"},std::tuple{"menu-help","action-guide","guide"}}) {
   action.clear();press(window,menu);require(surface->ui.current==menu,"dropdown opens");
   auto p=point(command);input(shield,WM_MOUSEMOVE,0,p);
   // Windows posts the parent's leave while pointer messages arrive from its input child.
   input(window,WM_MOUSELEAVE);
   input(shield,WM_LBUTTONDOWN,MK_LBUTTON,p);input(shield,WM_LBUTTONUP,0,p);frame();
   require(action==expected,"dropdown item remains clickable after parent-to-shield handoff");
   require(!FrontendUiCapturing(),"selection closes dropdown");
   // Re-enter the menu while an already-queued shield leave arrives.
   input(window,WM_MOUSEMOVE,0,point(menu));input(shield,WM_MOUSELEAVE);frame();
   require(item(menu)->IsPseudoClassSet("hover"),"stale child leave preserves parent hover");
   input(window,WM_MOUSELEAVE);frame();
   require(!item(menu)->IsPseudoClassSet("hover"),"real parent exit clears hover after handoff");
  }
  press(window,"menu-video");input(shield,WM_MOUSEMOVE,0,point("action-video"));input(shield,WM_MOUSELEAVE);frame();
  require(!item("action-video")->IsPseudoClassSet("hover"),"leaving input child clears dropdown hover");
  FrontendUiPanel("");frame();require(!FrontendUiCapturing(),"host dismissal closes menu");
  input(window,WM_KEYDOWN,VK_F10);frame();require(FrontendUiCapturing(),"F10 opens menu");
  input(window,WM_KEYDOWN,VK_F10);frame();require(!FrontendUiCapturing(),"F10 closes menu");
  std::ofstream(output/"result.json")<<"{\"passed\":true,\"checks\":"<<checks<<"}";
  FrontendUiShutdown();ready=false;DestroyWindow(window);return 0;
 } catch(const std::exception& e) {std::ofstream(output/"error.txt")<<e.what();if(ready)FrontendUiShutdown();if(window)DestroyWindow(window);return 1;}
}
