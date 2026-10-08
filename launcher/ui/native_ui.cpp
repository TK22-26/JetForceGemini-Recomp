// Native RmlUi design review harness. Game/process integration remains
// separate.
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include "native_ui.hpp"
#include <RmlUi/Core.h>
#include <RmlUi/Core/Elements/ElementFormControlInput.h>
#include <RmlUi_Platform_Win32.h>
#include <RmlUi_Renderer_DX11.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <commdlg.h>
#include <dcomp.h>
#include <deque>
#include <filesystem>
#include <fstream>
#include <jfg/audio/master_volume.hpp>
#include <jfg/runtime/controller_ports.hpp>
#include <memory>
#include <shellapi.h>
#include <sstream>
#include <string>
#include <windows.h>
#include <wrl/client.h>
#include <xinput.h>
namespace fs = std::filesystem;
static std::string u8(const std::wstring &s) {
  int n = WideCharToMultiByte(CP_UTF8, 0, s.data(), static_cast<int>(s.size()),
                              nullptr, 0, nullptr, nullptr);
  std::string out(n, '\0');
  WideCharToMultiByte(CP_UTF8, 0, s.data(), static_cast<int>(s.size()),
                      out.data(), n, nullptr, nullptr);
  return out;
}
static std::string escape(std::string s) {
  std::string out;
  for (char c : s) {
    if (c == '&')
      out += "&amp;";
    else if (c == '<')
      out += "&lt;";
    else if (c == '>')
      out += "&gt;";
    else if (c == '"')
      out += "&quot;";
    else
      out += c;
  }
  return out;
}
struct LogSystem : Rml::SystemInterface {
  Rml::SystemInterface *platform;
  std::ofstream file;
  explicit LogSystem(Rml::SystemInterface *p) : platform(p), file() {}
  double GetElapsedTime() override { return platform->GetElapsedTime(); }
  void SetMouseCursor(const Rml::String &s) override {
    platform->SetMouseCursor(s);
  }
  void SetClipboardText(const Rml::String &s) override {
    platform->SetClipboardText(s);
  }
  void GetClipboardText(Rml::String &s) override {
    platform->GetClipboardText(s);
  }
  bool LogMessage(Rml::Log::Type type, const Rml::String &message) override {
    file << int(type) << ": " << message << "\n";
    file.flush();
    return true;
  }
};
struct Ui : Rml::EventListener {
  bool building = false;
  HWND window = nullptr;
  std::function<void(const std::string &)> action;
  FrontendUiState state;
  jfg::ControllerPorts assignments;
  std::array<jfg::ControllerMapping, 4> mappings{};
  std::array<int, 4> devices{-2, -2, -2, -2};
  int learning = -1;
  bool learnReleased = false;
  double learnDeadline = 0;
  void close() {
    current.clear();
    learning = -1;
    el("modal")->SetProperty("display", "none");
    el("game-popup")->SetProperty("display", "none");
  }
  bool writeFile(const std::string &name, const std::string &value) {
    auto dest = profile / name, tmp = profile / (name + ".ui.tmp");
    {
      std::ofstream f(tmp, std::ios::binary);
      f << value;
      f.flush();
      if (!f) {
        status("Cannot save settings.");
        return false;
      }
    }
    if (!MoveFileExW(tmp.c_str(), dest.c_str(),
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
      status("Cannot save settings.");
      return false;
    }
    return true;
  }
  std::string controllerFile(int p) {
    return p ? "controller-" + std::to_string(p + 1) + ".ini"
             : "controller.ini";
  }
  void loadControllers() {
    for (int p = 0; p < 4; p++) {
      jfg::parse_controller_mapping(read(controllerFile(p).c_str()),
                                    mappings[p]);
      assignments.configure(p, mappings[p]);
    }
  }
  void saveController() {
    auto &m = mappings[player];
    std::ostringstream s;
    s << "version=1\ndevice=" << m.device << "\nstick=" << m.stick
      << "\ndeadzone=" << m.deadzone << "\nthreshold=" << m.threshold
      << "\ntrigger=" << m.trigger << "\ninvert_x=" << m.invert_x
      << "\ninvert_y=" << m.invert_y << "\n";
    for (int i = 0; i < 14; i++)
      s << "map" << i << "=" << m.bindings[i] << "\n";
    if (writeFile(controllerFile(player), s.str())) {
      assignments.configure(player, m);
      label("dialog-note", "Saved. Applied to the game immediately.");
    }
  }
  static std::string bindingName(int b) {
    static const char *names[] = {
        "A / Cross",        "B / Circle",        "X / Square",
        "Y / Triangle",     "Back / Share",      "Guide",
        "Start / Menu",     "Left stick click",  "Right stick click",
        "LB / L1",          "RB / R1",           "D-pad up",
        "D-pad down",       "D-pad left",        "D-pad right",
        "Left stick right", "Left stick left",   "Left stick down",
        "Left stick up",    "Right stick right", "Right stick left",
        "Right stick down", "Right stick up",    "LT / L2",
        "LT negative",      "RT / R2",           "RT negative"};
    return b >= 0 && b < 27 ? names[b] : "Unbound";
  }
  static std::array<bool, 27> sample(const XINPUT_STATE &s) {
    constexpr WORD masks[] = {0x1000, 0x2000, 0x4000, 0x8000, 0x20,
                              0,      0x10,   0x40,   0x80,   0x100,
                              0x200,  1,      2,      4,      8};
    std::array<bool, 27> out{};
    for (int i = 0; i < 15; i++)
      out[i] = (s.Gamepad.wButtons & masks[i]) != 0;
    int axes[] = {s.Gamepad.sThumbLX,
                  -int(s.Gamepad.sThumbLY),
                  s.Gamepad.sThumbRX,
                  -int(s.Gamepad.sThumbRY),
                  s.Gamepad.bLeftTrigger * 32767 / 255,
                  s.Gamepad.bRightTrigger * 32767 / 255};
    for (int i = 0; i < 6; i++) {
      out[15 + i * 2] = axes[i] > 16000;
      out[16 + i * 2] = axes[i] < -16000;
    }
    return out;
  }

  Rml::ElementDocument *doc = nullptr;
  fs::path profile;
  int volume = 100, player = 0;
  bool muted = false;
  double toastUntil = 0;
  std::array<bool, 4> connected{};
  std::array<WORD, 4> buttons{};
  std::array<bool, 4> activated{};
  std::deque<std::string> notices;
  bool reducedMotion = false;
  std::string current, sessionList, selectedSession;
  Rml::Element *el(const char *id) { return doc->GetElementById(id); }
  void label(const char *id, const std::string &s) {
    el(id)->SetInnerRML(escape(s));
  }
  std::string read(const char *file) {
    std::ifstream f(profile / file, std::ios::binary | std::ios::ate);
    if (!f || f.tellg() < 0 || f.tellg() > 65536)
      return {};
    f.seekg(0);
    return {std::istreambuf_iterator<char>(f), {}};
  }
  void status(const std::string &s) { label("status", s); }
  void toast(const std::string &s) {
    if (toastUntil > Rml::GetSystemInterface()->GetElapsedTime()) {
      if ((notices.empty() || notices.back() != s) && notices.size() < 8)
        notices.push_back(s);
      return;
    }
    label("toast-text", s);
    el("toast")->SetClass("visible", false);
    doc->GetContext()->Update();
    el("toast")->SetClass("visible", true);
    toastUntil = Rml::GetSystemInterface()->GetElapsedTime() + 4.62;
  }
  void refreshController() {
    if (current != "controllers" || !el("assignment"))
      return;
    const int d = devices[player];
    std::string description =
        d == -3 ? "Keyboard: WASD move; Z or Space = A, X = B, C = fire, Enter "
                  "= Start."
        : d < 0 ? "No physical controller is assigned."
                : "Controller " + std::to_string(d + 1) +
                      (connected[d] ? " connected." : " offline.");
    label("assignment", description);
    const bool disabled = d < 0 || !connected[d];
    for (int i = 0; i < 14; i++)
      if (auto *b = el(("action-learn" + std::to_string(i)).c_str())) {
        b->SetClass("disabled", disabled);
        if (disabled)
          b->SetAttribute("disabled", "disabled");
        else
          b->RemoveAttribute("disabled");
      }
  }
  void ports() {
    for (DWORD i = 0; i < 4; i++) {
      const bool previouslyConnected = connected[i];
      XINPUT_STATE s{};
      bool on = XInputGetState(i, &s) == ERROR_SUCCESS;
      const WORD pressed =
          on ? static_cast<WORD>(s.Gamepad.wButtons & ~buttons[i]) : 0;
      if (on != connected[i]) {
        connected[i] = on;
        activated[i] = false;
        devices = assignments.devices(connected);
        std::string port;
        for (int p = 0; p < 4; p++)
          if (devices[p] == int(i))
            port = " - Player " + std::to_string(p + 1);
        toast("Controller " + std::to_string(i + 1) +
              (on ? " connected" : " disconnected") + port);
      } else if (pressed && !activated[i]) {
        activated[i] = true;
        toast("Controller " + std::to_string(i + 1) + " active");
      }

      if (learning >= 0 && devices[player] == int(i)) {
        if (!on) {
          learning = -1;
          label("dialog-note",
                "Controller disconnected. Select a device and retry.");
        } else {
          auto active = sample(s);
          bool neutral = std::none_of(active.begin(), active.end(),
                                      [](bool b) { return b; });
          if (!learnReleased) {
            if (neutral) {
              learnReleased = true;
              label("dialog-note",
                    "Press the new button or move an axis. Esc cancels.");
            }
          } else
            for (int b = 0; b < 27; b++)
              if (active[b]) {
                mappings[player].bindings[learning] = b;
                learning = -1;
                saveController();
                modal("controllers");
                break;
              }
        }
      }
      if (pressed && on && previouslyConnected && current.empty() &&
          !state.playing && !state.busy && (pressed & XINPUT_GAMEPAD_A))
        action("play");
      buttons[i] = on ? s.Gamepad.wButtons : 0;
    }

    devices = assignments.devices(connected);
    refreshController();
    for (int p = 0; p < 4; p++) {
      bool on = devices[p] == -3 || (devices[p] >= 0 && connected[devices[p]]);
      el(("p" + std::to_string(p + 1)).c_str())->SetClass("connected", on);
    }
    if (learning >= 0 &&
        Rml::GetSystemInterface()->GetElapsedTime() > learnDeadline) {
      learning = -1;
      label("dialog-note", "Mapping timed out. No binding was changed.");
    }
    if (toastUntil) {
      double elapsed = Rml::GetSystemInterface()->GetElapsedTime() -
                       (toastUntil - 4.62),
             y = 0, opacity = 1;
      if (elapsed < 0.4) {
        double t = std::clamp(elapsed / 0.4, 0.0, 1.0), q = t - 1;
        double eased = 1 + 2.70158 * q * q * q + 1.70158 * q * q;
        y = 96 * (1 - eased);
        opacity = t;
      } else if (elapsed > 4.4) {
        double t = std::clamp((elapsed - 4.4) / 0.22, 0.0, 1.0);
        y = 120 * t * t;
        opacity = 1 - t;
      }
      el("toast")->SetProperty(
          "transform",
          "translate(-50%, " + std::to_string(reducedMotion ? 0 : y) + "dp)");
      el("toast")->SetProperty("opacity", std::to_string(opacity));
    }
    if (toastUntil &&
        Rml::GetSystemInterface()->GetElapsedTime() > toastUntil) {
      el("toast")->SetClass("visible", false);
      toastUntil = 0;
      if (!notices.empty()) {
        auto n = notices.front();
        notices.pop_front();
        toast(n);
      }
    }
  }
  void loadAudio() {
    if (auto settings = jfg::audio::read_volume(profile / "audio.ini")) {
      volume = static_cast<int>(settings->percent);
      muted = settings->muted;
    }
  }
  void saveAudio() {
    std::error_code ec;
    fs::create_directories(profile, ec);
    if (ec) {
      status("Cannot save audio settings.");
      return;
    }
    const auto tmp = profile / "audio.ini.ui.tmp", dest = profile / "audio.ini";
    {
      std::ofstream f(tmp, std::ios::binary);
      f << "version=1\nvolume=" << volume << "\nmuted=" << (muted ? 1 : 0)
        << "\n";
      f.flush();
      if (!f) {
        status("Cannot save audio settings.");
        return;
      }
    }
    if (!MoveFileExW(tmp.c_str(), dest.c_str(),
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
      status("Cannot save audio settings.");
  }
  std::string button(const std::string &action, const std::string &text,
                     bool disabled = false) {
    return "<button id=\"action-" + action + "\" data-action=\"" + action +
           "\"" +
           (disabled ? " disabled=\"disabled\" class=\"disabled\"" : "") + ">" +
           escape(text) + "</button>";
  }
  void modal(const std::string &page) {
    struct Building {
      bool &b;
      Building(bool &v) : b(v) { b = true; }
      ~Building() { b = false; }
    } guard(building);
    const auto scroll = (current == page && el("dialog-body"))
                            ? el("dialog-body")->GetScrollTop()
                            : 0.f;
    current = page;
    el("game-popup")->SetProperty("display", "none");
    if (page == "game" || page == "tools") {
      el("modal")->SetProperty("display", "none");
      el("game-popup")->SetProperty("left", page == "tools" ? "286dp" : "8dp");
      std::string menu;
      if (page == "tools") {
        menu = button("map", "Live map") +
               button("inventory", "Live inventory") +
               button("saves", "Open save folder") +
               button("support", "Support report");
      } else {
        menu = button(state.playing ? "stop" : "play",
                      state.playing ? "Stop / return home" : "Play",
                      state.busy && !state.playing);
        menu += button("setup", "Set up and build", state.playing) +
                button("rom", "Change ROM", state.busy) +
                button("mods",
                       state.mods ? "Testing mods: on" : "Testing mods: off",
                       state.busy);
        menu += "<div class=\"separator\"/>";
        menu += button("map", "Live map") +
                button("inventory", "Live inventory") +
                button("saves", "Open save folder") + button("quit", "Quit");
      }
      el("game-popup")->SetInnerRML(menu);
      el("game-popup")->SetProperty("display", "block");
      return;
    }
    el("modal")->SetProperty("display", "block");
    std::string html, note = "Settings are saved to your game profile.";
    label("dialog-title", page == "controllers" ? "CONTROLLER MAPPING"
                          : page == "setup"     ? "SET UP AND BUILD"
                          : page == "support"   ? "SUPPORT REPORT"
                          : page == "video"     ? "VIDEO"
                          : page == "audio"     ? "AUDIO"
                          : page == "game"      ? "GAME"
                                                : "JFG RECOMP");
    el("dialog")->SetProperty("width", page == "audio" ? "480dp" : "760dp");
    el("dialog")->SetProperty("height", page == "controllers" ? "620dp"
                                        : page == "audio"     ? "380dp"
                                        : page == "video"     ? "400dp"
                                                              : "450dp");
    if (page == "audio") {
      html = "<div class=\"row\"><div class=\"grow\">Master volume<div "
             "class=\"muted\">Music and effects</div></div><span "
             "id=\"volume-value\" class=\"title-font\" "
             "style=\"font-size:36dp;color:#ffb23e\">" +
             (muted ? std::string("MUTED") : std::to_string(volume) + "%") +
             "</span></div>";
      html += "<div class=\"row\">" + button("down", "-") +
              "<input class=\"volume\" type=\"range\" min=\"0\" max=\"100\" "
              "step=\"1\" value=\"" +
              std::to_string(volume) + "\" data-action=\"volume\"/>" +
              button("up", "+") + "</div>";
      html += "<div class=\"row\"><div class=\"grow\">Mute<div "
              "class=\"muted\">Volume is remembered when muted.</div></div>" +
              button("mute", muted ? "ON" : "OFF") + "</div>";
      note = "Applied immediately. Volume is remembered when muted.";
    } else if (page == "video") {
      for (const auto &name : {"Window mode", "Window size", "Aspect ratio"}) {
        html += "<div class=\"row\"><span class=\"grow\">" + std::string(name) +
                "</span>";
        if (std::string(name) == "Window mode")
          html += button("fullscreen", "Toggle fullscreen");
        else if (std::string(name) == "Window size")
          html += button("size720", "1280 x 720") +
                  button("size1080", "1920 x 1080");
        else
          html += "Original game setting";
        html += "</div>";
      }
      note = "Window size and fullscreen apply immediately. Aspect follows the "
             "original in-game widescreen option.";
    } else if (page == "controllers") {
      auto &m = mappings[player];
      html = "<div class=\"tabs\">";
      for (int i = 0; i < 4; i++)
        html += button("player" + std::to_string(i),
                       "PLAYER " + std::to_string(i + 1) +
                           (i == player ? " *" : ""));
      html += "</div><div class=\"row\"><span "
              "class=\"grow\">Device</span><select data-action=\"device\">";
      for (int d = -3; d < 4; d++) {
        std::string name =
            d == -3   ? "Keyboard"
            : d == -2 ? "Disconnected"
            : d == -1 ? "Automatic"
                      : "Controller " + std::to_string(d + 1) +
                            (connected[d] ? " (connected)" : " (offline)");
        html += "<option value=\"" + std::to_string(d) + "\"" +
                (d == m.device ? " selected=\"selected\"" : "") + ">" + name +
                "</option>";
      }
      html += "</select></div>";
      html += "<p id=\"assignment\" class=\"muted\">Changes apply live.</p>";
      const char *names[] = {
          "A",          "B",          "Z / fire",    "Start",  "D-pad up",
          "D-pad down", "D-pad left", "D-pad right", "L",      "R",
          "C up",       "C down",     "C left",      "C right"};
      html += "<div class=\"bindings\">";
      for (int i = 0; i < 14; i++)
        html += "<div class=\"row\"><span class=\"grow\">" +
                std::string(names[i]) + "</span>" +
                button("learn" + std::to_string(i), bindingName(m.bindings[i]),
                       devices[player] < 0) +
                button("clear" + std::to_string(i), "Clear") + "</div>";
      html += "</div><div class=\"row\"><span class=\"grow\">Movement "
              "stick</span>" +
              button("stick", m.stick ? "Right stick" : "Left stick") +
              "</div>";
      for (auto pair : {std::pair{"deadzone", m.deadzone},
                        std::pair{"threshold", m.threshold},
                        std::pair{"trigger", m.trigger}})
        html += "<div class=\"row\"><span class=\"grow\">" +
                std::string(pair.first) + "</span>" +
                button(std::string(pair.first) + "-", "-") + " " +
                std::to_string(pair.second) + " " +
                button(std::string(pair.first) + "+", "+") + "</div>";
      html += "<div class=\"row\">" +
              button("invertx", m.invert_x ? "Invert X: on" : "Invert X: off") +
              button("inverty", m.invert_y ? "Invert Y: on" : "Invert Y: off") +
              button("reset", "Reset mappings") + "</div>";
      note = "Choose Learn, release every control, then press the new input. "
             "Changes save automatically.";
    } else if (page == "setup") {
      html = "<div class=\"tabs\"><button>1  ROM</button><button>2  "
             "Verify</button><button>3  Build</button><button>4  "
             "Play</button></div><div class=\"name\">Set up your game</div><p "
             "class=\"muted\">Setup verifies your ROM and downloads the source "
             "and missing build tools. Your ROM stays on this PC.</p>";
      html += "<div class=\"row\" id=\"setup-status\">" +
              escape(u8(state.status)) + "</div>";
      if (!state.runtime.empty())
        html +=
            "<p class=\"muted\">Installed build: " + escape(u8(state.runtime)) +
            "</p>";
      html +=
          button("setup-start",
                 state.runtime.empty() ? "Set up game" : "Rebuild",
                 state.busy) +
          button("cancel-setup", "Cancel setup", !state.busy || state.playing);
      note = "Closing this panel keeps setup running. Completed downloads are "
             "retained.";
    } else if (page == "support") {
      html = "<p>Which session had the problem?</p><select "
             "data-action=\"session\" style=\"width:100%\">";
      std::istringstream lines(read("frontend-sessions.tsv"));
      std::string line;
      bool any = false;
      while (std::getline(lines, line)) {
        auto split = line.find('\t');
        if (split == std::string::npos)
          continue;
        auto id = line.substr(0, split);
        if (selectedSession.empty())
          selectedSession = id;
        html += "<option value=\"" + escape(id) + "\"" +
                (id == selectedSession ? " selected=\"selected\"" : "") + ">" +
                escape(line.substr(split + 1)) + "</option>";
        any = true;
      }
      html +=
          "</select><div class=\"label\" style=\"margin-top:24dp\">THE ZIP "
          "INCLUDES</div><p>Sanitized game and launcher logs<br/>Settings and "
          "mapping<br/>System and GPU diagnostics</p><p class=\"muted\">No ROM "
          "or save data. Review the ZIP before attaching it to your issue.</p>";
      html += button("zip", "Create ZIP", !any) +
              button("freeze", "Capture freeze", !state.playing) +
              button("refresh-sessions", "Refresh");
      note = "Nothing is uploaded automatically.";
    } else if (page == "game") {
      html = "<div class=\"row\">" +
             button(state.playing ? "stop" : "play",
                    state.playing ? "Stop / return home" : "Play") +
             button("setup", "Set up and build", state.playing) +
             button("rom", "Change ROM", state.busy) + "</div>";
      html +=
          "<div class=\"row\">" +
          button("mods", state.mods ? "Testing mods: on" : "Testing mods: off",
                 state.busy) +
          button("map", "Live map") + button("inventory", "Live inventory") +
          "</div>";
      html += "<div class=\"row\">" + button("saves", "Open save folder") +
              button("quit", "Quit") + "</div>";
      note = state.playing
                 ? "Settings capture game input. Escape returns to play."
                 : "Your game uses this same window.";
    } else {
      html = "<div class=\"name\">Jet Force Gemini Recomp</div><p>Native RmlUi "
             "/ C++ interface</p><p class=\"muted\">Escape opens or closes the "
             "menu. F11 toggles fullscreen. Your ROM and saves stay on this "
             "PC.</p>" +
             button("guide", "Setup guide") +
             button("support", "Support report");
    }
    el("dialog-body")->SetInnerRML(html);
    el("dialog-body")->SetScrollTop(scroll);
    label("dialog-note", note);
  }
  void rom() {
    wchar_t path[32768]{};
    OPENFILENAMEW dialog{};
    dialog.lStructSize = sizeof(dialog);
    dialog.hwndOwner = GetActiveWindow();
    dialog.lpstrFile = path;
    dialog.nMaxFile = 32768;
    dialog.lpstrFilter = L"N64 ROM\0*.z64;*.n64;*.v64\0";
    dialog.Flags = OFN_FILEMUSTEXIST | OFN_NOCHANGEDIR;
    if (GetOpenFileNameW(&dialog)) {
      fs::path p(path);
      label("rom-name", u8(p.filename().wstring()));
      label("rom-folder", u8(p.parent_path().wstring()));
      label("rom-badge", "SELECTED");
      status("ROM selected. Verification is performed by setup.");
    }
  }

  void ProcessEvent(Rml::Event &event) override {
    if (building)
      return;
    auto *t = event.GetTargetElement();
    while (t && !t->HasAttribute("data-action"))
      t = t->GetParentNode();
    if (!t || t->HasAttribute("disabled"))
      return;
    auto a = t->GetAttribute<Rml::String>("data-action", "");
    if (event.GetType() == "change") {
      if (a == "volume") {
        volume = std::clamp(event.GetParameter<int>("value", volume), 0, 100);
        saveAudio();
        label("volume-value", muted ? "MUTED" : std::to_string(volume) + "%");
        return;
      }
      if (a == "session") {
        selectedSession = event.GetParameter<Rml::String>("value", "");
        return;
      }
      if (a == "device") {
        int d = event.GetParameter<int>("value", -1);
        for (int p = 0; p < 4; p++)
          if (p != player && (d >= 0 || d == -3) && mappings[p].device == d) {
            modal("controllers");
            label("dialog-note", "That device is assigned to another player. "
                                 "Disconnect it there first.");
            return;
          }
        mappings[player].device = d;
        saveController();
        devices = assignments.devices(connected);
        learning = -1;
        refreshController();
      }
      return;
    }
    if (a == "device" || a == "session" || a == "volume")
      return;
    if (a == "zip") {
      if (writeFile("frontend-report.txt", selectedSession))
        action("export");
      return;
    }
    if (a == "freeze") {
      writeFile("frontend-capture.request", "1");
      label("dialog-note",
            "Capture requested. Leave the game open while diagnostics finish.");
      return;
    }
    if (a == "refresh-sessions") {
      action("sessions");
      return;
    }
    if (a == "close") {
      close();
      return;
    }
    if (a == "mute" || a == "up" || a == "down") {
      if (a == "mute")
        muted = !muted;
      else
        volume = std::clamp(volume + (a == "up" ? 5 : -5), 0, 100);
      saveAudio();
      modal("audio");
      return;
    }
    if (a.rfind("player", 0) == 0) {
      learning = -1;
      player = std::clamp(a.back() - '0', 0, 3);
      modal("controllers");
      return;
    }
    if (a.rfind("learn", 0) == 0) {
      learning = std::stoi(a.substr(5));
      learnReleased = false;
      learnDeadline = Rml::GetSystemInterface()->GetElapsedTime() + 12;
      label("dialog-note", "Release all controls first...");
      return;
    }
    if (a.rfind("clear", 0) == 0) {
      mappings[player].bindings[std::stoi(a.substr(5))] = -1;
      saveController();
      modal("controllers");
      return;
    }
    auto &m = mappings[player];
    bool changed = true;
    if (a == "stick")
      m.stick = !m.stick;
    else if (a == "invertx")
      m.invert_x = !m.invert_x;
    else if (a == "inverty")
      m.invert_y = !m.invert_y;
    else if (a == "reset") {
      int d = m.device;
      m = jfg::ControllerMapping{};
      m.device = d;
    } else if (a.rfind("deadzone", 0) == 0)
      m.deadzone =
          std::clamp(m.deadzone + (a.back() == '+' ? 1000 : -1000), 0, 30000);
    else if (a.rfind("threshold", 0) == 0)
      m.threshold = std::clamp(m.threshold + (a.back() == '+' ? 1000 : -1000),
                               1000, 32000);
    else if (a.rfind("trigger", 0) == 0)
      m.trigger =
          std::clamp(m.trigger + (a.back() == '+' ? 1000 : -1000), 1000, 32000);
    else
      changed = false;
    if (changed) {
      saveController();
      modal("controllers");
      return;
    }
    if (a == "audio") {
      loadAudio();
      modal(a);
    } else if (a == "controllers") {
      loadControllers();
      modal(a);
    } else if (a == "support") {
      action("sessions");
      modal(a);
    } else if (a == "video" || a == "setup" || a == "game" || a == "tools" ||
               a == "help")
      modal(a);
    else {
      if (a == "play" || a == "stop")
        close();
      action(a);
    }
  }
};

namespace {
using Microsoft::WRL::ComPtr;
struct MemoryFile {
  const unsigned char *data;
  size_t size, position = 0;
};
struct Resources : Rml::FileInterface {
  Rml::FileHandle Open(const Rml::String &path) override {
    struct Entry {
      const char *name;
      int id;
    };
    constexpr Entry entries[] = {{"main.rml", 201},
                                 {"theme.rcss", 202},
                                 {"Barlow-Regular.ttf", 203},
                                 {"Barlow-SemiBold.ttf", 204},
                                 {"ChakraPetch-Bold.ttf", 205}};
    for (auto &e : entries)
      if (fs::path(path).filename() == e.name) {
        auto r = FindResourceW(nullptr, MAKEINTRESOURCEW(e.id), RT_RCDATA);
        if (!r)
          return 0;
        auto p = LockResource(LoadResource(nullptr, r));
        if (!p)
          return 0;
        return reinterpret_cast<Rml::FileHandle>(new MemoryFile{
            static_cast<const unsigned char *>(p), SizeofResource(nullptr, r)});
      }
    return 0;
  }
  void Close(Rml::FileHandle f) override {
    delete reinterpret_cast<MemoryFile *>(f);
  }
  size_t Read(void *b, size_t n, Rml::FileHandle f) override {
    auto &m = *reinterpret_cast<MemoryFile *>(f);
    n = std::min(n, m.size - m.position);
    memcpy(b, m.data + m.position, n);
    m.position += n;
    return n;
  }
  bool Seek(Rml::FileHandle f, long off, int origin) override {
    auto &m = *reinterpret_cast<MemoryFile *>(f);
    auto p = (origin == SEEK_SET   ? 0LL
              : origin == SEEK_CUR ? static_cast<long long>(m.position)
                                   : static_cast<long long>(m.size)) +
             off;
    if (p < 0 || p > static_cast<long long>(m.size))
      return false;
    m.position = size_t(p);
    return true;
  }
  size_t Tell(Rml::FileHandle f) override {
    return reinterpret_cast<MemoryFile *>(f)->position;
  }
};
struct Surface {
  HWND window = nullptr;
  ComPtr<ID3D11Device> device;
  ComPtr<ID3D11DeviceContext> gpu;
  ComPtr<IDXGISwapChain1> swap;
  ComPtr<ID3D11RenderTargetView> target;
  ComPtr<IDCompositionDevice> composition;
  ComPtr<IDCompositionTarget> compositionTarget;
  ComPtr<IDCompositionVisual> visual;
  SystemInterface_Win32 platform;
  TextInputMethodEditor_Win32 ime;
  Resources files;
  std::unique_ptr<LogSystem> log;
  std::unique_ptr<RenderInterface_DX11> renderer;
  Rml::Context *context = nullptr;
  Ui ui;
  bool initialized = false;
  int width = 0, height = 0;
  ~Surface() {
    if (initialized) {
      if (ui.doc) {
        ui.doc->RemoveEventListener("click", &ui);
        ui.doc->RemoveEventListener("change", &ui);
      }
      Rml::Shutdown();
    }
  }
};
std::unique_ptr<Surface> surface;
void check(HRESULT r) {
  if (FAILED(r))
    throw std::runtime_error("UI graphics error " +
                             std::to_string(static_cast<unsigned long>(r)));
}
} // namespace
bool FrontendUiInit(HWND w, const fs::path &profile,
                    std::function<void(const std::string &)> action) {
  try {
    surface = std::make_unique<Surface>();
    auto &s = *surface;
    s.window = w;
    check(D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr,
                            D3D11_CREATE_DEVICE_BGRA_SUPPORT, nullptr, 0,
                            D3D11_SDK_VERSION, &s.device, nullptr, &s.gpu));
    ComPtr<IDXGIDevice> dxgi;
    check(s.device.As(&dxgi));
    ComPtr<IDXGIAdapter> adapter;
    check(dxgi->GetAdapter(&adapter));
    ComPtr<IDXGIFactory2> factory;
    check(adapter->GetParent(IID_PPV_ARGS(&factory)));
    DXGI_SWAP_CHAIN_DESC1 desc{};
    desc.Width = 1;
    desc.Height = 1;
    desc.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
    desc.SampleDesc.Count = 1;
    desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    desc.BufferCount = 2;
    desc.Scaling = DXGI_SCALING_STRETCH;
    desc.SwapEffect = DXGI_SWAP_EFFECT_FLIP_SEQUENTIAL;
    desc.AlphaMode = DXGI_ALPHA_MODE_PREMULTIPLIED;
    check(factory->CreateSwapChainForComposition(s.device.Get(), &desc, nullptr,
                                                 &s.swap));
    check(DCompositionCreateDevice(dxgi.Get(), IID_PPV_ARGS(&s.composition)));
    check(s.composition->CreateTargetForHwnd(w, TRUE, &s.compositionTarget));
    check(s.composition->CreateVisual(&s.visual));
    check(s.visual->SetContent(s.swap.Get()));
    check(s.compositionTarget->SetRoot(s.visual.Get()));
    check(s.composition->Commit());
    s.platform.SetWindow(w);
    s.log = std::make_unique<LogSystem>(&s.platform);
    s.log->file.close();
    s.log->file.open(profile / "frontend-ui.log", std::ios::trunc);
    s.renderer = std::make_unique<RenderInterface_DX11>(s.device.Get());
    Rml::SetSystemInterface(s.log.get());
    Rml::SetRenderInterface(s.renderer.get());
    Rml::SetFileInterface(&s.files);
    Rml::SetTextInputHandler(&s.ime);
    if (!Rml::Initialise())
      throw std::runtime_error("Cannot initialize RmlUi");
    s.initialized = true;
    for (const char *font :
         {"Barlow-Regular.ttf", "Barlow-SemiBold.ttf", "ChakraPetch-Bold.ttf"})
      if (!Rml::LoadFontFace(font))
        throw std::runtime_error("Cannot load UI font");
    s.context = Rml::CreateContext("frontend", {1, 1});
    s.ui.window = w;
    s.ui.profile = profile;
    s.ui.action = std::move(action);
    s.ui.doc = s.context->LoadDocument("main.rml");
    if (!s.ui.doc)
      throw std::runtime_error("Cannot load UI document");
    s.ui.doc->AddEventListener("click", &s.ui);
    s.ui.doc->AddEventListener("change", &s.ui);
    s.ui.doc->Show();
    s.ui.loadAudio();
    s.ui.loadControllers();
    BOOL animations = TRUE;
    SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, &animations, 0);
    s.ui.reducedMotion = !animations;
    s.ui.doc->SetClass("reduced-motion", s.ui.reducedMotion);
    FrontendUiResize();
    return true;
  } catch (const std::exception &e) {
    MessageBoxW(w, RmlWin32::ConvertToUTF16(e.what()).c_str(),
                L"Cannot start interface", MB_OK | MB_ICONERROR);
    surface.reset();
    return false;
  }
}
void FrontendUiShutdown() { surface.reset(); }
void FrontendUiResize() {
  if (!surface || !surface->context)
    return;
  auto &s = *surface;
  RECT r{};
  GetClientRect(s.window, &r);
  int w = std::max(1L, r.right), h = std::max(1L, r.bottom);
  s.context->SetDensityIndependentPixelRatio(GetDpiForWindow(s.window) / 96.f);
  if (w == s.width && h == s.height)
    return;
  s.width = w;
  s.height = h;
  s.gpu->OMSetRenderTargets(0, nullptr, nullptr);
  s.target.Reset();
  check(s.swap->ResizeBuffers(0, w, h, DXGI_FORMAT_UNKNOWN, 0));
  ComPtr<ID3D11Texture2D> buffer;
  check(s.swap->GetBuffer(0, IID_PPV_ARGS(&buffer)));
  check(s.device->CreateRenderTargetView(buffer.Get(), nullptr, &s.target));
  s.context->SetDimensions({w, h});
  s.renderer->SetViewport(w, h);
}
void FrontendUiFrame(const FrontendUiState &state) {
  if (!surface || !surface->context || IsIconic(surface->window))
    return;
  auto &s = *surface;
  auto &ui = s.ui;
  const bool refreshPanel =
      (state.mods != ui.state.mods || state.busy != ui.state.busy ||
       state.playing != ui.state.playing) &&
      (ui.current == "game" || ui.current == "setup");
  if (state.playing != ui.state.playing) {
    if (state.playing) {
      ui.assignments = jfg::ControllerPorts{};
      ui.loadControllers();
      ui.devices = ui.assignments.devices(ui.connected);
    }
    ui.doc->SetClass("playing", state.playing);
    if (state.playing)
      for (int p = 0; p < 4; p++)
        if (ui.devices[p] >= 0 && ui.connected[ui.devices[p]])
          ui.toast("Controller " + std::to_string(ui.devices[p] + 1) +
                   " connected - Player " + std::to_string(p + 1));
  }
  if (state.fullscreen != ui.state.fullscreen)
    ui.doc->SetClass("fullscreen", state.fullscreen);
  if (state.rom != ui.state.rom) {
    fs::path p(state.rom);
    ui.label("rom-name", state.rom.empty() ? "Choose your game ROM"
                                           : u8(p.filename().wstring()));
    ui.label("rom-folder", state.rom.empty() ? "Required to set up and play."
                                             : u8(p.parent_path().wstring()));
    ui.label("rom-badge", state.rom.empty() ? "" : "SELECTED");
  }
  if (state.status != ui.state.status) {
    ui.status(u8(state.status));
    if (auto *e = ui.el("setup-status"))
      e->SetInnerRML(escape(u8(state.status)));
  }
  ui.doc->SetClass("paused",
                   state.playing &&
                       GetPropW(s.window, L"JfgFrontendPaused") != nullptr);
  ui.state = state;
  if (refreshPanel)
    ui.modal(ui.current);
  if (ui.current == "support") {
    auto list = ui.read("frontend-sessions.tsv");
    if (list != ui.sessionList) {
      ui.sessionList = list;
      ui.modal("support");
    }
  }
  ui.ports();
  s.context->Update();
  const float clear[] = {0, 0, 0, 0};
  s.gpu->ClearRenderTargetView(s.target.Get(), clear);
  s.renderer->BeginFrame();
  s.context->Render();
  s.renderer->EndFrame(s.target.Get());
  s.swap->Present(1, 0);
}
void FrontendUiMessage(UINT m, WPARAM w, LPARAM l) {
  if (surface && surface->context)
    RmlWin32::WindowProcedure(surface->context, surface->ime, surface->window,
                              m, w, l);
}
void FrontendUiPanel(const std::string &name) {
  if (surface) {
    if (name.empty())
      surface->ui.close();
    else
      surface->ui.modal(name);
  }
}
bool FrontendUiCapturing() { return surface && !surface->ui.current.empty(); }
