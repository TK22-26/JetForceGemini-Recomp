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

    // Original bridge fixture: rotated/translated triangle in the current
    // deforming buffer, then an invalid face index. No game geometry embedded.
    const unsigned modelTable=0x80006000U,instance=0x80006100U,header=0x80006200U,
      verts=0x80006400U,faces=0x80006500U,batches=0x80006600U,col=0x80006700U,
      facets=0x80006800U,planes=0x80006900U;
    m.put16(actor+0x48U,55);put32(actor+0x6CU,modelTable);put32(modelTable,instance);put32(instance,header);
    put32(instance+4U,verts);put32(instance+12U,0);put32(header+0x60U,col);
    m.put16(state+0x12AU,0);m.put16(state+0x132U,0);
    m.put16(header+0x12U,3);m.put16(header+0x14U,1);m.put16(header+0x16U,1);
    put32(header+0x20U,faces);put32(header+0x24U,batches);
    put32(col,facets);put32(col+12U,planes);m.put16(facets,0);
    putfloat(planes,0);putfloat(planes+4U,1);putfloat(planes+8U,0);
    for(unsigned i=0;i<15;++i)m.put16(verts+i*2U,0);
    m.put16(verts+14U,40);m.put16(verts+20U,40);
    m.put16(faces,0);m.put16(faces+2U,0x0102);
    m.put16(batches+6U,0);m.put16(batches+8U,0);m.put16(batches+24U,1);
    for(unsigned i=0;i<16;++i)putfloat(state+0x80U+i*4U,0);
    putfloat(state+0x88U,-1);putfloat(state+0x94U,1);putfloat(state+0xA0U,1);putfloat(state+0xBCU,1);
    putfloat(state+0xB0U,10);putfloat(state+0xB4U,20);putfloat(state+0xB8U,30);
    const auto surface=bridge_surface(m,actor,state);
    check(surface.vertices.size()==3&&surface.triangles.size()==1);
    check(surface.vertices[1].x==50&&surface.vertices[1].y==20&&surface.vertices[2].z==-10);
    check(surface.triangles[0].normal.y==1);
    m.put16(faces+2U,0x0103);bool invalid=false;
    try{(void)bridge_surface(m,actor,state);}catch(const std::runtime_error &){invalid=true;}check(invalid);
    m.put16(actor+0x48U,7);check(bridge_surface(m,actor,state).triangles.empty());

  }
}
