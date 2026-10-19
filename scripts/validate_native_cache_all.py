"""Differentially qualify the coherent cache walk against private original C."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--generated-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 root=Path(__file__).resolve().parents[1];g=a.generated_root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 cl=shutil.which('cl.exe')
 if not cl:p.error('Run from an x64 MSVC developer shell.')
 subprocess.run([sys.executable,str(root/'scripts/prepare_native_cache_all.py'),'--generated-root',str(g),'--output',str(out/'cache.inc')],check=True,timeout=30)
 shutil.copy2(root/'include/jfg/boot/original_timing_fast.h',out/'timing.h')
 raw=(g/'baseline/fn_000_1568_recomp.c').read_text();unit=out/'reference.c';unit.write_text(raw.replace('#include "funcs.h"','#include "timing.h"').replace('fn_000_1568_recomp','cache_all_reference'))
 common=['/nologo','/O2','/Ob2','/fp:precise','/DNDEBUG','/MD','/wd4702','/I'+str(out),'/I'+str(g/'include'),'/I'+str(root/'include')]
 with (out/'build.log').open('w') as log:
  for args in [[cl,*common,'/std:c11','/c',str(unit),'/Fo'+str(out/'reference.obj')],
   [cl,*common,'/std:c++20','/EHs','/DJFG_NATIVE_CACHE_ALL_ENABLED=1','/DJFG_NATIVE_CACHE_ALL_BODY="'+str(out/'cache.inc').replace('\\','/')+'"','/c',str(root/'src/boot/native_cache_all.cpp'),'/Fo'+str(out/'native.obj')],
   [cl,*common,'/std:c++20','/EHs','/DJFG_NATIVE_CACHE_ALL_ENABLED=1',str(root/'tests/native_cache_all_reference.cpp'),str(out/'reference.obj'),str(out/'native.obj'),'/Fe'+str(out/'fixture.exe'),'/Fo'+str(out/'fixture.obj')]]:
   subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
 run=subprocess.run([str(out/'fixture.exe')],capture_output=True,text=True,timeout=180)
 result={'passed':run.returncode==0,'stdout':run.stdout,'stderr':run.stderr,'cases':512,'full_context_and_ram':run.returncode==0,'source_sha256':hashlib.sha256(raw.encode()).hexdigest()}
 (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True);run.check_returncode()
if __name__=='__main__':main()
