"""Create private probe-preserving SP access variants from pinned local inputs."""
import argparse,hashlib,json,re
from pathlib import Path
SPECS = [('fn_000_1226_recomp', 'a114af99d0c07bb3996029768d3d12c23c1e7af36fcfe761518bef661bce7827', 2147962928), ('fn_000_1558_recomp', 'cea11682aeb9b508367b775e0eafbff3a84b5aabc3b7f0ff90aadfdebe87d521', 2148106288), ('fn_000_1643_recomp', 'fb6334c52be1cf4025d4d88a0b54293719d6097c609579cd199cdde04c0db50f', 2148120864), ('fn_000_1644_recomp', '9f1d7b0824370bc22cd2730914912788c2eb88ecc3a9965f0935e442976ecf5e', 2148120928), ('fn_000_1645_recomp', '4b2a32f472e6450ceeec6ba68d5e59dd2f52b52d6680ff093dec9b4ac0bae5c1', 2148121072), ('fn_000_1646_recomp', '5a54c2458207c36573562ce5e126d3f33df5d5a47665df6da912c889c9e31c66', 2148121120)]
def rewrite(source,name):
 if source.count('RECOMP_FUNC void '+name+'(')!=1:raise ValueError('Expected one pinned routine')
 source=source.replace('#include "recomp.h"','').replace('#include "funcs.h"','')
 source=source.replace('RECOMP_FUNC void '+name+'(','static void sp_access_'+name+'(')
 pattern=r'(?m)^(\s*)MEM_W\(([^,\n]+), ([^)]+)\) = \(int32_t\)\(([^;]+)\);'
 source,stores=re.subn(pattern,lambda m:m[1]+'jfg_sp_store_word(rdram, '+m[3]+', '+m[2]+', (int32_t)('+m[4]+'));',source)
 source,loads=re.subn(r'MEM_W\(([^,\n]+), ([^)]+)\)',r'jfg_sp_load_word(rdram, \1, \2)',source)
 if not stores+loads or 'MEM_W(' in source:raise ValueError('Missing or unhandled word access')
 return source,{'loads':loads,'stores':stores}
def generate(root,output):
 chunks=[];receipt=[]
 for name,digest,target in SPECS:
  source=(root/'baseline'/(name+'.c')).read_text(encoding='utf-8')
  if hashlib.sha256(source.encode()).hexdigest()!=digest:raise ValueError('Pinned SP routine differs: '+name)
  body,counts=rewrite(source,name);chunks.append(body)
  receipt.append({'name':name,'target':target,'sha256':digest,**counts})
 chunks.append('bool sp_access_dispatch(std::uint32_t target,std::uint8_t* ram,recomp_context* cpu) { switch(target) {')
 for name,digest,target in SPECS:chunks.append('case '+hex(target)+'U: sp_access_'+name+'(ram,cpu);return true;')
 chunks.append('default:return false;}}')
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text('\n'.join(chunks),encoding='utf-8',newline='\n')
 output.with_suffix(output.suffix+'.json').write_text(json.dumps(receipt,indent=2)+'\n')
 return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--generated-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(generate(a.generated_root,a.output)))
