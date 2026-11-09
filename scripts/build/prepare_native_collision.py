"""Derive the qualified collision closure from owner-generated private code.

No game instructions are stored in this script. Revision-qualified owners select sources through the generated operation map.
Source digests and closed call graphs are checked before extraction.
Generated output belongs in the private build tree.
"""

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"

from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path
import re

@dataclass(frozen=True)
class Source:
    name: str
    filename: str
    symbol: str
    sha256: str
    spans: int

OPERATIONS = (("bsp","overlay.collision.accessor"),("split","native.collision_split"),("line","native.collision_line"))

def selected_source(root,operation,alias):
    from scripts.regional.native_operations import load,source
    document,_,_=load(root);text,row=source(root,document,operation)
    return text,Source(alias,row['source'],row['symbol'],row['source_sha256'],text.count('JFG_NATIVE_TIMING_SPAN'))

SPAN = re.compile(
    r"    \{ /\* JFG_NATIVE_TIMING_SPAN \*/\n.*?"
    r"    goto jfg_native_span_(\d+)_done;\n    \}\n"
    r"(.*?)jfg_native_span_\1_done:;\n    \}", re.S)

def extract(source: str, spec: Source, calls=None) -> str:
    if hashlib.sha256(source.encode()).hexdigest() != spec.sha256:
        raise ValueError(f"Unqualified collision source: {spec.filename}")
    if source.count("RECOMP_FUNC void " + spec.symbol + "(") != 1:
        raise ValueError("Unexpected collision entry definition")
    body, count = SPAN.subn(lambda match: match[2], source)
    if count != spec.spans or count != source.count("JFG_NATIVE_TIMING_SPAN"):
        raise ValueError("Incomplete collision span extraction")
    body = re.sub(r"^jfg_native_span_\d+_fallback_\d+:\s*\n", "", body, flags=re.M)
    body = re.sub(r"^\s*jfg_phase9_execution_probe_predecoded\([^\n]*\);\n",
                  "\n", body, flags=re.M)
    if "jfg_native_" in body or "jfg_phase9_" in body:
        raise ValueError("Unexpected remaining timing operation")
    body = re.sub(r"^#include.*\n", "", body, flags=re.M)
    body = body.replace(spec.symbol, spec.name + "_core")
    for address,target in (calls or {}).items():
        body = re.sub(r"LOOKUP_FUNC\(0x"+format(address,"08x")+r"\)",target,body,flags=re.I)
    if "LOOKUP_FUNC" in body or re.search(r"\bfn_\w+\s*\(", body):
        raise ValueError("Collision closure contains an unqualified call")
    return body

def generate(root: Path, output: Path) -> dict:
    from scripts.regional.native_operations import load,source
    document,_,_=load(root)
    calls={document['operations'][operation]['entry_pc']:target for operation,target in
        (("overlay.collision.accessor","bounded"),("native.collision_split","split_core"),("native.collision_line","line_core"))}
    parts, receipts = [], []
    for alias,operation in OPERATIONS:
        text,row=source(root,document,operation)
        spec=Source(alias,row['source'],row['symbol'],row['source_sha256'],text.count('JFG_NATIVE_TIMING_SPAN'))
        body = extract(text, spec, calls)
        parts.append(body)
        receipts.append({"operation":operation,"file":spec.filename,"source_sha256":spec.sha256,
                         "body_sha256":hashlib.sha256(body.encode()).hexdigest()})
    text = "// Private, locally generated collision bodies. Do not publish.\n" + "\n".join(parts)
    receipt = {"schema": 1, "sources": receipts,
               "output_sha256": hashlib.sha256(text.encode()).hexdigest()}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(output)
    output.with_suffix(output.suffix + ".json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = generate(args.generated_root, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(receipt))

if __name__ == "__main__":
    main()
