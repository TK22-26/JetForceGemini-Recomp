#pragma once
#include "jfg/renderer/frame_diagnostics_state.hpp"
#include "common/rt64_plume.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>
#include <thread>
#include <vector>
#if defined(_WIN32)
#include <Windows.h>
#endif
namespace jfg {
// Swapchain diagnostics only: never draw into guest feedback or block the render
// thread on disk I/O. One producer, one writer, bounded queue and rotated files.
#if defined(_WIN32)
class FrameDiagnostics {
    struct Sample { std::uint64_t us, frame, interval, scenes, age, vi, dropped; };
    static constexpr std::size_t capacity = 8192;
    std::array<Sample, capacity> queue{};
    std::atomic<std::size_t> head{0}, tail{0};
    std::atomic<bool> stopping{false}, failed{false};
    std::thread writer;
    std::filesystem::path directory;
    std::string stem, settings;
    HWND window = nullptr;
    bool enabled = false, key_down = false;
    std::uint64_t start = 0, last = 0, frame = 0, dropped = 0;
    std::uint64_t window_start = 0, window_frames = 0, window_scenes = 0, max_us = 0;
    double fps = 0, game_fps = 0, ms = 0, maximum_ms = 0;
    static std::array<unsigned,7> glyph(char c) noexcept {
        switch(c) {
        case '0':return {14,17,19,21,25,17,14}; case '1':return {4,12,4,4,4,4,14};
        case '2':return {14,17,1,2,4,8,31}; case '3':return {30,1,1,14,1,1,30};
        case '4':return {2,6,10,18,31,2,2}; case '5':return {31,16,16,30,1,1,30};
        case '6':return {14,16,16,30,17,17,14}; case '7':return {31,1,2,4,8,8,8};
        case '8':return {14,17,17,14,17,17,14}; case '9':return {14,17,17,15,1,1,14};
        case 'A':return {14,17,17,31,17,17,17}; case 'E':return {31,16,16,30,16,16,31};
        case 'F':return {31,16,16,30,16,16,16}; case 'G':return {14,17,16,23,17,17,15};
        case 'I':return {14,4,4,4,4,4,14}; case 'L':return {16,16,16,16,16,16,31};
        case 'M':return {17,27,21,21,17,17,17}; case 'N':return {17,25,25,21,19,19,17};
        case 'O':return {14,17,17,17,17,17,14}; case 'P':return {30,17,17,30,16,16,16};
        case 'R':return {30,17,17,30,20,18,17}; case 'S':return {15,16,16,14,1,1,30};
        case 'T':return {31,4,4,4,4,4,4}; case 'X':return {17,17,10,4,10,17,17};
        case '.':return {0,0,0,0,0,12,12}; case '-':return {0,0,0,31,0,0,0};
        default:return {};
        }
    }
    void write_loop() noexcept {
        try {
            std::ofstream file;
            std::size_t bytes = 0, segment = 0;
            std::uint64_t flushed = frame_clock_us();
            while (!stopping.load(std::memory_order_acquire) ||
                   tail.load(std::memory_order_relaxed) != head.load(std::memory_order_acquire)) {
                auto read = tail.load(std::memory_order_relaxed);
                const auto end = head.load(std::memory_order_acquire);
                while (read != end) {
                    const auto sample = queue[read];
                    read = (read + 1) % capacity;
                    tail.store(read, std::memory_order_release);
                    if (!file.is_open() || bytes >= 16U*1024U*1024U) {
                        if (file.is_open()) { file.close(); ++segment; }
                        std::filesystem::create_directories(directory);
                        file.open(directory/(stem+"-"+std::to_string(segment%4)+".csv"),std::ios::binary|std::ios::trunc);
                        if (!file) { failed.store(true); return; }
                        file << "# JFG frame diagnostics schema 1; render-hook intervals, not monitor scanout\n"
                             << "# GAME counts screen-scene submissions; excludes 64x64 shadows\n"
                             << "# " << settings << "\n"
                             << "# Four rotating 16 MiB segments; queue overflow counted, never blocks rendering\n"
                             << "elapsed_us,render_frame,interval_us,scene_frames,scene_age_us,vi,queue_dropped\n";
                        bytes=512;
                    }
                    char line[256]{};
                    const int count=std::snprintf(line,sizeof(line),"%llu,%llu,%llu,%llu,%llu,%llu,%llu\n",
                        static_cast<unsigned long long>(sample.us),static_cast<unsigned long long>(sample.frame),
                        static_cast<unsigned long long>(sample.interval),static_cast<unsigned long long>(sample.scenes),
                        static_cast<unsigned long long>(sample.age),static_cast<unsigned long long>(sample.vi),
                        static_cast<unsigned long long>(sample.dropped));
                    if (count>0 && count<static_cast<int>(sizeof(line))) { file.write(line,count); bytes+=static_cast<std::size_t>(count); }
                    if (!file) { failed.store(true); return; }
                }
                const auto now=frame_clock_us();
                if (file.is_open() && now-flushed>=1000000) { file.flush(); flushed=now; }
                std::this_thread::sleep_for(std::chrono::milliseconds(25));
            }
        } catch (...) { failed.store(true); }
    }
public:
    ~FrameDiagnostics() { stopping.store(true,std::memory_order_release); if(writer.joinable())writer.join(); }
    void initialize(void* native_window, unsigned cap, bool unlimited, bool vsync) {
        window=static_cast<HWND>(native_window);
        wchar_t* value=nullptr; std::size_t length=0;
        (void)_wdupenv_s(&value,&length,L"JFG_VIDEO_CONFIG");
        auto profile=value ? std::filesystem::path(value).parent_path() : std::filesystem::current_path();
        std::free(value);
        directory=profile/L"performance";
        std::ifstream preferences(profile/L"performance.ini");std::string line;
        while(std::getline(preferences,line))if(line=="enabled=1" || line=="enabled=1\r")enabled=true;
        SYSTEMTIME utc{};GetSystemTime(&utc);char name[96]{};
        std::snprintf(name,sizeof(name),"frames-%04u%02u%02u-%02u%02u%02u-%lu",static_cast<unsigned>(utc.wYear),static_cast<unsigned>(utc.wMonth),static_cast<unsigned>(utc.wDay),static_cast<unsigned>(utc.wHour),static_cast<unsigned>(utc.wMinute),static_cast<unsigned>(utc.wSecond),GetCurrentProcessId());
        stem=name;settings="mode="+std::string(unlimited?"unlimited":cap?"custom":"original")+" target="+std::to_string(cap)+" vsync="+(vsync?"1":"0");
        start=frame_clock_us();
        auto& state=frame_diagnostic_state();state.scenes=0;state.scene_time=0;state.vi=0;
        writer=std::thread([this]{write_loop();});
    }
    void draw(RenderCommandList* list,unsigned width,unsigned height) {
        if(!list || width<100 || height<80)return;
        const bool focused=window && GetAncestor(window,GA_ROOT)==GetForegroundWindow();
        const bool down=focused && (GetAsyncKeyState(VK_F8)&0x8000)!=0;
        if(down && !key_down){ enabled=!enabled; last=0;window_start=0;window_frames=0;max_us=0; }
        key_down=down;
        if(!enabled)return;
        const auto now=frame_clock_us();const auto interval=last?now-last:0;last=now;++frame;
        auto& state=frame_diagnostic_state();const auto scenes=state.scenes.load(std::memory_order_relaxed);
        const auto scene_time=state.scene_time.load(std::memory_order_relaxed);
        if(!window_start){window_start=now;window_scenes=scenes;}
        else ++window_frames;
        max_us=(std::max)(max_us,interval);
        if(now-window_start>=500000){
            const double seconds=static_cast<double>(now-window_start)/1000000.;
            fps=static_cast<double>(window_frames)/seconds;game_fps=static_cast<double>(scenes-window_scenes)/seconds;
            ms=window_frames?static_cast<double>(now-window_start)/static_cast<double>(window_frames)/1000.:0;
            maximum_ms=static_cast<double>(max_us)/1000.;window_start=now;window_frames=0;window_scenes=scenes;max_us=0;
        }
        const auto write=head.load(std::memory_order_relaxed),next=(write+1)%capacity;
        if(next!=tail.load(std::memory_order_acquire)){
            queue[write]={now-start,frame,interval,scenes,scene_time && now>=scene_time?now-scene_time:0,state.vi.load(std::memory_order_relaxed),dropped};
            head.store(next,std::memory_order_release);
        }else ++dropped;
        std::array<std::array<char,64>,3> lines{};
        std::snprintf(lines[0].data(),lines[0].size(),"FPS %.1f  MS %.1f",fps,ms);
        std::snprintf(lines[1].data(),lines[1].size(),"GAME %.1f MAX %.1f",game_fps,maximum_ms);
        std::snprintf(lines[2].data(),lines[2].size(),"LOG %s  F8 TOGGLE",failed.load()?"ERROR":dropped?"GAPS":"ON");
        const int scale=width>=480?2:1;const int panel=22*6*scale+12;const int left=static_cast<int>(width)-panel-8;
        const RenderRect background(left,8,static_cast<int>(width)-8,8+27*scale+12);
        list->clearColor(0U,RenderColor(0.02f,0.03f,0.05f,1.f),&background,1U);
        std::vector<RenderRect> pixels;pixels.reserve(1200);
        for(std::size_t row=0;row<lines.size();++row){
            int x=left+6;const int y=14+static_cast<int>(row)*9*scale;
            for(char c:lines[row]){
                if(!c)break;if(x+5*scale>=static_cast<int>(width)-10)break;
                const auto bitmap=glyph(c);
                for(int dy=0;dy<7;++dy)for(int dx=0;dx<5;++dx)if(bitmap[static_cast<std::size_t>(dy)]&(1U<<(4-dx)))pixels.emplace_back(x+dx*scale,y+dy*scale,x+(dx+1)*scale,y+(dy+1)*scale);
                x+=6*scale;
            }
        }
        // Keep clear batches small: the tested NVIDIA driver fast-failed on
        // a single very large rectangle array. No dependency modification.
        for(std::size_t i=0;i<pixels.size();i+=16) {
            const auto count=static_cast<std::uint32_t>((std::min)(std::size_t{16},pixels.size()-i));
            list->clearColor(0U,RenderColor(0.95f,0.95f,0.85f,1.f),pixels.data()+i,count);
        }
    }
};
#else
class FrameDiagnostics {
public:
    void initialize(void*, unsigned, bool, bool) {}
    void draw(RenderCommandList*, unsigned, unsigned) {}
};
#endif
} // namespace jfg
