#pragma once
#include "../native/video_settings_protocol.hpp"
#include <RmlUi/Core.h>
#include <RmlUi/Core/Elements/ElementFormControlInput.h>
#include <RmlUi/Core/Elements/ElementFormControlSelect.h>
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <functional>
#include <string>
#include <sstream>
#include <vector>
#include <cctype>
namespace jfg_video {
struct Ui final : Rml::EventListener {
  using Settings = jfg::frontend::VideoDialogSettings;
  HWND window = nullptr, owner = nullptr;
  Rml::ElementDocument *doc = nullptr;
  Settings saved{}, draft{};
  bool updating = false, failedLoad = false, running = false,
       pendingRestart = false;
  std::string fpsText = "60", error, search;
  unsigned activeTab = 0;
  std::function<bool(const Settings &)> save;
  Rml::Element *el(const char *id) const { return doc->GetElementById(id); }
  void text(const char *id, const std::string &s) { el(id)->SetInnerRML(s); }
  static bool sameRender(const jfg::VideoSettings &a,
                         const jfg::VideoSettings &b) {
    return a.mode == b.mode && a.vsync == b.vsync && a.blur == b.blur &&
           (a.mode != jfg::FrameRateMode::custom || a.fps == b.fps);
  }
  bool dirty() const {
    return draft.actor_lod != saved.actor_lod || draft.fullscreen != saved.fullscreen ||
           draft.window_size != saved.window_size ||
           draft.pause_inactive != saved.pause_inactive ||
           !sameRender(draft.rendering, saved.rendering) ||
           draft.rendering.fog_percent != saved.rendering.fog_percent ||
           draft.rendering.fps != saved.rendering.fps ||
           fpsText != std::to_string(saved.rendering.fps);
  }
  bool invalid() const {
    return draft.rendering.mode == jfg::FrameRateMode::custom &&
           !jfg::parse_video_fps(fpsText);
  }
  void init(HWND w, Rml::ElementDocument *d,
            const std::filesystem::path &profile) {
    window = w;
    doc = d;
    owner = reinterpret_cast<HWND>(GetPropW(w, L"JfgLiveOwner"));
    const auto loaded = jfg::load_video_settings(profile / L"video.ini");
    failedLoad = !loaded;
    if (loaded)
      saved.rendering = *loaded;
    DWORD_PTR state = 0;
    if (IsWindow(owner))
      SendMessageTimeoutW(owner, jfg::frontend::kVideoState, 0, 0,
                          SMTO_ABORTIFHUNG, 1000, &state);
    saved.fullscreen = (state & 1) != 0;
    saved.pause_inactive = (state & 2) != 0;
    running = (state & 4) != 0;
    saved.actor_lod=jfg::load_actor_lod(profile).value_or(jfg::ActorLod::original);
    draft = saved;
    fpsText = std::to_string(draft.rendering.fps);
    save = [this](const Settings &candidate) {
      if (!IsWindow(owner))
        return false;
      jfg::frontend::VideoRequest request;
      request.actor_lod=candidate.actor_lod==jfg::ActorLod::high?1U:0U;
      request.mode = static_cast<unsigned>(candidate.rendering.mode);
      request.fps = candidate.rendering.fps;
      request.vsync = candidate.rendering.vsync;
      request.fog_percent = candidate.rendering.fog_percent;
      request.blur = static_cast<unsigned>(candidate.rendering.blur);
      request.fullscreen = candidate.fullscreen;
      request.window_size = candidate.window_size;
      request.pause_inactive = candidate.pause_inactive;
      COPYDATASTRUCT packet{jfg::frontend::kVideoApply, sizeof(request),
                            &request};
      DWORD_PTR result = 0;
      return SendMessageTimeoutW(owner, WM_COPYDATA,
                                 reinterpret_cast<WPARAM>(window),
                                 reinterpret_cast<LPARAM>(&packet),
                                 SMTO_ABORTIFHUNG, 5000, &result) &&
             result == 1;
    };
    doc->AddEventListener("click", this);
    doc->AddEventListener("change", this);
    if (failedLoad)
      error = "Could not read video.ini. Check your save folder before "
              "changing settings.";
    refresh(true);
  }
  void selected(const char *id, bool on) {
    el(id)->SetClass("selected", on);
    el(id)->SetAttribute("aria-checked", on ? "true" : "false");
  }
  void refresh(bool input = false) {
    updating = true;
    selected("video-windowed", !draft.fullscreen);
    selected("video-fullscreen", draft.fullscreen);
    selected("video-pause", draft.pause_inactive);
    selected("video-vsync", draft.rendering.vsync);
    selected("video-lod-original",draft.actor_lod==jfg::ActorLod::original);
    selected("video-lod-high",draft.actor_lod==jfg::ActorLod::high);
    static_cast<Rml::ElementFormControlInput*>(el("video-fog"))->SetValue(std::to_string(draft.rendering.fog_percent));
    text("video-fog-value",std::to_string(draft.rendering.fog_percent)+"%");
    selected("video-blur-off", draft.rendering.blur == jfg::BlurMode::off);
    selected("video-blur-reduced", draft.rendering.blur == jfg::BlurMode::reduced);
    selected("video-blur-original", draft.rendering.blur == jfg::BlurMode::original);
    text("video-blur-hint", draft.rendering.blur == jfg::BlurMode::off
         ? "Removes the game's full-screen motion trails."
         : draft.rendering.blur == jfg::BlurMode::reduced
         ? "Lighter motion trails. Recommended for comfortable play."
         : "Preserves the game's original blur strength.");
    const bool blurWarning = draft.rendering.blur == jfg::BlurMode::original &&
                             draft.rendering.mode != jfg::FrameRateMode::original;
    el("video-blur-warning")->SetProperty("display", blurWarning ? "block" : "none");
    selected("video-original",
             draft.rendering.mode == jfg::FrameRateMode::original);
    selected("video-custom",
             draft.rendering.mode == jfg::FrameRateMode::custom);
    selected("video-unlimited",
             draft.rendering.mode == jfg::FrameRateMode::unlimited);
    auto *size = static_cast<Rml::ElementFormControlSelect *>(el("video-size"));
    size->SetValue(std::to_string(draft.window_size));
    size->SetDisabled(draft.fullscreen || failedLoad);
    text("video-size-hint",
         draft.fullscreen ? "Fills the screen" : "Windowed mode only");
    const bool custom = draft.rendering.mode == jfg::FrameRateMode::custom;

    if (input)
      static_cast<Rml::ElementFormControlInput *>(el("video-fps"))
          ->SetValue(fpsText);
    static_cast<Rml::ElementFormControlInput *>(el("video-slider"))
        ->SetValue(std::to_string(draft.rendering.fps));
    for (unsigned n : {60U, 120U, 144U, 165U, 240U, 360U}) {
      const auto id = "video-preset-" + std::to_string(n);
      el(id.c_str())->SetClass("selected", draft.rendering.fps == n);
    }
    const bool bad = invalid();
    el("video-fps")->SetClass("invalid", bad);
    el("video-range")->SetClass("invalid", bad);
    text("video-range",
         bad ? "Enter a whole number from 60 to 1000" : "Range 60 to 1000 FPS");
    std::string hint;
    if (draft.rendering.mode == jfg::FrameRateMode::original)
      hint = "Uses the game's original presentation rate.";
    else if (custom)
      hint = "Experimental smooth rendering up to your cap.";
    else
      hint = "Experimental smooth rendering with no FPS cap.";
    if (draft.rendering.mode != jfg::FrameRateMode::original &&
        draft.rendering.vsync)
      hint = "Experimental smooth rendering. VSync limits output to your "
             "display's refresh rate.";
    text("video-fps-hint", hint);
    const bool renderDirty = !sameRender(draft.rendering, saved.rendering);
    el("video-restart")->SetProperty("display", running && (renderDirty || pendingRestart) ? "block" : "none");
    el("video-restart")->SetClass("pending", renderDirty || pendingRestart);
    text("video-restart", renderDirty || pendingRestart
                              ? "Restart game to apply"
                              : "Applies next game launch");
    text("video-error", error);
    el("video-error")->SetProperty("display", error.empty() ? "none" : "block");
    if (bad || failedLoad)
      el("video-apply")->SetAttribute("disabled", true);
    else
      el("video-apply")->RemoveAttribute("disabled");
    refreshTabs();
    updating = false;
  }
  void refreshTabs() {
    struct Row {const char* id;unsigned tab;const char* keywords;};
    constexpr Row rows[]={
      {"mode",0,"window mode windowed borderless fullscreen"},
      {"size",0,"window size resolution dimensions 1280 720 1600 900 1920 1080 2560 1440"},
      {"pause",0,"pause inactive background focus"},
      {"vsync",1,"vsync v-sync vertical sync display tearing refresh"},
      {"lod",1,"actor lod level detail high original distance models graphics"},
      {"blur",1,"motion blur trails ghosting sickness nausea"},
      {"fps",2,"frame rate framerate fps original custom unlimited smooth cap"},
      {"cap",2,"frame rate cap fps limit 60 120 144 165 240 360 1000"},
      {"fog",3,"remove fog mist distance haze visibility"}
    };
    const char* names[]={"display","rendering","framerate","enhance"};
    const char* titles[]={"Display","Rendering","Frame rate","Enhancements"};
    const char* subtitles[]={"Choose how the game window appears.",
      "Control rendering, actor detail and motion blur.","Set how many frames per second the game renders.",
      "Optional changes to the game's visuals."};
    std::string query=search;
    std::transform(query.begin(),query.end(),query.begin(),[](unsigned char c){return static_cast<char>(std::tolower(c));});
    std::istringstream words(query);std::vector<std::string> tokens;
    for(std::string word;words>>word;)tokens.push_back(word);
    const bool searching=!tokens.empty();
    unsigned counts[4]{},total=0;
    for(const auto& row:rows) {
      bool show=searching||activeTab==row.tab;
      for(const auto& word:tokens)show=show&&std::string(row.keywords).find(word)!=std::string::npos;
      if(std::string(row.id)=="cap"&&draft.rendering.mode!=jfg::FrameRateMode::custom)show=false;
      el((std::string("video-card-")+row.id).c_str())->SetProperty("display",show?"block":"none");
      if(show){++counts[row.tab];++total;}
    }
    const bool changed[]={draft.fullscreen!=saved.fullscreen||draft.window_size!=saved.window_size||draft.pause_inactive!=saved.pause_inactive,
      draft.rendering.vsync!=saved.rendering.vsync||draft.rendering.blur!=saved.rendering.blur||draft.actor_lod!=saved.actor_lod,
      draft.rendering.mode!=saved.rendering.mode||fpsText!=std::to_string(saved.rendering.fps),
      draft.rendering.fog_percent!=saved.rendering.fog_percent};
    for(unsigned i=0;i<4;++i) {
      auto* tab=el((std::string("video-tab-")+names[i]).c_str());
      tab->SetClass("selected",!searching&&activeTab==i);
      tab->SetAttribute("aria-selected",!searching&&activeTab==i?"true":"false");
      auto* count=el((std::string("video-count-")+names[i]).c_str());
      count->SetInnerRML(std::to_string(counts[i]));count->SetProperty("display",searching?"block":"none");
      el((std::string("video-dirty-")+names[i]).c_str())->SetProperty("display",changed[i]?"block":"none");
    }
    text("video-title",searching?"Search results":titles[activeTab]);
    text("video-subtitle",searching?"Matching settings across all sections.":subtitles[activeTab]);
    el("video-empty")->SetProperty("display",total?"none":"block");
  }
  bool apply() {
    if (failedLoad || invalid()) {
      refresh();
      return false;
    }
    if (!dirty())
      return true;
    const bool renderingChanged = !sameRender(draft.rendering, saved.rendering);
    if (!save || !save(draft)) {
      error =
          "Could not save video settings. Check access to your save folder.";
      refresh();
      return false;
    }
    pendingRestart |= running && renderingChanged;
    saved = draft;
    fpsText = std::to_string(draft.rendering.fps);
    error.clear();
    refresh(true);
    return true;
  }
  void ProcessEvent(Rml::Event &event) override {
    if (updating)
      return;
    auto *target = event.GetTargetElement();
    while (target && target->GetId().empty())
      target = target->GetParentNode();
    if (!target)
      return;
    const auto id = target->GetId();
    if (event.GetType() == "change") {
      if(id=="video-search") {search=static_cast<Rml::ElementFormControlInput*>(target)->GetValue();refreshTabs();return;}
      if (id == "video-fog") {
        const auto value=event.GetParameter<float>("value",float(draft.rendering.fog_percent));
        if(std::isfinite(value)&&value>=0&&value<=100)draft.rendering.fog_percent=static_cast<unsigned>(std::round(value));
      } else if (id == "video-fps") {
        fpsText =
            static_cast<Rml::ElementFormControlInput *>(target)->GetValue();
        if (auto n = jfg::parse_video_fps(fpsText))
          draft.rendering.fps = *n;
      } else if (id == "video-slider") {
        const auto value =
            event.GetParameter<float>("value", float(draft.rendering.fps));
        if (std::isfinite(value) && value >= 60 && value <= 1000) {
          draft.rendering.fps = static_cast<unsigned>(std::round(value));
          fpsText = std::to_string(draft.rendering.fps);
        }
      } else if (id == "video-size") {
        const auto value =
            static_cast<Rml::ElementFormControlSelect *>(target)->GetValue();
        if (value.size() == 1 && value[0] >= '0' && value[0] <= '4')
          draft.window_size = static_cast<unsigned>(value[0] - '0');
      } else
        return;
      error.clear();
      refresh(id != "video-fps");
      return;
    }
    if (event.GetType() != "click" || target->HasAttribute("disabled"))
      return;
    if(id.rfind("video-tab-",0)==0||id=="video-clear") {
      if(id=="video-tab-display")activeTab=0;
      else if(id=="video-tab-rendering")activeTab=1;
      else if(id=="video-tab-framerate")activeTab=2;
      else if(id=="video-tab-enhance")activeTab=3;
      search.clear();static_cast<Rml::ElementFormControlInput*>(el("video-search"))->SetValue("");
      refreshTabs();el("video-content")->SetScrollTop(0);return;
    }
    if (id == "video-cancel") {
      PostMessageW(window, WM_CLOSE, 0, 0);
      return;
    }
    if (id == "video-apply") {
      if (apply())
        PostMessageW(window, WM_CLOSE, 0, 0);
      return;
    }
    if (id == "video-windowed")
      draft.fullscreen = false;
    else if (id == "video-fullscreen")
      draft.fullscreen = true;
    else if (id == "video-pause")
      draft.pause_inactive = !draft.pause_inactive;
    else if (id == "video-vsync")
      draft.rendering.vsync = !draft.rendering.vsync;
    else if (id == "video-lod-original")
      draft.actor_lod=jfg::ActorLod::original;
    else if (id == "video-lod-high")
      draft.actor_lod=jfg::ActorLod::high;
    else if (id == "video-blur-off")
      draft.rendering.blur = jfg::BlurMode::off;
    else if (id == "video-blur-reduced")
      draft.rendering.blur = jfg::BlurMode::reduced;
    else if (id == "video-blur-original")
      draft.rendering.blur = jfg::BlurMode::original;
    else if (id == "video-original")
      draft.rendering.mode = jfg::FrameRateMode::original;
    else if (id == "video-custom")
      draft.rendering.mode = jfg::FrameRateMode::custom;
    else if (id == "video-unlimited")
      draft.rendering.mode = jfg::FrameRateMode::unlimited;
    else if (id.rfind("video-preset-", 0) == 0) {
      if (auto n =
              jfg::parse_video_fps(id.substr(sizeof("video-preset-") - 1))) {
        draft.rendering.fps = *n;
        fpsText = std::to_string(*n);
      }
    } else
      return;
    error.clear();
    refresh(true);
  }
  bool keyboard(UINT m, WPARAM key) {
    if (m != WM_KEYDOWN)
      return false;
    auto *size = static_cast<Rml::ElementFormControlSelect *>(el("video-size"));
    if (size->IsSelectBoxVisible()) {
      if (key == VK_ESCAPE) {
        size->CancelSelectBox();
        return true;
      }
      if (key == VK_TAB)
        size->HideSelectBox();
      else
        return false;
    }
    if (key == VK_ESCAPE) {
      if(!search.empty()) {
        search.clear();static_cast<Rml::ElementFormControlInput*>(el("video-search"))->SetValue("");
        refreshTabs();return true;
      }
      PostMessageW(window, WM_CLOSE, 0, 0);
      return true;
    }
    auto *context = doc->GetContext();
    auto *focused = context->GetFocusElement();
    if (key == VK_TAB) {
      Rml::ElementList controls;
      doc->QuerySelectorAll(controls, "button, input, select");
      controls.erase(std::remove_if(controls.begin(), controls.end(),
                                    [](auto *e) {
                                      return !e->IsVisible(true) ||
                                             e->HasAttribute("disabled");
                                    }),
                     controls.end());
      if (!controls.empty()) {
        const bool back = (GetKeyState(VK_SHIFT) & 0x8000) != 0;
        auto it = std::find(controls.begin(), controls.end(), focused);
        int n =
            it == controls.end() ? (back ? 0 : -1) : int(it - controls.begin());
        n = (n + (back ? -1 : 1) + int(controls.size())) % int(controls.size());
        controls[n]->Focus(true);
        controls[n]->ScrollIntoView(false);
      }
      return true;
    }
    if ((key == VK_RETURN || key == VK_SPACE) && focused &&
        focused->GetTagName() == "button") {
      focused->Click();
      return true;
    }
    if (key == VK_RETURN && focused && focused->GetId() == "video-fps") {
      if (apply())
        PostMessageW(window, WM_CLOSE, 0, 0);
      return true;
    }
    return false;
  }
};
} // namespace jfg_video
