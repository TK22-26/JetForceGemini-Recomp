#include "jfg/mod/navigation_mod.hpp"
#include <sstream>
#include <iostream>
#include <limits>
#include <random>
#include <chrono>
#include <fstream>
using namespace jfg::mod;
inline void legacy_write_mesh(std::ostream &out, const Mesh &mesh, std::uint32_t level,
                       std::uint64_t generation) {
  out << "{\"schema\":1,\"level\":" << level << ",\"generation\":" << generation
      << ",\"blocks\":" << mesh.blocks << ",\"vertices\":[";
  bool first = true;
  for (const auto &v : mesh.vertices) {
    if (!first)
      out << ',';
    first = false;
    json_vec(out, v);
  }
  out << "],\"triangles\":[";
  first = true;
  for (const auto &t : mesh.triangles) {
    if (!first)
      out << ',';
    first = false;
    out << "{\"v\":[" << t.vertices[0] << ',' << t.vertices[1] << ','
        << t.vertices[2] << "],\"flags\":" << t.flags
        << ",\"block\":" << t.block << ",\"normal\":";
    json_vec(out, t.normal);
    out << '}';
  }
  out << "]}\n";
}


void check(const Mesh& mesh) {
  std::ostringstream old,newer;
  legacy_write_mesh(old,mesh,119,18446744073709551615ULL);
  write_mesh(newer,mesh,119,18446744073709551615ULL);
  if(old.str()!=newer.str())throw std::runtime_error("mesh JSON differs from legacy values/format");
}
int main(int argc,char** argv) {
  check({});
  Mesh mesh;mesh.blocks=512;
  const float edge[]={0.0F,-0.0F,1,-1,1.2345678F,999999,1000000,0.0001F,0.00001F,
      std::numeric_limits<float>::max(),std::numeric_limits<float>::min(),
      std::numeric_limits<float>::denorm_min(),-32768,32767};
  for(float x:edge)mesh.vertices.push_back({x,-x,x});
  std::mt19937 random(149);
  while(mesh.vertices.size()<10000) {
    const auto bits=static_cast<std::uint32_t>(random());const auto f=std::bit_cast<float>(bits);
    if(std::isfinite(f))mesh.vertices.push_back({f,f,f});
  }
  for(std::uint32_t n=0;n<10000;++n)
    mesh.triangles.push_back({{n,(n+1)%10000,(n+2)%10000},n,511,mesh.vertices[n]});
  check(mesh);
  if(argc==2) {
    std::ifstream in(argv[1],std::ios::binary);
    std::vector<std::uint8_t> data{std::istreambuf_iterator<char>(in),{}};
    if(data.size()!=0x400000)throw std::runtime_error("4 MiB logical reference dump required");
    Memory memory(data,false);check(decode_mesh(memory,memory.u32(0x800a0d60)));
  }
  auto measure=[&](bool legacy) {
    const auto start=std::chrono::steady_clock::now();
    for(int i=0;i<20;++i) {
      std::ostringstream text;
      if(legacy)legacy_write_mesh(text,mesh,119,42);else write_mesh(text,mesh,119,42);
      if(text.str().empty())throw std::runtime_error("empty mesh");
    }
    return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count()/20;
  };
  std::cout<<"Exact legacy output: empty, limits, 10000 random finite floats, triangles";
  if(argc==2)std::cout<<", captured native geometry";
  std::cout<<"; legacy_ms="<<measure(true)<<"; candidate_ms="<<measure(false)<<'\n';
}
