#include "../native_ui.cpp"
#include <chrono>
#include <stdexcept>
static unsigned checks=0;
static void demand(bool ok,const char* why){++checks;if(!ok)throw std::runtime_error(why);}
static void frame(){for(unsigned i=0;i<3;++i)FrontendUiFrame({});}
static std::string readFile(const fs::path& p){std::ifstream f(p,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
static void capture(const fs::path& name) {
 auto& s=*surface;ComPtr<ID3D11Resource> resource;s.target->GetResource(&resource);
 ComPtr<ID3D11Texture2D> target;check(resource.As(&target));D3D11_TEXTURE2D_DESC desc{};target->GetDesc(&desc);
 desc.Usage=D3D11_USAGE_STAGING;desc.BindFlags=0;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;desc.MiscFlags=0;
 ComPtr<ID3D11Texture2D> staging;check(s.device->CreateTexture2D(&desc,nullptr,&staging));s.gpu->CopyResource(staging.Get(),target.Get());
 D3D11_MAPPED_SUBRESOURCE mapped{};check(s.gpu->Map(staging.Get(),0,D3D11_MAP_READ,0,&mapped));
 std::ofstream f(name,std::ios::binary);unsigned char h[18]{};h[2]=2;h[12]=static_cast<unsigned char>(desc.Width);h[13]=static_cast<unsigned char>(desc.Width>>8);h[14]=static_cast<unsigned char>(desc.Height);h[15]=static_cast<unsigned char>(desc.Height>>8);h[16]=32;h[17]=40;
 f.write(reinterpret_cast<char*>(h),18);for(unsigned y=0;y<desc.Height;++y)f.write(static_cast<char*>(mapped.pData)+y*mapped.RowPitch,desc.Width*4);s.gpu->Unmap(staging.Get(),0);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR,int) {
 const auto root=fs::temp_directory_path()/(L"jfg-audio-ui-"+std::to_wstring(GetCurrentProcessId()));fs::create_directories(root);
 HWND window=nullptr;bool ready=false;
 try {
  const auto desktopName=L"JfgAudioUi-"+std::to_wstring(GetCurrentProcessId());
  HDESK desktop=CreateDesktopW(desktopName.c_str(),nullptr,nullptr,0,GENERIC_ALL,nullptr);demand(desktop&&SetThreadDesktop(desktop),"isolated desktop");
  WNDCLASSW cls{};cls.lpfnWndProc=DefWindowProcW;cls.hInstance=instance;cls.lpszClassName=L"JfgAudioUiFixture";RegisterClassW(&cls);
  const std::string initial="version=1\nvolume=80\nmuted=0\n";std::ofstream(root/"audio.ini",std::ios::binary)<<initial;
  double openingMs=0;
  auto open=[&](){
   window=CreateWindowExW(0,cls.lpszClassName,L"Audio Settings",WS_OVERLAPPEDWINDOW,100,100,560,370,nullptr,nullptr,instance,nullptr);
   const auto started=std::chrono::steady_clock::now();
   demand(FrontendUiInit(window,root,[](const std::string&){},"audio"),"dedicated Audio document loads");ready=true;
   ShowWindow(window,SW_SHOWNOACTIVATE);FrontendUiResize();frame();
   openingMs=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();
   demand(surface->audio&&!surface->live&&!surface->video&&!surface->storage,"Audio has its own UI model");
   demand(!surface->ui.doc->GetElementById("modal"),"window content has no game modal layer");
   demand(!FrontendUiCapturing(),"no main-window modal state");
  };
  auto close=[&](){FrontendUiShutdown();ready=false;DestroyWindow(window);window=nullptr;MSG message;while(PeekMessageW(&message,nullptr,WM_CLOSE,WM_CLOSE,PM_REMOVE)){};};
  open();const auto firstOpen=openingMs;demand(firstOpen<5000,"Audio opens in less than five seconds");
  demand(readFile(root/"audio.ini")==initial,"opening does not rewrite saved preferences");
  auto click=[&](const char* id){auto* e=surface->audio->el(id);demand(e&&e->IsVisible(true),id);e->Click();frame();};
  auto value=[&](){const auto saved=jfg::audio::read_volume(root/"audio.ini");demand(saved.has_value(),"saved audio is accepted by runtime parser");return *saved;};
  demand(value().percent==80&&!value().muted,"saved volume and mute loaded");
  click("audio-down");demand(value().percent==75,"decrease applies immediately");
  click("audio-up");demand(value().percent==80,"increase applies immediately");
  click("audio-mute");demand(value().muted&&value().percent==80,"mute preserves remembered volume");
  auto* slider=static_cast<Rml::ElementFormControlInput*>(surface->audio->el("audio-volume"));slider->SetValue("37");Rml::Dictionary change;change["value"]=Rml::String("37");slider->DispatchEvent("change",change);frame();
  demand(value().percent==37&&value().muted,"slider applies while muted without unmuting");
  FrontendUiToggleMute();demand(!value().muted&&value().percent==37,"mute shortcut uses Audio window model");
  slider->Focus(true);FrontendUiMessage(WM_KEYDOWN,VK_RIGHT,0);demand(value().percent==38,"keyboard increments slider");
  FrontendUiMessage(WM_KEYDOWN,VK_HOME,0);click("audio-down");demand(value().percent==0,"lower volume boundary");
  slider->Focus(true);FrontendUiMessage(WM_KEYDOWN,VK_END,0);click("audio-up");demand(value().percent==100,"upper volume boundary");
  surface->audio->volume(80);frame();
  for(const auto* id:{"audio-volume","audio-mute","audio-done"}) {
   auto* e=surface->audio->el(id);const auto at=e->GetAbsoluteOffset(Rml::BoxArea::Border)+Rml::Vector2f(e->GetClientWidth()/2,e->GetClientHeight()/2);
   auto* hit=surface->context->GetElementAtPoint(at);while(hit&&hit!=e)hit=hit->GetParentNode();demand(hit==e,"audio controls receive pointer hits");
  }
  capture(root/"audio-window.tga");
  FrontendUiMessage(WM_KEYDOWN,VK_TAB,0);demand(surface->context->GetFocusElement()!=nullptr,"Tab focuses a control");
  click("audio-done");MSG done{};demand(PeekMessageW(&done,window,WM_CLOSE,WM_CLOSE,PM_REMOVE)!=0,"Done closes window");close();
  open();demand(surface->audio->settings.percent==80&&!surface->audio->settings.muted,"preferences survive reopening");
  FrontendUiMessage(WM_KEYDOWN,VK_ESCAPE,0);demand(PeekMessageW(&done,window,WM_CLOSE,WM_CLOSE,PM_REMOVE)!=0,"Escape closes window");close();
  std::ofstream(root/"audio.ini",std::ios::binary|std::ios::trunc)<<"invalid settings";
  open();demand(!surface->audio->error.empty(),"invalid preferences reported");demand(readFile(root/"audio.ini")=="invalid settings","invalid preferences preserved until edit");click("audio-up");demand(value().muted,"explicit recovery keeps safe mute");close();
  fs::rename(root/"audio.ini",root/"audio.saved");fs::create_directory(root/"audio.ini");open();
  demand(!surface->audio->save({50,false})&&!surface->audio->error.empty(),"save failure is visible");demand(fs::is_directory(root/"audio.ini"),"failed save preserves existing destination");close();
  fs::remove(root/"audio.ini");fs::rename(root/"audio.saved",root/"audio.ini");
  window=CreateWindowExW(0,cls.lpszClassName,L"Menu",WS_OVERLAPPEDWINDOW,100,100,1280,780,nullptr,nullptr,instance,nullptr);
  std::string routed;demand(FrontendUiInit(window,root,[&](const std::string& a){routed=a;}),"main UI loads");ready=true;ShowWindow(window,SW_SHOWNOACTIVATE);FrontendUiResize();frame();
  surface->ui.modal("menu-audio");frame();surface->ui.el("action-audio")->Click();demand(routed=="audio"&&!FrontendUiCapturing(),"Audio menu routes to separate window and closes popup");
  routed.clear();FrontendUiPanel("audio");demand(routed=="audio"&&!FrontendUiCapturing(),"native Audio command routes to window");close();
  std::ofstream(root/"result.json")<<"{\"checks\":"<<checks<<",\"first_open_ms\":"<<firstOpen<<",\"complete\":true}";return 0;
 }catch(const std::exception& e){std::ofstream(root/"error.txt")<<e.what();if(ready)FrontendUiShutdown();if(window)DestroyWindow(window);return 1;}
}
