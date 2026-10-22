#include "jfg/renderer/daynight_fog.hpp"
#include "jfg/renderer/fog_settings.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <cstdint>
int main() {
    unsigned failures=0, checks=0;
    auto check=[&](bool ok) { ++checks; if(!ok) ++failures; };
    auto pack=[](int n,int f) {
        return (std::uint32_t(std::uint16_t(128000/(f-n)))<<16) |
               std::uint16_t((128000-256*n)/(f-n));
    };
    auto offset=[](std::uint32_t word) { return int(std::int16_t(word & 65535U)); };
    constexpr auto white=0xffffffffU;
    // Constant fog and phase endpoints preserve native command encoding.
    for(int near_value=900;near_value<=1000;near_value+=5) {
        auto a=jfg::make_daynight_fog(0,480,near_value,1020,near_value+3,1023,near_value,1020,white);
        check(a.valid && a.smooth_coefficients==pack(near_value,1020));
        auto b=jfg::make_daynight_fog(239,480,near_value,1020,near_value,1020,near_value,1020,white);
        check(b.valid && b.smooth_coefficients==pack(near_value,1020));
    }
    // Moving fog must not jump seven alpha levels once per 160 native ticks.
    for(bool backwards:{false,true}) {
        std::uint32_t previous=0; int largest=0, changes=0;
        for(unsigned tick=0;tick<480;tick+=2) {
            const int delta=int((std::int64_t(tick)<<14)/480)*3;
            const int fractional=(985<<14)+(backwards ? (3<<14)-delta : delta);
            const int near_value=fractional/(1<<14);
            auto fog=jfg::make_daynight_fog(tick,480,
                backwards?988:985,backwards?1023:1020,
                backwards?985:988,backwards?1020:1023,near_value,near_value+35,white);
            check(fog.valid && fog.native_coefficients==pack(near_value,near_value+35));
            if(tick) {
                const int step=offset(fog.smooth_coefficients)-offset(previous);
                check(backwards ? step>=0 : step<=0);
                largest=std::max(largest,std::abs(step));changes+=step!=0;
            }
            previous=fog.smooth_coefficients;
            check(jfg::daynight_fog_command(fog,fog.native_coefficients,white)==fog.smooth_coefficients);
            check(jfg::daynight_fog_command(fog,0x05000500U,white)==0x05000500U);
            check(jfg::daynight_fog_command(fog,fog.native_coefficients,0xff3232ffU)==fog.native_coefficients);
            check(jfg::fog_coefficients(fog.smooth_coefficients,0)==0);
            check(jfg::fog_coefficients(fog.smooth_coefficients,100)==fog.smooth_coefficients);
        }
        check(largest<=1 && changes>=20);
    }
    check(!jfg::make_daynight_fog(480,480,985,1020,988,1023,985,1020,white).valid);
    check(!jfg::make_daynight_fog(0,0,985,1020,988,1023,985,1020,white).valid);
    check(!jfg::make_daynight_fog(0,480,985,984,988,1023,985,1020,white).valid);
    check(!jfg::make_daynight_fog(0,480,985,1020,988,1024,985,1020,white).valid);
    check(!jfg::make_daynight_fog(0,480,985,1020,988,1023,984,1020,white).valid);
    check(jfg::daynight_fog_command({},0x12345678U,white)==0x12345678U);
    check(!jfg::make_daynight_fog(0,480,985,1020,988,1023,INT32_MAX,INT32_MIN,white).valid);
    // A native getter builds a list, then the controller advances before the
    // RSP task is captured. Two queued buffers must retain their own query,
    // including colour changes and integer fog boundaries.
    jfg::DayNightFogFrames frames;
    for (unsigned tick=2; tick<478; tick+=2) {
        auto query=[&](unsigned t) {
            const auto n=(std::int64_t(988)*(1<<14)-3*((std::int64_t(t)<<14)/480))/(1<<14);
            return jfg::make_daynight_fog(t,480,988,1023,985,1020,
                int(n),int(n+35),0xff0000ffU | ((255U-t/2)<<16) | ((255U-t/2)<<8));
        };
        const auto first=query(tick), advanced=query(tick+2);
        check(first.valid && advanced.valid && first.color!=advanced.color);
        frames.queried(first);
        frames.submit(0x80100000U,true,true);
        frames.queried(advanced);
        frames.submit(0x80110000U,true,true);
        const auto first_task=frames.take(0x00100000U);
        const auto next_task=frames.take(0x00110000U);
        check(jfg::daynight_fog_command(first_task,first.native_coefficients,first.color)==first.smooth_coefficients);
        check(jfg::daynight_fog_command(next_task,advanced.native_coefficients,advanced.color)==advanced.smooth_coefficients);
        check(!frames.take(0x00100000U).valid);
        // No getter in the next primary task must not reuse a previous room.
        frames.submit(0x80100000U,true,true);
        check(!frames.take(0x00100000U).valid);
        // An override invalidates submission even when a prior query exists.
        frames.queried(first);
        frames.submit(0x80100000U,true,false);
        check(!frames.take(0x00100000U).valid);
        // Offscreen work can precede primary submission; both get that frame.
        frames.queried(first);
        frames.submit(0x80120000U,false,true);
        frames.submit(0x80100000U,true,true);
        check(frames.take(0x00120000U).color==first.color);
        check(frames.take(0x00100000U).color==first.color);
    }
    std::cout << checks << " day/night fog checks; " << failures << " failures\n";
    return failures?1:0;
}
