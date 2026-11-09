/*
ares

Copyright (c) 2004-2021 ares team, Near et al

Permission to use, copy, modify, and/or distribute this software for any

purpose with or without fee is hereby granted, provided that the above

copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES

WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF

MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR

ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES

WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN

ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF

OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

Instruction/cache timing model based on ares VR4300 costs, as vendored by
BizHawk bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5.
*/

#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdbool.h>
#include "recomp.h"
#if defined(_MSC_VER)
#define JFG_CLOCK_INLINE __forceinline
#define JFG_CLOCK_NOINLINE __declspec(noinline)
#else
#define JFG_CLOCK_INLINE inline __attribute__((always_inline))
#define JFG_CLOCK_NOINLINE __attribute__((noinline,unused))
#endif
typedef struct { unsigned tag,valid,dirty; } JfgTimingCacheLine;
// Shared host state only. The native event handler and generated instruction
// fast path access the same storage; no guest clocks or observations are cached.
typedef struct JfgOriginalTimingFast {
 uint8_t* rdram;
 // Immutable revision-qualified runlink layout, composed by the native host.
 // Slot numbers are original module identities, never source-section indices.
 uint32_t timing_rdram_size,timing_table_pointer,timing_slot_count,timing_record_size;
 const uint8_t* timing_valid_slots;
 uint64_t cpu_count,observed_guest_instructions;
 uint64_t execution_fast_revision,execution_fast_deadline,execution_fast_hits;
 uint64_t diagnostic_cpu_half_tick;
 uint32_t execution_fast_pending,guest_last_pc,guest_last_word;
 bool execution_fast_profile_ready,guest_previous_branch,guest_previous_delay;
 bool guest_eret_boundary,play_mode;
 bool diagnostic_host_clock;
 unsigned host_clock_poll_budget;
 unsigned native_fast_status;
 bool native_fast_ready;
 bool native_spans_enabled;
 uint64_t native_span_instructions,native_span_commits;
 const volatile uint64_t* io_revision;
 volatile uint64_t* io_guest_count;
 JfgTimingCacheLine *instruction_cache,*data_cache;
 uint64_t* cache_counters;
} JfgOriginalTimingFast;
#ifdef __cplusplus
extern "C" {
#endif
extern JfgOriginalTimingFast* jfg_original_timing_state;
void jfg_phase9_execution_probe_predecoded(unsigned,unsigned,unsigned,void*);
#ifdef __cplusplus
}
#endif
// Both cache paths use this translation. Resident/hardware addresses pass
// through; an unavailable guest allocation is counted, never replaced by a US
// table or by a generated source-section ordinal.
static JFG_CLOCK_INLINE unsigned jfg_clock_translate(const JfgOriginalTimingFast* s,
    const uint8_t* ram,unsigned a,uint64_t* counters) {
 unsigned slot,table,base,offset;uint64_t record;
 if(a>=0x10000000U || a<0x100000U)return a;
 slot=a>>20;offset=a&0xfffffU;
 if(!s || !ram || !s->timing_valid_slots || slot>=s->timing_slot_count ||
    !s->timing_valid_slots[slot] || s->timing_rdram_size<4U ||
    s->timing_table_pointer>s->timing_rdram_size-4U ||
    (s->timing_table_pointer&3U)!=0U || s->timing_record_size<4U ||
    (s->timing_record_size&3U)!=0U)goto unresolved;
 memcpy(&table,ram+s->timing_table_pointer,4);
 if(table<0x80000000U || (table&3U)!=0U)goto unresolved;
 record=(uint64_t)(table-0x80000000U)+(uint64_t)slot*s->timing_record_size;
 if(record>s->timing_rdram_size-4U)goto unresolved;
 memcpy(&base,ram+(size_t)record,4);
 if(base<0x80000000U || (uint64_t)(base-0x80000000U)+offset>=s->timing_rdram_size)goto unresolved;
 return base+offset;
 unresolved:
 if(counters)++counters[11];
 return a;
}
static JFG_CLOCK_INLINE unsigned jfg_clock_address(JfgOriginalTimingFast* s,unsigned a) {
 return jfg_clock_translate(s,s?s->rdram:NULL,a,s?s->cache_counters:NULL);
}
static JFG_CLOCK_INLINE unsigned jfg_clock_fetch(JfgOriginalTimingFast* s,unsigned pc) {
 unsigned a=jfg_clock_address(s,pc)&0x1fffffffU,tag=a&~0xfffU;
 JfgTimingCacheLine* line=&s->instruction_cache[(a>>5)&511U];
 ++s->cache_counters[0];
 if(line->valid && line->tag==tag){++s->cache_counters[1];return 1;}
 ++s->cache_counters[2];line->valid=1;line->tag=tag;return 48;
}
static JFG_CLOCK_INLINE unsigned jfg_clock_data(JfgOriginalTimingFast* s,unsigned address,unsigned write) {
 unsigned a,tag,cost=1;JfgTimingCacheLine* line;
 address=jfg_clock_address(s,address);a=address&0x1fffffffU;tag=a&~0xfffU;
 ++s->cache_counters[write?4:3];
 if((address&0xe0000000U)!=0x80000000U){++s->cache_counters[8];return 1;}
 line=&s->data_cache[(a>>4)&511U];
 if(line->valid && line->tag==tag)++s->cache_counters[5];
 else {
  ++s->cache_counters[6];cost=40;
  if(line->valid && line->dirty){++s->cache_counters[7];cost+=40;}
  line->valid=1;line->dirty=0;line->tag=tag;
 }
 if(write)line->dirty=1;
 return cost;
}
// Refresh only at the fully checked CPU/device handler. Clock, pending state and
// deadlines cannot change in ordinary generated instructions. CPU register writes
// and ERET invalidate the certificate; live Status and I/O revision are checked
// at every instruction. The bounded poll interval and all instruction metadata
// boundaries remain intact. This caches eligibility, never elapsed time.
static JFG_CLOCK_INLINE void jfg_native_timing_refresh(JfgOriginalTimingFast* s,
    const recomp_context* cpu) {
 s->native_fast_ready=false;
 if(!s->diagnostic_host_clock || !cpu || s->guest_eret_boundary ||
    s->execution_fast_deadline<=s->cpu_count ||
    s->execution_fast_revision!=*s->io_revision ||
    ((cpu->status_reg&7U)==1U &&
     (s->execution_fast_pending&cpu->status_reg&0xff00U)!=0U))return;
 if(!s->play_mode) {
  if(s->observed_guest_instructions>=24000000000ULL)return;
  uint64_t remaining=24000000000ULL-s->observed_guest_instructions+1U;
  if(remaining<s->host_clock_poll_budget)s->host_clock_poll_budget=(unsigned)remaining;
 }
 s->native_fast_status=cpu->status_reg;
 s->native_fast_ready=true;
}
// Generated spans contain only register arithmetic and dynamically validated
// cached RDRAM accesses. They cannot change Status, I/O revision, pending events
// or the clock. Calls, branches, CACHE/CP0, labels and observers are boundaries.
// Admission reserves enough of the existing sampling quantum for every member.
static JFG_CLOCK_INLINE bool jfg_native_timing_span_begin(unsigned flags,unsigned count,void* context) {
 JfgOriginalTimingFast* s=jfg_original_timing_state;
 return s && context && s->native_spans_enabled && s->diagnostic_host_clock &&
   count>=2U && count<=16U && (flags&~0x100U)==0U &&
   s->native_fast_ready && s->host_clock_poll_budget>count &&
   s->native_fast_status==((recomp_context*)context)->status_reg &&
   s->execution_fast_revision==*s->io_revision &&
   ((flags&0x100U)==0U || (s->native_fast_status&0x20000000U)!=0U);
}
static JFG_CLOCK_INLINE bool jfg_native_timing_span_ram(uint64_t address,unsigned width) {
 // Match generated full-width address arithmetic, not a truncating virtual
 // address test. Only permanently mapped cached RDRAM can avoid MMIO traps.
 return (width==1U || width==2U || width==4U || width==8U) &&
   address>=UINT64_C(0xffffffff80000000) &&
   address<=UINT64_C(0xffffffff80400000)-width &&
   (address&(width-1U))==0U;
}
static JFG_CLOCK_INLINE void jfg_native_timing_span_commit(unsigned first_pc,unsigned last_pc,unsigned last_word,unsigned count) {
 JfgOriginalTimingFast* s=jfg_original_timing_state;
 // Caller commits a nonempty executed prefix, or the whole admitted span.
 // No externally observable instruction or host callback occurs before this.
 bool delay=count==1U && s->guest_previous_branch && first_pc==s->guest_last_pc+4U;
 s->host_clock_poll_budget-=count;
 s->observed_guest_instructions+=count;s->execution_fast_hits+=count;
 s->native_span_instructions+=count;++s->native_span_commits;
 *s->io_guest_count=s->cpu_count;
 s->guest_last_pc=last_pc;s->guest_last_word=last_word;
 s->guest_previous_branch=false;s->guest_previous_delay=delay;
}

static JFG_CLOCK_INLINE void jfg_native_timing_step(unsigned metadata,unsigned pc,unsigned word,void* context) {
 JfgOriginalTimingFast* s=jfg_original_timing_state;
 unsigned kind=(metadata>>12U)&3U;
 if(s && context && kind!=3U && (metadata&0xa00U)==0U &&
    s->native_fast_ready && s->host_clock_poll_budget>1U &&
    s->native_fast_status==((recomp_context*)context)->status_reg &&
    s->execution_fast_revision==*s->io_revision &&
    ((metadata&0x100U)==0U || (s->native_fast_status&0x20000000U)!=0U)) {
  bool delay=s->guest_previous_branch && pc==s->guest_last_pc+4U;
  --s->host_clock_poll_budget;
  ++s->observed_guest_instructions;++s->execution_fast_hits;
  *s->io_guest_count=s->cpu_count;
  s->guest_last_pc=pc;s->guest_last_word=word;
  s->guest_previous_delay=delay;s->guest_previous_branch=(metadata&0x400U)!=0U;
  return;
 }
 jfg_phase9_execution_probe_predecoded(metadata,pc,word,context);
}
// Forced inlining of the cache model substantially expands generated code
// under MSVC. Keep one callable copy per translation unit; native instruction
// and span checks stay inline, and all modeled costs and fallbacks remain.
#ifdef __cplusplus
[[maybe_unused]]
#endif
static JFG_CLOCK_NOINLINE void jfg_original_timing_step(unsigned metadata,unsigned pc,unsigned word,void* context) {
 JfgOriginalTimingFast* s=jfg_original_timing_state;
 unsigned kind=(metadata>>12U)&3U;
 // CACHE instructions and every event/observer boundary retain the fully
// checked native handler. Constant instruction operands fold at generation sites.
 if(s && context && kind!=3U && (s->execution_fast_profile_ready ||
    (s->diagnostic_host_clock && s->host_clock_poll_budget>1U)) &&
    !s->guest_eret_boundary && (metadata&0x800U)==0U &&
    (s->play_mode || s->observed_guest_instructions<24000000000ULL) &&
    s->execution_fast_deadline>s->cpu_count && s->execution_fast_revision==*s->io_revision) {
  recomp_context* cpu=(recomp_context*)context;
  bool fpu=(metadata&0x100U)!=0U;
  bool eligible=(cpu->status_reg&7U)==1U && (s->execution_fast_pending&cpu->status_reg&0xff00U)!=0U;
  if(!eligible && !(fpu && (cpu->status_reg&0x20000000U)==0U) && (metadata&0x200U)==0U) {
   bool delay=s->guest_previous_branch && pc==s->guest_last_pc+4U;
   if(s->diagnostic_host_clock) {
    // Ordinary native instructions carry no emulated execution penalty.
    // A bounded budget returns to the host clock/device handler; hardware,
    // observer, exception and interrupt checks above are never bypassed.
    --s->host_clock_poll_budget;
   } else {
    uint64_t cost=jfg_clock_fetch(s,pc)+((metadata>>16U)&127U);
    if(kind==1U || kind==2U) {
     unsigned reg=(word>>21U)&31U;uint64_t value=0;
     if(reg)memcpy(&value,(const unsigned char*)cpu+offsetof(recomp_context,r1)+(reg-1)*sizeof(uint64_t),sizeof(value));
     cost+=jfg_clock_data(s,(uint32_t)value+(uint32_t)(int32_t)(int16_t)word,kind==2U);
    }
    s->cache_counters[10]+=cost;
    cost+=s->diagnostic_cpu_half_tick;
    s->cpu_count+=cost/2U;s->diagnostic_cpu_half_tick=cost%2U;
   }
   ++s->observed_guest_instructions;++s->execution_fast_hits;
   *s->io_guest_count=s->cpu_count;
   s->guest_last_pc=pc;s->guest_last_word=word;
   s->guest_previous_delay=delay;s->guest_previous_branch=(metadata&0x400U)!=0U;
   return;
  }
 }
 jfg_phase9_execution_probe_predecoded(metadata,pc,word,context);
}
#ifndef __cplusplus
// Generated C retains its existing hook ABI and source/object inventory.
#define jfg_phase9_execution_probe_predecoded(m,p,w,c) do { if (jfg_original_timing_state && jfg_original_timing_state->diagnostic_host_clock) jfg_native_timing_step(m,p,w,c); else if ((m)&0x800000U) jfg_original_timing_step(m,p,w,c); else (jfg_phase9_execution_probe_predecoded)(m,p,w,c); } while (0)
#endif
#undef JFG_CLOCK_INLINE
#undef JFG_CLOCK_NOINLINE
