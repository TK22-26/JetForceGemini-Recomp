# Enhanced shadows: bridge environmental shading

Status: native rendering classified; documented scope limitation. No bridge
lighting replacement requested, implemented or released.

## Report and evidence

The owner approved the improved actor shadows, then asked whether the long
wooden bridge's own apparent ground shadow was baked into the environment.
The investigation used the preserved bridge-end capture and original native
shadow dispatcher. A later chief clipping report was prioritized and fixed as
a separate candidate before completing this classification.

The longwoodbridge actor is behavior55, at (-2,1,583), with its collision/model
footprint approximately X=-73..70 and Z=583..1144. Its shadow-control pointer
(actor+0x50) is null in the bridge capture. The native shadow dispatcher reads
this pointer at US 0x8001DB68; this actor does not supply a projected shadow for
Enhanced to replace.

The level's ground beneath it already contains a dark central strip. Block0,
batch93, faces817..826 cover X=-103..102, Y=-102..-93 and Z=618..1104.
Their vertex RGBA values are (33,64,70,255) and (0,27,54,255). They use texture
slot46, the SAME texture used by adjacent brighter ground, whose vertices
include (255,255,255,255). A private top-down plot using only the native vertex
colours, with no texture sampling, reproduces the dark strip under the bridge.
This distinguishes pre-existing mesh vertex shading from a special shadow
bitmap or a newly generated dynamic actor shadow. We did not trace the
original authoring/export tool that produced those colours.

The evidence and plots remain private under
D:/JFG-private/enhanced-shadow-bridge-20261026/bridge-shadow-material.
No ROM, game mesh or extracted texture is included in this repository.
The initial plotting attempt found matplotlib unavailable; the inspection
plot was produced with the already installed Pillow library.

## Consequences and compatibility

Enhanced replaces native projected actor shadows. A character's shadow can
receive on this bridge using the new renderer. The bridge's existing dark
ground strip remains part of the level material and does not regenerate with
the bridge's motion or the Enhanced quality setting.

A future dynamic environment-shadow implementation would need environmental
casters/receivers and a deliberate treatment of the existing vertex darkening;
simply adding another bridge shadow would shade the same area twice. Blanket
brightening would also erase unrelated level shading. This is a separate
feature, not a reason to remove the original level colours during the chief fix.

Related: [actor shadow investigation](github-character-shadow-jitter.md),
[deforming bridge presentation](tutorial-late-object-jitter.md),
[receiver sizing](../../../include/jfg/renderer/enhanced_shadow_footprint.hpp).
