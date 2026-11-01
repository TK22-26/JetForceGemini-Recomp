"""Pinned context-save/restore MI-mask accesses; retain every timing boundary.

The interrupt-entry variant also retains the separately qualified SP accesses.
This candidate therefore requires the direct-SP diagnostic switch. Unsupported
device states and reference-clock execution use the existing mapped fallback.
"""

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"

import argparse,hashlib,json,re
from pathlib import Path
from scripts.prepare_direct_sp_access import rewrite as rewrite_sp

OPERATIONS=(('native.exception_entry','native.mi_exception'),('os.scheduler_park','native.mi_park'),('sdk.__osDispatchThread','native.mi_dispatch'))
from scripts.regional.native_operations import load,source as operation_source

COMMENT=re.compile(r'^\s*// (?:native )?0x([0-9a-f]{8}):[^\n]*',re.I|re.M)
HOOK=re.compile(r'jfg_phase9_execution_probe_predecoded\(0x[0-9a-f]+U, 0x([0-9a-f]+)U, 0x([0-9a-f]+)U, ctx\);',re.I)
def rewrite(source,spec,*,sp_variant=False):
 name,digest,target,pc,word,base,reg,offset,count=spec
 hooks=[int(m[2],16) for m in HOOK.finditer(source) if int(m[1],16)==pc]
 if hooks!=[word]:raise ValueError('Missing or changed instruction hook')
 comments=list(COMMENT.finditer(source));edits=[]
 for i,comment in enumerate(comments):
  if int(comment[1],16)!=pc:continue
  start=comment.end();end=comments[i+1].start() if i+1<len(comments) else len(source)
  body=source[start:end];address=f'U64(ctx->r{base} + {offset}U)'
  if word>>26==0x23:
   old=f'ctx->r{reg} = U64(MEM_W(ctx->r{base}, 0X{offset:X}));'
   new=f'ctx->r{reg} = U64(jfg_mmio_mask_read32(rdram, ctx, {address}));'
  else:
   old=f'MEM_W(0X{offset:X}, ctx->r{base}) = (int32_t)(ctx->r{reg});'
   new=f'jfg_mmio_mask_write32(rdram, ctx, {address}, (uint32_t)(ctx->r{reg}));'
  if body.count(old)!=1:raise ValueError('Changed MI-mask expression')
  edits.append((start,end,body.replace(old,new)))
 if len(edits)!=count:raise ValueError('Changed instruction instance count')
 before_hooks=HOOK.findall(source)
 for start,end,body in reversed(edits):source=source[:start]+body+source[end:]
 if sp_variant:
  source,_=rewrite_sp(source,name)
  source=source.replace('static void sp_access_'+name+'(','static void mi_mask_'+name+'(')
 else:
  if source.count('RECOMP_FUNC void '+name+'(')!=1:raise ValueError('Changed function entry')
  source=source.replace('#include "recomp.h"','').replace('#include "funcs.h"','')
  source=source.replace('RECOMP_FUNC void '+name+'(','static void mi_mask_'+name+'(')
 if HOOK.findall(source)!=before_hooks:raise ValueError('Instruction hooks changed')
 return source
def generate(root,output):
 document,bindings,descriptor=load(root);chunks=[];receipt=[];selected=[]
 sections={s['id']:s for s in descriptor['model']['sections']}
 for operation,instruction in OPERATIONS:
  source,row=operation_source(root,document,operation);name=row['symbol'];target=row['entry_pc']
  ins=bindings['instructions'][instruction];pc=sections[ins['section']]['linked_vram']+ins['offset'];word=ins['original_word']
  if word>>26 not in (35,43) or word&0x8000:raise ValueError('Unsupported MI-mask memory operand')
  count=sum(int(m[1],16)==pc for m in COMMENT.finditer(source))
  if count not in (1,2):raise ValueError('Missing or duplicated MI-mask instruction')
  spec=(name,row['source_sha256'],target,pc,word,(word>>21)&31,(word>>16)&31,word&65535,count)
  chunks.append(rewrite(source,spec,sp_variant=operation=='native.exception_entry'));selected.append((name,target))
  receipt.append({'operation':operation,'name':name,'sha256':row['source_sha256'],'target':target,'pc':pc,'instances':count})
 chunks.append('bool mi_mask_dispatch(std::uint32_t target,std::uint8_t* ram,recomp_context* cpu) { switch(target) {')
 for name,target in selected:chunks.append('case '+hex(target)+'U: mi_mask_'+name+'(ram,cpu);return true;')
 chunks.append('default:return false;}}')
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text('\n'.join(chunks),encoding='utf-8',newline='\n')
 output.with_suffix(output.suffix+'.json').write_text(json.dumps(receipt,indent=2)+'\n')
 return receipt
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--generated-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args();print(json.dumps(generate(a.generated_root,a.output)))
