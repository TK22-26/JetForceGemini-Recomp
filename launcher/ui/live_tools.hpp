#pragma once
#include <RmlUi/Core.h>
#include <RmlUi/Core/Elements/ElementFormControl.h>
#include <RmlUi/Core/RenderManager.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <sstream>
#include <vector>

namespace jfg_live {
using Point = Rml::Vector2f;
inline std::string escaped(const std::string &text) {
  std::string out;
  for (char c : text) {
    if (c == '&')
      out += "&amp;";
    else if (c == '<')
      out += "&lt;";
    else if (c == '>')
      out += "&gt;";
    else if (c == '\"')
      out += "&quot;";
    else if (c == '\n')
      out += "<br/>";
    else if (c != '\r')
      out += c;
  }
  return out;
}
struct Triangle {
  Point a, b, c;
  unsigned color;
};
struct Line {
  Point a, b;
  float width;
  unsigned color;
};
struct Marker {
  unsigned id;
  float x, y, z;
  int shape;
  unsigned color;
  std::string label, details, kind, action;
};
struct Snapshot {
  int sequence = 0;
  bool active = false, paused = false, ready = false, navigation = false,
       art = false, known = false;
  unsigned level = 0, mods = 0, modError = 0;
  long long generation = 0, update = 0;
  int current = -1;
  std::array<unsigned, 3> weapons{}, items{};
  unsigned shared = 0;
  std::string ai = "AI stopped", status = "Connecting to live tools...",
              progress = "Not loaded yet",
              artStatus = "Reading images from your ROM...";
  float lx = 0, lz = 0, hx = 1, hz = 1, height = 0, low = 0, high = 1;
  std::vector<Triangle> triangles;
  std::vector<Line> lines;
  std::vector<Marker> markers;
};
class Reader {
  std::vector<char> bytes;
  size_t at = 0;

public:
  explicit Reader(const std::filesystem::path &path) {
    HANDLE file =
        CreateFileW(path.c_str(), GENERIC_READ,
                    FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                    nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE)
      throw std::runtime_error("No complete live update");
    LARGE_INTEGER size{};
    bool valid = GetFileSizeEx(file, &size) && size.QuadPart >= 0 &&
                 size.QuadPart <= 64 * 1024 * 1024;
    if (!valid) {
      CloseHandle(file);
      throw std::runtime_error("Invalid live update size");
    }
    bytes.resize(static_cast<size_t>(size.QuadPart));
    DWORD read = 0;
    bool ok = ReadFile(file, bytes.data(), static_cast<DWORD>(bytes.size()),
                       &read, nullptr) != FALSE;
    CloseHandle(file);
    if (!ok || read != bytes.size())
      throw std::runtime_error("Incomplete live update");
  }

  template <class T> T get() {
    if (at + sizeof(T) > bytes.size())
      throw std::runtime_error("Truncated live update");
    T value;
    memcpy(&value, bytes.data() + at, sizeof(T));
    at += sizeof(T);
    return value;
  }
  int count(int max) {
    int n = get<int>();
    if (n < 0 || n > max)
      throw std::runtime_error("Invalid live count");
    return n;
  }
  float number() {
    float f = get<float>();
    if (!std::isfinite(f) || std::abs(f) > 1e9f)
      throw std::runtime_error("Invalid live position");
    return f;
  }
  Point point() {
    float x = number(), y = number();
    return {x, y};
  }
  std::string text() {
    int n = count(1024 * 1024);
    if (at + n > bytes.size())
      throw std::runtime_error("Truncated live text");
    std::string s(bytes.data() + at, n);
    at += n;
    return s;
  }
  Snapshot read() {
    if (get<unsigned>() != 0x32544c4a)
      throw std::runtime_error("Unsupported live protocol");
    Snapshot d;
    d.sequence = get<int>();
    d.active = get<int>() != 0;
    d.paused = get<int>() != 0;
    d.ready = get<int>() != 0;
    d.level = get<unsigned>();
    d.generation = get<long long>();
    d.update = get<long long>();
    d.navigation = get<int>() != 0;
    d.ai = text();
    d.status = text();
    d.progress = text();
    d.artStatus = text();
    d.art = get<int>() != 0;
    d.current = get<int>();
    d.known = get<int>() != 0;
    if (d.current < -1 || d.current > 2)
      throw std::runtime_error("Invalid character");
    for (int i = 0; i < 3; i++) {
      d.weapons[i] = get<unsigned>();
      d.items[i] = get<unsigned>();
    }
    d.shared = get<unsigned>();
    d.lx = number();
    d.lz = number();
    d.hx = number();
    d.hz = number();
    d.height = number();
    d.low = number();
    d.high = number();
    int n = count(2000000);
    d.triangles.reserve(n);
    for (int i = 0; i < n; i++) {
      auto a = point(), b = point(), c = point();
      d.triangles.push_back({a, b, c, get<unsigned>()});
    }
    n = count(100000);
    d.lines.reserve(n);
    for (int i = 0; i < n; i++) {
      auto a = point(), b = point();
      float width = number();
      d.lines.push_back({a, b, width, get<unsigned>()});
    }
    n = count(10000);
    d.markers.reserve(n);
    for (int i = 0; i < n; i++) {
      Marker m;
      m.id = get<unsigned>();
      m.x = number();
      m.y = number();
      m.z = number();
      m.shape = get<int>();
      m.color = get<unsigned>();
      m.label = text();
      m.details = text();
      m.kind = text();
      m.action = text();
      d.markers.push_back(std::move(m));
    }
    if (bytes.size() - at == sizeof(unsigned) || bytes.size() - at == 2*sizeof(unsigned)) d.mods = get<unsigned>();
    if (bytes.size() - at == sizeof(unsigned)) d.modError = get<unsigned>();
    if (at != bytes.size())
      throw std::runtime_error("Unexpected live payload");
    return d;
  }
};
class MapScene final : public Rml::Element, public Rml::EventListener {
  Rml::Mesh mesh;
  Rml::Geometry geometry;
  Point lastSize{}, mouse{}, start{};
  bool dragging = false, dirty = true;
  int renderedSequence = -1;
  float renderedZoom = -1;
  Point renderedPan{};
  static Rml::ColourbPremultiplied color(unsigned c) {
    return Rml::Colourb((c >> 24) & 255, (c >> 16) & 255, (c >> 8) & 255,
                        c & 255)
        .ToPremultiplied();
  }
  void triangle(Point a, Point b, Point c, unsigned tint) {
    int i = static_cast<int>(mesh.vertices.size());
    auto v = color(tint);
    mesh.vertices.push_back({a, v, {}});
    mesh.vertices.push_back({b, v, {}});
    mesh.vertices.push_back({c, v, {}});
    mesh.indices.insert(mesh.indices.end(), {i, i + 1, i + 2});
  }
  void line(Point a, Point b, float width, unsigned tint) {
    auto d = b - a;
    float len = std::sqrt(d.x * d.x + d.y * d.y);
    if (len < .001f)
      return;
    Point n(-d.y * width * .5f / len, d.x * width * .5f / len);
    triangle(a + n, b + n, b - n, tint);
    triangle(a + n, b - n, a - n, tint);
  }
  void disc(Point at, float radius, unsigned tint) {
    for (int i = 0; i < 24; i++) {
      float a = i * 6.2831853f / 24, b = (i + 1) * 6.2831853f / 24;
      triangle(at, at + Point(std::cos(a), std::sin(a)) * radius,
               at + Point(std::cos(b), std::sin(b)) * radius, tint);
    }
  }
  void ring(Point at, float radius, float width, unsigned tint) {
    for (int i = 0; i < 72; i++) {
      float a = i * 6.2831853f / 72, b = (i + 1) * 6.2831853f / 72;
      line(at + Point(std::cos(a), std::sin(a)) * radius,
           at + Point(std::cos(b), std::sin(b)) * radius, width, tint);
    }
  }

public:
  const Snapshot *data = nullptr;
  float zoom = 1;
  Point pan{};
  unsigned selected = 0;
  bool reducedMotion = false;
  std::function<void(unsigned)> pick, activate;
  unsigned lastPick = 0;
  ULONGLONG lastPickTime = 0;
  Point lastPickPoint{};
  std::function<void()> zoomChanged;
  explicit MapScene(const Rml::String &tag) : Element(tag) {
    for (auto name :
         {"mousescroll", "mousedown", "mousemove", "mouseup", "mouseout"})
      AddEventListener(name, this);
  }
  Point dimensions() {
    return GetBox().GetSize(Rml::BoxArea::Content) /
           GetContext()->GetDensityIndependentPixelRatio();
  }
  float scale() {
    auto size = dimensions();
    return std::min(std::max(1.f, size.x - 80) /
                        std::max(1.f, data->hx - data->lx),
                    std::max(1.f, size.y - 80) /
                        std::max(1.f, data->hz - data->lz)) *
           zoom;
  }
  Point project(Point p) {
    auto size = dimensions();
    return size * .5f +
           (p -
            Point((data->lx + data->hx) * .5f, (data->lz + data->hz) * .5f)) *
               scale() +
           pan;
  }
  Point unproject(Point p) {
    return (p - dimensions() * .5f - pan) / scale() +
           Point((data->lx + data->hx) * .5f, (data->lz + data->hz) * .5f);
  }
  void fit() {
    zoom = 1;
    pan = {};
    dirty = true;
    if (zoomChanged)
      zoomChanged();
  }
  void zoomAt(float amount, Point anchor) {
    float next = std::clamp(zoom * amount, .25f, 16.f), ratio = next / zoom;
    auto origin = dimensions() * .5f;
    pan = anchor - origin - (anchor - origin - pan) * ratio;
    zoom = next;
    dirty = true;
    if (zoomChanged)
      zoomChanged();
  }
  void center(Point p) {
    pan += dimensions() * .5f - project(p);
    dirty = true;
  }
  void invalidate() { dirty = true; }
  void ProcessEvent(Rml::Event &e) override {
    auto type = e.GetType();
    float dpi = GetContext()->GetDensityIndependentPixelRatio();
    Point p = (Point(e.GetParameter<float>("mouse_x", 0),
                     e.GetParameter<float>("mouse_y", 0)) -
               GetAbsoluteOffset(Rml::BoxArea::Content)) /
              dpi;
    if (type == "mousescroll") {
      zoomAt(std::pow(1.2f, -e.GetParameter<float>("wheel_delta_y", 0)), p);
      e.StopPropagation();
    }
    if (type == "mousedown" && e.GetParameter<int>("button", -1) == 0) {
      dragging = true;
      start = mouse = p;
    }
    if (type == "mousemove" && dragging) {
      pan += p - mouse;
      mouse = p;
      dirty = true;
    }
    if (type == "mouseup" && dragging) {
      dragging = false;
      if (std::abs(p.x - start.x) + std::abs(p.y - start.y) < 5 && data) {
        float best = 14;
        unsigned chosen = 0;
        for (const auto &m : data->markers) {
          if (!m.id)
            continue;
          auto d = project({m.x, m.z}) - p;
          float distance = std::sqrt(d.x * d.x + d.y * d.y);
          if (distance < best) {
            best = distance;
            chosen = m.id;
          }
        }
        if (chosen && pick) pick(chosen);
        auto now = GetTickCount64();
        if (chosen && chosen == lastPick && now - lastPickTime <= GetDoubleClickTime() &&
            std::abs(p.x-lastPickPoint.x) <= GetSystemMetrics(SM_CXDOUBLECLK) &&
            std::abs(p.y-lastPickPoint.y) <= GetSystemMetrics(SM_CYDOUBLECLK)) {
          lastPick = 0; lastPickTime = 0;
          if (activate) activate(chosen);
        } else { lastPick=chosen;lastPickTime=now;lastPickPoint=p; }
      }
      dirty = true;
    }
    if (type == "mouseout" && e.GetTargetElement() == this)
      dragging = false;
  }

protected:
  void OnRender() override {
    if (!data)
      return;
    auto size = dimensions();
    float dpi = GetContext()->GetDensityIndependentPixelRatio();
    if (size != lastSize || renderedSequence != data->sequence ||
        renderedZoom != zoom || renderedPan != pan || !data->ready)
      dirty = true;
    if (dirty) {
      mesh = {};
      for (float x = 0; x < size.x; x += 40)
        line({x, 0}, {x, size.y}, .6f, 0x151e2b80);
      for (float y = 0; y < size.y; y += 40)
        line({0, y}, {size.x, y}, .6f, 0x151e2b80);
      if (data->ready) {
        for (auto &t : data->triangles)
          triangle(project(t.a), project(t.b), project(t.c), t.color);
        for (auto &l : data->lines)
          line(project(l.a), project(l.b), l.width, l.color);
        for (auto &m : data->markers) {
          auto p = project({m.x, m.z});
          if (p.x < -20 || p.x > size.x + 20 || p.y < -20 || p.y > size.y + 20)
            continue;
          if (m.id && m.id == selected)
            ring(p, 11, 1.5f, 0xffb23eff);
          if (m.shape == 1) {
            triangle(p + Point(-4, -4), p + Point(4, -4), p + Point(4, 4),
                     m.color);
            triangle(p + Point(-4, -4), p + Point(4, 4), p + Point(-4, 4),
                     m.color);
          } else if (m.shape == 2) {
            triangle(p + Point(0, -6), p + Point(6, 0), p + Point(0, 6),
                     m.color);
            triangle(p + Point(0, -6), p + Point(0, 6), p + Point(-6, 0),
                     m.color);
          } else if (m.shape == 4) {
            line(p - Point(4, 4), p + Point(4, 4), 1, m.color);
            line(p + Point(-4, 4), p + Point(4, -4), 1, m.color);
          } else if (m.shape == 3) {
            disc(p, 8, 0x070a10ff);
            disc(p, 5.5f, m.color);
            ring(p, 10, .8f, 0x6fd3ee66);
          } else
            ring(p, 5, 2, m.color);
        }
      } else {
        Point c(size.x * .5f, std::max(70.f, size.y * .5f - 150));
        for (float r : {20.f, 38.f, 56.f})
          ring(c, r, .8f, 0x2a3550bb);
        float t =
            reducedMotion
                ? 0
                : static_cast<float>(
                      Rml::GetSystemInterface()->GetElapsedTime() * 2.61799);
        line(c, c + Point(std::sin(t), -std::cos(t)) * 54, 1.5f, 0xffb23ebb);
        disc(c, 3, 0xffb23eff);
      }
      for (auto &v : mesh.vertices)
        v.position *= dpi;
      geometry = GetContext()->GetRenderManager().MakeGeometry(std::move(mesh));
      lastSize = size;
      renderedSequence = data->sequence;
      renderedZoom = zoom;
      renderedPan = pan;
      dirty = false;
    }
    geometry.Render(GetAbsoluteOffset(Rml::BoxArea::Content));
  }
};

class ToolUi : public Rml::EventListener {
  std::filesystem::path root;
  Rml::ElementDocument *doc = nullptr;
  HWND window = nullptr;
  std::string kind, popup, tab = "display", lastList, lastInventory, lastLabels;
  Snapshot data;
  MapScene *scene = nullptr;
  unsigned selected = 0;
  int filter = 0, character = 1, selectedItem = 0, mode = 0, slice = 64,
      jump = 0;
  bool allLabels = false;
  bool follow = true, inspector = true, legend = true, other = true,
       collision = true, origins = false, advanced = false, modal = false,
       building = false;
  float height = 0;
  ULONGLONG lastRead = 0, lastSuccess = 0;
  unsigned commandId = 0, lastModError = 0;
  double toastUntil = 0;
  bool modsWriteFailed = false, modsCommandPending = false;
  ULONGLONG modsSentAt = 0;
  std::function<void(const std::string &)> action;
  Rml::Element *el(const char *id) { return doc->GetElementById(id); }
  void label(const char *id, const std::string &text) {
    if (auto e = el(id)) {
      auto rml = escaped(text);
      if (e->GetInnerRML() != rml)
        e->SetInnerRML(rml);
    }
  }
  void display(const char *id, bool show, const char *type = "block") {
    if (auto e = el(id))
      e->SetProperty("display", show ? type : "none");
  }
  void enable(const char *id, bool value) {
    if (auto e = el(id)) {
      e->SetPseudoClass("disabled", !value);
      e->SetClass("disabled", !value);
      if (value)
        e->RemoveAttribute("disabled");
      else
        e->SetAttribute("disabled", "");
    }
  }
  void modsError() {
    label("toast-text", "Error loading mods");
    if (auto toast = el("toast")) toast->SetClass("visible", true);
    toastUntil=Rml::GetSystemInterface()->GetElapsedTime()+4.62;
  }
  void animateToast() {
    if(!toastUntil)return;
    auto toast=el("toast");if(!toast)return;
    double now=Rml::GetSystemInterface()->GetElapsedTime(),elapsed=now-(toastUntil-4.62),y=0,opacity=1;
    if(now>=toastUntil){toast->SetClass("visible",false);toast->SetProperty("opacity","0");toastUntil=0;return;}
    if(elapsed<.4){double t=std::clamp(elapsed/.4,0.,1.),q=t-1;double eased=1+2.70158*q*q*q+1.70158*q*q;y=96*(1-eased);opacity=t;}
    else if(elapsed>4.4){double t=std::clamp((elapsed-4.4)/.22,0.,1.);y=120*t*t;opacity=1-t;}
    toast->SetProperty("transform","translate(0dp, "+std::to_string(scene&&scene->reducedMotion?0:y)+"dp)");
    toast->SetProperty("opacity",std::to_string(opacity));
  }
  void command(const std::string &value) {
    auto path = root / ("command-" + std::to_string(GetTickCount64()) + "-" +
                        std::to_string(++commandId) + ".txt"),
         temp = path;
    temp += L".tmp";
    std::ofstream f(temp, std::ios::binary);
    f << value;
    f.close();
    bool modCommand=value.rfind("warp-mod ",0)==0 || value.rfind("health-mod ",0)==0 || value.rfind("kill-mod ",0)==0 || value=="mods-off";
    if (!f || !MoveFileExW(temp.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING)) {
      if(modCommand){modsWriteFailed=true;modsError();}
      else label("tool-status", "Cannot send the setting to live tools.");
    } else if(modCommand){modsCommandPending=true;modsSentAt=GetTickCount64();}
  }
  void closePopup() {
    popup.clear();
    display("view-popup", false);
    display("settings-popup", false);
    display("tools-popup", false);
    for (auto id : {"tool-view", "tool-settings", "tool-tools"})
      if (auto e = el(id))
        e->SetClass("selected", false);
  }
  void openPopup(const std::string &name) {
    closePopup();
    popup = name;
    display((name + "-popup").c_str(), true);
    auto menu = el(("tool-" + name).c_str());
    el((name + "-popup").c_str())->SetProperty("left", std::to_string(menu->GetAbsoluteOffset(Rml::BoxArea::Border).x) + "px");
    menu->SetClass("selected", true);
  }
  void showModal(bool show) {
    closePopup();
    modal = show;
    display("tool-modal", show);
    if (show)
      settings();
    if (show)
      SetPropW(window, L"JfgLiveModal", reinterpret_cast<HANDLE>(1));
    else
      RemovePropW(window, L"JfgLiveModal");
    action(show ? "modal-open" : "modal-close");
  }
  static std::string button(const std::string &id, const std::string &text,
                            const std::string &cls = "") {
    return "<button id=\"" + id + "\" class=\"" + cls + "\"><span>" + text +
           "</span></button>";
  }
  std::string toggle(const char *id, const char *title, const char *help,
                     bool on) {
    return std::string("<div class=\"setting-toggle\"><div class=\"grow\"><div "
                       "class=\"setting-name\">") +
           title + "</div><div class=\"muted\">" + help +
           "</div></div><button id=\"" + id + "\" class=\"switch " +
           (on ? "on" : "") + "\" aria-label=\"" + title +
           "\"><span/></button></div>";
  }
  void settings() {
    building = true;
    for (auto name : {"display", "ai", "mods"})
      el((std::string("tab-") + name).c_str())
          ->SetClass("selected", tab == name);
    std::string html;
    if (tab == "display") {
      html = "<div class=\"section-label\">HEIGHT SLICE</div><p "
             "class=\"muted\">Choose which vertical band of the room is drawn "
             "bright.</p><div class=\"setting-fields\"><div "
             "class=\"floor-field\"><label>Floor</label><select "
             "id=\"floor-mode\">";
      const char *modes[] = {"Player floor", "Height slice", "All heights"};
      for (int i = 0; i < 3; i++)
        html += "<option value=\"" + std::to_string(i) + "\"" +
                (i == mode ? " selected" : "") + ">" + modes[i] + "</option>";
      html += "</select></div><div class=\"height-field\"><label>Height "
              "Y</label><input id=\"height-value\" type=\"text\" value=\"" +
              (mode == 1 ? std::to_string(static_cast<int>(height))
                         : "Follows player") +
              "\" " + (mode == 1 ? "" : "disabled") +
              "/></div><div class=\"slice-field\"><label>Slice "
              "width</label><div class=\"stepper\">" +
              button("slice-minus", "−") + "<span id=\"slice-value\">" +
              std::to_string(slice) + "</span>" + button("slice-plus", "+") +
              "</div></div></div>";
      html += toggle("toggle-other", "Show other heights",
                     "Draw floors outside the selected slice faintly.", other) +
              "<div class=\"separator\"/><div "
              "class=\"section-label\">OVERLAYS</div>" +
              toggle("toggle-collision", "Entity collision boxes",
                     "Show the bounds of loaded objects and characters.",
                     collision) +
              toggle("toggle-origins", "Unknown entity origins",
                     "Mark entities whose collision shape is unavailable.",
                     origins);
    } else if (tab == "ai") {
      html = "<div class=\"section-label\">AUTOPILOT</div><div "
             "class=\"ai-card\"><div class=\"setting-name\" "
             "id=\"ai-title\">Autopilot</div><p class=\"muted\" "
             "id=\"ai-help\"/><div id=\"ai-state\"/></div><div "
             "class=\"setting-toggle\"><div class=\"grow\"><div "
             "class=\"setting-name\">Explore automatically</div><div "
             "class=\"muted\">Visits untried exits and objectives on its "
             "own.</div></div>" +
             button("ai-explore", "Start exploring", "primary") +
             "</div><div class=\"setting-toggle\"><div class=\"grow\"><div "
             "class=\"setting-name\">Movement mode</div><div "
             "class=\"muted\">How the AI jumps between "
             "ledges.</div></div><select id=\"jump-mode\"><option value=\"0\"" +
             (jump == 0 ? " selected" : "") +
             ">Normal (C-Up jump)</option><option value=\"1\"" +
             (jump == 1 ? " selected" : "") +
             ">Expert (A jump)</option></select></div>" +
             toggle("toggle-advanced", "Advanced individual tests",
                    "Plan and inspect a selected exit route.", advanced) +
             "<div class=\"ai-actions\">" + button("ai-stop", "Stop AI") +
             "</div>";
      if (advanced)
        html += "<div class=\"ai-actions\">" +
                button("ai-plan", "Plan exit route") +
                button("ai-start", "Start planned route") +
                button("ai-retry", "Retry room exits") + "</div>";
    }
    if (tab == "mods") {
      html = "<div class=\"section-label\">MODS</div><p class=\"muted\">Optional gameplay changes.</p>";
      html += toggle("toggle-warp-mod", "Warp to exits", "Double-click an exit marker on the map or an exit in the inspector to warp to it. Normal exit requirements still apply.", (data.mods & 2) != 0);
      html += toggle("toggle-health-mod", "Infinite health", "Keep your current character at full health and prevent damage during gameplay.", (data.mods & 4) != 0);
      html += toggle("toggle-kill-mod", "Instant kill enemies", "Automatically defeat loaded ordinary enemies during gameplay. Tribals and friendly NPCs are spared; defeated enemies stay defeated when switched off.", (data.mods & 8) != 0);
      html += "<p id=\"mods-help\" class=\"muted\"/>";
    }
    el("settings-content")->SetInnerRML(html);
    enable("slice-minus", mode != 2);
    enable("slice-plus", mode != 2);
    building = false;
    refreshAi();
  }
  void refreshAi() {
    bool failed=modsWriteFailed || (data.mods & 16)!=0;
    for (auto id : {"toggle-warp-mod", "toggle-health-mod", "toggle-kill-mod"}) enable(id, !failed);
    label("mods-help", failed ? "Mods could not be loaded. Reopen the map or start a new game to try again."
                             : "Your choices are saved and apply when you play.");
    label("ai-state", data.ai);
    label("ai-help",
          data.navigation ? "Navigation is available in this session."
          : data.active ? "Autopilot is unavailable in this game session. The "
                          "map remains live."
                        : "Start a game to receive live navigation data.");
    for (auto id : {"ai-explore", "ai-plan", "ai-start", "ai-retry"})
      enable(id, data.navigation);
  }
  bool inFilter(const Marker &m) const {
    return m.kind != "player" &&
           (filter == 0 || filter == 1 && m.action == "open_chest" ||
            filter == 2 &&
                (m.kind == "key" || m.kind == "weapon" || m.kind == "item" ||
                 m.kind == "pickup" || m.kind == "health" || m.kind == "ammo" ||
                 m.kind == "token") ||
            filter == 3 && m.kind == "exit" ||
            filter == 4 && (m.kind == "npc" || m.kind == "tribal") ||
            filter == 5 && m.kind == "enemy");
  }
  void select(unsigned id) {
    selected = id;
    if (scene) {
      scene->selected = id;
      scene->invalidate();
    }
    command("select " + std::to_string(id));
    refreshInspector();
  }
  void refreshLabels() {
    if (!scene)
      return;
    struct LabelBox {
      float x, y, width, height;
    };
    std::vector<LabelBox> placed;
    std::string links, labels;
    auto dimensions = scene->dimensions();
    auto layer = el("marker-labels");
    const float dpi = doc->GetContext()->GetDensityIndependentPixelRatio();
    const float lineHeight = layer->GetLineHeight() / dpi + 4;
    if (data.ready)
      for (const auto &m : data.markers) {
        if (!allLabels && m.kind != "exit" && !(selected && m.id == selected))
          continue;
        const auto point = scene->project({m.x, m.z});
        if (point.x < 0 || point.y < 0 || point.x > dimensions.x ||
            point.y > dimensions.y)
          continue;
        const float width = std::min(
            238.f,
            Rml::ElementUtilities::GetStringWidth(layer, m.label) / dpi + 8);
        const float left = std::clamp(
            point.x + 10 + width > dimensions.x ? point.x - width - 10
                                                : point.x + 10,
            4.f, std::max(4.f, dimensions.x - width - 4));
        const float top = std::clamp(
            point.y - 8, 4.f, std::max(4.f, dimensions.y - lineHeight - 4));
        LabelBox box{left, top, width, lineHeight};
        // Spread nearby pickups into readable rows; keep a leader to each
        // marker. Bound the search so crowded rooms still render promptly.
        for (int attempt = 0; attempt < 32; ++attempt) {
          const int row =
              attempt == 0 ? 0 : (attempt + 1) / 2 * (attempt % 2 ? 1 : -1);
          LabelBox candidate{left, top + row * (lineHeight + 3), width,
                             lineHeight};
          if (candidate.y < 4 || candidate.y + lineHeight > dimensions.y - 4)
            continue;
          bool overlaps = std::any_of(
              placed.begin(), placed.end(), [&](const LabelBox &other) {
                return candidate.x < other.x + other.width + 3 &&
                       candidate.x + candidate.width + 3 > other.x &&
                       candidate.y < other.y + other.height + 3 &&
                       candidate.y + candidate.height + 3 > other.y;
              });
          if (!overlaps) {
            box = candidate;
            break;
          }
        }
        placed.push_back(box);
        if (std::abs(box.y - top) > 1) {
          Point end(box.x >= point.x ? box.x : box.x + box.width,
                    box.y + lineHeight * .5f);
          auto direction = end - point;
          links += "<div class=\"map-label-link\" style=\"left:" +
                   std::to_string(point.x) +
                   "dp;top:" + std::to_string(point.y) + "dp;width:" +
                   std::to_string(std::sqrt(direction.x * direction.x +
                                            direction.y * direction.y)) +
                   "dp;transform:rotate(" +
                   std::to_string(std::atan2(direction.y, direction.x) *
                                  57.2957795f) +
                   "deg)\"/>";
        }
        labels += "<div class=\"map-label " +
                  std::string(selected && m.id == selected ? "selected" : "") +
                  "\" style=\"left:" + std::to_string(box.x) +
                  "dp;top:" + std::to_string(box.y) + "dp\">" +
                  escaped(m.label) + "</div>";
      }
    auto html = links + labels;
    if (html != lastLabels) {
      lastLabels = html;
      layer->SetInnerRML(html);
    }
  }
  void refreshInspector() {
    std::string list;
    bool found = false;
    for (auto &m : data.markers)
      if (inFilter(m)) {
        list +=
            button("node-" + std::to_string(m.id), escaped(m.label),
                   "interaction");
        if (m.id == selected) {
          found = true;
          label("interaction-details", m.details.empty() ? m.label : m.details);
        }
      }
    if (list != lastList) {
      lastList = list;
      auto pane = el("interaction-list");
      float scroll = pane->GetScrollTop();
      pane->SetInnerRML(list);
      pane->SetScrollTop(scroll);
    }
    // Keep inspector elements alive across selection so RmlUi can recognize
    // a double-click on a previously unselected exit.
    for (const auto &m : data.markers)
      if (auto item = el(("node-" + std::to_string(m.id)).c_str()))
        item->SetClass("selected", m.id == selected);
    if (!found)
      label(
          "interaction-details",
          data.ready
              ? "Select anything on the map to inspect its reward, "
                "requirements and coordinates."
              : "Nothing to inspect yet. Once a room loads, select anything on "
                "the map to see its reward, requirements and coordinates.");
    enable("center-selected", found);
    label("progress-value", data.progress);
  }
  struct Item {
    int id;
    std::string name;
    int group, bit;
  };
  static const std::vector<Item> &inventoryItems() {
    static const std::vector<Item> list = []() {
      std::vector<Item> v;
      const char *weapons[] = {
          "Pistol",         "Homing missiles", "Machine gun",
          "Plasma shotgun", "Shocker",         "Tri-rocket launcher",
          "Flamethrower",   "Sniper rifle",    "Grenades",
          "Shurikens",      "Fish Food",       "Timed mines",
          "Remote mines",   "Flares",          "Cluster bombs"};
      for (int i = 0; i < 15; i++)
        v.push_back({i, weapons[i], 0, i});
      // ID 10 is an internal flag, not a verified physical inventory pickup.
      int ids[] = {0, 1, 2, 3, 9, 16, 17, 20, 21, 22, 23, 24, 25, 26, 27};
      const char *names[] = {"Yellow key",
                             "Red key",
                             "Magenta key",
                             "Green key",
                             "Blue key",
                             "Specialist magazine",
                             "Mine key",
                             "Pants",
                             "Crowbar",
                             "Night vision goggles",
                             "Gold bar 3",
                             "Gold bar 2",
                             "Gold bar 1",
                             "Ear plugs",
                             "Arcade chip"};
      for (int i = 0; i < static_cast<int>(std::size(ids)); i++)
        v.push_back({100 + ids[i], names[i], 1, ids[i]});
      const char *parts[] = {
          "Power cell",       "Radar dish",       "Fin",
          "Cargo bay key",    "Deflector shield", "Fuse",
          "Vela's hatch key", "Juno's hatch key", "Lupus's hatch key",
          "Nitrogen tank",    "Oxygen tank",      "Stabilizer"};
      for (int i = 0; i < 12; i++)
        v.push_back({200 + i, parts[i], 2, i});
      return v;
    }();
    return list;
  }
  bool owned(const Item &i) const {
    return data.known && ((i.group == 0   ? data.weapons[character]
                           : i.group == 1 ? data.items[character]
                                          : data.shared) &
                          (1u << i.bit));
  }
  void refreshInventory() {
    if (follow && data.known && data.current >= 0)
      character = data.current;
    std::string html;
    const char *headings[] = {"WEAPONS", "KEYS &amp; QUEST", "SHIP PARTS"};
    const auto &items = inventoryItems();
    for (int g = 0; g < 3; g++) {
      int count = 0, total = 0;
      for (auto &i : items)
        if (i.group == g) {
          total++;
          if (owned(i))
            count++;
        }
      html +=
          "<div class=\"inventory-group group-" + std::to_string(g) +
          "\"><div class=\"group-heading\"><span>" + headings[g] + "</span>" +
          (g == 2 ? "<span class=\"shared-tag\">SHARED</span>" : "") +
          "<span class=\"count\">" +
          (data.known ? std::to_string(count) : "--") + " / " +
          std::to_string(total) + "</span></div><div class=\"inventory-grid\">";
      for (int n = 0; n < static_cast<int>(items.size()); n++) {
        auto &i = items[n];
        if (i.group != g)
          continue;
        std::string cls = "inventory-tile";
        if (n == selectedItem)
          cls += " selected";
        if (!owned(i))
          cls += " missing";
        std::string content;
        if (data.art)
          content =
              "<img src=\"rom-asset/asset-" + std::to_string(i.id) + ".tga\"/>";
        else
          content =
              "<span class=\"fallback-name\">" + escaped(i.name) + "</span>";
        if (owned(i))
          content += "<span class=\"owned-dot\"/>";
        html += "<button id=\"item-" + std::to_string(n) + "\" class=\"" + cls +
                "\" title=\"" +
                escaped(i.name + (!data.known ? " — unknown"
                                  : owned(i)  ? " — owned"
                                              : " — missing")) +
                "\">" + content + "</button>";
      }
      html += "</div></div>";
    }
    if (html != lastInventory) {
      lastInventory = html;
      auto pane = el("inventory-groups");
      float scroll = pane->GetScrollTop();
      pane->SetInnerRML(html);
      pane->SetScrollTop(scroll);
    }
    const char *names[] = {"Vela", "Juno", "Lupus"};
    for (int i = 0; i < 3; i++) {
      auto e = el(("character-" + std::to_string(i)).c_str());
      e->SetClass("selected", i == character);
      std::string content = data.art ? "<img src=\"rom-asset/asset-" +
                                           std::to_string(300 + i) + ".tga\"/>"
                                     : names[i];
      if (e->GetInnerRML() != content)
        e->SetInnerRML(content);
    }
    el("follow-character")->SetClass("selected", follow);
    label("inventory-state", !data.active ? "NO GAME RUNNING"
                             : data.known ? (data.paused ? "PAUSED" : "LIVE")
                                          : "WAITING FOR LIVE DATA");
    el("inventory-state")->SetClass("is-live", data.known);
    label("art-status", data.artStatus);
  }

public:
  void init(HWND w, Rml::ElementDocument *document,
            const std::filesystem::path &folder, const std::string &modeName,
            std::function<void(const std::string &)> callback) {
    window = w;
    doc = document;
    root = folder;
    kind = modeName;
    action = std::move(callback);
    lastSuccess = GetTickCount64();
    for (auto name : {"click", "dblclick", "change", "mouseover"})
      doc->AddEventListener(name, this);
    if (kind == "map") {
      scene = static_cast<MapScene *>(el("map-scene"));
      scene->data = &data;
      scene->pick = [this](unsigned id) { select(id); };
      scene->activate = [this](unsigned id) { warp(id); };
      scene->zoomChanged = [this]() {
        label("zoom-level",
              std::to_string(static_cast<int>(std::round(scene->zoom * 100))) +
                  "%");
        enable("zoom-minus", scene->zoom > .25f);
        enable("zoom-plus", scene->zoom < 16);
      };
      BOOL animations = TRUE;
      SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, &animations, 0);
      scene->reducedMotion = !animations;
      refreshInspector();
    } else
      refreshInventory();
  }
  void tick() {
    animateToast();
    if (scene)
      refreshLabels();
    auto now = GetTickCount64();
    if (now - lastRead < 100)
      return;
    lastRead = now;
    try {
      auto next = Reader(root / "snapshot.bin").read();
      if (next.sequence != data.sequence) {
        bool changed = next.generation != data.generation ||
                       next.level != data.level || next.ready != data.ready;
        bool modsChanged = data.mods != next.mods;
        data = std::move(next);
        modsCommandPending=false;
        if(data.modError && data.modError!=lastModError){lastModError=data.modError;modsError();}
        if (modsChanged && modal && tab == "mods") settings();
        lastSuccess = now;
        if (changed && scene) {
          scene->fit();
          selected = 0;
          scene->selected = 0;
          scene->lastPick = 0;
          scene->lastPickTime = 0;
        }
        if (scene)
          scene->invalidate();
      }
    } catch (const std::exception &) {
    }
    if (now - lastSuccess > 3000) {
      data.active = false;
      if(modsCommandPending && now-modsSentAt>3000 && !modsWriteFailed){modsWriteFailed=true;modsCommandPending=false;modsError();}
      data.ready = false;
      data.known = false;
      data.markers.clear();
      data.triangles.clear();
      data.lines.clear();
      data.status =
          "Live data connection unavailable. Reopen this window to reconnect.";
    }
    if (kind == "inventory") {
      refreshInventory();
      return;
    }
    enable("zoom-minus", data.ready && scene->zoom > .25f);
    enable("zoom-plus", data.ready && scene->zoom < 16);
    enable("zoom-fit", data.ready);
    enable("fit-room", data.ready);
    doc->SetClass("empty-room", !data.ready);
    label("tool-status", data.status);
    
    display("waiting-room", !data.ready, "flex");
    label("connection-state",
          data.active ? "Connected to game" : "No game running");
    el("connection-state")->SetClass("connected-state", data.active);
    label("gameplay-state", data.active ? "Waiting for gameplay"
                                        : "Start a game from the launcher");
    refreshInspector();
    refreshAi();
  }
  bool keyboard(UINT message, WPARAM key) {
    if (message == WM_ACTIVATEAPP && !key) {
      closePopup();
      return true;
    }
    if (message != WM_KEYDOWN && message != WM_SYSKEYDOWN)
      return false;
    if (key == VK_RETURN || key == VK_SPACE) {
      auto focused = doc->GetContext()->GetFocusElement();
      if (focused && focused->GetTagName() == "button" &&
          !focused->HasAttribute("disabled")) {
        focused->Click();
        return true;
      }
    }
    if (key == VK_TAB) {
      auto root = modal            ? el("tool-modal")
                  : !popup.empty() ? el((popup + "-popup").c_str())
                                   : doc;
      Rml::ElementList controls;
      root->QuerySelectorAll(controls, "button, input, select");
      controls.erase(std::remove_if(controls.begin(), controls.end(),
                                    [](auto e) {
                                      return !e->IsVisible(true) ||
                                             e->HasAttribute("disabled");
                                    }),
                     controls.end());
      if (!controls.empty()) {
        auto it = std::find(controls.begin(), controls.end(),
                            doc->GetContext()->GetFocusElement());
        bool back = (GetKeyState(VK_SHIFT) & 0x8000) != 0;
        int i = it == controls.end() ? (back ? 0 : -1)
                                     : static_cast<int>(it - controls.begin());
        i = (i + (back ? -1 : 1) + static_cast<int>(controls.size())) %
            static_cast<int>(controls.size());
        controls[i]->Focus(true);
        controls[i]->ScrollIntoView(false);
      }
      return true;
    }
    if (key == VK_ESCAPE) {
      if (modal)
        showModal(false);
      else if (!popup.empty())
        closePopup();
      else if (kind == "map")
        command("stop");
      return true;
    }
    if (kind != "map")
      return false;
    if (key == '0' && (GetKeyState(VK_CONTROL) & 0x8000)) {
      scene->fit();
      return true;
    }
    if (key == VK_F10 ||
        message == WM_SYSKEYDOWN && (key == 'V' || key == 'S' || key == 'T')) {
      if (!modal) {
        if (key == VK_F10 && !popup.empty())
          closePopup();
        else
          openPopup(key == 'T' ? "tools" : key == 'S' ? "settings" : "view");
      }
      return true;
    }
    if (popup.empty())
      return false;
    if (key == VK_LEFT || key == VK_RIGHT) {
      constexpr const char* menus[] = {"view", "settings", "tools"};
      int index = popup == "view" ? 0 : popup == "settings" ? 1 : 2;
      openPopup(menus[(index + (key == VK_RIGHT ? 1 : 2)) % 3]);
      return true;
    }
    if (key == VK_DOWN || key == VK_UP) {
      Rml::ElementList buttons;
      el((popup + "-popup").c_str())->GetElementsByTagName(buttons, "button");
      buttons.erase(
          std::remove_if(buttons.begin(), buttons.end(),
                         [](auto e) { return e->HasAttribute("disabled"); }),
          buttons.end());
      if (buttons.empty())
        return true;
      auto focus = doc->GetContext()->GetFocusElement();
      auto at = std::find(buttons.begin(), buttons.end(), focus);
      int n = at == buttons.end() ? (key == VK_UP ? 0 : -1)
                                  : static_cast<int>(at - buttons.begin());
      n = (n + (key == VK_DOWN ? 1 : -1) + static_cast<int>(buttons.size())) %
          static_cast<int>(buttons.size());
      buttons[n]->Focus(true);
      return true;
    }
    return false;
  }

  void warp(unsigned id) {
    if (modsWriteFailed || (data.mods & 16) || !(data.mods & 2) || !data.ready) return;
    for (const auto &marker : data.markers)
      if (marker.id == id && marker.kind == "exit") {
        command("warp " + std::to_string(id));
        break;
      }
  }
  void ProcessEvent(Rml::Event &event) override {
    if (building)
      return;
    auto *target = event.GetTargetElement();
    std::string id;
    for (auto *e = target; e; e = e->GetParentNode()) {
      if (e->HasAttribute("disabled"))
        return;
      if (!e->GetId().empty()) {
        id = e->GetId();
        break;
      }
    }
    if (event.GetType() == "dblclick") {
      if (id.rfind("node-", 0) == 0) warp(static_cast<unsigned>(std::stoul(id.substr(5))));
      return;
    }
    if (event.GetType() == "mouseover") {
      if (!popup.empty() && (id == "tool-view" || id == "tool-settings" || id == "tool-tools"))
        openPopup(id.substr(5));
      return;
    }
    if (event.GetType() == "change") {
      auto *control = dynamic_cast<Rml::ElementFormControl *>(target);
      if (!control)
        return;
      auto value = control->GetValue();
      try {
        if (id == "floor-mode") {
          mode = std::clamp(std::stoi(value), 0, 2);
          height = data.height;
          command("mode " + std::to_string(mode));
          command("height " + std::to_string(height));
          settings();
        } else if (id == "height-value") {
          height = std::clamp(std::stof(value), -1000000.f, 1000000.f);
          if (std::isfinite(height))
            command("height " + std::to_string(height));
        } else if (id == "jump-mode") {
          jump = std::stoi(value);
          command("jump " + std::to_string(jump));
        } else if (id == "interaction-filter") {
          filter = std::stoi(value);
          refreshInspector();
        }
      } catch (const std::exception &) {
      }
      return;
    }
    if (event.GetType() != "click")
      return;
    // Text labels and the canvas are not commands even if their IDs share a
    // prefix.
    auto clickable = target;
    while (clickable && clickable->GetTagName() != "button")
      clickable = clickable->GetParentNode();
    if (!clickable) {
      if (!popup.empty())
        closePopup();
      return;
    }
    id = clickable->GetId();
    if (clickable->HasAttribute("disabled"))
      return;
    if (id == "tool-view" || id == "tool-settings" || id == "tool-tools") {
      std::string name = id.substr(5);
      if (popup == name)
        closePopup();
      else
        openPopup(name);
      return;
    }
    if (id == "map-settings") {
      showModal(true);
      return;
    }
    if (id == "settings-close" || id == "settings-done") {
      showModal(false);
      return;
    }
    if (id.rfind("tab-", 0) == 0) {
      tab = id.substr(4);
      settings();
      return;
    }
    if (id == "restore-defaults") {
      mode = 0;
      slice = 64;
      other = collision = true;
      origins = false;
      jump = 0;
      advanced = false;
      for (auto cmd : {"mode 0", "slice 64", "other 1", "collision 1",
                       "origins 0", "jump 0"})
        command(cmd);
      modsWriteFailed=false;command("mods-off");data.mods &= 1U;
      settings();
      return;
    }
    if (id == "toggle-warp-mod" || id == "toggle-health-mod" || id == "toggle-kill-mod") {
      if (modsWriteFailed || (data.mods & 16)) return;
      unsigned bit = id == "toggle-warp-mod" ? 2U : id == "toggle-health-mod" ? 4U : 8U;
      data.mods ^= bit;
      command(id.substr(7) + ((data.mods & bit) ? " 1" : " 0"));
      settings();
      return;
    }
    if (id == "toggle-other" || id == "toggle-collision" ||
        id == "toggle-origins" || id == "toggle-advanced") {
      bool *value = id == "toggle-other"       ? &other
                    : id == "toggle-collision" ? &collision
                    : id == "toggle-origins"   ? &origins
                                               : &advanced;
      *value = !*value;
      if (id != "toggle-advanced")
        command(id.substr(7) + (*value ? " 1" : " 0"));
      settings();
      return;
    }
    if (id == "slice-minus" || id == "slice-plus") {
      slice = std::clamp(slice + (id == "slice-plus" ? 16 : -16), 4, 4096);
      command("slice " + std::to_string(slice));
      label("slice-value", std::to_string(slice));
      return;
    }
    if (id.rfind("ai-", 0) == 0) {
      command(id.substr(3));
      if (id == "ai-explore" || id == "ai-start")
        showModal(false);
      return;
    }
    if (id == "open-exports") {
      command("exports");
      closePopup();
      return;
    }
    if (id == "open-inventory") {
      action("inventory");
      showModal(false);
      return;
    }
    if (id == "fit-room" || id == "zoom-fit") {
      scene->fit();
      closePopup();
      return;
    }
    if (id == "zoom-minus" || id == "zoom-plus") {
      scene->zoomAt(id == "zoom-plus" ? 1.2f : 1 / 1.2f,
                    scene->dimensions() * .5f);
      return;
    }
    if (id == "view-inspector" || id == "hide-inspector" ||
        id == "show-inspector") {
      inspector = !inspector;
      doc->SetClass("hide-inspector", !inspector);
      closePopup();
      return;
    }
    if (id == "view-labels") {
      allLabels = !allLabels;
      auto item = el("view-labels");
      item->SetClass("checked", allLabels);
      item->SetAttribute("aria-checked", allLabels ? "true" : "false");
      closePopup();
      refreshLabels();
      return;
    }
    if (id == "view-legend") {
      legend = !legend;
      display("map-legend", legend);
      closePopup();
      return;
    }
    if (id == "center-selected") {
      for (auto &m : data.markers)
        if (m.id == selected) {
          scene->center({m.x, m.z});
          break;
        }
      return;
    }
    if (id.rfind("node-", 0) == 0) {
      select(static_cast<unsigned>(std::stoul(id.substr(5))));
      return;
    }
    if (id.rfind("character-", 0) == 0) {
      character = std::stoi(id.substr(10));
      follow = false;
      refreshInventory();
      return;
    }
    if (id == "follow-character") {
      follow = !follow;
      refreshInventory();
      return;
    }
    if (id.rfind("item-", 0) == 0) {
      selectedItem = std::stoi(id.substr(5));
      refreshInventory();
      return;
    }
    if (!popup.empty())
      closePopup();
  }
};
} // namespace jfg_live
