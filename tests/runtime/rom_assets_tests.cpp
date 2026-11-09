#include "jfg/game/rom_assets.hpp"
#include <array>
#include <cstdlib>
#include <iostream>
using namespace jfg::game;
void check(bool ok){if(!ok)std::abort();}
int main(){
 std::array<std::uint8_t,128> bytes{};
 const auto word=[&](unsigned p,unsigned v){for(unsigned i=0;i<4;++i)bytes[p+i]=std::uint8_t(v>>(24U-8U*i));};
 word(16,2);word(20,0);word(24,8);word(28,24);
 RomAssetDirectory layout{"fixture",16,64};
 RomAssetView view(bytes,layout,"fixture");check(view.section(0).size()==8 && view.section(1).size()==16);
 const auto rejects=[&](auto run){try{run();return false;}catch(const std::exception&){return true;}};
 check(rejects([&]{RomAssetView bad(bytes,layout,"different");}));
 check(rejects([&]{(void)view.section(2);}));
 word(24,25);check(rejects([&]{RomAssetView bad(bytes,layout,"fixture");}));
 word(24,8);word(28,65);check(rejects([&]{RomAssetView bad(bytes,layout,"fixture");}));
 word(28,24);word(16,4096);check(rejects([&]{RomAssetView bad(bytes,layout,"fixture");}));
 check(rom_address_operand(0x3c080001,0x2508fff0)==0xfff0U);
 std::cout<<"ROM asset revision and range checks passed\n";
}
