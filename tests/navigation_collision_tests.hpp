static void navigation_collision_tests() {
  using namespace jfg::mod;
  for (bool swapped : {false, true}) {
    std::vector<std::uint8_t> bytes(4194304U); Memory m(bytes, swapped);
    const auto put32 = [&](std::uint32_t a, std::uint32_t v) {m.put16(a, std::uint16_t(v >> 16U));m.put16(a+2U,std::uint16_t(v));};
    const auto putfloat = [&](std::uint32_t a,float v) {put32(a,std::bit_cast<std::uint32_t>(v));};
    constexpr std::array<std::uint32_t,7> pin={0x3C0E8010,0x8DCE47E0,0x3C028010,0xAC8E0000,0x8C4247E4,0x03E00008,0};
    const std::uint32_t table=0x80001000U,actor=0x80002000U,state=0x80003000U,props=0x80004000U;
    std::vector<Actor> list{{actor,7,{100,200,300}}};
    check(!collision_models(m,list).known);
    for(unsigned i=0;i<pin.size();++i)put32(0x8007E484U+i*4U,pin[i]);
    check(collision_models(m,list).known && collision_models(m,list).models.empty());
    put32(0x801047E0U,1);put32(0x801047E4U,table);put32(table,actor);
    put32(actor+0x5CU,state);put32(actor+0x4CU,props);m.put16(props+10U,1);
    for(unsigned i=0;i<3;++i){putfloat(state+0x100U+4U*i,float(i*100));putfloat(state+0x10CU+4U*i,float(i*100+50));}
    auto original=bytes;auto result=collision_models(m,list);
    check(result.known && result.models.size()==1 && result.models[0].enabled && result.models[0].lower.y==100 && result.models[0].upper.y==150 && bytes==original);
    std::ostringstream json;write_collision(json,result);check(json.str().find("\"known\":true")!=std::string::npos);
    m.put16(props+10U,0);check(!collision_models(m,list).models[0].enabled);
    put32(0x801047E0U,2);put32(table+4U,actor|0x20000000U);
    check(!collision_models(m,list).known && collision_models(m,list).models.empty());
    put32(0x801047E0U,1);put32(table,actor+0x100U);check(!collision_models(m,list).known);put32(table,actor);
    putfloat(state+0x100U,60);check(!collision_models(m,list).known);putfloat(state+0x100U,0);
    put32(state+0x104U,0x7FC00000U);check(!collision_models(m,list).known);putfloat(state+0x104U,100);
    put32(actor+0x5CU,0x803FFFF0U);check(!collision_models(m,list).known);put32(actor+0x5CU,state);
    put32(0x801047E0U,1025);check(!collision_models(m,list).known);
    put32(actor+0x40U,0x80005000U);m.put16(0x80005004U,0x4122U);m.put16(0x80005006U,0x5C01U);m.put16(0x80005008U,0);
    check(actor_name(m,actor)=="A???");
  }
}
