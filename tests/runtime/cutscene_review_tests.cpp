#include "jfg/runtime/cutscene_review.hpp"
#include <array>
#include <cstdlib>
#include <iostream>
#include <vector>
int main() {
 unsigned checks=0;
 const auto check=[&](bool ok){++checks;if(!ok){std::cerr<<"failed check "<<checks<<"\n";std::exit(1);}};
 {
   jfg::CutsceneReviewMode mode;
   check(mode.destination(15,0)==0U);
   check(mode.destination(360,0)==23U);
   check(mode.destination(360,23)==23U); // Repeat must retain pre-credits mode.
   check(mode.destination(361,23)==0U);
   check(!mode.before_credits);
   check(mode.destination(360,5)==23U);
   check(mode.destination(15,23)==0U); // Restore known review mode after frontend entry.
   check(mode.destination(361,23)==0U); // Recover the original review mode.
   jfg::CutsceneReviewMode unknown;
   check(!unknown.destination(361,23)); // No loaded game context still rejects.
   jfg::CutsceneReviewMode chain;
   check(chain.destination(334,16)==16U);
   check(chain.destination(15,23)==16U); // Ending script entered credits.
   check(chain.destination(207,16)==16U);
   check(chain.destination(335,5)==16U); // Native ending returned to character select.
   check(chain.destination(341,3)==16U); // Native credits returned to title.
   check(chain.destination(360,5)==23U);
   check(chain.destination(15,23)==16U);
   check(mode.destination(360,2)==23U);
   check(mode.destination(15,4)==4U); // Native mode already changed independently.
   check(!mode.before_credits);
 }
 // Only the reviewed direct-entry fixture gets unlock prerequisites.
 check(jfg::cutscene_review_needs_character_unlocks(207,0));
 check(!jfg::cutscene_review_needs_character_unlocks(207,1));
 check(!jfg::cutscene_review_needs_character_unlocks(206,0));
 check(!jfg::cutscene_review_needs_character_unlocks(208,0));
 const auto req=jfg::parse_cutscene_review("JFGCUTSCENE1 5 1000 378 2 0",4,1100);
 check(req.has_value());check(req->level==378&&req->group==2);
 for(const auto bad:{"JFGCUTSCENE1 4 1000 378 2 0","JFGCUTSCENE1 -1 1000 378 2 0",
    "JFGCUTSCENE1 5 1000 412 2 0","JFGCUTSCENE1 5 1000 378 256 0",
    "JFGCUTSCENE1 5 1000 378 2 3","JFGCUTSCENE1 5 1000 378 2 0 extra",
    "JFGCUTSCENE1 5 -1 378 2 0","JFGCUTSCENE1 5 2000 378 2 0","wrong 5 1000 378 2 0"})
   check(!jfg::parse_cutscene_review(bad,4,1100));
 check(!jfg::parse_cutscene_review("JFGCUTSCENE1 5 1000 378 2 0",4,61001));
 // The same still-fresh file must not be replayed by a new Play session,
 // including a restart before the first session consumed the request.
 const auto saved_request="JFGCUTSCENE1 5 1000 378 2 0";
 check(jfg::parse_cutscene_review(saved_request,0,1100,900).has_value());
 check(!jfg::parse_cutscene_review(saved_request,5,1100,900));
 check(!jfg::parse_cutscene_review(saved_request,0,1200,1150));
 check(!jfg::parse_cutscene_review(saved_request,0,1200,1000));
 check(jfg::parse_cutscene_review("JFGCUTSCENE1 6 1200 378 2 0",0,1250,1150).has_value());
 check(!jfg::parse_cutscene_review("JFGCUTSCENE1 6 1200 378 2 0",6,1250,1150));
 // Future timestamps and expired files remain rejected with a session bound.
 check(!jfg::parse_cutscene_review("JFGCUTSCENE1 6 1300 378 2 0",0,1250,1150));
 check(!jfg::parse_cutscene_review("JFGCUTSCENE1 6 1200 378 2 0",0,61201,1150));
 std::vector<std::uint8_t> li(413*4),h(280),si(8),s(16);
 auto word=[](auto& v,unsigned i,std::uint32_t n){for(unsigned k=0;k<4;k++)v[i+k]=std::uint8_t(n>>(24-k*8));};
 word(li,379*4,280);h[0x6c]=1;word(si,4,16);word(s,0,(2U<<24)|8U);
 word(s,4,0xFF000000);word(s,8,4);word(s,12,0x00007F00);
 check(jfg::cutscene_review_entry_valid(li,h,si,s,*req));
 auto x=*req;x.group=1;check(!jfg::cutscene_review_entry_valid(li,h,si,s,x));
 for(unsigned n=0;n<16;n++)check(!jfg::cutscene_review_entry_valid(li,h,si,std::span{s}.first(n),*req));
 h[0x6c]=0;check(!jfg::cutscene_review_entry_valid(li,h,si,s,*req));h[0x6c]=1;
 for(unsigned bad:{0U,1U,45U,73U,79U,127U,161U,412U}) {x=*req;x.level=bad;check(!jfg::cutscene_review_entry_valid(li,h,si,s,x));}
 // A structurally valid BigShip catalog entry still must not load:
 // rejecting a malformed header alone would not protect an older selector.
 {
  auto safe_index=li;word(safe_index,46*4,280);
  x=*req;x.level=45;
  check(!jfg::cutscene_review_entry_valid(safe_index,h,si,s,x));
 }
 word(s,0,(2U<<24)|0xFFFFFF);check(!jfg::cutscene_review_entry_valid(li,h,si,s,*req));
 word(s,0,(2U<<24)|8U);word(s,8,0xFFFFFF);check(!jfg::cutscene_review_entry_valid(li,h,si,s,*req));
 word(s,8,4);word(si,4,0xFFFFFFFF);check(!jfg::cutscene_review_entry_valid(li,h,si,s,*req));
 std::cout<<"PASS "<<checks<<" checks\n";
}
