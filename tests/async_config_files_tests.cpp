#include "jfg/runtime/async_config_files.hpp"
#include <atomic>
#include <cstdlib>
#include <fstream>
#include <future>
#include <iostream>
using namespace std::chrono_literals;
namespace {
void check(bool okay,const char* message) {
    if (!okay) { std::cerr << message << '\n'; std::abort(); }
}
void write(const std::filesystem::path& path,const std::string& text) {
    std::ofstream stream(path,std::ios::binary|std::ios::trunc);
    stream << text; stream.close();check(bool(stream),"fixture write");
}
template<class Predicate> bool await(Predicate predicate) {
    const auto deadline=std::chrono::steady_clock::now()+3s;
    do { if(predicate())return true;std::this_thread::sleep_for(10ms); }
    while(std::chrono::steady_clock::now()<deadline);
    return false;
}
}
int main() {
    using Status=jfg::ConfigFileValue::Status;
    const auto path=std::filesystem::temp_directory_path()/
        ("jfg-config-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())+".ini");
    check(!std::filesystem::exists(path),"fresh fixture");
    check(jfg::AsyncConfigFiles::read({path,4096}).status==Status::missing,"confirmed deletion is distinguishable");
    write(path,std::string(4096,'x'));
    check(jfg::AsyncConfigFiles::read({path,4096}).text.size()==4096,"bounded file accepted");
    check(jfg::AsyncConfigFiles::read({path,4095}).status==Status::unavailable,"oversize rejected");
    write(path,std::string(32768,'x'));
    check(jfg::AsyncConfigFiles::read({path,32768}).text.size()==32768,"navigation command bound accepted");
    check(jfg::AsyncConfigFiles::read({path,32769}).status==Status::unavailable,"reader maximum stays bounded");
    write(path,std::string(32769,'x'));
    check(jfg::AsyncConfigFiles::read({path,32768}).status==Status::unavailable,"oversize navigation command rejected");
    write(path,"");check(jfg::AsyncConfigFiles::read({path,4096}).status==Status::unavailable,"partial/empty file rejected");
    write(path,"one");
    jfg::AsyncConfigFiles reader;
    reader.start({{path,4096}});
    auto initial=reader.latest();
    check(initial && initial->at(0).text=="one","initial values precede first input");
    write(path,"two");
    check(await([&]{return reader.latest()->at(0).text=="two";}),"live update becomes visible");
    check(initial->at(0).text=="one","old snapshot is immutable");
#if defined(_WIN32)
    const HANDLE exclusive=CreateFileW(path.c_str(),GENERIC_READ,0,nullptr,OPEN_EXISTING,0,nullptr);
    check(exclusive!=INVALID_HANDLE_VALUE,"exclusive fixture handle");
    check(jfg::AsyncConfigFiles::read({path,4096}).status==Status::unavailable,"sharing violation is not deletion");
    CloseHandle(exclusive);
#endif
    check(std::filesystem::remove(path),"remove owned fixture");
    check(await([&]{return reader.latest()->at(0).status==Status::missing;}),"deletion becomes visible");
    reader.finish();reader.finish();

    // A stalled disk read must not hold the snapshot mutex or block input.
    std::atomic<unsigned> calls{0};
    std::atomic<bool> blocked{false},release{false};
    jfg::AsyncConfigFiles slow;
    slow.start({{path,4096}},[&](const jfg::ConfigFileRequest&) {
        if(calls.fetch_add(1)>0) {
            blocked=true;
            while(!release.load()) std::this_thread::sleep_for(1ms);
            return jfg::ConfigFileValue{Status::ready,"after"};
        }
        return jfg::ConfigFileValue{Status::ready,"before"};
    });
    check(await([&]{return blocked.load();}),"background read entered");
    auto future=std::async(std::launch::async,[&]{return slow.latest();});
    check(future.wait_for(250ms)==std::future_status::ready,"input snapshot does not wait for blocked I/O");
    check(future.get()->at(0).text=="before","prior complete snapshot survives in-flight read");
    release=true;
    check(await([&]{return slow.latest()->at(0).text=="after";}),"completed read published");
    slow.finish();
    std::cout << "asynchronous settings snapshot checks passed\n";
}
