#!/usr/bin/env python3
"""Derive an ignored TRP1-v2 runtime-trap case from normalized sources.

The reviewed ledger is JSON: {"schema_version":1,"kind":"jfg-g2-trap-ledger",
"source_inventory_sha256":"…","records":[{"class":"checksum", "reachability":"reachable",
"behavior_sha256":"…","provenance_sha256":"…"}]}.  The four ledger
classes are boot-self-check, dangling-jump-workaround, checksum, anti-tamper.
Optional overrides use the same record shape and match the full class plus
behavior/provenance binding. No locator, generated symbol, or address is emitted.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, struct, subprocess
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{64}$")
ROOT = Path(__file__).resolve().parents[1]
KIND = {"cpu-break": 1, "cpu-syscall": 2, "switch-bounds": 3,
        "boot-self-check": 4, "dangling-jump-workaround": 5, "checksum": 6, "anti-tamper": 7}
BRIDGES = (("do_break", "cpu-break"), ("recomp_syscall_handler", "cpu-syscall"),
           ("switch_error", "switch-bounds"))
LEDGER = set(KIND) - {"cpu-break", "cpu-syscall", "switch-bounds"}

class Reject(Exception): pass
def digest(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def reparse(path: Path) -> bool:
    try: return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)
    except FileNotFoundError: return False
    except OSError: return True
def safe_components(path: Path) -> None:
    absolute=path.absolute()
    for current in (absolute, *absolute.parents):
        if reparse(current): raise Reject()
def private_tools(path: Path) -> None:
    safe_components(path)
    try: path.resolve().relative_to((ROOT / "tools").resolve())
    except ValueError: raise Reject() from None
    try:
        checked = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", str(path)],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, check=False, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired): raise Reject() from None
    if checked.returncode != 0: raise Reject()
def load(path: Path) -> object:
    private_tools(path)
    payload=regular(path)
    try: return json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError): raise Reject() from None
def regular(path: Path) -> bytes:
    safe_components(path)
    if reparse(path) or not path.is_file(): raise Reject()
    flags=os.O_RDONLY|getattr(os,"O_BINARY",0)|getattr(os,"O_NOFOLLOW",0)
    descriptor=-1
    try:
        before=path.lstat(); descriptor=os.open(path,flags); opened=os.fstat(descriptor); after=path.lstat()
        if not os.path.samestat(before,opened) or not os.path.samestat(after,opened) or not os.path.isfile(path): raise Reject()
        chunks=[]
        while True:
            block=os.read(descriptor,1024*1024)
            if not block: break
            chunks.append(block)
        return b"".join(chunks)
    except OSError: raise Reject() from None
    finally:
        if descriptor>=0: os.close(descriptor)
def canonical(value: object) -> bytes: return json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=True).encode()
def source_text(raw: bytes) -> str:
    text = raw.decode("utf-8")
    # Preserve byte positions only for scanning boundaries; comments/strings
    # cannot create candidates.
    return re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " ", text, flags=re.S)
def ignored_output(path: Path) -> None:
    private_tools(path.parent)
    if path.exists() or reparse(path): raise Reject()
def root_inventory(root: Path) -> tuple[list[tuple[str, bytes]], str]:
    private_tools(root)
    if reparse(root) or not root.is_dir(): raise Reject()
    manifest = load(root / "sources.json")
    if not isinstance(manifest, dict) or manifest.get("version") != 2: raise Reject()
    normalizer = regular(ROOT / "scripts" / "build_private_generated_root.py")
    if manifest.get("normalizer_revision_sha256") != digest(normalizer): raise Reject()
    lists = ("baseline_body_sources", "normal_wrapper_sources", "support_sources", "patch_sources", "link_smoke_sources")
    names: list[str] = []
    for key in lists:
        value = manifest.get(key)
        if not isinstance(value, list) or any(not isinstance(x,str) or not x.endswith((".c", ".cc", ".cpp")) for x in value): raise Reject()
        names.extend(value)
    if not names or len(names) != len(set(names)): raise Reject()
    inventory = manifest.get("symbol_inventory")
    if inventory != "symbol_inventory.json" or manifest.get("symbol_inventory_sha256") != digest(regular(root / inventory)): raise Reject()
    files: list[tuple[str,bytes]] = []
    for name in sorted(names):
        if Path(name).is_absolute() or ".." in Path(name).parts: raise Reject()
        files.append((name, regular(root / name)))
    # Bind the complete normalized inventory, but scan only game bodies and
    # replacement bodies. Wrapper, support, and link-audit sources may name
    # the trap ABI deliberately; those references are not guest call sites.
    scan_names = set(manifest["baseline_body_sources"]) | set(manifest["patch_sources"])
    scan_files = [(name, data) for name, data in files if name in scan_names]
    if not scan_files: raise Reject()
    return scan_files, digest(canonical({name:digest(data) for name,data in files}))
def ledger_records(value: object, inventory: str) -> list[tuple[str,int,bytes,bytes,bool]]:
    if not isinstance(value,dict) or set(value) != {"schema_version","kind","source_inventory_sha256","records"} or value.get("schema_version") != 1 or value.get("kind") != "jfg-g2-trap-ledger" or value.get("source_inventory_sha256") != inventory or not isinstance(value.get("records"),list): raise Reject()
    result=[]
    for item in value["records"]:
        if not isinstance(item,dict) or set(item) != {"class","reachability","behavior_sha256","provenance_sha256"}: raise Reject()
        name=item.get("class"); reach=item.get("reachability"); behavior=item.get("behavior_sha256"); provenance=item.get("provenance_sha256")
        if name not in LEDGER or reach not in {"reachable","unreachable"} or not isinstance(behavior,str) or not isinstance(provenance,str) or not SHA.fullmatch(behavior) or not SHA.fullmatch(provenance): raise Reject()
        result.append((name, 1 if reach=="reachable" else 0, bytes.fromhex(behavior), bytes.fromhex(provenance), False))
    return result
def apply_overrides(records: list[tuple[str,int,bytes,bytes,bool]], value: object, inventory: str) -> list[tuple[str,int,bytes,bytes,bool]]:
    if not isinstance(value,dict) or set(value)!={"schema_version","kind","source_inventory_sha256","records"} or value.get("schema_version")!=1 or value.get("kind")!="jfg-g2-trap-overrides" or value.get("source_inventory_sha256")!=inventory or not isinstance(value.get("records"),list): raise Reject()
    replacements={}
    for item in value["records"]:
        if not isinstance(item,dict) or set(item)!={"class","reachability","behavior_sha256","provenance_sha256"}: raise Reject()
        name=item.get("class"); reach=item.get("reachability"); behavior=item.get("behavior_sha256"); provenance=item.get("provenance_sha256")
        if name not in KIND or reach not in {"reachable","unreachable"} or not isinstance(behavior,str) or not isinstance(provenance,str) or not SHA.fullmatch(behavior) or not SHA.fullmatch(provenance): raise Reject()
        key=(name,bytes.fromhex(behavior),bytes.fromhex(provenance))
        if key in replacements: raise Reject()
        replacements[key]=1 if reach=="reachable" else 0
    result=[]
    for name,reach,behavior,provenance,derived in records:
        replacement=replacements.pop((name,behavior,provenance),None)
        result.append((name, reach if replacement is None else replacement, behavior, provenance, derived))
    if replacements: raise Reject()
    return result
def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--generated-root",type=Path,required=True); parser.add_argument("--ledger",type=Path,required=True); parser.add_argument("--overrides",type=Path); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args()
    try:
        ignored_output(args.output); files, inventory=root_inventory(args.generated_root); records=[]
        for name,data in files:
            clean=source_text(data)
            for bridge,klass in BRIDGES:
                for ordinal,match in enumerate(re.finditer(r"\b"+re.escape(bridge)+r"\s*\(",clean),1):
                    position=match.start()
                    behavior=bytes.fromhex(digest((klass+"\0"+digest(clean.encode())+"\0"+str(ordinal)+"\0"+str(position)).encode()))
                    provenance=bytes.fromhex(digest(name.encode()+b"\0"+data+b"\0"+str(ordinal).encode()+b"\0"+str(position).encode()))
                    records.append((klass,1,behavior,provenance,True))
        records.extend(ledger_records(load(args.ledger),inventory))
        if args.overrides is not None: records=apply_overrides(records,load(args.overrides),inventory)
        if not records or len(records)>1024: raise Reject()
        records.sort(key=lambda item:(KIND[item[0]], item[2], item[3]))
        if len({(item[0],item[2],item[3]) for item in records}) != len(records): raise Reject()
        events=[]
        for ordinal,(klass,reachable,behavior,provenance,_) in enumerate(records,1):
            hits=1 if reachable else 0
            material=struct.unpack("<I",behavior[:4])[0]
            oracle=struct.unpack("<I",provenance[:4])[0]
            events.append(struct.pack("<IIIIII",KIND[klass],ordinal,reachable,hits,material,oracle)+behavior+provenance)
        reachable_kinds={KIND[item[0]] for item in records if item[1]}
        decisions=b"".join(struct.pack("<IIII", index, 1 if index in reachable_kinds else 0, 1, 1) for index in range(1,8))
        args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_bytes(b"JFG2TRP1"+struct.pack("<III",2,len(events),7)+b"".join(events)+decisions)
        return 0
    except Reject: return 1
if __name__=="__main__": raise SystemExit(main())
