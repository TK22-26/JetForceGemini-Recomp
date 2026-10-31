#include "jfg/runtime/mouse_input_diagnostics.hpp"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <filesystem>
#include <fstream>
#include <limits>
#include <string>
#include <iostream>

static std::uint64_t count(const jfg::MouseSupportSnapshot& s,jfg::MouseCount c) {
    return s.counts[static_cast<std::size_t>(c)];
}
int main(int argc,char** argv) {
    jfg::MouseInputDiagnostics d;
    auto s=d.snapshot();
    assert(count(s,jfg::MouseCount::messages)==0 && count(s,jfg::MouseCount::accepted_nonzero)==0);
    assert(s.state[5]==0 && s.state[6]==0); // unknown focus must not claim a focus measurement
    d.registration(true,999);s=d.snapshot();assert(s.state[0]==1 && s.state[1]==0);
    d.raw(true,false,false,true,true,false,0); // non-mouse is never motion
    d.raw(true,true,true,true,true,false,0); // absolute coordinates are never retained
    d.raw(false,false,false,true,false,false,87);
    d.raw(true,true,false,false,true,false,0);
    d.raw(true,true,false,true,false,true,0);
    d.raw(true,true,false,true,true,false,0);
    s=d.snapshot();
    assert(count(s,jfg::MouseCount::messages)==6);
    assert(count(s,jfg::MouseCount::read_errors)==1 && s.state[2]==87);
    assert(count(s,jfg::MouseCount::non_mouse)==1 && count(s,jfg::MouseCount::absolute)==1);
    assert(count(s,jfg::MouseCount::relative)==3 && count(s,jfg::MouseCount::nonzero_relative)==2);
    assert(count(s,jfg::MouseCount::accepted_relative)==2 && count(s,jfg::MouseCount::accepted_nonzero)==1);
    assert(count(s,jfg::MouseCount::dropped_uncaptured)==1);
    assert(count(s,jfg::MouseCount::foreground_messages)==5 && count(s,jfg::MouseCount::background_messages)==1);
    assert(count(s,jfg::MouseCount::mailbox_nonzero)==0 && count(s,jfg::MouseCount::look_nonzero)==0);
    // Registration success with zero packets is distinguishable from accepted or rejected motion.
    jfg::MouseInputDiagnostics silent;silent.registration(true,0);
    assert(silent.snapshot().state[0]==1 && count(silent.snapshot(),jfg::MouseCount::messages)==0);
    d.increment(jfg::MouseCount::focus_lost);d.increment(jfg::MouseCount::mailbox_nonzero);d.increment(jfg::MouseCount::look_nonzero);
    s=d.snapshot();s.elapsed_ms=1234;
    s.players[0]={0,1,1,1,1,100,100,100,0,0,1,1,3};
    for(std::size_t p=1;p<4;++p)s.players[p][0]=static_cast<std::uint16_t>(p);
    char formatted[1024]{};assert(jfg::format_mouse_support(s,formatted));
    jfg::MouseSupportHistory history;
    assert(history.size()==0);
    for(std::uint64_t i=0;i<70;++i) {
        s.elapsed_ms=i;s.state[3]=i<60?1U:0U;history.push(s);
        assert(history.size()==(i<60?i+1:60));
    }
    assert(history.at(0).elapsed_ms==10 && history.at(59).elapsed_ms==69);
    assert(history.at(49).state[3]==1 && history.at(50).state[3]==0);
    std::string expected;
    for(std::size_t i=0;i<history.size();++i) {
        assert(history.at(i).elapsed_ms==i+10);
        assert(jfg::format_mouse_support(history.at(i),formatted));expected+=formatted;
    }
#if defined(_WIN32)
    if(argc==2) {
        const auto directory=std::filesystem::path(argv[1]);std::filesystem::create_directories(directory);
        const auto support=(directory/L"native.log").wstring();
        assert(SetEnvironmentVariableW(L"JFG_SUPPORT_LOG",support.c_str()));
        assert(jfg::write_mouse_support(history));
        std::ifstream input(directory/L"mouse.log",std::ios::binary);
        const std::string actual((std::istreambuf_iterator<char>(input)),{});assert(actual==expected);
    }
#else
    (void)argc;(void)argv;
#endif
    for(auto& v:s.counts)v=std::numeric_limits<std::uint64_t>::max();
    s.elapsed_ms=std::numeric_limits<std::uint64_t>::max();
    for(auto& v:s.state)v=std::numeric_limits<std::uint32_t>::max();
    for(auto& p:s.players)for(auto& v:p)v=std::numeric_limits<std::uint16_t>::max();
    assert(jfg::format_mouse_support(s,formatted));
    const std::string maximum=formatted;assert(maximum.size()<1024);
    std::size_t start=0,lines=0;
    while(start<maximum.size()) {
        const auto end=maximum.find('\n',start);assert(end!=std::string::npos && end-start<=256);
        start=end+1;++lines;
    }
    assert(lines==8);
    jfg::MouseSupportHistory maximum_history;
    for(std::size_t i=0;i<75;++i)maximum_history.push(s);
    std::size_t history_bytes=0;
    for(std::size_t i=0;i<maximum_history.size();++i) {
        assert(jfg::format_mouse_support(maximum_history.at(i),formatted));
        history_bytes+=std::strlen(formatted);
    }
    assert(maximum_history.size()==60 && history_bytes==53040 && history_bytes<65536);
#if defined(_WIN32)
    if(argc==2) {
        assert(jfg::write_mouse_support(maximum_history));
        std::ifstream input(std::filesystem::path(argv[1])/L"mouse.log",std::ios::binary);
        const std::string actual((std::istreambuf_iterator<char>(input)),{});
        std::string expected_maximum;
        for(std::size_t i=0;i<60;++i)expected_maximum+=maximum;
        assert(actual==expected_maximum && actual.size()==53040);
    }
#endif
    std::cout<<"mouse diagnostics tests passed; maximum snapshot bytes="<<maximum.size()<<"; maximum history bytes="<<history_bytes<<"\n";
}
