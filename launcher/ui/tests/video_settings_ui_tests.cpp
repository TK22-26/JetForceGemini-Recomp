#include "../native_ui.cpp"
#include <stdexcept>
static fs::path home;
static unsigned checks = 0;
static bool capture_images = true;
static void demand(bool value, const char *why) {
  ++checks;
  if (!value)
    throw std::runtime_error(why);
}
static void settle() {
  for (unsigned i = 0; i < 3; ++i)
    FrontendUiFrame({});
}
static Rml::Element *element(const char *id) {
  auto *e = surface->video->el(id);
  demand(e != nullptr, id);
  return e;
}
static void click(const char *id) {
  auto *e = element(id);
  demand(!e->HasAttribute("disabled"), id);
  e->Click();
  settle();
}
static void pointer(const char *id) {
  auto *e = element(id);
  for(auto* parent=e;parent;parent=parent->GetParentNode()) {
    const auto card=parent->GetId();
    const char* tab=nullptr;
    if(card=="video-card-mode"||card=="video-card-size"||card=="video-card-pause")tab="video-tab-display";
    else if(card=="video-card-api"||card=="video-card-vsync"||card=="video-card-blur")tab="video-tab-rendering";
    else if(card=="video-card-fps"||card=="video-card-cap")tab="video-tab-framerate";
    else if(card=="video-card-fog"||card=="video-card-lod"||card=="video-card-shadows")tab="video-tab-enhance";
    if(tab&&!parent->IsVisible(true)){click(tab);break;}
  }
  e->ScrollIntoView();
  settle();
  auto point = e->GetAbsoluteOffset(Rml::BoxArea::Border) +
               Rml::Vector2f(e->GetClientWidth() / 2, e->GetClientHeight() / 2);
  auto *hit = surface->context->GetElementAtPoint(point);
  while (hit && hit != e)
    hit = hit->GetParentNode();
  demand(hit == e, (std::string("visible control receives pointer hits: ") + id).c_str());
  surface->context->ProcessMouseMove(int(point.x), int(point.y), 0);
  surface->context->ProcessMouseButtonDown(0, 0);
  surface->context->ProcessMouseButtonUp(0, 0);
  settle();
}
static void type(const std::string &value) {
  auto *e = static_cast<Rml::ElementFormControlInput *>(element("video-fps"));
  e->SetValue(value);
  Rml::Dictionary args;
  args["value"] = value;
  e->DispatchEvent("change", args);
  settle();
}
static void capture(const char *name) {
  if (!capture_images) return;
  auto &s = *surface;
  settle();
  ComPtr<ID3D11Resource> resource;
  s.target->GetResource(&resource);
  ComPtr<ID3D11Texture2D> target;
  check(resource.As(&target));
  D3D11_TEXTURE2D_DESC desc{};
  target->GetDesc(&desc);
  desc.Usage = D3D11_USAGE_STAGING;
  desc.BindFlags = 0;
  desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
  desc.MiscFlags = 0;
  ComPtr<ID3D11Texture2D> staging;
  check(s.device->CreateTexture2D(&desc, nullptr, &staging));
  s.gpu->CopyResource(staging.Get(), target.Get());
  D3D11_MAPPED_SUBRESOURCE mapped{};
  check(s.gpu->Map(staging.Get(), 0, D3D11_MAP_READ, 0, &mapped));
  std::ofstream file(home / name, std::ios::binary);
  unsigned char header[18]{};
  header[2] = 2;
  header[12] = static_cast<unsigned char>(desc.Width);
  header[13] = static_cast<unsigned char>(desc.Width >> 8);
  header[14] = static_cast<unsigned char>(desc.Height);
  header[15] = static_cast<unsigned char>(desc.Height >> 8);
  header[16] = 32;
  header[17] = 40;
  file.write(reinterpret_cast<char *>(header), 18);
  for (unsigned y = 0; y < desc.Height; ++y)
    file.write(static_cast<char *>(mapped.pData) + y * mapped.RowPitch,
               desc.Width * 4);
  s.gpu->Unmap(staging.Get(), 0);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int) {
  HWND window = nullptr;
  bool ready = false;
  try {
    int argc = 0;
    auto **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argc != 2 && argc != 3) {
      LocalFree(argv);
      return 2;
    }
    home = argv[1];
    if (argc == 3) {
      if (std::wstring(argv[2]) != L"--no-captures") { LocalFree(argv); return 2; }
      capture_images = false;
    }
    LocalFree(argv);
    if (fs::exists(home))
      return 3;
    fs::create_directories(home);
    const auto desktopName =
        L"JfgRmlVideoChecks-" + std::to_wstring(GetCurrentProcessId());
    HDESK desktop = CreateDesktopW(desktopName.c_str(), nullptr, nullptr, 0,
                                   GENERIC_ALL, nullptr);
    demand(desktop && SetThreadDesktop(desktop), "isolated inactive desktop");
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    WNDCLASSW cls{};
    cls.lpfnWndProc = DefWindowProcW;
    cls.hInstance = instance;
    cls.lpszClassName = L"JfgRmlVideoTests";
    RegisterClassW(&cls);
    window = CreateWindowExW(0, cls.lpszClassName, L"Video Settings",
                             WS_OVERLAPPEDWINDOW, 40, 40, 720, 600, nullptr,
                             nullptr, instance, nullptr);
    const auto profile = home / "profile";
    fs::create_directories(profile);
    std::ofstream(profile / "video.ini")
        << "version=1\nmode=custom\nfps=60\nvsync=1\n";
    auto init = [&] {
      demand(FrontendUiInit(
                 window, profile, [](const std::string &) {}, "video"),
             "RmlUi initializes");
      ready = true;
      surface->video->save = [&](const jfg_video::Ui::Settings &value) {
        std::ofstream(profile / "video.ini")
            << jfg::serialize_video_settings(value.rendering);
        std::ofstream(profile / "game-settings.ini") << jfg::serialize_actor_lod(value.actor_lod);
        std::ofstream(profile / "shadows.ini") << jfg::serialize_shadow_quality(value.shadows);
        return true;
      };
    };
    init();
    RECT frame{0, 0, 720, 600};
    AdjustWindowRectExForDpi(&frame, WS_OVERLAPPEDWINDOW, FALSE, 0,
                             GetDpiForWindow(window));
    SetWindowPos(window, nullptr, 40, 40, frame.right - frame.left,
                 frame.bottom - frame.top, SWP_NOZORDER | SWP_NOACTIVATE);
    ShowWindow(window, SW_SHOWNOACTIVATE);
    FrontendUiResize();
    surface->context->SetDensityIndependentPixelRatio(1);
    settle();
    auto &ui = *surface->video;
    demand(element("video-card-mode")->IsVisible(true)&&!element("video-card-fog")->IsVisible(true),"Display is initial tab");
    pointer("video-tab-enhance");
    demand(element("video-card-fog")->IsVisible(true)&&!element("video-card-mode")->IsVisible(true),"Enhancements switches the page");
    auto fog=[&](float v){Rml::Dictionary event;event["value"]=v;element("video-fog")->DispatchEvent("change",event);settle();};
    fog(35);demand(ui.draft.rendering.fog_percent==35&&ui.dirty(),"fog percentage modifies draft");
    pointer("video-tab-display");demand(ui.draft.rendering.fog_percent==35,"tab switch retains unsaved fog");
    pointer("video-tab-enhance");fog(100);demand(!ui.dirty(),"original fog restored");
    ui.running=true;fog(50);demand(!element("video-restart")->IsVisible(true),"fog requires no restart");
    fog(100);ui.running=false;
    auto* search=static_cast<Rml::ElementFormControlInput*>(element("video-search"));
    search->SetValue("mist");Rml::Dictionary query;query["value"]=std::string("mist");search->DispatchEvent("change",query);settle();
    demand(element("video-card-fog")->IsVisible(true)&&!element("video-card-mode")->IsVisible(true),"search matches fog synonym across tabs");
    search->SetValue("zzzz");search->DispatchEvent("change",query);settle();
    demand(element("video-empty")->IsVisible(true),"search empty state");
    pointer("video-clear");pointer("video-tab-display");

    {
      std::ofstream coordinates(home / "controls.tsv");
      Rml::ElementList buttons;
      surface->ui.doc->QuerySelectorAll(buttons, "button, input, select");
      for (auto *e : buttons) {
        const auto point =
            e->GetAbsoluteOffset(Rml::BoxArea::Border) +
            Rml::Vector2f(e->GetClientWidth() / 2, e->GetClientHeight() / 2);
        coordinates << e->GetId() << '\t' << point.x << '\t' << point.y << '\n';
      }
    }

    demand(!element("video-restart")->IsVisible(true),
           "no restart chip when no game is running");
    demand(ui.draft.rendering.blur == jfg::BlurMode::reduced, "old file defaults to Reduced");
    demand(element("video-blur-reduced")->IsClassSet("selected"), "Reduced selected initially");
    demand(!element("video-blur-warning")->IsVisible(false), "Reduced has no Original warning");
    pointer("video-blur-original");
    demand(ui.draft.rendering.blur == jfg::BlurMode::original && ui.dirty(), "Original changes saved preference");
    demand(element("video-blur-warning")->IsVisible(false), "high-FPS Original comfort warning");
    pointer("video-original");
    demand(!element("video-blur-warning")->IsVisible(false), "native-rate Original hides high-FPS warning");
    pointer("video-custom");
    demand(element("video-blur-warning")->IsVisible(false), "custom restores warning");
    pointer("video-blur-off");
    demand(ui.draft.rendering.blur == jfg::BlurMode::off && !element("video-blur-warning")->IsVisible(false), "Off hides warning");
    pointer("video-blur-reduced");
    demand(!ui.dirty(), "return to initial Reduced clears dirty state");
    jfg::frontend::VideoRequest request;
    demand(jfg::frontend::valid_video_request(request), "default blur protocol valid");
    request.shadows = 2;
    demand(!jfg::frontend::valid_video_request(request), "invalid shadow mode accepted");
    request.shadows = 0;
    request.actor_lod = 2;
    demand(!jfg::frontend::valid_video_request(request), "reject invalid LOD protocol");
    request.actor_lod = 0; request.version = 4;
    demand(!jfg::frontend::valid_video_request(request), "reject pre-LOD protocol");
    request.version = 6;
    demand(!jfg::frontend::valid_video_request(request), "reject pre-API protocol");
    request.version = 7; request.graphics_api = 3;
    demand(!jfg::frontend::valid_video_request(request), "reject invalid API protocol");
    request.graphics_api = 0;
    request.blur = 3;
    demand(!jfg::frontend::valid_video_request(request), "reject invalid blur protocol");
    request.blur = 1; request.version = 1;
    demand(!jfg::frontend::valid_video_request(request), "reject old protocol layout");
    MSG close{};
    auto accepted = [&] {
      demand(PeekMessageW(&close, window, WM_CLOSE, WM_CLOSE, PM_REMOVE) != 0,
             "Apply accepts and closes");
    };
    demand(!element("video-apply")->HasAttribute("disabled"),
           "Apply can accept unchanged values");
    pointer("video-apply");
    accepted();
    ui.running = true;
    pointer("video-lod-high");
    demand(ui.activeTab==3 && element("video-dirty-enhance")->IsVisible(true) &&
           !element("video-dirty-rendering")->IsVisible(true),
           "LOD belongs to Enhancements including unsaved change marker");
    demand(ui.draft.actor_lod == jfg::ActorLod::high && ui.dirty(),
           "High LOD changes Enhancements draft");
    demand(element("video-card-lod")->IsVisible(true) &&
               !element("video-restart")->IsVisible(true),
           "LOD appears in Enhancements and applies without restart");
    capture("enhancements-lod.tga");
    demand(jfg::load_actor_lod(profile) == jfg::ActorLod::original,
           "LOD choice does not write before Apply");
    pointer("video-apply");
    accepted();
    demand(jfg::load_actor_lod(profile) == jfg::ActorLod::high &&
               !ui.pendingRestart, "Apply persists High LOD without restart");
    pointer("video-lod-original");
    pointer("video-cancel");
    demand(PeekMessageW(&close, window, WM_CLOSE, WM_CLOSE, PM_REMOVE) != 0 &&
               jfg::load_actor_lod(profile) == jfg::ActorLod::high,
           "Cancel leaves saved High LOD unchanged");
    ui.draft = ui.saved; ui.refresh(); settle();
    auto goodSave = ui.save;
    pointer("video-lod-original");
    ui.save = [](const auto &) { return false; };
    pointer("video-apply");
    demand(!ui.error.empty() && ui.saved.actor_lod == jfg::ActorLod::high &&
               jfg::load_actor_lod(profile) == jfg::ActorLod::high &&
               !PeekMessageW(&close, window, WM_CLOSE, WM_CLOSE, PM_REMOVE),
           "failed LOD Apply preserves saved value and keeps dialog open");
    ui.save = goodSave; ui.draft = ui.saved; ui.error.clear(); ui.refresh();
    demand(jfg::load_shadow_quality(profile)==jfg::ShadowQuality::original,
           "Original shadows remain the default");
    pointer("video-shadow-enhanced");
    demand(ui.draft.shadows==jfg::ShadowQuality::enhanced && ui.dirty() &&
           jfg::load_shadow_quality(profile)==jfg::ShadowQuality::original,
           "Enhanced shadows remain a draft until Apply");
    pointer("video-apply");accepted();
    demand(jfg::load_shadow_quality(profile)==jfg::ShadowQuality::enhanced &&
           !ui.pendingRestart, "Enhanced shadows persist and apply live");
    pointer("video-shadow-original");pointer("video-cancel");
    demand(PeekMessageW(&close,window,WM_CLOSE,WM_CLOSE,PM_REMOVE)!=0 &&
           jfg::load_shadow_quality(profile)==jfg::ShadowQuality::enhanced,
           "Cancel must not change the active shadow renderer");
    ui.draft=ui.saved;ui.refresh();settle();capture("enhancements-shadows.tga");
    ui.running = true;
    pointer("video-api");
    auto *api = static_cast<Rml::ElementFormControlSelect *>(element("video-api"));
    demand(api->IsSelectBoxVisible(), "Graphics API combo opens like Window size");
    demand(ui.keyboard(WM_KEYDOWN, VK_ESCAPE) && !api->IsSelectBoxVisible(),
           "Escape dismisses API list first");
    demand(!PeekMessageW(&close,window,WM_CLOSE,WM_CLOSE,PM_REMOVE),
           "API dropdown Escape keeps settings open");
    auto chooseApi = [&](jfg::GraphicsApi wanted) {
      pointer("video-api");
      const int delta = static_cast<int>(wanted) - static_cast<int>(ui.draft.rendering.graphics_api);
      for (int i=0;i<std::abs(delta);++i)
        surface->context->ProcessKeyDown(delta>0?Rml::Input::KI_DOWN:Rml::Input::KI_UP,0);
      surface->context->ProcessKeyDown(Rml::Input::KI_RETURN,0);settle();
      demand(ui.draft.rendering.graphics_api==wanted && !api->IsSelectBoxVisible(),
             "API combo accepts keyboard selection and closes");
    };
    chooseApi(jfg::GraphicsApi::vulkan);
    demand(ui.draft.rendering.graphics_api == jfg::GraphicsApi::vulkan && ui.dirty() &&
           element("video-dirty-rendering")->IsVisible(true) && element("video-restart")->IsVisible(true),
           "API draft is a Rendering change requiring game restart");
    pointer("video-cancel");
    demand(PeekMessageW(&close,window,WM_CLOSE,WM_CLOSE,PM_REMOVE)!=0 &&
           jfg::load_video_settings(profile/"video.ini")->graphics_api == jfg::GraphicsApi::automatic,
           "Cancel preserves the saved API");
    ui.save = [](const auto&) { return false; };
    demand(!ui.apply() && jfg::load_video_settings(profile/"video.ini")->graphics_api == jfg::GraphicsApi::automatic,
           "failed API save preserves settings");
    ui.save = goodSave; pointer("video-apply"); accepted();
    demand(ui.pendingRestart && jfg::load_video_settings(profile/"video.ini")->graphics_api == jfg::GraphicsApi::vulkan,
           "API Apply persists without changing an active renderer");
    capture("rendering-api.tga");
    jfg_video::Ui reopened; reopened.init(window,surface->ui.doc,profile);
    demand(reopened.draft.rendering.graphics_api == jfg::GraphicsApi::vulkan,"reopen loads selected API");
    surface->ui.doc->RemoveEventListener("click", &reopened);surface->ui.doc->RemoveEventListener("change", &reopened);
    // The temporary reopen fixture changed this shared document to Display.
    // Restore and lay out the original UI before its next pointer assertion.
    ui.refresh(); settle();
    ui.running = false;chooseApi(jfg::GraphicsApi::d3d12);pointer("video-apply");accepted();
    demand(jfg::load_video_settings(profile/"video.ini")->graphics_api == jfg::GraphicsApi::d3d12,"Direct3D 12 persists");
    chooseApi(jfg::GraphicsApi::automatic);pointer("video-apply");accepted();ui.pendingRestart=false;ui.refresh();
    ui.running = false;
    pointer("video-preset-360");
    demand(ui.draft.rendering.fps == 360, "360 preset");
    pointer("video-vsync");
    demand(!ui.draft.rendering.vsync, "VSync switch");
    pointer("video-apply");
    accepted();
    auto saved = jfg::load_video_settings(profile / "video.ini");
    demand(saved && saved->fps == 360 && !saved->vsync,
           "Apply persists rendering");
    ui.running = true;
    ui.refresh();
    settle();
    demand(!element("video-restart")->IsVisible(true),
           "unchanged settings need no restart notice");
    type("59");
    demand(ui.invalid() && element("video-apply")->HasAttribute("disabled"),
           "reject underflow");
    type("1001");
    demand(ui.invalid(), "reject overflow");
    type("60.5");
    demand(ui.invalid(), "reject fraction");
    type("");
    demand(ui.invalid(), "reject empty FPS");
    type("144");
    demand(ui.draft.rendering.fps == 144 && !ui.invalid(),
           "exact numeric field");
    Rml::Dictionary change;
    change["value"] = 165.0f;
    element("video-slider")->DispatchEvent("change", change);
    settle();
    demand(ui.fpsText == "165" && ui.draft.rendering.fps == 165,
           "slider syncs exact number");
    pointer("video-slider");
    demand(ui.draft.rendering.fps != 165 && ui.draft.rendering.fps >= 60 &&
               ui.draft.rendering.fps <= 1000,
           "real slider pointer changes cap");
    element("video-fps")->Focus(true);
    surface->context->ProcessKeyDown(Rml::Input::KI_HOME, 0);
    for (unsigned i = 0; i < 4; ++i)
      surface->context->ProcessKeyDown(Rml::Input::KI_DELETE, 0);
    surface->context->ProcessTextInput("240");
    settle();
    demand(ui.fpsText == "240" && ui.draft.rendering.fps == 240,
           "real text widget edits cap");
    pointer("video-preset-165");
    capture("custom.tga");
    pointer("video-blur-off");
    pointer("video-unlimited");
    demand(!element("video-card-cap")->IsVisible(true),
           "Unlimited hides cap controls");
    pointer("video-apply");
    accepted();
    demand(ui.pendingRestart, "saved rendering needs next game session");
    demand(jfg::load_video_settings(profile / "video.ini")->blur == jfg::BlurMode::off, "Off persists");
    capture("unlimited.tga");
    pointer("video-original");
    demand(ui.draft.rendering.mode == jfg::FrameRateMode::original,
           "Original selectable");
    pointer("video-cancel");
    demand(PeekMessageW(&close, window, WM_CLOSE, WM_CLOSE, PM_REMOVE) != 0,
           "Cancel closes");
    saved = jfg::load_video_settings(profile / "video.ini");
    demand(saved && saved->mode == jfg::FrameRateMode::unlimited &&
               saved->fps == 165,
           "Cancel keeps last Apply and remembered cap");
    FrontendUiShutdown();
    ready = false;
    init();
    settle();
    demand(surface->video->draft.rendering.mode ==
               jfg::FrameRateMode::unlimited,
           "reopen restores saved mode");
    demand(surface->video->draft.actor_lod == jfg::ActorLod::high,
           "reopen restores saved High LOD");
    pointer("video-fullscreen");
    demand(element("video-size")->HasAttribute("disabled"),
           "window size disabled in fullscreen");
    pointer("video-windowed");
    demand(!element("video-size")->HasAttribute("disabled"),
           "window size reenabled");
    pointer("video-size");
    auto *size =
        static_cast<Rml::ElementFormControlSelect *>(element("video-size"));
    demand(size->IsSelectBoxVisible(), "window-size list opens");
    demand(surface->video->keyboard(WM_KEYDOWN, VK_ESCAPE) &&
               !size->IsSelectBoxVisible(),
           "Escape dismisses size list first");
    demand(!PeekMessageW(&close, window, WM_CLOSE, WM_CLOSE, PM_REMOVE),
           "dropdown Escape keeps settings open");
    pointer("video-size");
    surface->context->ProcessKeyDown(Rml::Input::KI_DOWN, 0);
    surface->context->ProcessKeyDown(Rml::Input::KI_RETURN, 0);
    settle();
    demand(surface->video->draft.window_size != 0,
           "window-size list supports keyboard selection");
    pointer("video-custom");
    pointer("video-pause");
    demand(surface->video->draft.pause_inactive, "pause switch");
    surface->video->save = [](const auto &) { return false; };
    pointer("video-apply");
    demand(!surface->video->error.empty() && surface->video->dirty(),
           "save failure preserves draft");
    demand(element("video-error")->IsVisible(true) &&
               !PeekMessageW(&close, window, WM_CLOSE, WM_CLOSE, PM_REMOVE),
           "failed Apply stays open with visible error");
    surface->video->save = [&](const auto &value) {
      std::ofstream(profile / "video.ini")
          << jfg::serialize_video_settings(value.rendering);
      return true;
    };
    for (unsigned i = 0; i < 20; ++i)
      demand(surface->video->keyboard(WM_KEYDOWN, VK_TAB),
             "Tab handled inside settings");
    surface->video->error.clear();
    surface->video->draft.window_size = 0; // Capture the reported default label.
    surface->video->refresh();
    for (float scale : {1.0f, 1.25f, 1.5f}) {
      RECT scaled{0, 0, int(720 * scale), int(600 * scale)};
      AdjustWindowRectExForDpi(&scaled, WS_OVERLAPPEDWINDOW, FALSE, 0,
                               GetDpiForWindow(window));
      SetWindowPos(window, nullptr, 0, 0, scaled.right - scaled.left,
                   scaled.bottom - scaled.top,
                   SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
      FrontendUiResize();
      surface->context->SetDensityIndependentPixelRatio(scale);
      settle();
      pointer("video-preset-240");
      demand(surface->video->draft.rendering.fps == 240,
             "decorated preset stays clickable at each DPI");
      // Move the hover away so the screenshot shows the saved selection alone.
      surface->context->ProcessMouseMove(0, 0, 0);
      element("video-apply")->Focus(true);
      capture(scale == 1.0f ? "dpi100.tga" : scale == 1.25f ? "dpi125.tga" : "dpi150.tga");
    }
    pointer("video-apply");
    accepted();
    std::ofstream(home / "result.json")
        << "{\"passed\":true,\"checks\":" << checks
        << ",\"physical_desktop_input\":false}";
    FrontendUiShutdown();
    ready = false;
    DestroyWindow(window);
    return 0;
  } catch (const std::exception &e) {
    if (!home.empty())
      std::ofstream(home / "result.json")
          << "{\"passed\":false,\"checks\":" << checks << ",\"error\":\""
          << escape(e.what()) << "\"}";
    if (ready)
      FrontendUiShutdown();
    if (window)
      DestroyWindow(window);
    return 1;
  }
}
