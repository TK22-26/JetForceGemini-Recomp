"""Pinned context-save/restore MI-mask accesses; retain every timing boundary.

The interrupt-entry variant also retains the separately qualified SP accesses.
This candidate therefore requires the direct-SP diagnostic switch. Unsupported
device states and reference-clock execution use the existing mapped fallback.
"""
import argparse,hashlib,json,re
from pathlib import Path
from prepare_direct_sp_access import rewrite as rewrite_sp

SPECS = [
 ('fn_000_1226_recomp','a114af99d0c07bb3996029768d3d12c23c1e7af36fcfe761518bef661bce7827',0x80075030,0x8007514c,0x8d29000c,9,9,12,2),
 ('fn_000_1231_recomp','40bd34136aa399dfe6a55e9f07c177411178188fa2b977fd2b0a8f86c67fecc2',0x80075698,0x80075764,0x8f7b000c,27,27,12,1),
 ('fn_000_1235_recomp','42b1bc35ca062fde5c1779d9d334c4f6bbf07fec53385cbba4ce292c3dcce274',0x80075808,0x800759ac,0xaf5b0000,26,27,0,2),
]
COMMENT=re.compile(r'^\s*// (?:native )?0x([0-9a-f]{8}):[^\n]*',re.I|re.M)
HOOK=re.compile(r'jfg_phase9_execution_probe_predecoded\(0x[0-9a-f]+U, 0x([0-9a-f]+)U, 0x([0-9a-f]+)U, ctx\);',re.I)
def rewrite(source,spec):
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
 if name=='fn_000_1226_recomp':
  source,_=rewrite_sp(source,name)
  source=source.replace('static void sp_access_'+name+'(','static void mi_mask_'+name+'(')
 else:
  if source.count('RECOMP_FUNC void '+name+'(')!=1:raise ValueError('Changed function entry')
  source=source.replace('#include "recomp.h"','').replace('#include "funcs.h"','')
  source=source.replace('RECOMP_FUNC void '+name+'(','static void mi_mask_'+name+'(')
 if HOOK.findall(source)!=before_hooks:raise ValueError('Instruction hooks changed')
 return source
def generate(root,output):
 chunks=[];receipt=[]
 for spec in SPECS:
  name,digest,target,*_=spec;source=(root/'baseline'/(name+'.c')).read_text(encoding='utf-8')
  if hashlib.sha256(source.encode()).hexdigest()!=digest:raise ValueError('Pinned routine differs: '+name)
  chunks.append(rewrite(source,spec));receipt.append({'name':name,'sha256':digest,'target':target,'pc':spec[3],'instances':spec[-1]})
 chunks.append('bool mi_mask_dispatch(std::uint32_t target,std::uint8_t* ram,recomp_context* cpu) { switch(target) {')
 for name,digest,target,*_ in SPECS:chunks.append('case '+hex(target)+'U: mi_mask_'+name+'(ram,cpu);return true;')
 chunks.append('default:return false;}}')
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text('\n'.join(chunks),encoding='utf-8',newline='\n')
 output.with_suffix(output.suffix+'.json').write_text(json.dumps(receipt,indent=2)+'\n')
 return receipt
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--generated-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args();print(json.dumps(generate(a.generated_root,a.output)))
