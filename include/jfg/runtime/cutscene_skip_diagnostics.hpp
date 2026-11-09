#pragma once
#include "jfg/runtime/support_log.hpp"
#include <array>
#include <cstdint>
#include <cstdio>
#include <string_view>

namespace jfg {
enum class CutsceneSupportPhase { request, complete, settled, unqualified, destination, timeout };
// This is the bounded ordinary support log, independent of gameplay/Proton
// tracing. Keep its restricted alphabet: spaces silently reject the whole event.
inline std::array<char,161> cutscene_support_record(CutsceneSupportPhase phase,
    unsigned level,unsigned group,unsigned next,unsigned next_group,unsigned segments,
    std::uint64_t elapsed_ms) noexcept {
    constexpr std::array<std::string_view,6> names{
        "request","complete","settled","resume-unqualified","resume-destination","resume-timeout"};
    std::array<char,161> text{};
    const auto index=static_cast<unsigned>(phase);
    if(index>=names.size())return text;
    const auto count=std::snprintf(text.data(),text.size(),
        "cutscene=%s_level=%u_group=%u_next=%u_next_group=%u_n=%u_ms=%llu",
        names[index].data(),level,group,next,next_group,segments,
        static_cast<unsigned long long>(elapsed_ms));
    if(count<0 || static_cast<std::size_t>(count)>=text.size())text[0]='\0';
    return text;
}
inline void cutscene_support_event(CutsceneSupportPhase phase,unsigned level,unsigned group,
    unsigned next,unsigned next_group,unsigned segments,std::uint64_t elapsed_ms) noexcept {
    const auto text=cutscene_support_record(phase,level,group,next,next_group,segments,elapsed_ms);
    support_event(text.data());
}
constexpr std::uint64_t cutscene_elapsed_ms(std::uint64_t start,std::uint64_t now) noexcept {
    return now>=start?now-start:0;
}
} // namespace jfg
