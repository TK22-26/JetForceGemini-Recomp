"""Extract a pinned bounded integer leaf; generated game code stays private."""

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"

import argparse,hashlib,json
from pathlib import Path
from scripts.prepare_native_collision import extract,selected_source
def generate(root,output):
 source,spec=selected_source(root,'overlay.shadows.filter','shadow_filter')
 if 'LOOKUP_FUNC' in source:raise ValueError('Shadow filter must remain a closed leaf')
 body=extract(source,spec)
 if 'LOOKUP_FUNC' in body:raise ValueError('Shadow filter must remain a closed leaf')
 output.parent.mkdir(parents=True,exist_ok=True)
 output.write_text('// Private locally generated body. Do not publish.\n'+body,encoding='utf-8',newline='\n')
 receipt={'schema':1,'source_sha256':spec.sha256,'body_sha256':hashlib.sha256(body.encode()).hexdigest()}
 output.with_suffix(output.suffix+'.json').write_text(json.dumps(receipt,indent=2)+'\n')
 return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--generated-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 print(json.dumps(generate(a.generated_root,a.output)))
