#pragma once
#include <RmlUi/Core.h>
#include <algorithm>
#include <cmath>
#include <deque>
#include <string>

// Every card owns its birth time and DOM node. Stack movement never restarts
// entry/exit animation, and incoming messages never wait for older ones.
class NotificationStack {
  struct Card {
    Rml::Element* element;
    std::string message;
    double born;
    float bottom=0;
  };
  std::deque<Card> cards;
  double lastTick=-1;
  static constexpr double lifetime=4.62;
  static constexpr std::size_t capacity=8;
  static std::string escaped(const std::string& text) {
    std::string result;
    for(char c:text) {
      if(c=='&')result+="&amp;";
      else if(c=='<')result+="&lt;";
      else if(c=='>')result+="&gt;";
      else if(c=='\"')result+="&quot;";
      else result+=c;
    }
    return result;
  }
  void removeOldest() {
    auto* element=cards.front().element;
    element->GetParentNode()->RemoveChild(element);
    cards.pop_front();
  }
public:
  void show(Rml::ElementDocument& document,const std::string& message,double now) {
    auto* stack=document.GetElementById("toast");if(!stack || message.empty())return;
    // Consecutive duplicates do not extend the existing notification's life.
    if(!cards.empty() && cards.back().message==message && now<cards.back().born+lifetime)return;
    while(!cards.empty() && (now>=cards.front().born+lifetime || cards.size()>=capacity))removeOldest();
    auto element=document.CreateElement("div");element->SetClass("toast-item",true);
    element->SetInnerRML("<span class=\"notice-dot\"/><span class=\"toast-message\">"+escaped(message)+"</span>");
    element->SetProperty("opacity","0");
    auto* card=stack->AppendChild(std::move(element));cards.push_back({card,message,now,0});
    if(lastTick<0)lastTick=now;
  }
  void tick(double now,bool reducedMotion) {
    while(!cards.empty() && now>=cards.front().born+lifetime)removeOldest();
    const double dt=lastTick<0?0:std::clamp(now-lastTick,0.0,0.25);lastTick=now;
    float bottom=0;
    for(auto it=cards.rbegin();it!=cards.rend();++it) {
      auto& card=*it;auto* context=card.element->GetContext();if(!context)continue;
      const float dpi=context->GetDensityIndependentPixelRatio();
      const float height=std::max(42.f,card.element->GetBox().GetSize(Rml::BoxArea::Border).y/dpi);
      const float blend=reducedMotion?1.f:static_cast<float>(1-std::exp(-dt/.10));
      card.bottom+=(bottom-card.bottom)*blend;bottom+=height+8.f;
      const double age=std::max(0.0,now-card.born);
      double entrance=0,opacity=1;
      if(age<.4) {
        const double t=std::clamp(age/.4,0.0,1.0),q=t-1;
        entrance=96*(1-(1+2.70158*q*q*q+1.70158*q*q));opacity=t;
      } else if(age>4.4) {
        const double t=std::clamp((age-4.4)/.22,0.0,1.0);
        entrance=-12*t;opacity=1-t;
      }
      card.element->SetProperty("transform","translate(0dp, "+std::to_string(-card.bottom+(reducedMotion?0:entrance))+"dp)");
      card.element->SetProperty("opacity",std::to_string(opacity));
    }
  }
};
