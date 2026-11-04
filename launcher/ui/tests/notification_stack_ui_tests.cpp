// Injected devices and an offscreen, nonactivating HWND. Never sends desktop input.
// Usage: jfg_notification_ui_tests.exe <new-artifact-directory>.
#include "../native_ui.cpp"
#include <stdexcept>
static fs::path home;
static int checks=0;
static void demand(bool pass,const char* message) {
  ++checks;if(!pass)throw std::runtime_error(message);
}
static FrontendUiState frameState;
static void settle() {for(int i=0;i<3;++i)FrontendUiFrame(frameState);}
static Rml::Element* element(const std::string& id) {
  auto* e=surface->ui.el(id.c_str());demand(e!=nullptr,id.c_str());return e;
}
static void capture(const char* name) {
  auto& s=*surface;settle();ComPtr<ID3D11Resource> resource;s.target->GetResource(&resource);
  ComPtr<ID3D11Texture2D> target;check(resource.As(&target));D3D11_TEXTURE2D_DESC desc{};target->GetDesc(&desc);
  desc.Usage=D3D11_USAGE_STAGING;desc.BindFlags=0;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;desc.MiscFlags=0;
  ComPtr<ID3D11Texture2D> staging;check(s.device->CreateTexture2D(&desc,nullptr,&staging));s.gpu->CopyResource(staging.Get(),target.Get());
  D3D11_MAPPED_SUBRESOURCE mapped{};check(s.gpu->Map(staging.Get(),0,D3D11_MAP_READ,0,&mapped));
  std::ofstream file(home/name,std::ios::binary);unsigned char header[18]{};
  header[2]=2;header[12]=static_cast<unsigned char>(desc.Width);header[13]=static_cast<unsigned char>(desc.Width>>8);
  header[14]=static_cast<unsigned char>(desc.Height);header[15]=static_cast<unsigned char>(desc.Height>>8);header[16]=32;header[17]=40;
  file.write(reinterpret_cast<char*>(header),18);
  for(unsigned y=0;y<desc.Height;++y)file.write(static_cast<char*>(mapped.pData)+y*mapped.RowPitch,desc.Width*4);
  s.gpu->Unmap(staging.Get(),0);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR,int) {
  HWND window=nullptr;bool ready=false;
  try {
    int argc=0;auto** argv=CommandLineToArgvW(GetCommandLineW(),&argc);
    if(argc!=2){LocalFree(argv);return 2;}home=argv[1];LocalFree(argv);
    if(fs::exists(home))return 3;fs::create_directories(home);
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    WNDCLASSW cls{};cls.lpfnWndProc=DefWindowProcW;cls.hInstance=instance;cls.lpszClassName=L"JfgNotificationUiTests";RegisterClassW(&cls);
    window=CreateWindowExW(WS_EX_TOOLWINDOW,cls.lpszClassName,L"Offscreen notification stack",WS_OVERLAPPEDWINDOW,-30000,-30000,1280,780,nullptr,nullptr,instance,nullptr);
    auto profile=home/"profile";fs::create_directories(profile);
    demand(FrontendUiInit(window,profile,[](const std::string&){}),"native UI initializes");ready=true;
    auto& ui=surface->ui;ui.controllerState=[](DWORD,XINPUT_STATE*)->DWORD{return ERROR_DEVICE_NOT_CONNECTED;};
    ui.sdlDiscovery=[] {return std::vector<jfg::ControllerDeviceInfo>{};};
    double now=100;ui.notificationClock=[&] {return now;};
    ShowWindow(window,SW_SHOWNOACTIVATE);FrontendUiResize();surface->context->SetDensityIndependentPixelRatio(1.f);
    auto* stack=element("toast");
    auto advance=[&](double target) {while(now+1.0/60<target){now+=1.0/60;FrontendUiFrame(frameState);}now=target;settle();};
    auto opacity=[](Rml::Element* e){return e->GetProperty<float>("opacity");};
    auto top=[](Rml::Element* e) {auto point=e->GetAbsoluteOffset(Rml::BoxArea::Border);auto projected=point;if(!e->Project(projected))throw std::runtime_error("notification projection");return (point+point-projected).y;};
    ui.toast("Controller 1 connected");settle();demand(stack->GetNumChildren()==1,"first notice appears immediately");auto* first=stack->GetChild(0);
    advance(100.2);demand(std::abs(opacity(first)-.5f)<.02f,"first entry owns its animation clock");
    ui.toast("Controller 2 connected");settle();demand(stack->GetNumChildren()==2,"second notice appears without waiting");auto* second=stack->GetChild(1);
    demand(stack->GetChild(0)==first,"adding notice keeps previous DOM node");demand(std::abs(opacity(first)-.5f)<.02f,"arrival does not reset first animation");
    advance(100.3);demand(std::abs(opacity(first)-.75f)<.02f && std::abs(opacity(second)-.25f)<.02f,"overlapping entries retain different animation ages");
    advance(101);demand(top(first)+first->GetBox().GetSize(Rml::BoxArea::Border).y+6<=top(second),"older notice rises above newer without overlap");
    ui.toast("Audio muted");advance(101.7);demand(stack->GetNumChildren()==3,"third notice joins rising list");capture("three-stacked.tga");
    ui.toast("Audio muted");settle();demand(stack->GetNumChildren()==3,"consecutive duplicate neither queues nor restarts");
    advance(104.5);demand(opacity(first)<.6f && opacity(second)>.95f,"first exits while second keeps its own lifetime");capture("independent-exit.tga");
    advance(104.63);demand(stack->GetNumChildren()==2 && stack->GetChild(0)==second,"first expires without removing later cards");
    advance(104.83);demand(stack->GetNumChildren()==1,"second expires on its original schedule");
    advance(105.63);demand(stack->GetNumChildren()==0,"duplicate did not extend third lifetime");
    ui.toast("<b>Literal & notification</b>");settle();demand(stack->QuerySelector("b")==nullptr,"notification text cannot inject markup");
    ui.toast("A longer controller message that wraps across several lines and still pushes earlier cards upward without resetting their timers.");advance(106.4);
    demand(top(stack->GetChild(0))+stack->GetChild(0)->GetBox().GetSize(Rml::BoxArea::Border).y+6<=top(stack->GetChild(1)),"stack uses measured wrapped card height");capture("wrapped-stack.tga");
    advance(111);demand(stack->GetNumChildren()==0,"long cards expire normally");
    ui.reducedMotion=true;ui.toast("Reduced motion first");advance(111.5);ui.toast("Reduced motion second");settle();
    demand(top(stack->GetChild(0))+stack->GetChild(0)->GetBox().GetSize(Rml::BoxArea::Border).y+6<=top(stack->GetChild(1)),"reduced motion places stack without a movement animation");
    advance(115.63);demand(stack->GetNumChildren()==1,"reduced motion preserves independent expiry");advance(116.13);demand(stack->GetNumChildren()==0,"reduced motion newest expires independently");
    ui.reducedMotion=false;
    for(int i=0;i<10;++i)ui.toast("Burst notification "+std::to_string(i));settle();
    demand(stack->GetNumChildren()==8,"burst is bounded without queuing");
    demand(stack->GetChild(0)->GetInnerRML().find("Burst notification 2")!=std::string::npos,"overflow evicts oldest instead of delaying newest");
    demand(stack->GetChild(7)->GetInnerRML().find("Burst notification 9")!=std::string::npos,"newest burst message is immediately present");
    advance(117);capture("burst-stack.tga");
    surface->context->SetDensityIndependentPixelRatio(1.5f);settle();advance(117.5);capture("stack-dpi150.tga");
    auto* newest=stack->GetChild(7);demand(top(newest)<surface->height && top(newest)>=0,"newest remains on screen at 150 percent DPI");
    ui.modal("game");advance(118);demand(!stack->IsVisible(true),"modal hides stack without changing lifetime");ui.close();advance(120.76);demand(stack->GetNumChildren()==0,"hidden notices expire instead of resetting on close");
    FrontendUiShutdown();ready=false;
    demand(FrontendUiInit(window,profile,[](const std::string&){},"map"),"live map initializes with shared notification styles");ready=true;
    surface->context->SetDensityIndependentPixelRatio(1.f);settle();
    auto liveRoot=surface->files.liveAssets;
    demand(liveRoot.parent_path()==profile && fs::is_empty(liveRoot),"map error fixture stays inside empty private test directory");
    fs::remove(liveRoot);std::ofstream(liveRoot)<<"Block writes for the private mod-error fixture.";
    element("map-settings")->Click();settle();element("restore-defaults")->Click();settle();
    auto* mapStack=element("toast");demand(mapStack->GetNumChildren()==1,"real map command failure creates one notification card");
    auto* mapCard=mapStack->GetChild(0);demand(mapCard->IsClassSet("toast-item"),"live map uses styled independent notification card");
    for(int i=0;i<30;++i){Sleep(20);FrontendUiFrame(frameState);}
    demand(opacity(mapCard)>.95f && mapCard->GetBox().GetSize(Rml::BoxArea::Border).y>=42,"map error notice is visible with nonzero height");
    element("restore-defaults")->Click();settle();demand(mapStack->GetNumChildren()==1 && mapStack->GetChild(0)==mapCard,"repeat map error preserves existing card");
    element("settings-done")->Click();settle();capture("live-map-error.tga");fs::remove(liveRoot);
    std::ofstream(home/"result.json")<<"{\"passed\":true,\"checks\":"<<checks<<"}";
    FrontendUiShutdown();ready=false;DestroyWindow(window);return 0;
  }catch(const std::exception& error){std::ofstream(home/"error.txt")<<error.what();if(ready)FrontendUiShutdown();if(window)DestroyWindow(window);return 1;}
}
