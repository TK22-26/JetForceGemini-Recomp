#include "jfg/boot/recorded_input_timeline.hpp"
#include <array>
#include <cstdio>
int main() {
  unsigned checks=0,failures=0;
  const auto check=[&](bool ok,const char* label){++checks;if(!ok){++failures;std::fprintf(stderr,"FAILED: %s\n",label);}};
  using jfg::InputReplayEvent; using jfg::ControllerReplaySample; using jfg::boot::RecordedInputTimeline;
  ControllerReplaySample moving; moving.pc_mode=3;moving.stick_y=80;moving.look_x=10;moving.look_y=-4;moving.modern_flags=128;
  auto second=moving;second.look_x=-3;second.look_y=7;
  auto stopped=second;stopped.stick_y=0;stopped.look_x=0;stopped.look_y=0;
  const std::array<InputReplayEvent,3> events{{{10,11,moving},{12,13,second},{15,16,stopped}}};
  RecordedInputTimeline slow,fast;
  check(slow.sample(9,events)->neutral(),"before recording starts input is neutral");
  auto a=slow.sample(13,events);
  check(a && a->look_x==7 && a->look_y==3 && a->stick_y==80,"late poll conserves mouse displacement and held movement");
  a=slow.sample(14,events);check(a && a->look_x==0 && a->look_y==0 && a->stick_y==80,"mouse delta is not repeated between polls");
  a=slow.sample(14,events);check(a && a->look_x==0,"same-VI repeated poll cannot repeat motion");
  int x=0,y=0;
  for(unsigned t=9;t<=16;++t){a=fast.sample(t,events);x+=a->look_x;y+=a->look_y;}
  check(x==7 && y==3,"fast and slow polling consume identical total mouse motion");
  check(fast.sample(20,events)->stick_y==0,"released movement stays released");
  check(!fast.sample(19,events),"rewinding the clock is rejected");
  auto click=stopped;click.menu_kind=3;click.menu_target=2;
  const std::array<InputReplayEvent,2> clicked{{{10,11,click},{11,12,click}}};
  RecordedInputTimeline menus;a=menus.sample(11,clicked);
  check(a && a->menu_kind==3 && a->menu_target==2,"repeated identical menu selection merges");
  check(menus.sample(12,clicked)->menu_target==0,"menu selection is consumed once");
  auto other=click;other.menu_target=3;
  const std::array<InputReplayEvent,2> ambiguous{{{10,11,click},{11,12,other}}};
  RecordedInputTimeline conflict;check(!conflict.sample(12,ambiguous),"distinct menu selections cannot be silently merged");
  const std::array<InputReplayEvent,1> ranged{{{10,14,moving}}};RecordedInputTimeline ranges;
  check(!ranges.sample(12,ranged),"scripted held range is not a live poll recording");
  auto large=moving;large.look_x=32767;
  const std::array<InputReplayEvent,2> over{{{10,11,large},{11,12,large}}};RecordedInputTimeline overflow;
  check(!overflow.sample(12,over),"excess mouse motion is rejected rather than clipped");
  auto stick=moving;stick.pc_mode=5;stick.look_x=2048;const std::array<InputReplayEvent,1> sticks{{{10,11,stick}}};RecordedInputTimeline rate;
  check(rate.sample(10,sticks)->look_x==2048 && rate.sample(12,sticks)->look_x==2048,"stick look remains a held rate");
  auto press=stopped;press.buttons=0x1000;
  auto release=press;release.buttons=0;
  const std::array<InputReplayEvent,2> taps{{{20,21,press},{20,21,release}}};
  RecordedInputTimeline tap;a=tap.sample(20,taps);
  check(a && a->buttons==0x1000,"same-VI press and release produces one pressed sample");
  check(tap.sample(20,taps)->buttons==0,"repeat poll observes release without repeating edge");
  const std::array<InputReplayEvent,2> held{{{20,21,press},{25,26,release}}};
  RecordedInputTimeline holding;
  check(holding.sample(20,held)->buttons==0x1000 && holding.sample(24,held)->buttons==0x1000,"held button persists across polls");
  check(holding.sample(25,held)->buttons==0,"release after delivered press has no extra edge");
  RecordedInputTimeline skipped;
  check(skipped.sample(30,held)->buttons==0x1000 && skipped.sample(31,held)->buttons==0,"late consumer preserves one short button edge");
  for(std::uint8_t mode:{std::uint8_t{0},std::uint8_t{3},std::uint8_t{5}}) {
    ControllerReplaySample neutral;neutral.pc_mode=mode;neutral.modern_flags=0x80;
    auto left=neutral;left.modern_flags|=jfg::kModernRollLeftFlag;left.stick_x=-80;
    auto right=neutral;right.modern_flags|=jfg::kModernRollRightFlag;right.stick_x=80;
    const std::array<InputReplayEvent,3> short_roll{{{0,1,neutral},{1,2,left},{2,3,neutral}}};
    RecordedInputTimeline roll;a=roll.sample(2,short_roll);
    check(a && jfg::modern_roll_side_buttons(a->modern_flags)==2 && a->stick_x==0,
      "skipped short roll intent survives once without changing final movement");
    a=roll.sample(2,short_roll);
    check(a && jfg::modern_roll_side_buttons(a->modern_flags)==0,"same-VI poll clears consumed roll pulse");
    check(jfg::modern_roll_side_buttons(roll.sample(3,short_roll)->modern_flags)==0,
      "next-VI poll cannot repeat consumed roll pulse");
    const std::array<InputReplayEvent,2> same_vi_roll{{{4,5,right},{4,5,neutral}}};
    RecordedInputTimeline same_vi;a=same_vi.sample(4,same_vi_roll);
    check(a && jfg::modern_roll_side_buttons(a->modern_flags)==1,"same-VI recorded roll press and release preserved");
    check(jfg::modern_roll_side_buttons(same_vi.sample(4,same_vi_roll)->modern_flags)==0,
      "same-VI recorded release does not create repeated roll");
    const std::array<InputReplayEvent,2> held_roll{{{5,6,left},{10,11,neutral}}};
    RecordedInputTimeline held_direction;
    check(jfg::modern_roll_side_buttons(held_direction.sample(5,held_roll)->modern_flags)==2 &&
      jfg::modern_roll_side_buttons(held_direction.sample(9,held_roll)->modern_flags)==2,
      "held roll intent persists for native repeat semantics");
    check(jfg::modern_roll_side_buttons(held_direction.sample(10,held_roll)->modern_flags)==0,
      "delivered held roll releases without an extra pulse");
    const std::array<InputReplayEvent,3> reverse_roll{{{5,6,left},{6,7,right},{7,8,neutral}}};
    RecordedInputTimeline unrepresentable;
    check(!unrepresentable.sample(8,reverse_roll),"opposing skipped roll actions cannot be silently merged or cancelled");
    RecordedInputTimeline delivered_reverse;
    check(jfg::modern_roll_side_buttons(delivered_reverse.sample(5,reverse_roll)->modern_flags)==2 &&
      jfg::modern_roll_side_buttons(delivered_reverse.sample(6,reverse_roll)->modern_flags)==1,
      "distinct consumer polls preserve recorded reversal order");
    auto both=neutral;both.modern_flags|=jfg::kModernRollFlags;
    const std::array<InputReplayEvent,1> cancelled{{{1,2,both}}};RecordedInputTimeline cancellation;
    check(jfg::modern_roll_side_buttons(cancellation.sample(2,cancelled)->modern_flags)==0,
      "one packet with opposing intent keeps explicit cancellation semantics");
    for(const auto &pending_direction:{left,right}) {
      const std::array<InputReplayEvent,2> pending_conflict{{{1,2,pending_direction},{2,3,both}}};RecordedInputTimeline invalid_order;
      check(!invalid_order.sample(2,pending_conflict),"explicit conflicting packet cannot resurrect a pending direction");
    }
    const std::array<InputReplayEvent,2> conflict_then_right{{{1,2,both},{2,3,right}}};RecordedInputTimeline later_direction;
    check(jfg::modern_roll_side_buttons(later_direction.sample(2,conflict_then_right)->modern_flags)==1,
      "later unambiguous intent remains usable after a standalone conflicting packet");
    auto scope=neutral;scope.modern_flags|=1;
    const std::array<InputReplayEvent,2> scope_after_roll{{{1,2,left},{2,3,scope}}};RecordedInputTimeline scoped_roll;
    a=scoped_roll.sample(2,scope_after_roll);
    check(a && (a->modern_flags&7U)==1U && jfg::modern_roll_side_buttons(a->modern_flags)==2,
      "preserving short roll leaves final scope commands intact");
    auto original=neutral;original.modern_flags=0;original.pc_mode=0;
    auto disconnected=original;disconnected.connected=false;
    auto changed_mode=neutral;changed_mode.pc_mode=mode==3?5:3;
    for(const auto &new_lifetime:{original,disconnected,changed_mode}) {
      const std::array<InputReplayEvent,2> cross_lifetime{{{1,2,left},{2,3,new_lifetime}}};RecordedInputTimeline changed;
      check(!changed.sample(2,cross_lifetime),"pending roll cannot cross connection, Modern identity or source-mode lifetime");
    }
    auto old_lateral=neutral;old_lateral.stick_x=-80;
    const std::array<InputReplayEvent,2> old_recording{{{1,2,old_lateral},{2,3,neutral}}};RecordedInputTimeline legacy;
    a=legacy.sample(2,old_recording);
    check(a && jfg::modern_roll_side_buttons(a->modern_flags)==0,"legacy lateral recordings never acquire synthetic roll intent");
  }
  for(std::uint8_t mode:{std::uint8_t{1},std::uint8_t{2},std::uint8_t{4}}) {
    ControllerReplaySample legacy_mode;legacy_mode.pc_mode=mode;legacy_mode.modern_flags=0x80;
    auto flagged=legacy_mode;flagged.modern_flags|=jfg::kModernRollLeftFlag;
    const std::array<InputReplayEvent,2> legacy_tap{{{1,2,flagged},{2,3,legacy_mode}}};RecordedInputTimeline legacy_context;
    a=legacy_context.sample(2,legacy_tap);
    check(a && jfg::modern_roll_side_buttons(a->modern_flags)==0,"legacy aim modes do not preserve Modern roll pulses");
  }
  ControllerReplaySample original_mode;auto stray_flag=original_mode;stray_flag.modern_flags=jfg::kModernRollLeftFlag;
  const std::array<InputReplayEvent,2> no_identity{{{1,2,stray_flag},{2,3,original_mode}}};RecordedInputTimeline original_context;
  a=original_context.sample(2,no_identity);
  check(a && jfg::modern_roll_side_buttons(a->modern_flags)==0,"mode 0 alone does not opt Original controls into roll semantics");
  std::printf("%u recorded timeline checks, %u failures\n",checks,failures);return failures==0?0:1;
}
