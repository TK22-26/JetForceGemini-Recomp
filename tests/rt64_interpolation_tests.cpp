#define SDL_MAIN_HANDLED
#include "rt64_interpolation_adapter.hpp"
#include <cstdlib>
#include <cmath>
static void require(bool value) { if (!value) std::abort(); }
int main() {
    RT64::Workload workload;
    const hlslpp::float4x4 endpoint(1,0,0,0,0,1,0,0,0,0,1,0,2,0,0,1);
    workload.drawData.worldTransforms.push_back(endpoint);
    require(!jfg::apply_presentation_interpolation(workload, 0, 1));
    auto frame=std::make_shared<jfg::PresentationHistoryFrame>();
    frame->scene=true;
    frame->transforms.push_back({{1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1},true});
    jfg::publish_presentation_snapshot(&workload,frame);
    require(jfg::apply_presentation_interpolation(workload,0,0.25f));
    float row[4];
    for (unsigned c=0;c<4;++c) row[c]=workload.drawData.lerpWorldTransforms[0].m[3][c];
    require(std::abs(row[0]-0.5f)<0.00001f && row[3]==1.0f);
    for (unsigned c=0;c<4;++c) row[c]=workload.drawData.worldTransforms[0].m[3][c];
    require(row[0]==2.0f); // Authored endpoint is untouched.
    require(jfg::apply_presentation_interpolation(workload,0.5f,1));
    for (unsigned c=0;c<4;++c) row[c]=workload.drawData.lerpWorldTransforms[0].m[3][c];
    require(row[0]==2.0f);
    for (unsigned c=0;c<4;++c) row[c]=workload.drawData.prevWorldTransforms[0].m[3][c];
    require(row[0]==1.0f);
    const auto retained=jfg::presentation_snapshot(&workload);
    jfg::publish_presentation_snapshot(&workload,nullptr);
    require(!jfg::presentation_snapshot(&workload));
    require(retained->transforms[0].matched); // An in-flight reader owns its data.
    frame=std::make_shared<jfg::PresentationHistoryFrame>();
    frame->transforms.push_back({});
    jfg::publish_presentation_snapshot(&workload,frame);
    require(jfg::apply_presentation_interpolation(workload,0,0.5f));
    for (unsigned c=0;c<4;++c) row[c]=workload.drawData.lerpWorldTransforms[0].m[3][c];
    require(row[0]==2.0f); // Unmatched geometry uses the current endpoint.
    jfg::publish_presentation_snapshot(&workload,nullptr);
    return 0;
}
