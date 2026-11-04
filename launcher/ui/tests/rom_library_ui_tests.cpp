// Injected devices and an offscreen, nonactivating HWND. Never sends desktop input.
// Usage: jfg_update_ui_tests.exe <new-artifact-directory>.
#include <RmlUi/Core/Elements/ElementFormControlSelect.h>
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
static void click(const std::string& id) {
  std::ofstream(home/"events.txt",std::ios::app)<<id<<"\n";
  auto* e=element(id);demand(!e->HasAttribute("disabled"),("enabled "+id).c_str());e->Click();settle();
}
static void editInput(int binding) {
  const auto value=std::to_string(binding);
  if(surface->ui.modernDiagram) {
    click("action-mc-select-"+value);click("action-mc-input-"+value);
  } else click("mc-row-"+value);
}
static void change(const std::string& id,int value) {
  Rml::Dictionary event;event["value"]=value;element(id)->DispatchEvent("change",event);settle();
}
static void captureAction(int action) {
  surface->ui.modernReturnFocus="action-mc-tab-buttons";
  surface->ui.modernBeginCapture(action);settle();
}

static void pointerClick(const std::string& id) {
  auto* control=element(id);
  auto point=control->GetAbsoluteOffset(Rml::BoxArea::Border)+Rml::Vector2f(control->GetClientWidth()/2,control->GetClientHeight()/2);
  auto projected=point;demand(control->Project(projected),"project native hit target");point+=point-projected;
  auto* hit=surface->context->GetElementAtPoint(point);
  while(hit && hit!=control)hit=hit->GetParentNode();
  demand(hit==control,("native hit target "+id).c_str());
  surface->context->ProcessMouseMove(int(point.x),int(point.y),0);
  surface->context->ProcessMouseButtonDown(0,0);surface->context->ProcessMouseButtonUp(0,0);settle();
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
    WNDCLASSW cls{};cls.lpfnWndProc=DefWindowProcW;cls.hInstance=instance;cls.lpszClassName=L"JfgRomLibraryUiTests";RegisterClassW(&cls);
    window=CreateWindowExW(WS_EX_TOOLWINDOW,cls.lpszClassName,L"Offscreen ROM library",WS_OVERLAPPEDWINDOW,-30000,-30000,1280,780,nullptr,nullptr,instance,nullptr);
    std::string lastAction;auto profile=home/"profile";fs::create_directories(profile);
    demand(FrontendUiInit(window,profile,[&](const std::string& action){lastAction=action;}),"native UI initializes");ready=true;
    auto& ui=surface->ui;ui.controllerState=[](DWORD,XINPUT_STATE*)->DWORD{return ERROR_DEVICE_NOT_CONNECTED;};
    ShowWindow(window,SW_SHOWNOACTIVATE);FrontendUiResize();surface->context->SetDensityIndependentPixelRatio(1.f);
    auto library=[&](const std::string& selected,bool jp){
      std::ofstream(profile/"frontend-rom-library.tsv",std::ios::binary)<<"jfg-rom-library-1\n"<<selected<<"\nus\tverified\tC:/Games/JFG/roms/jfg-us.z64\npal\tverified\tC:/Games/JFG/roms/jfg-pal-r0.z64\njpn\t"<<(jp?"verified\tC:/Games/JFG/roms/star-twins-jp-r0.z64":"empty\t")<<"\n";
      frameState.rom=(selected=="jpn"&&!jp)?L"":L"C:/fixture/rom.z64";frameState.runtime=frameState.rom.empty()?L"":L"C:/fixture/game.exe";ui.libraryPoll=0;settle();
    };
    settle();demand(element("action-play")->HasAttribute("disabled"),"empty initial library cannot play");
    library("us",false);demand(element("rom-count")->GetInnerRML().find("2 of 3")!=std::string::npos,"count reflects loaded regions");
    demand(element("action-region-us")->IsClassSet("selected"),"USA selected");demand(!element("action-play")->HasAttribute("disabled"),"loaded selection can play");
    capture("two-loaded.tga");pointerClick("action-region-pal");demand(lastAction=="region-pal","PAL tile routes through host selection");
    library("pal",false);pointerClick("action-play");demand(lastAction=="play","Play uses host active selection");
    pointerClick("action-region-jpn");demand(lastAction=="region-jpn","empty JP remains selectable");library("jpn",false);
    demand(element("action-play")->HasAttribute("disabled"),"empty selected region cannot launch prior ROM");
    demand(element("action-rom")->GetInnerRML().find("Add JP")!=std::string::npos,"empty region offers Add");capture("jp-empty.tga");
    library("jpn",true);demand(element("action-region-jpn")->IsClassSet("selected"),"JP selection retained after load");
    demand(element("rom-count")->GetInnerRML().find("3 of 3")!=std::string::npos,"all three count");capture("three-loaded.tga");
    frameState.busy=true;settle();demand(element("action-region-us")->HasAttribute("disabled") && element("action-play")->HasAttribute("disabled"),"busy selection and Play locked");
    frameState.busy=false;settle();element("action-region-us")->Focus();FrontendUiMessage(WM_KEYDOWN,VK_RETURN,0);demand(lastAction=="region-us","keyboard selects region");
    for(float dpi:{1.f,1.5f}) {
      SetWindowPos(window,nullptr,-30000,-30000,1200,900,SWP_NOZORDER|SWP_NOACTIVATE);FrontendUiResize();surface->context->SetDensityIndependentPixelRatio(dpi);settle();
      for(const auto* code:{"us","pal","jpn"}) {
        auto* tile=element(std::string("action-region-")+code);auto pos=tile->GetAbsoluteOffset(Rml::BoxArea::Border);
        demand(pos.x>=0 && pos.x+tile->GetClientWidth()<=surface->width,"tile fits viewport");
        pointerClick(std::string("action-region-")+code);
      }
      capture(dpi==1.f?"desktop.tga":"dpi150.tga");
    }
    std::ofstream(home/"result.json")<<"{\"passed\":true,\"checks\":"<<checks<<"}";
    FrontendUiShutdown();ready=false;DestroyWindow(window);return 0;
  }catch(const std::exception& error){std::ofstream(home/"error.txt")<<error.what();if(ready)FrontendUiShutdown();if(window)DestroyWindow(window);return 1;}
}
