"""Create private probe-preserving SP access variants from pinned local inputs."""

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"

import argparse,hashlib,json,re
from pathlib import Path
OPERATIONS=('native.exception_entry','native.sp_status_set','native.sp_pc_set','native.sp_dma','native.sp_busy','native.sp_status_get')
from scripts.regional.native_operations import load,source as operation_source
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
 document,_,_=load(root);chunks=[];receipt=[];selected=[]
 for operation in OPERATIONS:
  source,row=operation_source(root,document,operation);name=row['symbol'];digest=row['source_sha256'];target=row['entry_pc']
  body,counts=rewrite(source,name);chunks.append(body);selected.append((name,target))
  receipt.append({'operation':operation,'name':name,'target':target,'sha256':digest,**counts})
 chunks.append('bool sp_access_dispatch(std::uint32_t target,std::uint8_t* ram,recomp_context* cpu) { switch(target) {')
 for name,target in selected:chunks.append('case '+hex(target)+'U: sp_access_'+name+'(ram,cpu);return true;')
 chunks.append('default:return false;}}')
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text('\n'.join(chunks),encoding='utf-8',newline='\n')
 output.with_suffix(output.suffix+'.json').write_text(json.dumps(receipt,indent=2)+'\n')
 return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--generated-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(generate(a.generated_root,a.output)))
