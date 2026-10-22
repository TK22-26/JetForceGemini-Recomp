#pragma once
#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#if defined(_WIN32)
#include "jfg/runtime/support_snapshot.hpp"
#endif

namespace jfg {
// Numeric allowlist only: never retain positions, key codes, handles or device names.
enum class MouseCount : std::size_t {
    messages, read_errors, non_mouse, relative, absolute, nonzero_relative,
    accepted_relative, accepted_nonzero, dropped_uncaptured, foreground_messages,
    background_messages, focus_lost, mailbox_nonzero, look_nonzero, count
};
struct MouseSupportSnapshot {
    std::array<std::uint64_t,14> counts{};
    std::uint64_t elapsed_ms=0;
    // registered,error,read_error,captured,root_foreground,child_focus,focus_known,
    // settings_open,input_blocked,replay,extended_recording,target_known,target_matches,flags
    std::array<std::uint32_t,14> state{};
    // port,device_kind,modern,connected,mouse_aim,normal,aim,vertical,invert_x,invert_y,actions,free_view,mode
    std::array<std::array<std::uint16_t,13>,4> players{};
};
class MouseInputDiagnostics {
public:
    void increment(MouseCount key) noexcept { counts_[static_cast<std::size_t>(key)].fetch_add(1,std::memory_order_relaxed); }
    void registration(bool success,std::uint32_t error) noexcept {
        registered.store(success?1U:0U,std::memory_order_relaxed);
        registration_error.store(success?0U:error,std::memory_order_relaxed);
    }
    void raw(bool read_ok,bool mouse,bool absolute,bool captured,bool nonzero,bool background,std::uint32_t error) noexcept {
        increment(MouseCount::messages);
        increment(background?MouseCount::background_messages:MouseCount::foreground_messages);
        if(!read_ok) { increment(MouseCount::read_errors);last_read_error.store(error,std::memory_order_relaxed);return; }
        if(!mouse) { increment(MouseCount::non_mouse);return; }
        if(absolute) { increment(MouseCount::absolute);return; }
        increment(MouseCount::relative);
        if(nonzero)increment(MouseCount::nonzero_relative);
        if(!captured) { increment(MouseCount::dropped_uncaptured);return; }
        increment(MouseCount::accepted_relative);
        if(nonzero)increment(MouseCount::accepted_nonzero);
    }
    MouseSupportSnapshot snapshot() const noexcept {
        MouseSupportSnapshot result;
        for(std::size_t i=0;i<counts_.size();++i)result.counts[i]=counts_[i].load(std::memory_order_relaxed);
        result.state[0]=registered.load(std::memory_order_relaxed);
        result.state[1]=registration_error.load(std::memory_order_relaxed);
        result.state[2]=last_read_error.load(std::memory_order_relaxed);
        return result;
    }
private:
    std::array<std::atomic<std::uint64_t>,14> counts_{};
    std::atomic<std::uint32_t> registered{0},registration_error{0},last_read_error{0};
};
// The guest thread owns this ring. Opening support/settings retains the preceding
// gameplay state; input packets only update counters and never write files.
class MouseSupportHistory {
public:
    static constexpr std::size_t capacity=60;
    void push(const MouseSupportSnapshot& snapshot) noexcept {
        entries_[cursor_]=snapshot;cursor_=(cursor_+1)%capacity;
        if(count_<capacity)++count_;
    }
    [[nodiscard]] std::size_t size() const noexcept { return count_; }
    // Index is relative to the oldest retained sample and must be below size().
    [[nodiscard]] const MouseSupportSnapshot& at(std::size_t index) const noexcept {
        return entries_[(cursor_+capacity-count_+index)%capacity];
    }
private:
    std::array<MouseSupportSnapshot,capacity> entries_{};
    std::size_t cursor_=0,count_=0;
};
// The maximum schema-1 output is below 1 KiB and every line is below 256 bytes.
inline bool format_mouse_support(const MouseSupportSnapshot& value,char (&output)[1024]) noexcept {
    std::size_t used=0;output[0]='\0';
    const auto text=[&](const char* s) {
        const auto n=std::strlen(s);if(n>=sizeof(output)-used)return false;
        std::memcpy(output+used,s,n+1);used+=n;return true;
    };
    const auto number=[&](std::uint64_t n,bool last) {
        char part[24]{};std::snprintf(part,sizeof(part),"%llu%c",static_cast<unsigned long long>(n),last?'\n':'/');return text(part);
    };
    if(!text("mouse_schema=1\nmouse_counts="))return false;
    for(std::size_t i=0;i<8;++i)if(!number(value.counts[i],i==7))return false;
    if(!text("mouse_flow="))return false;
    for(std::size_t i=8;i<14;++i)if(!number(value.counts[i],i==13))return false;
    if(!text("mouse_state=") || !number(value.elapsed_ms,false))return false;
    for(std::size_t i=0;i<value.state.size();++i)if(!number(value.state[i],i+1==value.state.size()))return false;
    for(const auto& player:value.players) {
        if(!text("mouse_player="))return false;
        for(std::size_t i=0;i<player.size();++i)if(!number(player[i],i+1==player.size()))return false;
    }
    return true;
}
#if defined(_WIN32)
inline bool write_mouse_support(const MouseSupportHistory& history) noexcept {
    const HANDLE file=support_file(L"mouse.log");if(file==INVALID_HANDLE_VALUE)return false;
    bool ok=true;
    for(std::size_t i=0;i<history.size();++i) {
        char text[1024]{};
        if(!format_mouse_support(history.at(i),text)) { ok=false;break; }
        DWORD written=0;const DWORD size=static_cast<DWORD>(std::strlen(text));
        if(WriteFile(file,text,size,&written,nullptr)==FALSE || written!=size) { ok=false;break; }
    }
    CloseHandle(file);return ok;
}
#endif
} // namespace jfg
