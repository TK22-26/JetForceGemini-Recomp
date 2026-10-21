#include "jfg/runtime/cutscene_skip.hpp"
#include "jfg/runtime/cutscene_skip_button.hpp"
#include "jfg/runtime/cutscene_script.hpp"
#include "jfg/runtime/cutscene_completion.hpp"
#include <cstdlib>
#include <iostream>
#include <limits>
#define CHECK(x) do { if(!(x)){std::cerr<<"line "<<__LINE__<<": "<<#x<<'\n';return 1;} ++checks;}while(false)
int main() {
 unsigned checks=0;
 for(unsigned hz: {20U,30U,60U,120U,360U}) {
   jfg::CutsceneSkipHold s;
   CHECK(!s.sample(1,true,false,true,0));
   CHECK(!s.sample(1,true,true,true,100));
   CHECK(s.visible());
   for(unsigned n=1;n<hz;++n) CHECK(!s.sample(1,true,true,true,100+1000*n/hz));
   CHECK(s.progress(1099)<1.0f);
   CHECK(s.sample(1,true,true,true,1100));
   CHECK(!s.sample(1,true,true,true,2100));
   CHECK(!s.sample(2,true,true,true,2200));
   CHECK(!s.visible());
   CHECK(!s.sample(2,true,true,true,4000));
   CHECK(!s.sample(2,true,false,true,4001));
   CHECK(!s.sample(2,true,true,true,4100));
   CHECK(s.sample(2,true,true,true,5100));
 }
 {
   jfg::CutsceneSkipHold s;
   CHECK(!s.sample(1,true,false,true,0));
   CHECK(!s.sample(1,true,true,true,1));
   CHECK(!s.sample(1,true,false,true,400));
   CHECK(s.progress(400)==0);
   CHECK(!s.sample(1,true,true,true,700));
   CHECK(!s.sample(1,true,true,true,1699));
   CHECK(s.sample(1,true,true,true,1700));
 }
 {
   jfg::CutsceneSkipHold s;
   CHECK(!s.sample(1,true,false,true,0));
   CHECK(!s.sample(1,true,true,true,1));
   CHECK(!s.sample(1,true,false,true,20));
   CHECK(!s.sample(1,true,false,true,2499));CHECK(s.visible());
   CHECK(!s.sample(1,true,false,true,2501));CHECK(!s.visible());
   CHECK(!s.sample(1,true,true,true,3000));
   CHECK(!s.sample(1,true,true,false,3300));CHECK(!s.visible());
   CHECK(!s.sample(1,true,true,true,6000));
   CHECK(!s.sample(1,true,false,true,6001));
   CHECK(!s.sample(1,true,true,true,6100));
   CHECK(s.sample(1,true,true,true,7100));
 }
 for(bool eligible: {false,true}) {
   jfg::CutsceneSkipHold s;
   CHECK(!s.sample(0,eligible,false,true,0));
   CHECK(!s.sample(0,eligible,true,true,1));
   CHECK(!s.sample(0,eligible,true,true,10000));CHECK(!s.visible());
 }
 {
   jfg::CutsceneSkipHold s;
   CHECK(!s.sample(1,false,false,true,0));
   CHECK(!s.sample(1,false,true,true,1));
   CHECK(!s.sample(1,false,true,true,10000));CHECK(!s.visible());
 }
 for(auto dims: {std::pair{320U,240U}, {320U,180U}, {424U,240U}, {640U,480U}}) {
   std::size_t previous=0;
   for(float progress: {0.0f,0.25f,0.5f,0.75f,1.0f}) {
     const auto g=jfg::cutscene_skip_gbi(dims.first,dims.second,progress);
     CHECK(!g.empty());CHECK(g.size()<360);CHECK(g.size()>=previous);previous=g.size();
     CHECK(g.front().w0==0xE7000000U);CHECK(g.back().w0==0xE7000000U);
     bool blue=false,white=false;
     for(auto c:g) {
       switch(c.w0>>24) {
        case 0xE7: case 0xED: case 0xBA: case 0xB9:break;
        case 0xF7:
         CHECK((c.w1>>16)==(c.w1&65535));CHECK(c.w1&1);
         blue|=(c.w1&65535)==0x2AF9;white|=(c.w1&65535)==65535;break;
        case 0xF6:{
         const auto x1=(c.w0>>12)&4095,y1=c.w0&4095;
         const auto x0=(c.w1>>12)&4095,y0=c.w1&4095;
         CHECK(x0<=x1&&y0<=y1);CHECK(x1<dims.first*4&&y1<dims.second*4);
         CHECK(((x0|y0|x1|y1)&3)==0); // Never rely on fractional fill spans.
         break;}
        default:CHECK(false);
       }
     }
     CHECK(blue&&white);
   }
 }
 CHECK(jfg::cutscene_skip_gbi(0,240,0).empty());
 CHECK(jfg::cutscene_skip_gbi(320,0,0).empty());
 CHECK(jfg::cutscene_skip_gbi(320,240,std::numeric_limits<float>::quiet_NaN()).empty());


 // B and Start reveal the prompt but never contribute to confirmation.
 for(unsigned other_button: {0x4000U,0x1000U}) {
   jfg::CutsceneSkipHold s;
   CHECK(!s.sample(1,true,false,true,0));
   CHECK(!s.sample(1,true,false,true,100,other_button!=0));CHECK(s.visible());
   CHECK(!s.sample(1,true,false,true,5100,true));CHECK(s.progress(5100)==0);
   CHECK(!s.sample(1,true,false,true,5101,false));
   CHECK(!s.sample(1,true,true,true,5200,false));
   CHECK(!s.sample(1,true,true,true,6199,true));CHECK(s.progress(6199)<1);
   CHECK(s.sample(1,true,true,true,6200,true));
 }

 using Status=jfg::CutsceneScriptStatus;
 const auto inspect=[](std::initializer_list<std::uint8_t> b){return jfg::inspect_cutscene_script({b.begin(),b.size()});};
 {
   const auto plan=inspect({0,0,0x78,1,0,90, 0,10,0x7A,3,0x10,35, 0,10,0x76,0, 0,0,0x7F,0});
   CHECK(plan.status==Status::finite);CHECK(plan.commands.size()==4);
   CHECK(plan.changes_level&&plan.writes_game_flags&&!plan.conditional_end);
   CHECK(plan.commands[0].payload[0]==90);CHECK(plan.commands[1].payload[0]==0x1023);
   CHECK(plan.commands[1].word==0x7A03);CHECK(plan.commands[2].offset==12);
 }
 CHECK(inspect({0,0,0x77,0,0,0,0x7F,0}).conditional_end);
 CHECK(inspect({0,0,0x7E,0}).status==Status::loop);
 CHECK(inspect({0,0,0x7B,0}).status==Status::pause_gate);
 CHECK(inspect({0,0,0x70,0}).status==Status::unsupported_command);
 CHECK(inspect({0,0,0x7A,0,0}).status==Status::truncated);
 {
   const auto s=inspect({0,1,0x00,0,0,0,0x00,0,0,0,0x7f,0});
   CHECK(s.status==Status::finite&&s.has_out_of_order_times);
   CHECK(s.commands[0].time==1&&s.commands[1].time==0);
   CHECK(inspect({0,1,0x00,0,0,0,0x00,0}).status==Status::truncated);
 }
 CHECK(inspect({0,0,0x7F,1}).status==Status::unsupported_command);
 CHECK(inspect({0,0,0x00}).status==Status::truncated);
 std::vector<std::uint8_t> endless(4*2049);
 CHECK(jfg::inspect_cutscene_script(endless).status==Status::command_limit);


 {
   auto script=inspect({0,0,0x78,1,0,90, 0,10,0x7A,3,0x10,35, 0,10,0x76,0, 0,0,0x7F,0});
   auto p=jfg::plan_cutscene_completion(script,0);
   CHECK(p&&p->actions.size()==2&&p->destination==35&&p->group==3&&p->sentinel_offset==16);
   CHECK(p->actions[0].kind==jfg::CutsceneCompletionActionKind::game_flag);
   CHECK(p->actions[0].argument==90&&p->actions[0].value==1);
   p=jfg::plan_cutscene_completion(script,6);CHECK(p&&p->actions.size()==1);
   CHECK(!jfg::plan_cutscene_completion(script,1));
   CHECK(!jfg::plan_cutscene_completion(script,12)); // Already departed.
   CHECK(!jfg::plan_cutscene_completion(script,16));
 }
 CHECK(!jfg::plan_cutscene_completion(inspect({0,0,0x00,0,0,0,0x7F,0}),0));
 // Rewinding a cinematic path is visual, including the ship's group 2.
 CHECK(jfg::plan_cutscene_completion(inspect({0,0,0x02,0,0,1,0x77,0,0,0,0x7F,0}),0));
 // Do not schedule the unplayed MIDI cue at departure.
 CHECK(jfg::plan_cutscene_completion(inspect({0,0,0x76,0,0,1,0x77,0,0,0,0x7F,0}),0)->actions.size()==1);
 // Music start already executed at time zero must not block later skipping.
 CHECK(jfg::plan_cutscene_completion(inspect({0,0,0x21,0x42,0,1,0x77,0,0,0,0x7F,0}),4));
 {
   auto p=jfg::plan_cutscene_completion(inspect({0,0,0x21,0x42,0,1,0x77,0,0,0,0x7F,0}),0);
   CHECK(p&&p->actions.size()==2);
   CHECK(p->actions[0].kind==jfg::CutsceneCompletionActionKind::music_track);
   CHECK(p->actions[0].argument==0x42);
 }
 // Tawfret's screen fade and local fog envelope are presentation effects.
 // Its tune selection and ordinary destination remain explicit completion.
 {
   const auto script=inspect({0,0,0x43,0,0,2, 0,1,0x45,0,0,0,7,8,3,187,3,255,
       0,2,0x21,46, 0,3,0x7a,0,0,158, 0,3,0x7f,0});
   auto p=jfg::plan_cutscene_completion(script,0);
   CHECK(p&&p->actions.size()==2&&p->destination==158);
   CHECK(p->actions[0].kind==jfg::CutsceneCompletionActionKind::music_track);
   CHECK(p->actions[0].argument==46);
   CHECK(jfg::plan_cutscene_completion(script,22)->actions.size()==1);
   CHECK(jfg::cutscene_actor_control_reviewed(19));
 }
 {
   auto p=jfg::plan_cutscene_completion(inspect({0,0,0x22,0,0,200,0,1,0x7A,0,0,92,0,0,0x7F,0}),0);
   CHECK(p&&p->actions.size()==2);
   CHECK(p->actions[0].kind==jfg::CutsceneCompletionActionKind::music_fade);
   CHECK(p->actions[0].argument==0&&p->destination==92);
 }
 CHECK(!jfg::plan_cutscene_completion(inspect({0,0,0x77,0,0,1,0x78,1,0,90,0,0,0x7F,0}),0));
 CHECK(!jfg::plan_cutscene_completion(inspect({0,0,0x77,0,0,0,0x77,0,0,0,0x7F,0}),0));
 CHECK(jfg::plan_cutscene_completion(inspect({0,0,0x77,0,0,0,0x7F,0}),0)->conditional);
 for(unsigned next=0;next<16;++next) for(unsigned selector=0;selector<16;++selector) {
   const auto d=jfg::cutscene_destination(0x2023,(selector<<4)|3,next,2,77,5);
   CHECK(d.level==35&&d.entrance==2&&d.mode==5&&d.group==3);
   const auto expected=selector==0?next:((next&3)==3&&((selector-1)&3)!=3?2:selector-1);
   CHECK(d.character==expected);
 }
 CHECK(jfg::cutscene_destination(0xFFF,0,0,0,102,5).level==102);
 CHECK(jfg::cutscene_destination(360,0,0,0,0,5).mode==23);

 { // Music volume is a persistent completion effect, not a visual opcode.
   const std::array<std::uint8_t,14> raw{0,0,0x23,45,0,10,0x7a,0,0,166,0,10,0x7f,0};
   const auto script=jfg::inspect_cutscene_script(raw);
   const auto plan=jfg::plan_cutscene_completion(script,0);
   CHECK(plan&&plan->destination==166&&plan->actions.size()==2);
   CHECK(plan->actions[0].kind==jfg::CutsceneCompletionActionKind::music_volume);
   CHECK(plan->actions[0].argument==45);
   CHECK(jfg::cutscene_actor_control_reviewed(30));
   CHECK(jfg::cutscene_actor_control_reviewed(45));
   CHECK(jfg::cutscene_actor_control_reviewed(54));
   CHECK(jfg::cutscene_actor_control_reviewed(57));
   CHECK(jfg::cutscene_actor_control_reviewed(65));
 }

 CHECK((jfg::cutscene_skip_button_rgba16[0]&1U)==0);
 CHECK((jfg::cutscene_skip_button_rgba16[16*32+16]&1U)==1);
 CHECK(!jfg::cutscene_skip_gbi(320,240,0.92f,true).empty());
 {
   // Landing/takeoff ambient state must survive a skip in native order.
   const auto script=inspect({0,0,0x24,0x1b, 0,0,0x26,0x50,
       0,10,0x7a,0,0,88, 0,10,0x7f,0});
   auto p=jfg::plan_cutscene_completion(script,0);
   CHECK(p&&p->actions.size()==3&&p->destination==88);
   CHECK(p->actions[0].kind==jfg::CutsceneCompletionActionKind::ambient_track);
   CHECK(p->actions[0].argument==27);
   CHECK(p->actions[1].kind==jfg::CutsceneCompletionActionKind::ambient_volume);
   CHECK(p->actions[1].argument==80);
   CHECK(jfg::plan_cutscene_completion(script,8)->actions.size()==1);
   // Unreviewed ambient fades and ambient effects after departure stay closed.
   CHECK(!jfg::plan_cutscene_completion(inspect({0,0,0x25,0,0,60,
       0,10,0x7a,0,0,88,0,10,0x7f,0}),0));
   CHECK(!jfg::plan_cutscene_completion(inspect({0,0,0x7a,0,0,88,
       0,1,0x24,27,0,1,0x7f,0}),0));
 }
 {
   // Cave-exit scripts issue two departures in one native interpreter update.
   const auto script=inspect({5,120,0x7a,0,1,27, 5,120,0x7a,2,1,98, 0,0,0x7f,0});
   const auto p=jfg::plan_cutscene_completion(script,0);
   CHECK(p&&p->destination==354&&p->group==2&&p->actions.size()==2);
   CHECK(p->actions[0].kind==jfg::CutsceneCompletionActionKind::change_level);
   CHECK(p->actions[0].argument==283&&p->actions[1].argument==354);
   CHECK(p->actions[1].value==2);
   CHECK(!jfg::plan_cutscene_completion(script,6)); // First departure already ran.
   CHECK(!jfg::plan_cutscene_completion(inspect({0,1,0x7a,0,0,1,
       0,2,0x7a,0,0,2,0,0,0x7f,0}),0));
   CHECK(!jfg::plan_cutscene_completion(inspect({0,1,0x77,0,
       0,1,0x7a,0,0,2,0,0,0x7f,0}),0));
   CHECK(!jfg::plan_cutscene_completion(inspect({0,1,0x7a,0,0,1,
       0,1,0x77,0,0,0,0x7f,0}),0));
 }
 {
   // Material RGBA interpolation changes presentation, not progression.
   const auto p=jfg::plan_cutscene_completion(inspect({0,0,0x6b,1,
       0,255,128,255,0,0,0,60, 0,60,0x7a,0,0,93,0,0,0x7f,0}),0);
   CHECK(p&&p->destination==93&&p->actions.size()==1);
   CHECK(!jfg::plan_cutscene_completion(inspect({0,0,0x61,0,0,1,
       0,60,0x7a,0,0,93,0,0,0x7f,0}),0));
 }
 {
   // Native stream order, not sorted timestamp order, determines side effects.
   const auto s=inspect({0,10,0x00,0, 0,5,0x78,1,0,89,
       0,6,0x7a,0,0,93, 0,0,0x7f,0});
   const auto p=jfg::plan_cutscene_completion(s,0);
   CHECK(s.has_out_of_order_times&&p&&p->actions.size()==2&&p->destination==93);
   CHECK(p->actions[0].kind==jfg::CutsceneCompletionActionKind::game_flag);
   CHECK(p->actions[0].argument==89);
   CHECK(jfg::plan_cutscene_completion(s,10)->actions.size()==1);
   // A late visual wait also delays an earlier-stamped flag after departure.
   CHECK(!jfg::plan_cutscene_completion(inspect({0,5,0x7a,0,0,93,
       0,10,0x00,0, 0,1,0x78,1,0,89, 0,0,0x7f,0}),0));
   // Two departure commands already due in the same update retain their order.
   const auto q=jfg::plan_cutscene_completion(inspect({0,10,0x00,0,
       0,5,0x7a,0,0,93, 0,6,0x7a,0,0,94, 0,0,0x7f,0}),0);
   CHECK(q&&q->destination==94&&q->actions.size()==2);
 }
 {
   // A reviewed scene completion keeps its generator flag after requesting
   // the native destination. An identical unqualified tail stays rejected.
   const auto s=inspect({9,187,0x7a,0,0x11,0x0b,
       9,196,0x78,1,0,89, 0,0,0x7f,0});
   CHECK(!jfg::plan_cutscene_completion(s,0));
   const auto p=jfg::plan_cutscene_completion(s,0,{357,1});
   CHECK(p&&p->destination==267&&p->actions.size()==2);
   CHECK(p->actions[0].kind==jfg::CutsceneCompletionActionKind::change_level);
   CHECK(p->actions[0].argument==0x110b);
   CHECK(p->actions[1].kind==jfg::CutsceneCompletionActionKind::game_flag);
   CHECK(p->actions[1].argument==89&&p->actions[1].value==1);
   CHECK(!jfg::plan_cutscene_completion(s,0,{357,0}));
   CHECK(!jfg::plan_cutscene_completion(s,0,{356,1}));
   CHECK(!jfg::plan_cutscene_completion(s,6,{357,1}));
   for(unsigned field:{0U,1U,2U,3U}) {
     auto different=s;
     if(field==0)different.commands[0].payload[0]=0x110c;
     if(field==1)different.commands[1].payload[0]=90;
     if(field==2)different.commands[1].time=2501;
     if(field==3)different.commands[1].word=0x7800;
     CHECK(!jfg::plan_cutscene_completion(different,0,{357,1}));
   }
 }
 {
   // Model animation control is local presentation. Keep the following
   // departure and progression flag in their native stream order.
   const auto s=inspect({0,0,0x6f,1, 0,1,0,60,
       0,10,0x7a,0,1,76, 0,10,0x78,1,0,99, 0,0,0x7f,0});
   const auto p=jfg::plan_cutscene_completion(s,0);
   CHECK(p&&p->destination==332&&p->actions.size()==2);
   CHECK(p->actions[0].kind==jfg::CutsceneCompletionActionKind::change_level);
   CHECK(p->actions[1].kind==jfg::CutsceneCompletionActionKind::game_flag);
   CHECK(p->actions[1].argument==99&&p->actions[1].value==1);
 }
 {
   // Only credits can complete a presentation-only background loop through
   // its native frontend handler. Other loops and persistent effects reject.
   const auto loop=inspect({0,0,0,1, 0,10,0x65,1, 0,20,0x7e,0});
   const auto p=jfg::plan_cutscene_completion(loop,0,{360,0});
   CHECK(p&&p->native_credits&&p->actions.size()==1);
   CHECK(p->actions[0].kind==jfg::CutsceneCompletionActionKind::credits_end);
   CHECK(jfg::plan_cutscene_completion(loop,4,{360,0}));
   CHECK(!jfg::plan_cutscene_completion(loop,2,{360,0}));
   CHECK(!jfg::plan_cutscene_completion(loop,0,{359,0}));
   CHECK(!jfg::plan_cutscene_completion(loop,0,{360,1}));
   CHECK(!jfg::plan_cutscene_completion(loop,0));
   const auto persistent=inspect({0,0,0x78,1,0,89,0,20,0x7e,0});
   CHECK(!jfg::plan_cutscene_completion(persistent,0,{360,0}));
 }
 {
   const auto s=inspect({7,158,0x7a,0,1,136, 25,100,0x7a,2,1,132, 0,0,0x7f,0});
   auto p=jfg::plan_cutscene_completion(s,0,{388,0});
   CHECK(p&&p->destination==392&&p->group==0&&p->actions.size()==1);
   CHECK(!jfg::plan_cutscene_completion(s,0));
   CHECK(!jfg::plan_cutscene_completion(s,0,{388,1}));
   CHECK(!jfg::plan_cutscene_completion(s,6,{388,0}));
   auto changed=s;changed.commands[1].payload[0]=389;
   CHECK(!jfg::plan_cutscene_completion(changed,0,{388,0}));
   changed=s;changed.commands[1].time=6501;
   CHECK(!jfg::plan_cutscene_completion(changed,0,{388,0}));
 }
 std::cout<<checks<<" checks passed\n";
}
