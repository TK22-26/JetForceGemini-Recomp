"""Compare native resident math against locally generated C; keep outputs private.
Run from an x64 MSVC developer environment with the retained generated root.
"""

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"

from pathlib import Path
import argparse,hashlib,json,shutil,subprocess

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument("--generated-root",type=Path,required=True)
 parser.add_argument("--output",type=Path,required=True)
 args=parser.parse_args()
 root=Path(__file__).resolve().parents[2];generated=args.generated_root.resolve()
 out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
 cl=shutil.which("cl.exe")
 if not cl:parser.error("Run from an x64 MSVC developer environment.")
 shutil.copy2(root/"include/jfg/boot/original_timing_fast.h",out/"timing.h")
 common=["/nologo","/O2","/Ob2","/fp:precise","/DNDEBUG","/MD",
  "/I"+str(out),"/I"+str(generated/"include"),"/I"+str(root/"include")]
 from scripts.regional.native_operations import load
 operations,bindings,descriptor=load(generated)
 sections={row['id']:row for row in descriptor['model']['sections']}
 def address(category,name):
  ref=bindings[category][name];section=sections[ref['section']]
  base=section['linked_vram']
  if category=='data':base+=section['text_size']+(section['data_size'] if ref['domain']=='bss' else 0)
  return base+ref['offset']
 coordinates=[address('data','math.sineTable'),address('data','math.atanTable'),
  address('instructions','math.angle_direct_return'),address('instructions','math.angle_return'),
  address('code','game.mathDiffAngle'),address('instructions','math.diff_return'),
  address('instructions','math.diff_subtract_return'),address('instructions','math.diff_add_return'),
  address('code','game.Cosf'),address('code','game.Sinf'),address('instructions','math.trig_return')]
 (out/'math-layout.hpp').write_text('inline constexpr JfgNativeMathLayout kMathLayout{'+','.join(hex(x)+'U' for x in coordinates)+'};\n')
 definitions=[]
 for name,operation,call,kind in (
  ('angle','game.Arctanf','jfg_native_angle_try(kMathLayout,ram,ctx)',0),
  ('diff','game.mathDiffAngle','jfg_native_angle_diff_try(kMathLayout,ram,ctx)',1),
  ('sin','game.Sinf','jfg_native_trig_try(kMathLayout,ram,ctx,false)',2),
  ('cos','game.Cosf','jfg_native_trig_try(kMathLayout,ram,ctx,true)',3)):
  row=operations['operations'][operation];definitions.append((name,row['source'],row['symbol'],call,kind))
 results=[]
 for name,relative,symbol,call,kind in definitions:
  case=out/name;case.mkdir();reference=generated/relative
  source=reference.read_text().replace('#include "funcs.h"','#include "timing.h"')
  if source.count("void "+symbol+"(")!=1:raise ValueError("Unexpected generated reference: "+relative)
  for role in ("reference","original"):(case/(role+".c")).write_text(source.replace(symbol,"math_"+role))
  (case/"candidate.cpp").write_text('#include "timing.h"\n#include "jfg/boot/native_resident_math.h"\n#include "math-layout.hpp"\nextern "C" void math_original(uint8_t*,recomp_context*);\nextern "C" void math_candidate(uint8_t* ram,recomp_context* ctx) {if(!'+call+')math_original(ram,ctx);}\n')
  with (case/"build.log").open("w") as log:
   for unit in ("reference","original"):
    subprocess.run([cl,*common,"/std:c11","/c",str(case/(unit+".c")),"/Fo"+str(case/(unit+".obj"))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
   subprocess.run([cl,*common,"/std:c++20","/EHsc","/c",str(case/"candidate.cpp"),"/Fo"+str(case/"candidate.obj")],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
   subprocess.run([cl,*common,"/std:c++20","/EHsc","/DJFG_MATH_FIXTURE_KIND="+str(kind),
     str(root/"tests/boot/native_resident_math_reference.cpp"),
     *[str(case/(x+".obj"))for x in ("reference","original","candidate")],
     "/Fe"+str(case/"fixture.exe"),"/Fo"+str(case/"main.obj")],
     stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
  result=subprocess.run([str(case/"fixture.exe")],capture_output=True,text=True,timeout=120)
  item={"helper":name,"returncode":result.returncode,"output":result.stdout+result.stderr,
        "reference_sha256":hashlib.sha256(reference.read_bytes()).hexdigest()}
  results.append(item);(out/"results.json").write_text(json.dumps(results,indent=2))
  print(json.dumps(item),flush=True);result.check_returncode()
 (out/"result.json").write_text(json.dumps({"passed":True,"cases":400000,"references":"Private locally generated C","cpu_timing_fenv_ram_exact":True},indent=2))
 return 0
if __name__=="__main__":raise SystemExit(main())
