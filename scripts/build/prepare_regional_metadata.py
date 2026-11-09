"""Build matching original ELF metadata for an identified revision; no native admission."""
from __future__ import annotations

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from scripts.rom_profiles import identify_rom, PAL_ROM, JAPAN_ROM
from scripts.regional_overlays import expand_regional_overlays
from scripts.probe_n64recomp_cpu import verify_private_work_directory

ROOT = Path(__file__).resolve().parents[2]


from scripts.regional.reconstruction import regional_splat,pal_linker_symbols,reconstruct

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--rom',type=Path,required=True);parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--decomp',type=Path,default=ROOT/'tools/upstream/Jet-Force-Gemini');parser.add_argument('--jobs',type=int,default=4);args=parser.parse_args()
    if sys.platform!='linux':parser.error('Run reconstruction in WSL/Linux')
    profile,rom,order=identify_rom(args.rom.read_bytes(),normalize=True);workspace=args.workspace.resolve();verify_private_work_directory(workspace)
    if workspace.exists() or any(c.isspace() for c in str(workspace)):raise ValueError('Choose a new private workspace without whitespace')
    workspace.mkdir(parents=True);steps=[]
    def run(name,argv,cwd):
        start=time.monotonic();print(name,flush=True)
        with (workspace/(name+'.log')).open('w') as log:p=subprocess.run(argv,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,timeout=900)
        steps.append({'name':name,'exit_code':p.returncode,'seconds':time.monotonic()-start})
        (workspace/'metadata-progress.json').write_text(json.dumps({'complete':False,'steps':steps},indent=2))
        if p.returncode:raise RuntimeError('Reconstruction stage failed: '+name)
    elf,linker_map,result=reconstruct(rom,args.decomp,workspace/'decomp',args.jobs,run)
    result.update(region=profile.code,input_byte_order=order,steps=steps,remaining=['Qualify program metadata and generation','Migrate and validate runtime integration','Qualify gameplay and persistence'])
    (workspace/'metadata.json').write_text(json.dumps(result,indent=2)+'\n');print('Matching '+profile.code+' metadata complete; native gameplay remains unqualified.',flush=True);return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:print(str(error),file=sys.stderr);raise SystemExit(1)
