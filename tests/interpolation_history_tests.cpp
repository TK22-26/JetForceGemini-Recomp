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
    return 0;
}
