// Offscreen native input routing check. No desktop input or gameplay.
#include "../native_ui.cpp"
#include "../../native/ui_capture_windows.hpp"
#include <stdexcept>
static fs::path output;
static int checks=0;
static void require(bool ok,const char* message) { ++checks; if(!ok)throw std::runtime_error(message); }
static FrontendUiState frameState;
static void frame() { for(int i=0;i<2;++i)FrontendUiFrame(frameState); }
static Rml::Element* item(const char* id) {auto* e=surface->ui.el(id);require(e!=nullptr,id);return e;}
static LPARAM point(const char* id) {
 auto* e=item(id);auto p=e->GetAbsoluteOffset(Rml::BoxArea::Border)+Rml::Vector2f(e->GetClientWidth()/2,e->GetClientHeight()/2);
 auto q=p;require(e->Project(q),"project target");p+=p-q;
 return MAKELPARAM(int(p.x),int(p.y));
}
static void captureMenuPixels(const char* name="menu.ppm") {
 auto& s=*surface;frame();ComPtr<ID3D11Resource> resource;s.target->GetResource(&resource);
 ComPtr<ID3D11Texture2D> target;check(resource.As(&target));D3D11_TEXTURE2D_DESC desc{};target->GetDesc(&desc);
 desc.Usage=D3D11_USAGE_STAGING;desc.BindFlags=0;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;desc.MiscFlags=0;
 ComPtr<ID3D11Texture2D> staging;check(s.device->CreateTexture2D(&desc,nullptr,&staging));s.gpu->CopyResource(staging.Get(),target.Get());
 D3D11_MAPPED_SUBRESOURCE mapped{};check(s.gpu->Map(staging.Get(),0,D3D11_MAP_READ,0,&mapped));
 std::ofstream file(output/name,std::ios::binary);file<<"P6\n"<<desc.Width<<' '<<desc.Height<<"\n255\n";
 unsigned bright=0;
 for(unsigned y=0;y<desc.Height;++y)for(unsigned x=0;x<desc.Width;++x){
  const auto* pixel=static_cast<const unsigned char*>(mapped.pData)+std::size_t(y)*mapped.RowPitch+x*4U;
  const char rgb[]={static_cast<char>(pixel[2]),static_cast<char>(pixel[1]),static_cast<char>(pixel[0])};file.write(rgb,3);
  if(pixel[0]>160&&pixel[1]>160&&pixel[2]>160)++bright;
 }
 s.gpu->Unmap(staging.Get(),0);
 require(bright>500,"menu swapchain contains rendered text, not a blank background");
}
static void input(HWND source,UINT m,WPARAM w=0,LPARAM l=0) {
 FrontendUiMessage(m,w,l,source);
}
static void press(HWND source,const char* id) {
 auto p=point(id);input(source,WM_MOUSEMOVE,0,p);input(source,WM_LBUTTONDOWN,MK_LBUTTON,p);input(source,WM_LBUTTONUP,0,p);frame();
}
static LRESULT CALLBACK testWindowProcedure(HWND window, UINT message, WPARAM w, LPARAM l) {
 if(surface && ((message>=WM_MOUSEFIRST && message<=WM_MOUSELAST) || message==WM_CANCELMODE)) {
  FrontendUiMessage(message,w,l,window);return 0;
 }
 return DefWindowProcW(window,message,w,l);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR,int) {
 HWND window=nullptr;bool ready=false;
 try {
  int argc=0;auto** argv=CommandLineToArgvW(GetCommandLineW(),&argc);
  if(argc!=2){LocalFree(argv);return 2;}output=argv[1];LocalFree(argv);
  if(fs::exists(output))return 3;fs::create_directories(output);
  WNDCLASSW cls{};cls.lpfnWndProc=testWindowProcedure;cls.hInstance=instance;cls.lpszClassName=L"JfgMenuInputTests";RegisterClassW(&cls);
  window=CreateWindowExW(WS_EX_TOOLWINDOW,cls.lpszClassName,L"Offscreen menu checks",WS_OVERLAPPEDWINDOW|WS_CLIPCHILDREN,-30000,-30000,1280,780,nullptr,nullptr,instance,nullptr);
  HWND shield=CreateWindowExW(0,L"STATIC",L"",WS_CHILD,0,24,1200,700,window,nullptr,instance,nullptr);
  std::string action;fs::create_directories(output/"profile");
  require(FrontendUiInit(window,output/"profile",[&](const std::string& a){action=a;}),"initialize");ready=true;FrontendUiInputChild(shield);
#ifdef JFG_UI_TEST_COMPOSITION_UNAVAILABLE
  require(!FrontendUiCanOverlayGame(),"unsupported composition selects HWND presentation");
  ComPtr<IDXGISwapChain1> windowSwap=surface->swap;
  HWND swapWindow=nullptr;require(SUCCEEDED(windowSwap->GetHwnd(&swapWindow)) && swapWindow==window,"fallback presents to actual launcher HWND");
#else
  require(FrontendUiCanOverlayGame(),"Windows retains composition presentation");
#endif

  surface->ui.sdlDiscovery=[] {return std::vector<jfg::ControllerDeviceInfo>{};};
  surface->ui.controllerState=[](DWORD,XINPUT_STATE*)->DWORD{return ERROR_DEVICE_NOT_CONNECTED;};
  ShowWindow(window,SW_SHOWNOACTIVATE);FrontendUiResize();surface->context->SetDensityIndependentPixelRatio(1);frame();
  require(SUCCEEDED(surface->swap->Present(0,0)),"selected backend presents successfully");
  action.clear();press(window,"menu-help");press(window,"action-help");
  require(action=="about","About action requests a separate native window");
  require(!FrontendUiCapturing(),"About dismisses the main-window menu instead of embedding a modal");


  HWND viewport=CreateWindowExW(0,L"STATIC",L"",WS_CHILD|WS_VISIBLE,0,24,1200,700,window,nullptr,instance,nullptr);
  HWND game=CreateWindowExW(0,L"STATIC",L"",WS_CHILD|WS_VISIBLE,0,0,1200,700,viewport,nullptr,instance,nullptr);
  // The same helper is used by the actual launcher, including repeated calls.
  const bool overlays=FrontendUiCanOverlayGame();
  require((GetWindowLongPtrW(window,GWL_STYLE)&WS_CLIPCHILDREN)!=0,"host clipping style matches launcher");
  frameState.playing=true;frame();
  for(int cycle=0;cycle<3;++cycle) {
    auto target=jfg::frontend::sync_ui_capture_windows(window,viewport,game,shield,overlays,true);
    require(target==(overlays?shield:window),"capture selects a visible input surface");
    require((IsWindowVisible(shield)!=FALSE)==overlays,"HWND UI is never clipped by the input shield");
    require(IsWindowVisible(viewport) && IsWindowVisible(game),"opening a menu keeps hosted gameplay visible on both backends");
    press(window,"menu-video");
    if(!overlays) {
      HWND overlay=surface->fallbackOverlay.window();
      require(overlay && IsWindowVisible(overlay),"fallback menu has a visible owned presentation window");
      require(GetWindow(overlay,GW_OWNER)==window,"overlay stays owned by the launcher");
      require(IsWindowVisible(viewport) && IsWindowVisible(game),"rendering the dropdown never hides the game");
      RECT menuRect{},rootRect{};GetWindowRect(overlay,&menuRect);GetWindowRect(window,&rootRect);
      require(menuRect.right-menuRect.left < (rootRect.right-rootRect.left)/2 && menuRect.bottom-menuRect.top < (rootRect.bottom-rootRect.top)/2,"overlay covers only the dropdown bounds, not the whole viewport");
      HWND presented=nullptr;
      require(SUCCEEDED(surface->fallbackOverlay.swapChain()->GetHwnd(&presented)) && presented==overlay,"panel pixels present to the owned overlay HWND");
    }
    if(cycle==0)captureMenuPixels();
    if(!overlays) {
      HWND overlay=surface->fallbackOverlay.window();auto packed=point("action-video");
      POINT local{static_cast<short>(LOWORD(packed)),static_cast<short>(HIWORD(packed))};
      MapWindowPoints(window,overlay,&local,1);auto position=MAKELPARAM(local.x,local.y);
      action.clear();SendMessageW(overlay,WM_MOUSEMOVE,0,position);
      SendMessageW(overlay,WM_LBUTTONDOWN,MK_LBUTTON,position);
      SendMessageW(overlay,WM_LBUTTONUP,0,position);frame();
      require(action=="video","owned popup forwards a real menu click in root coordinates");
      require(!FrontendUiCapturing(),"forwarded selection closes dropdown");
      press(window,"menu-game");input(window,WM_ACTIVATEAPP,0);frame();
      require(!FrontendUiCapturing() && !IsWindowVisible(overlay),"app deactivation dismisses the fallback dropdown");
      press(window,"menu-game");SetCapture(window);surface->ownsMouseCapture=true;
      input(window,WM_CANCELMODE);frame();
      require(GetCapture()!=window && !FrontendUiCapturing(),"cancel mode releases mouse capture and dismisses the dropdown");
    }
    FrontendUiPanel("");frame();
    if(!overlays)require(!IsWindowVisible(surface->fallbackOverlay.window()),"closing the menu hides only the overlay");
    target=jfg::frontend::sync_ui_capture_windows(window,viewport,game,shield,overlays,false);
    require(IsWindowVisible(viewport)&&!IsWindowVisible(shield),"closing menus restores hosted game");
    require(target==window,"no hidden shield receives fallback focus");
  }
  DestroyWindow(viewport);frameState={};frame();
  press(window,"menu-game");
  require(item("action-rom")!=item("rom-library-import"),"menu and library ROM actions have distinct DOM identities");
  require(std::abs(item("action-rom")->GetBox().GetSize(Rml::BoxArea::Border).y-item("action-setup")->GetBox().GetSize(Rml::BoxArea::Border).y)<1.0f,"Select ROM uses ordinary dropdown row height");
  FrontendUiPanel("");frame();

  SetWindowPos(window,nullptr,0,0,1024,700,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE);
  FrontendUiResize();frame();
  DXGI_SWAP_CHAIN_DESC1 resized{};RECT client{};GetClientRect(window,&client);
  require(SUCCEEDED(surface->swap->GetDesc1(&resized)) &&
          resized.Width==static_cast<UINT>(client.right) &&
          resized.Height==static_cast<UINT>(client.bottom),"swap chain follows window resize");
  require(SUCCEEDED(surface->swap->Present(0,0)),"resized backend presents successfully");
  SetWindowPos(window,nullptr,0,0,1280,780,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE);
  FrontendUiResize();frame();
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

  FrontendUiState verifying;
  verifying.rom=L"fixture.z64";verifying.busy=true;
  verifying.status=L"Verifying game files: 1 of 14 (jfg-native-boot.exe)...";
  auto verificationFrame=[&] {for(int i=0;i<2;++i)FrontendUiFrame(verifying);};
  verificationFrame();FrontendUiPanel("setup");verificationFrame();
  require(item("action-setup-start")->HasAttribute("disabled"),"verify button disabled while hashing");
  require(item("action-setup-start")->GetInnerRML().find("Verifying")!=std::string::npos,"verify button shows busy label");
  require(item("verify-progress-fill")->GetClientWidth()>0,"verification activity bar is visible");
  require(item("verify-progress-time")->GetInnerRML().find("running")!=std::string::npos,"verification elapsed status is visible");
  action.clear();
  auto verifyPoint=point("action-setup-start");input(window,WM_MOUSEMOVE,0,verifyPoint);
  input(window,WM_LBUTTONDOWN,MK_LBUTTON,verifyPoint);input(window,WM_LBUTTONUP,0,verifyPoint);verificationFrame();
  require(action.empty(),"busy verification cannot be submitted twice");
  Sleep(1100);verificationFrame();
  require(item("verify-progress-time")->GetInnerRML().find("0s")==std::string::npos,"elapsed time continues while worker runs");
  require(item("status")->GetInnerRML().find("Verifying game files")!=std::string::npos,"home footer reports active verification");
  surface->ui.reducedMotion=true;verificationFrame();
  require(item("verify-progress-fill")->GetClientWidth()>0,"reduced motion keeps verification activity visible");
  verifying.busy=false;verifying.status=L"ROM and game files verified. Click Play.";verificationFrame();
  require(!item("action-setup-start")->HasAttribute("disabled"),"verification completion enables button");
  require(surface->ui.el("verify-progress-fill")==nullptr,"verification completion clears activity display");
  require(item("action-setup-start")->GetInnerRML().find("Verify files")!=std::string::npos,"completion restores button label");
  verifying.busy=true;verificationFrame();
  verifying.busy=false;verifying.status=L"Game files are missing or changed.";verificationFrame();
  require(!item("action-setup-start")->HasAttribute("disabled"),"failed verification can be retried");
  require(item("setup-status")->GetInnerRML().find("missing or changed")!=std::string::npos,"failed verification shows result");
  FrontendUiShutdown();ready=false;frameState={};
  require(FrontendUiInit(window,output/"profile",[&](const std::string& a){action=a;},"about"),"dedicated About document initializes");ready=true;
  SetWindowPos(window,nullptr,0,0,960,680,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE);FrontendUiResize();frame();captureMenuPixels("about.ppm");
  require(surface->ui.el("home-scene")==nullptr && surface->ui.el("modal")==nullptr && surface->ui.el("menu-help")==nullptr,"About window does not contain the main-screen modal or menus");
  require(item("dialog-body")->GetInnerRML().find("@VERSION@")==std::string::npos,"About build placeholders are resolved");
  for(const char* name:{"guide","known-issues","support","project","notices"}) {
    const auto id=std::string("action-")+name;item(id.c_str())->ScrollIntoView(false);frame();
    action.clear();press(window,id.c_str());require(action==name,"About link dispatches its existing launcher action");
  }
  for(const auto size:{std::pair{960,700},std::pair{720,480}}) {
    SetWindowPos(window,nullptr,0,0,size.first,size.second,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE);FrontendUiResize();frame();
    const auto box=item("dialog")->GetBox().GetSize(Rml::BoxArea::Border);
    require(std::abs(box.x-surface->width)<1 && std::abs(box.y-surface->height)<1,"About content resizes to its own client area");
    require(item("about-done")->GetAbsoluteOffset().y+item("about-done")->GetClientHeight()<=surface->height,"About Done remains inside the window after resize");
  }
  input(window,WM_KEYDOWN,VK_ESCAPE);MSG closed{};
  require(PeekMessageW(&closed,window,WM_CLOSE,WM_CLOSE,PM_REMOVE)!=FALSE,"Escape closes the About native window");
  press(window,"about-done");
  require(PeekMessageW(&closed,window,WM_CLOSE,WM_CLOSE,PM_REMOVE)!=FALSE,"Done closes the About native window");
  std::ofstream(output/"result.json")<<"{\"passed\":true,\"checks\":"<<checks<<"}";
  FrontendUiShutdown();ready=false;DestroyWindow(window);return 0;
 } catch(const std::exception& e) {std::ofstream(output/"error.txt")<<e.what();if(ready)FrontendUiShutdown();if(window)DestroyWindow(window);return 1;}
}
