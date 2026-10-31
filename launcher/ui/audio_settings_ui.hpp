#pragma once
#include <jfg/audio/master_volume.hpp>
#include <RmlUi/Core.h>
#include <RmlUi/Core/Elements/ElementFormControlInput.h>
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <string>
namespace jfg_audio {
struct Ui final : Rml::EventListener {
  HWND window=nullptr;
  Rml::ElementDocument* doc=nullptr;
  std::filesystem::path profile;
  jfg::audio::VolumeSettings settings;
  std::string error;
  bool refreshing=false;
  ULONGLONG nextRead=0;
  Rml::Element* el(const char* id) const {return doc->GetElementById(id);}
  void init(HWND w,Rml::ElementDocument* d,const std::filesystem::path& p) {
    window=w;doc=d;profile=p;
    if(const auto saved=jfg::audio::read_volume(profile/"audio.ini"))settings=*saved;
    else if(std::filesystem::exists(profile/"audio.ini")) {
      settings.muted=true;
      error="Saved audio settings could not be read. Adjust a control to replace them.";
    }
    doc->AddEventListener("click",this);doc->AddEventListener("change",this);refresh();
  }
  void refresh() {
    refreshing=true;
    el("audio-value")->SetInnerRML(std::to_string(settings.percent)+"%"+(settings.muted?" (muted)":""));
    static_cast<Rml::ElementFormControlInput*>(el("audio-volume"))->SetValue(std::to_string(settings.percent));
    el("audio-mute")->SetClass("selected",settings.muted);
    el("audio-mute")->SetAttribute("aria-pressed",settings.muted?"true":"false");
    el("audio-error")->SetInnerRML(error);
    el("audio-error")->SetProperty("display",error.empty()?"none":"block");
    refreshing=false;
  }
  bool save(jfg::audio::VolumeSettings next) {
    const auto temp=profile/("audio.ini.window-"+std::to_string(GetCurrentProcessId())+".tmp");
    bool ok=false;
    {
      std::ofstream f(temp,std::ios::binary|std::ios::trunc);
      f<<"version=1\nvolume="<<next.percent<<"\nmuted="<<(next.muted?1:0)<<"\n";
      f.flush();ok=bool(f);
    }
    ok=ok&&MoveFileExW(temp.c_str(),(profile/"audio.ini").c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=0;
    if(ok){settings=next;error.clear();}
    else {std::error_code ec;std::filesystem::remove(temp,ec);error="Cannot save audio settings. Check that your profile folder is writable.";}
    refresh();return ok;
  }
  void toggleMute() {auto next=settings;next.muted=!next.muted;save(next);}
  void volume(int value) {auto next=settings;next.percent=static_cast<unsigned>(std::clamp(value,0,100));save(next);}
  void tick() {
    if(GetTickCount64()<nextRead)return;
    nextRead=GetTickCount64()+250;
    if(const auto saved=jfg::audio::read_volume(profile/"audio.ini"))
      if(saved->percent!=settings.percent||saved->muted!=settings.muted){settings=*saved;refresh();}
  }
  void ProcessEvent(Rml::Event& event) override {
    if(refreshing)return;
    auto* target=event.GetTargetElement();
    while(target&&target->GetId().empty())target=target->GetParentNode();
    if(!target)return;
    const auto id=target->GetId();
    if(event.GetType()=="change"&&id=="audio-volume") {
      const auto value=static_cast<Rml::ElementFormControlInput*>(target)->GetValue();
      char* end=nullptr;const float n=std::strtof(value.c_str(),&end);
      if(end!=value.c_str()&&*end=='\0'&&std::isfinite(n)&&n>=0&&n<=100)volume(static_cast<int>(std::lround(n)));
    } else if(event.GetType()=="click") {
      if(id=="audio-down")volume(static_cast<int>(settings.percent)-5);
      else if(id=="audio-up")volume(static_cast<int>(settings.percent)+5);
      else if(id=="audio-mute")toggleMute();
      else if(id=="audio-done")PostMessageW(window,WM_CLOSE,0,0);
    }
  }
  bool keyboard(UINT message,WPARAM key) {
    if(message!=WM_KEYDOWN)return false;
    if(key==VK_ESCAPE){PostMessageW(window,WM_CLOSE,0,0);return true;}
    if(key=='M'&&(GetKeyState(VK_CONTROL)&0x8000)){toggleMute();return true;}
    auto* focused=doc->GetContext()->GetFocusElement();
    if(key==VK_TAB) {
      Rml::ElementList controls;doc->QuerySelectorAll(controls,"button, input");
      controls.erase(std::remove_if(controls.begin(),controls.end(),[](auto* e){return !e->IsVisible(true)||e->HasAttribute("disabled");}),controls.end());
      if(!controls.empty()) {
        const bool back=(GetKeyState(VK_SHIFT)&0x8000)!=0;
        const auto it=std::find(controls.begin(),controls.end(),focused);
        int n=it==controls.end()?(back?0:-1):int(it-controls.begin());
        n=(n+(back?-1:1)+int(controls.size()))%int(controls.size());controls[n]->Focus(true);controls[n]->ScrollIntoView(false);
      }return true;
    }
    if(focused&&focused->GetId()=="audio-volume") {
      if(key==VK_LEFT||key==VK_DOWN){volume(static_cast<int>(settings.percent)-1);return true;}
      if(key==VK_RIGHT||key==VK_UP){volume(static_cast<int>(settings.percent)+1);return true;}
      if(key==VK_HOME||key==VK_END){volume(key==VK_HOME?0:100);return true;}
    }
    if((key==VK_RETURN||key==VK_SPACE)&&focused&&focused->GetTagName()=="button"){focused->Click();return true;}
    return false;
  }
};
}
