#include "jfg/runtime/async_snapshots.hpp"
#include <stdexcept>
#include <chrono>
#include <future>
#include <iostream>
using W=jfg::AsyncSnapshots;
void check(bool value) {if(!value)throw std::runtime_error("snapshot check");}
struct Blocked final:W::Sink {
 std::promise<void> entered,release; std::shared_future<void> ready=release.get_future().share();
 std::vector<std::string> writes; bool first=true;
 bool replace(const W::File& f) override {
  if(first){first=false;entered.set_value();ready.wait();}
  writes.push_back(f.path.string()+":"+*f.text); return true;
 }
};
struct Failing final:W::Sink {
 std::vector<std::string> writes;
 bool replace(const W::File& f) override {writes.push_back(f.path.string());return f.path!="mesh";}
};
int main(int argc,char**argv) {
 check(argc==2);auto sink=std::make_unique<Blocked>();auto* b=sink.get();
 auto one=std::make_shared<const std::string>("one"),two=std::make_shared<const std::string>("two");
 W w(std::move(sink),1024);
 check(w.submit(1,{{"mesh",one},{"live",one}}));b->entered.get_future().wait();
 // Storage is deliberately blocked. One hundred newer publications must
 // complete on the producer and retain the matching mesh, not wait for I/O.
 auto begin=std::chrono::steady_clock::now();
 for(int n=0;n<100;++n)check(w.submit(1,{{"mesh",two},{"live",std::make_shared<const std::string>(std::to_string(n))}}));
 check(std::chrono::steady_clock::now()-begin<std::chrono::seconds(1));
 check(!w.submit(2,{{"bad",one}}));
 check(!w.submit(0,{{"big",std::make_shared<const std::string>(1025,'a')}}));
 b->release.set_value();w.finish();
 check(b->writes==std::vector<std::string>{"mesh:one","live:one","mesh:two","live:99"});
 check(w.coalesced()==99 && w.failed()==0 && !w.submit(0,{{"late",one}}));
 auto fail=std::make_unique<Failing>();auto*f=fail.get();W failed(std::move(fail));
 check(failed.submit(1,{{"mesh",one},{"live",one}}));failed.finish();
 check(f->writes==std::vector<std::string>{"mesh"} && failed.failed()==1);
 // Real replacement yields a complete file and drains accepted final state.
 {W disk;check(disk.submit(0,{{argv[1],two}}));disk.finish();check(disk.failed()==0);}
 std::ifstream in(argv[1],std::ios::binary);std::string content{std::istreambuf_iterator<char>(in),{}};
 check(content=="two");std::cout<<"blocked storage, ordered prerequisite, coalescing, bound, failure and shutdown: pass\n";
}
