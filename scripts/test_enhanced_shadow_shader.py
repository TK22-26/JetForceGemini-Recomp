"""Run the Enhanced shadow shader against analytic surfaces on D3D12 WARP.

Requires Windows, MSVC and the pinned DXC. Outputs stay in --output; no ROM used.
This opt-in GPU-API test is separate from the portable component test suite.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dxc", type=Path, required=True)
    parser.add_argument("--vcvars", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This qualification uses D3D12 WARP on Windows")
    root = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for tool in (args.dxc, args.vcvars):
        if not tool.is_file():
            parser.error(f"Missing tool: {tool}")
    source = root / "tests/enhanced_shadow_shader_tests.cpp"
    shader = root / "tests/enhanced_shadow_shader_tests.hlsl"
    binary = out / "check.dxil"
    executable = out / "check.exe"
    batch = out / "build.cmd"
    batch.write_text(
        '@echo off\ncall "' + str(args.vcvars.resolve()) + '" >nul\n'
        'if errorlevel 1 exit /b %errorlevel%\n'
        'cl /nologo /EHsc /std:c++20 /O2 "' + str(source) +
        '" /Fe:check.exe /link d3d12.lib dxgi.lib\n', encoding="utf-8")
    env = dict(os.environ)
    temp = out / "temp"
    temp.mkdir(exist_ok=True)
    env["TMP"] = env["TEMP"] = str(temp)
    jobs = [
        ("shader", [str(args.dxc.resolve()), "-E", "Check", "-T", "cs_6_3",
                    "-Wno-ignored-attributes", "-I", str(root / "src/renderer"),
                    str(shader), "-Fo", str(binary)]),
        ("cpp", [os.environ["COMSPEC"], "/d", "/c", str(batch)]),
        ("warp", [str(executable), str(binary)]),
    ]
    result = {"source_sha256": hashlib.sha256(
        (root / "src/renderer/enhanced_shadow.hlsl").read_bytes()).hexdigest(),
        "steps": []}
    for label, command in jobs:
        with (out / (label + ".log")).open("w", encoding="utf-8") as log:
            run = subprocess.run(command, cwd=out, env=env, stdout=log,
                                 stderr=subprocess.STDOUT, timeout=120,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        result["steps"].append({"step": label, "exit_code": run.returncode})
        (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if run.returncode:
            return run.returncode
    print((out / "warp.log").read_text(encoding="utf-8").strip())
    return 0

if __name__ == "__main__":
    sys.exit(main())
