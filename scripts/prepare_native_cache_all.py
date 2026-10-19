"""Extract a pinned coherent cache-maintenance leaf; generated game code stays private."""
import argparse,hashlib,json
from pathlib import Path
try:
 from .prepare_native_collision import Source,extract
except ImportError:
 from prepare_native_collision import Source,extract
SPEC=Source("cache_all","fn_000_1568_recomp.c","fn_000_1568_recomp","383c3f9c9fe50e4ea30dfa23eaa959902544eb334d1f6640b7f4d66eb2d8ca62",1)
def generate(root,output):
 source=(root/'baseline'/SPEC.filename).read_text(encoding='utf-8')
 if 'LOOKUP_FUNC' in source:raise ValueError('Cache maintenance must remain a closed leaf')
 body=extract(source,SPEC)
 call='cache_op(rdram, ctx, 1, ctx->r8 + 0);'
 if body.count(call)!=1 or 'MEM_' in body:raise ValueError('Unexpected cache leaf memory/operation')
 body=body.replace(call,'if (!jfg::boot::reference_coherent_cache_operation(1U, ctx->r8, 0x400000U)) std::terminate();')
 if 'cache_op(' in body:raise ValueError('Unhandled cache operation')
 if 'LOOKUP_FUNC' in body:raise ValueError('Cache maintenance must remain a closed leaf')
 output.parent.mkdir(parents=True,exist_ok=True)
 output.write_text('// Private locally generated body. Do not publish.\n'+body,encoding='utf-8',newline='\n')
 receipt={'schema':1,'source_sha256':SPEC.sha256,'body_sha256':hashlib.sha256(body.encode()).hexdigest()}
 output.with_suffix(output.suffix+'.json').write_text(json.dumps(receipt,indent=2)+'\n')
 return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--generated-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 print(json.dumps(generate(a.generated_root,a.output)))
