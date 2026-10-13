#include "jfg/renderer/interpolation_history.hpp"
#include <cstdlib>
#include <limits>
static void require(bool value) { if (!value) std::abort(); }
int main() {
    require(jfg::parse_render_fps("") == 0U);
    require(jfg::parse_render_fps("60") == 60U);
    require(jfg::parse_render_fps("360") == 360U);
    require(jfg::parse_render_fps("1000") == 1000U);
    for (auto text : {"59", "1001", "-60", "60hz", " 60", "999999999999"})
        require(!jfg::parse_render_fps(text));
    jfg::PresentationMesh a;
    a.key = {1,2,3}; a.positions = {{{0,0,0}}, {{0.1f,0,0}}, {{0,0.1f,0}}};
    a.matrix = {1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
    jfg::PresentationHistory history;
    require(!history.record(std::vector<jfg::PresentationMesh>{a},100,true).transforms[0].matched);
    auto b=a; b.matrix[12]=0.1f;
    const auto second=history.record(std::vector<jfg::PresentationMesh>{b},102,true);
    require(second.source_rate==30 && second.transforms[0].matched);
    require(second.transforms[0].previous==a.matrix);
    history.record({},103,false);
    b.matrix[12]=0.2f;
    require(history.record(std::vector<jfg::PresentationMesh>{b},104,true).transforms[0].matched);
    auto cut=b; cut.matrix[12]=1;
    require(!history.record(std::vector<jfg::PresentationMesh>{cut},106,true).transforms[0].matched);
    std::vector<jfg::PresentationMesh> duplicates{cut,cut};
    const auto duplicate=history.record(duplicates,108,true);
    require(!duplicate.transforms[0].matched && !duplicate.transforms[1].matched);
    require(!history.record(std::vector<jfg::PresentationMesh>{cut},110,true).transforms[0].matched);
    require(history.record(std::vector<jfg::PresentationMesh>{cut},112,true).transforms[0].matched);
    require(!history.record(std::vector<jfg::PresentationMesh>{cut},200,true).transforms[0].matched);
    cut.key.push_back(9);
    require(!history.record(std::vector<jfg::PresentationMesh>{cut},202,true).transforms[0].matched);
    auto invalid=cut; invalid.matrix[0]=std::numeric_limits<float>::quiet_NaN();
    require(!history.record(std::vector<jfg::PresentationMesh>{invalid},204,true).transforms[0].matched);
    // Two touching batches share one transform. A changed/cull-split batch
    // must follow the same motion as its exact-geometry anchor.
    auto left=a; auto right=a; right.key={4,5,6};
    jfg::PresentationHistory coherent;
    coherent.record({left,right},100,true);
    left.matrix[12]=right.matrix[12]=0.1f;
    right.key.push_back(7); // Topology changed; the transform did not split.
    auto together=coherent.record({left,right},102,true);
    require(together.transforms[0].matched && together.transforms[1].matched);
    require(together.transforms[0].previous==together.transforms[1].previous);
    const auto midpoint=[&](size_t i) {
        return 0.5f*together.transforms[i].previous[12]+0.05f;
    };
    require(midpoint(0)==midpoint(1));

    // Unsafe mixed-transform geometry holds the entire shared transform.
    jfg::PresentationHistory blocked;
    blocked.record({a,a},100,true);
    auto distinct=a; distinct.key={4,5,6};
    blocked.record({a,distinct},102,true);
    left=a; left.matrix[12]=0.1f;
    distinct.matrix=left.matrix; distinct.eligible=false;
    const auto held=blocked.record({left,distinct},104,true);
    require(!held.transforms[0].matched && !held.transforms[1].matched);

    // Different old transforms converging at the same matrix are ambiguous.
    jfg::PresentationHistory conflict;
    right=a; right.key={4,5,6}; right.matrix[12]=0.2f;
    conflict.record({a,right},100,true);
    right.matrix[12]=left.matrix[12]=0.1f;
    const auto ambiguous=conflict.record({left,right},102,true);
    require(!ambiguous.transforms[0].matched && !ambiguous.transforms[1].matched);
    // A changing 30/20 Hz cadence is valid motion. Shadow submissions do
    // not consume the scene's previous timestamp; cuts still reject it.
    jfg::PresentationHistory variable;
    auto moving=a;
    variable.record({moving},100,true);
    moving.matrix[12]=0.05f;
    require(variable.record({moving},102,true).source_rate==30);
    variable.record({},103,false);
    moving.matrix[12]=0.10f;
    const auto slower=variable.record({moving},105,true);
    require(slower.source_rate==20 && slower.transforms[0].matched);
    require(slower.transforms[0].previous[12]==0.05f);
    moving.matrix[12]=0.15f;
    const auto faster=variable.record({moving},107,true);
    require(faster.source_rate==30 && faster.transforms[0].matched);
    require(faster.transforms[0].previous[12]==0.10f);
    moving.matrix[12]=1.0f;
    require(!variable.record({moving},110,true).transforms[0].matched);
    require(!variable.record({moving},114,true).transforms[0].matched);
    require(variable.record({moving},118,true).source_rate==15);
    // A living sprite can change dimensions without becoming another object.
    // Its anchor still interpolates; free/reuse and topology changes hold.
    auto sprite = a;
    sprite.positions = {{{0,0,0}}};
    sprite.key = {0,0,0,0xFFFFFFFFU,1,0,0,0};
    sprite.matrix[12] = 0;
    auto resized = sprite;
    resized.positions[0][0] = 0.05f;
    resized.key[0] = 123;
    resized.matrix[12] = 0.1f;
    jfg::bind_presentation_billboard(sprite,{71,72,73,74});
    jfg::bind_presentation_billboard(resized,{71,72,73,74});
    jfg::PresentationHistory sprite_history;
    sprite_history.record({sprite},100,true);
    require(sprite_history.record({resized},102,true).transforms[0].matched);
    auto reused_sprite = a;
    reused_sprite.positions = {{{0,0,0}}};
    reused_sprite.key = {0,0,0,0xFFFFFFFFU,1,0,0,0};
    jfg::bind_presentation_billboard(reused_sprite,{75,72,73,74});
    require(!sprite_history.record({reused_sprite},104,true).transforms[0].matched);
    auto topology = resized;
    topology.key.push_back(1);
    jfg::PresentationHistory topology_history;
    topology_history.record({resized},100,true);
    require(!topology_history.record({topology},102,true).transforms[0].matched);
    auto unknown = a;
    const auto original_key = unknown.key;
    jfg::bind_presentation_billboard(unknown,{0,72,73,74});
    require(unknown.key == original_key);
    return 0;
}
