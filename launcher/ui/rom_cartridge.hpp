#pragma once
#include <RmlUi/Core.h>
#include <RmlUi/Core/RenderManager.h>
// Beveled cartridge silhouette in the launcher's existing native renderer.
class RomCartridge final : public Rml::Element {
  Rml::Geometry geometry;
public:
  explicit RomCartridge(const Rml::String& tag):Rml::Element(tag){}
protected:
  void OnRender() override {
    auto* parent=GetParentNode();auto* context=GetContext();if(!parent || !context)return;
    const float dpi=context->GetDensityIndependentPixelRatio();
    const auto size=GetBox().GetSize(Rml::BoxArea::Content);const float w=size.x,h=size.y;
    const bool selected=parent->IsClassSet("selected"),loaded=parent->IsClassSet("loaded");
    const bool focus=parent->IsPseudoClassSet("focus"),hover=parent->IsPseudoClassSet("hover");
    Rml::Mesh mesh;
    auto polygon=[&](float inset,unsigned rgb) {
      const float c=14*dpi,x=inset,y=inset,r=w-inset,b=h-inset;
      const Rml::Vector2f points[]={{x+c,y},{r-c,y},{r,y+c},{r,b},{x,b},{x,y+c}};
      const auto color=Rml::Colourb((rgb>>16)&255,(rgb>>8)&255,rgb&255,255).ToPremultiplied();
      const int start=static_cast<int>(mesh.vertices.size());
      for(const auto point:points)mesh.vertices.push_back({point,color,{}});
      for(int i=1;i<5;++i)mesh.indices.insert(mesh.indices.end(),{start,start+i,start+i+1});
    };
    polygon(0,focus?0xfff0c0:selected?0xffb23e:loaded?0x2a3550:0x1e2639);
    polygon(2*dpi,hover?(selected?0x2b2418:0x182033):selected?0x1e1a12:loaded?0x121826:0x0e1320);
    geometry=context->GetRenderManager().MakeGeometry(std::move(mesh));geometry.Render(GetAbsoluteOffset(Rml::BoxArea::Content));
  }
};
