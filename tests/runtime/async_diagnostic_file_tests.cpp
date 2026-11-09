#include "jfg/runtime/async_diagnostic_file.hpp"
#include <iomanip>
#include <stdexcept>
#include <iostream>
void check(bool v){if(!v)throw std::runtime_error("diagnostic stream");}
int main(int argc,char**argv){
 check(argc==2);jfg::AsyncDiagnosticFile f;check(!f.is_open());f.open(argv[1],std::ios::binary|std::ios::trunc);check(bool(f));
 std::string block(13000,'x');block[4059]='\0';block[9001]='\n';
 f<<"number "<<std::hex<<std::setfill('0')<<std::setw(8)<<1234U<<"\n";
 f.write(block.data(),static_cast<std::streamsize>(block.size()));f.flush();f<<"end\n";f.finish();
 std::ifstream in(argv[1],std::ios::binary);std::string actual{std::istreambuf_iterator<char>(in),{}};
 check(actual=="number 000004d2\n"+block+"end\n");
 std::cout<<"binary, formatting, buffer crossings, queued flush, shutdown drain: pass\n";
}
