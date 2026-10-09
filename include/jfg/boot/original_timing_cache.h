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
#if defined(_MSC_VER)
#define JFG_TIMING_INLINE __forceinline
#else
#define JFG_TIMING_INLINE inline __attribute__((always_inline))
#endif
// Instruction/cache cost model qualified against the accepted Quarry runtime.
// Values describe modeled VR4300 operations; this file contains no game data.
#include "recomp.h"
// Generated funcs.h already supplies the identical private ABI copy.
// Standalone model tests include the public header directly.
#ifndef JFG_ORIGINAL_TIMING_GENERATION
#include "jfg/boot/original_timing_fast.h"
#endif
typedef JfgTimingCacheLine CacheLine;
static CacheLine ic[512],dc[512];
/* instructions, I hits, I misses, reads, writes, D hits, D misses,
   writebacks, uncached accesses, cache operations, modeled CPU cycles, unknown ops */
static uint64_t cache_stats[12];
static uint8_t* cache_rdram;
static JFG_TIMING_INLINE unsigned cache_address(unsigned a,unsigned data) {
 unsigned section,table,base,slot;
 (void)data;
 if(a>=0x10000000U || a<0x100000U)return a;
 section=a>>20;slot=(section<158U && section!=21U && section!=56U)?section:0U;
 if(!slot||!cache_rdram){++cache_stats[11];return a;}
 table=*(unsigned*)(cache_rdram+0xfeaa0U);
 if(table<0x80000000U||table>=0x80400000U-157U*32U){++cache_stats[11];return a;}
 base=*(unsigned*)(cache_rdram+(table&0x1fffffffU)+slot*32U);
 if(base<0x80000000U||base>=0x80400000U){++cache_stats[11];return a;}
 return base+(a&0xfffffU);
}
void jfg_full_cache_snapshot(uint64_t* p) { unsigned i;for(i=0;i<12;i++)p[i]=cache_stats[i]; }
static JFG_TIMING_INLINE unsigned cache_fetch(unsigned pc) {
 pc=cache_address(pc,0);
 unsigned a=pc&0x1fffffff,tag=a&~0xfffU;CacheLine* l=&ic[(a>>5)&511];
 ++cache_stats[0];
 if(l->valid&&l->tag==tag) { ++cache_stats[1];return 1; }
 else { ++cache_stats[2];l->valid=1;l->tag=tag;return 48; }
}
static JFG_TIMING_INLINE unsigned cache_data(unsigned address,unsigned write) {
 address=cache_address(address,1);
 unsigned cost=1;
 unsigned a=address&0x1fffffff,tag=a&~0xfffU;CacheLine* l;
 ++cache_stats[write?4:3];
 if((address&0xe0000000U)!=0x80000000U) {++cache_stats[8];return 1;}
 l=&dc[(a>>4)&511];
 if(l->valid&&l->tag==tag) {++cache_stats[5];}
 else {
  ++cache_stats[6];cost=40;
  if(l->valid&&l->dirty){++cache_stats[7];cost+=40;}
  l->valid=1;l->dirty=0;l->tag=tag;
 }
 if(write)l->dirty=1;
 return cost;
}
static unsigned cache_operation(unsigned op,unsigned address) {
 address=cache_address(address,1);
 unsigned cost=0;
 unsigned a=address&0x1fffffff,tag=a&~0xfffU;CacheLine* l;unsigned hit;
 ++cache_stats[9];
 if((op&1)==0) {
  l=&ic[(a>>5)&511];hit=l->valid&&l->tag==tag;
  if(op==0)l->valid=0;
  else if(op==0x10){if(hit)l->valid=0;}
  else if(op==0x14){l->valid=1;l->tag=tag;cost+=48;}
  else if(op==0x18){if(hit)cost+=48;}
  else ++cache_stats[11];
 } else {
  l=&dc[(a>>4)&511];hit=l->valid&&l->tag==tag;
  if(op==1||op==0x15||op==0x19) {
   if((op==1?l->valid:hit)&&l->dirty){++cache_stats[7];cost+=40;l->dirty=0;}
   if(op==1||(op==0x15&&hit))l->valid=0;
  } else if(op==0x11){if(hit){l->valid=0;l->dirty=0;}}
  else ++cache_stats[11];
 }
 return cost;
}

static unsigned integer_extra_cost(unsigned operation) {
 switch(operation) {
 case 24U: case 25U: return 4U;
 case 28U: case 29U: return 7U;
 case 26U: case 27U: return 36U;
 case 30U: case 31U: return 68U;
 default:return 0U;
 }
}
static unsigned floating_extra_cost(unsigned format,unsigned operation) {
 switch(format) {
 case 16U:
  switch(operation) {
  case 0U:  case 1U: return 2U;
  case 2U:  case 8U:  case 9U:  case 10U:  case 11U:  case 12U:  case 13U:  case 14U:  case 15U:  case 36U:  case 37U: return 4U;
  case 3U:  case 4U: return 28U;
  default:return 0U;
  }
 case 17U:
  switch(operation) {
  case 32U: return 1U;
  case 0U:  case 1U: return 2U;
  case 8U:  case 9U:  case 10U:  case 11U:  case 12U:  case 13U:  case 14U:  case 15U:  case 36U:  case 37U: return 4U;
  case 2U: return 7U;
  case 3U:  case 4U: return 57U;
  default:return 0U;
  }
 case 20U:
  switch(operation) {
  case 32U:  case 33U: return 4U;
  default:return 0U;
  }
 case 21U:
  switch(operation) {
  case 32U:  case 33U: return 4U;
  default:return 0U;
  }
 default:return 0U;
 }
}

static_assert(offsetof(recomp_context,r31)-offsetof(recomp_context,r1)==30*sizeof(uint64_t));
static JFG_TIMING_INLINE uint32_t reg_value(recomp_context* ctx,unsigned reg) {
 if(reg==0)return 0;
 if(reg>31)abort();
 uint64_t value;
 memcpy(&value,(const unsigned char*)ctx+offsetof(recomp_context,r1)+(reg-1)*sizeof(uint64_t),sizeof(value));
 return (uint32_t)value;
}


JFG_TIMING_INLINE uint64_t jfg_full_cache_cost(unsigned pc,unsigned word,void* context,uint8_t* rdram) {
 recomp_context*ctx=(recomp_context*)context;unsigned primary=word>>26,extra=0;
 cache_rdram=rdram;unsigned cost=cache_fetch(pc);
 if(primary==0)extra=integer_extra_cost(word&63U);
 else if(primary==17)extra=floating_extra_cost((word>>21)&31U,word&63U);
 cost+=extra;
 switch(primary) {
 case 0x1a:case 0x1b:
 case 0x20:case 0x21:case 0x22:case 0x23:case 0x24:case 0x25:case 0x26:case 0x27:
 case 0x30:case 0x31:case 0x34:case 0x35:case 0x37:
  cost+=cache_data(reg_value(ctx,(word>>21)&31U)+(uint32_t)(int32_t)(int16_t)word,0);break;
 case 0x28:case 0x29:case 0x2a:case 0x2b:case 0x2c:case 0x2d:case 0x2e:
 case 0x38:case 0x39:case 0x3c:case 0x3d:case 0x3f:
  cost+=cache_data(reg_value(ctx,(word>>21)&31U)+(uint32_t)(int32_t)(int16_t)word,1);break;
 case 0x2f:
  cost+=cache_operation((word>>16)&31U,reg_value(ctx,(word>>21)&31U)+(uint32_t)(int32_t)(int16_t)word);break;
 default:break;
 }
 cache_stats[10]+=cost;return cost;
}

int jfg_full_cache_idle_skip(unsigned pc,uint64_t count_ticks,uint8_t* rdram) {
 unsigned a,b;CacheLine *x,*y;cache_rdram=rdram;
 a=cache_address(pc,0)&0x1fffffffU;b=cache_address(pc+4U,0)&0x1fffffffU;
 x=&ic[(a>>5)&511U];y=&ic[(b>>5)&511U];
 if(!x->valid||x->tag!=(a&~0xfffU)||!y->valid||y->tag!=(b&~0xfffU))return 0;
 if(count_ticks>UINT64_MAX/2U)return 0;
 cache_stats[0]+=count_ticks*2U;cache_stats[1]+=count_ticks*2U;cache_stats[10]+=count_ticks*2U;
 return 1;
}

JFG_TIMING_INLINE uint64_t jfg_full_cache_cost_predecoded(unsigned pc,unsigned word,
    void* context,uint8_t* rdram,unsigned metadata) {
 auto* ctx=static_cast<recomp_context*>(context);
 cache_rdram=rdram;
 uint64_t cost=cache_fetch(pc)+((metadata>>16U)&127U);
 switch((metadata>>12U)&3U) {
 case 1U:cost+=cache_data(reg_value(ctx,(word>>21U)&31U)+(uint32_t)(int32_t)(int16_t)word,0);break;
 case 2U:cost+=cache_data(reg_value(ctx,(word>>21U)&31U)+(uint32_t)(int32_t)(int16_t)word,1);break;
 case 3U:cost+=cache_operation((word>>16U)&31U,reg_value(ctx,(word>>21U)&31U)+(uint32_t)(int32_t)(int16_t)word);break;
 default:break;
 }
 cache_stats[10]+=cost;return cost;
}

#undef JFG_TIMING_INLINE
