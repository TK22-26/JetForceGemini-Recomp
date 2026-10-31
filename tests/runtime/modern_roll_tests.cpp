#include "jfg/runtime/modern_controls.hpp"
#include <array>
#include <cstdlib>
#include <iostream>
#include <limits>

namespace {
int checks=0;
void check(bool condition,const char *message) {
    ++checks;
    if(!condition){std::cerr<<message<<'\n';std::exit(1);}
}
constexpr auto index(jfg::ModernAction action){return static_cast<std::size_t>(action);}
}
int main() {
    using namespace jfg;
    for(unsigned character=0;character<4;++character) {
        check(modern_roll_stance(character,1)==(character<2),"only humanoid crouch qualifies");
        check(modern_roll_stance(character,2)==(character<2),"only humanoid crawl qualifies");
        for(unsigned state:{0U,3U,6U,7U,8U,10U,11U,12U,0x20U,0x23U,0x2AU})
            check(!modern_roll_stance(character,state),"standing, air, ledge, aim and boss states excluded");
    }
    check(!modern_roll_stance(4,1) && !modern_roll_stance(5,2),"caller must normalize native character identity");
    check(modern_roll_side_buttons(0)==0 && modern_roll_side_buttons(0x80)==0,"old recordings carry no roll intent");
    check(modern_roll_side_buttons(kModernRollLeftFlag)==2 && modern_roll_side_buttons(kModernRollRightFlag)==1,"intent decodes native side buttons");
    check(modern_roll_side_buttons(kModernRollFlags)==0,"opposing recorded intent cancels");
    check(modern_roll_side_buttons(0x87|kModernRollLeftFlag)==2,"scope and identity bits do not alter direction");

    ModernControlsConfig config;
    constexpr std::array<ModernAction,4> actions{ModernAction::move_left,ModernAction::move_right,
        ModernAction::move_forward,ModernAction::move_back};
    for(bool remapped:{false,true}) {
        if(remapped)for(std::size_t i=0;i<actions.size();++i)
            config.keys[index(actions[i])]=std::array<int,4>{'J','L','I','K'}[i];
        for(unsigned held=0;held<16;++held) {
            const auto input=sample_modern_keyboard(config,[&](int key) {
                for(std::size_t i=0;i<actions.size();++i)
                    if(key==config.keys[index(actions[i])] && (held&(1U<<i)))return true;
                return false;
            });
            const auto expected=(held&12U)?0U:(held&3U)==1U?kModernRollLeftFlag:
                (held&3U)==2U?kModernRollRightFlag:0U;
            check(modern_roll_flags(input)==expected,"keyboard only one lateral action without any W/S intent");
            check((map_modern_actions(input,false).buttons&3U)==0,"intent never injects unqualified standing side buttons");
        }
    }
    const auto shifted=sample_modern_keyboard(ModernControlsConfig{},[](int key){return key=='A'||key==16;});
    check(shifted.move.x==-127 && modern_roll_flags(shifted)==kModernRollLeftFlag,"full movement modifier preserves lateral intent");
    ModernActionSample toggled; toggled.move.x=-80;toggled.held=modern_bit(ModernAction::move_left);
    check(modern_roll_flags(toggled)==kModernRollLeftFlag,"roll intent does not require held crouch");
    toggled.held|=modern_bit(ModernAction::crouch);
    check(modern_roll_flags(toggled)==kModernRollLeftFlag,"crouch button binding does not alter roll direction");
    check(modern_roll_intent_flags(ModernRollSource::keyboard,-80,0,true)==0,"W+S+A cannot roll when net Y cancels");
    check(modern_roll_intent_flags(ModernRollSource::keyboard,-80,1,false)==0,"inconsistent forward keyboard axis fails closed");

    config={};
    const auto original_profile=serialize_modern_controls(config);
    for(int stick=0;stick<2;++stick) {
        config.movement_stick=stick;
        const auto axis=static_cast<std::size_t>(stick*2);
        for(int sign:{-1,1}) {
            for(int raw:{0,7848,7849}) {
                StandardControllerSample pad;pad.axes[axis]=sign*raw;
                check(modern_roll_flags(sample_modern_pad(config,pad))==0,"ordinary movement deadzone still blocks drift");
            }
            for(int raw:{8100,8689,20000,32767}) {
                StandardControllerSample pad;pad.axes[axis]=sign*raw;
                const auto input=sample_modern_pad(config,pad);
                check(input.move.x!=0 && modern_roll_flags(input)==(sign<0?kModernRollLeftFlag:kModernRollRightFlag),"any represented lateral tilt beyond ordinary deadzone qualifies");
            }
            StandardControllerSample diagonal;diagonal.axes[axis]=sign*32767;diagonal.axes[axis+1]=32767;
            check(modern_roll_flags(sample_modern_pad(config,diagonal))==0,"controller diagonal retains crawling");
            diagonal.axes[axis+1]=13000;
            check(modern_roll_flags(sample_modern_pad(config,diagonal))==(sign<0?kModernRollLeftFlag:kModernRollRightFlag),"lateral cone tolerates ordinary off-axis tilt");
            diagonal.axes[axis+1]=14000;
            check(modern_roll_flags(sample_modern_pad(config,diagonal))==0,"outside lateral cone retains crawling");
        }
        StandardControllerSample look;look.axes[static_cast<std::size_t>((1-stick)*2)]=32767;
        check(modern_roll_flags(sample_modern_pad(config,look))==0,"look stick never supplies roll intent");
        StandardControllerSample forward;forward.axes[axis+1]=32767;
        check(modern_roll_flags(sample_modern_pad(config,forward))==0,"forward and back alone remain crawl intent");
        config.movement_deadzone=20000;forward={};forward.axes[axis]=19999;
        check(modern_roll_flags(sample_modern_pad(config,forward))==0,"configured movement deadzone respected");
        forward.axes[axis]=21000;
        check(modern_roll_flags(sample_modern_pad(config,forward))==kModernRollRightFlag,"no additional strength band above configured deadzone");
        config.movement_deadzone=7849;
    }
    config.movement_stick=0;
    check(serialize_modern_controls(config)==original_profile,"roll sampling preserves profile schema and values");
    for(int sign:{-1,1})for(int ysign:{-1,1}) {
        check(modern_roll_intent_flags(ModernRollSource::controller,sign*80,ysign*33,false)==(sign<0?kModernRollLeftFlag:kModernRollRightFlag),"inside exact lateral cone");
        check(modern_roll_intent_flags(ModernRollSource::controller,sign*80,ysign*34,false)==0,"outside exact lateral cone");
    }
    check(modern_roll_intent_flags(ModernRollSource::controller,1,0,false)==kModernRollRightFlag,"smallest represented sideways axis qualifies");
    check(modern_roll_intent_flags(ModernRollSource::controller,1,1,false)==0,"small diagonal stays crawl");
    check(modern_roll_intent_flags(static_cast<ModernRollSource>(99),80,0,false)==0,"unknown input source fails closed");
    for(int invalid:{-129,128,(std::numeric_limits<int>::min)(),(std::numeric_limits<int>::max)()})
        check(modern_roll_intent_flags(ModernRollSource::controller,invalid,0,false)==0 &&
            modern_roll_intent_flags(ModernRollSource::controller,80,invalid,false)==0,"invalid axes fail closed without arithmetic overflow");
    ModernScopeZoom zoom;
    zoom.observe(kModernActionsFlag|kModernRollLeftFlag,true,1);
    check(zoom.take(1.0F)==1.0F,"roll flag does not become a scope command");
    zoom.observe(kModernActionsFlag|kModernRollRightFlag|1U,true,1);
    check(zoom.take(1.0F)==3.0F,"scope command coexists with roll intent");
    check(modern_roll_flags(ModernActionSample{})==0,"neutral/released input clears roll intent");
    StandardControllerSample original;original.buttons[1]=true;original.axes[2]=32767;
    check(map_controller(ControllerMapping{},original).buttons==0x4001,"Original Normal C-right mapping remains intact");
    {
        ModernControlsConfig bindings;
        const auto left=static_cast<std::size_t>(ModernAction::roll_left);
        const auto right=static_cast<std::size_t>(ModernAction::roll_right);
        check(bindings.automatic_roll && bindings.pad[left]==-1 && bindings.pad[right]==-1 &&
            bindings.keys[left]==0 && bindings.keys[right]==0,"automatic roll default on; dedicated actions unbound");
        bindings.keys[left]='J';bindings.keys[right]='L';bindings.pad[left]=3;bindings.pad[right]=4;
        for(bool automatic:{false,true}) {
            bindings.automatic_roll=automatic;
            for(unsigned manual=0;manual<4;++manual)for(int x:{-32767,0,32767})for(int y:{-32767,0,32767}) {
                const auto explicitFlag=manual==1?kModernRollLeftFlag:manual==2?kModernRollRightFlag:0;
                StandardControllerSample physical;physical.buttons[3]=(manual&1)!=0;physical.buttons[4]=(manual&2)!=0;
                physical.axes[0]=x;physical.axes[1]=-y;
                const auto padSample=sample_modern_pad(bindings,physical);
                const auto expectedPad=manual?explicitFlag:automatic?modern_roll_intent_flags(ModernRollSource::controller,padSample.move.x,padSample.move.y,false):0;
                check(modern_roll_flags(padSample)==expectedPad,"manual controller priority, cancellation and automatic preference");
                const auto keySample=sample_modern_keyboard(bindings,[&](int key){return
                    (key=='J'&&(manual&1)) || (key=='L'&&(manual&2)) ||
                    (key=='A'&&x<0) || (key=='D'&&x>0) || (key=='W'&&y>0) || (key=='S'&&y<0);});
                const auto expectedKeys=manual?explicitFlag:automatic?modern_roll_intent_flags(ModernRollSource::keyboard,keySample.move.x,keySample.move.y,y!=0):0;
                check(modern_roll_flags(keySample)==expectedKeys,"manual keyboard priority, cancellation and automatic preference");
                check((map_modern_actions(keySample,false).buttons&3)==0,"roll intent remains native-consumer scoped");
            }
            ModernControlsConfig restored;
            check(parse_modern_controls(serialize_modern_controls(bindings),restored) &&
                restored.automatic_roll==automatic && restored.keys[left]=='J' && restored.keys[right]=='L' &&
                restored.pad[left]==3 && restored.pad[right]==4,"manual bindings and preference roundtrip");
        }
        bindings.automatic_roll=false;
        check(modern_roll_flags(sample_modern_keyboard(bindings,[](int key){return key=='A';}))==0,"auto off leaves lateral key movement without roll");
        check(modern_roll_flags(sample_modern_keyboard(bindings,[](int key){return key=='J'||key=='W'||key=='S';}))==kModernRollLeftFlag,"manual roll independent of opposing fore/aft keys");
        auto invalid=serialize_modern_controls(bindings);const auto pos=invalid.find("roll.automatic=0");invalid.replace(pos,std::string("roll.automatic=0").size(),"roll.automatic=2");
        auto unchanged=bindings;check(!parse_modern_controls(invalid,unchanged) && serialize_modern_controls(unchanged)==serialize_modern_controls(bindings),"invalid roll preference rejected atomically");
    }
    std::cout<<checks<<" modern roll checks passed\n";
    return 0;
}
