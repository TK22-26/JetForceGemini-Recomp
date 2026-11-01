"""Generate ROM-free C++/C# catalog views from the canonical revision contract."""
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
from scripts.rom_profiles import ROM_PROFILES, NATIVE_ADMISSION, CATALOG_PATH, ADMISSION_PATH

def catalog_digest() -> str:
    values = [json.loads(p.read_text(encoding="utf-8")) for p in (CATALOG_PATH, ADMISSION_PATH)]
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()

def cpp_view() -> str:
    rows = []
    for p in ROM_PROFILES:
        digest = ", ".join("0x" + p.sha1[i:i+2] + "U" for i in range(0, 40, 2))
        strings = ", ".join(json.dumps(v, ensure_ascii=True) for v in (p.revision_id, p.code, p.title, p.sha1))
        rows.append("  RomRevision{" + strings + ", {" + digest + "}, " + str(p.size) + "U, " + str(p.country) + "U, " + str(p.revision) + "U, " + str(NATIVE_ADMISSION[p.revision_id]).lower() + "},")
    return (
        "// Generated from config/roms; do not edit. Contains no game code.\n#pragma once\n"
        "#include <array>\n#include <cstdint>\n#include <string_view>\n"
        "namespace jfg::roms {\nstruct RomRevision {\n"
        "  std::string_view id, code, title, sha1;\n  std::array<std::uint8_t, 20> sha1_bytes;\n"
        "  std::uint64_t size;\n  std::uint8_t country, revision;\n  bool native_build_admitted;\n};\n"
        f"inline constexpr std::string_view kCatalogDigest = \"{catalog_digest()}\";\n"
        f"inline constexpr std::array<RomRevision, {len(rows)}> kRevisions = {{{{\n" + "\n".join(rows) + "\n}};\n"
        "constexpr const RomRevision* find_revision(std::string_view id) noexcept {\n"
        "  for (const auto& revision : kRevisions) if (revision.id == id) return &revision;\n"
        "  return nullptr;\n}\n"
        "consteval const RomRevision& known_revision(std::string_view id) {\n"
        "  const auto* found = find_revision(id);\n  if (!found) throw \"Unknown ROM revision\";\n  return *found;\n}\n"
        "} // namespace jfg::roms\n")

def csharp_view() -> str:
    rows = []
    constants = []
    for p in ROM_PROFILES:
        label = p.code.capitalize()
        constants += [f'        internal const string {label}Sha1 = "{p.sha1}";',
                      f'        internal const long {label}Size = {p.size}L;']
        values = ", ".join(json.dumps(v, ensure_ascii=True) for v in (p.revision_id, p.code, p.title, p.sha1))
        rows.append("            new RomCatalogEntry(" + values + f", {p.size}L, {p.country}, {p.revision}, " + str(NATIVE_ADMISSION[p.revision_id]).lower() + "),")
    return (
        "// Generated from config/roms; do not edit.\nnamespace JfgLauncher {\n"
        "    internal sealed class RomCatalogEntry {\n"
        "        internal readonly string Id, Code, Title, Sha1;\n"
        "        internal readonly long Size;\n        internal readonly byte Country, Revision;\n"
        "        internal readonly bool NativeBuildAdmitted;\n"
        "        internal RomCatalogEntry(string id, string code, string title, string sha1, long size, byte country, byte revision, bool admitted) {\n"
        "            Id=id; Code=code; Title=title; Sha1=sha1; Size=size; Country=country; Revision=revision; NativeBuildAdmitted=admitted;\n"
        "        }\n    }\n    internal static class RomCatalog {\n" + "\n".join(constants) + "\n"
        f'        internal const string CatalogDigest = "{catalog_digest()}";\n'
        "        internal static readonly RomCatalogEntry[] Revisions = {\n" + "\n".join(rows) + "\n        };\n"
        "    }\n}\n")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpp", type=Path)
    parser.add_argument("--csharp", type=Path)
    args = parser.parse_args()
    if not args.cpp and not args.csharp:
        parser.error("Choose at least one output view")
    for path, producer in ((args.cpp, cpp_view), (args.csharp, csharp_view)):
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            text = producer()
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                path.write_text(text, encoding="utf-8", newline="\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
