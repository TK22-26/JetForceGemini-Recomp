"""Extract a pinned bounded integer leaf; generated game code stays private."""
import argparse,hashlib,json
from pathlib import Path
try:
 from .prepare_native_collision import Source,extract
except ImportError:
 from prepare_native_collision import Source,extract
SPEC=Source("shadow_filter","fn_004_0008_recomp.c","fn_004_0008_recomp","dc5adbd4ab4b3821c00c64038fc65133b633d0c538eaff2e99b5cd54b5389ad6",6)
def generate(root,output):
 source=(root/'baseline'/SPEC.filename).read_text(encoding='utf-8')
 if 'LOOKUP_FUNC' in source:raise ValueError('Shadow filter must remain a closed leaf')
 body=extract(source,SPEC)
 if 'LOOKUP_FUNC' in body:raise ValueError('Shadow filter must remain a closed leaf')
 output.parent.mkdir(parents=True,exist_ok=True)
 output.write_text('// Private locally generated body. Do not publish.\n'+body,encoding='utf-8',newline='\n')
 receipt={'schema':1,'source_sha256':SPEC.sha256,'body_sha256':hashlib.sha256(body.encode()).hexdigest()}
 output.with_suffix(output.suffix+'.json').write_text(json.dumps(receipt,indent=2)+'\n')
 return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--generated-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 print(json.dumps(generate(a.generated_root,a.output)))
