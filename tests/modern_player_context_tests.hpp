// Per-port control ownership and Floyd's independent native input route.
static void modern_player_context_tests() {
  using namespace jfg::mod;
  for(bool swapped:{false,true}) {
    std::vector<std::uint8_t> bytes(4194304);
    Memory m(bytes,swapped);
    auto put8=[&](std::uint32_t a,std::uint8_t v){bytes[(a&0x1FFFFFFFU)^(swapped?3U:0U)]=v;};
    auto put32=[&](std::uint32_t a,std::uint32_t v){for(unsigned i=0;i<4;++i)put8(a+i,static_cast<std::uint8_t>(v>>(24-i*8)));};
    for(unsigned p=0;p<4;++p)put8(0x800FB100U+p,static_cast<std::uint8_t>(p));
    constexpr std::uint32_t list=0x80110000U;
    put32(0x8000E468U,0x8DCE2D10U);put32(0x8000E474U,0x8C422D0CU);
    put32(0x800F2D0CU,list);put32(0x800F2D10U,4);
    for(unsigned p=0;p<4;++p) {
      const auto a=0x80120000U+p*0x2000U,c=a+0x100U;
      put32(list+(3-p)*4U,a);put32(a+0x68U,c);put8(c,static_cast<std::uint8_t>(p));
    }
    for(unsigned p=0;p<4;++p) {
      const auto a=0x80120000U+p*0x2000U,c=a+0x100U;
      check(pc_player_for_port(m,p)==a);
      put8(0x800A4FC4U,1);check(pc_gameplay_active(m,a));check(!gameplay_active(m,a));
      put8(c+0x56BU,1);check(!pc_gameplay_active(m,a));
      check(pc_gameplay_active(m,0x80120000U+((p+1)%4)*0x2000U));
      put8(c+0x56BU,0);
    }
    // A gap/reordered guest assignment must use the profile at the actual
    // controller slot, without swapping the actor's native camera number.
    put8(0x800FB100U,2);put8(0x800FB102U,0);
    check(pc_player_for_port(m,2)==0x80120000U && pc_player_for_port(m,0)==0x80124000U);
    put8(0x800FB100U,0);put8(0x800FB102U,2);
    check(!pc_player_for_port(m,4));
    put32(0x800F2D10U,5);check(!pc_player_for_port(m,0));put32(0x800F2D10U,4);
    put8(0x80122100U,0);check(!pc_player_for_port(m,0));put8(0x80122100U,1);
    put32(0x8000E474U,0);check(!pc_player_for_port(m,2));put32(0x8000E474U,0x8C422D0CU);
    put32(0x800F2D0CU,0x80400000U);check(!pc_player_for_port(m,3));put32(0x800F2D0CU,list);
    put32(0x80047C20U,0x91CE4FC4U);put32(0x80047C80U,0x8D29D7D4U);
    put32(0x800FD7D4U,0x80150000U);put8(0x800A4FD0U,4);
    for(unsigned p=0;p<4;++p)put8(0x800FED50U+0x16U+p*0xA0U+0x70U,static_cast<std::uint8_t>(p+5));
    for(unsigned p=0;p<4;++p)check(pc_player_weapon(m,0x80120100U+p*0x2000U)==p+5);
    put8(0x800FB100U,2);put8(0x800FB102U,0);
    check(pc_player_weapon(m,0x80120100U)==5); // Inventory follows logical player, not input port.
    put8(0x800FB100U,0);put8(0x800FB102U,2);
    put8(0x800A4FC4U,0);put8(0x80150000U+0x15CU+0x70U,7);
    check(pc_player_weapon(m,0x80120100U)==7);
    constexpr auto owner=0x80120000U,oc=owner+0x100U,floyd=0x80130000U,fc=floyd+0x100U;
    put32(0x8002F7A0U,0x0C010D44U);put32(0x8002F7A4U,0x24040001U);put32(0x8002F85CU,0x0C00DC94U);
    put32(0x800F2D14U,floyd);put32(floyd+0x68U,fc);put32(fc+0x24U,owner);
    check(!pc_floyd_context(m)); // Unlocking/spawning does not join.
    put8(0x800A4FC8U,1);check(!pc_floyd_context(m));
    put8(fc+0x94U,0x80);auto route=pc_floyd_context(m);
    check(route && route.port==1 && !route.mission && route.owner==owner && route.actor==floyd);
    put8(0x800FB101U,3);check(pc_floyd_context(m).port==3);put8(0x800FB101U,1);
    put8(0x800FD7BDU,1);check(!pc_floyd_context(m));put8(0x800FD7BDU,0);
    put32(0x801045B8U,1);check(!pc_floyd_context(m));put32(0x801045B8U,0);
    put8(0x800A4FC4U,1);check(!pc_floyd_context(m));put8(0x800A4FC4U,0);
    put8(0x800A4FC8U,0);put8(fc+0x94U,0);put8(oc+0x10DU,1);
    route=pc_floyd_context(m);check(route && route.mission && route.port==0);
    put8(fc+0x94U,0x80);check(pc_floyd_context(m).port==1);put8(fc+0x94U,0);
    check(!pc_gameplay_active(m,owner)); // Mission input never grants character camera ownership.
    for(unsigned mode:{2U,3U,4U,255U}){put8(oc+0x10DU,static_cast<std::uint8_t>(mode));check(!pc_floyd_context(m));}
    put8(oc+0x10DU,1);put8(oc,3);check(pc_floyd_context(m).port==3);
    put8(oc,4);check(!pc_floyd_context(m));put8(oc,0);
    put32(fc+0x24U,0x80400000U);check(!pc_floyd_context(m));put32(fc+0x24U,owner);
    put32(0x8002F85CU,0);check(!pc_floyd_context(m));
  }
}
