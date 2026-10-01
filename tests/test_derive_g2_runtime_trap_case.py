from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "derive_g2_runtime_trap_case.py"
spec = importlib.util.spec_from_file_location("derive_traps", SCRIPT)
assert spec and spec.loader
DERIVE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(DERIVE)


class RuntimeTrapDerivationTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path, Path]:
        generated = root / "generated"; generated.mkdir()
        source = "void f(void) { do_break(0); do_break(1); /* recomp_syscall_handler(0) */ }\n"
        (generated / "unit.c").write_text(source, encoding="utf-8")
        audit = (
            "void audit(void) { do_break(2); recomp_syscall_handler(0); "
            "switch_error(0, 0, 0); }\n"
        )
        (generated / "audit.cpp").write_text(audit, encoding="utf-8")
        inventory = b'{"version":1}\n'; (generated / "symbol_inventory.json").write_bytes(inventory)
        manifest = {"version": 2, "normalizer_revision_sha256": hashlib.sha256((ROOT / "scripts" / "build_private_generated_root.py").read_bytes()).hexdigest(), "symbol_inventory": "symbol_inventory.json", "symbol_inventory_sha256": hashlib.sha256(inventory).hexdigest(), "baseline_body_sources": ["unit.c"], "normal_wrapper_sources": [], "support_sources": [], "patch_sources": [], "link_smoke_sources": ["audit.cpp"]}
        (generated / "sources.json").write_text(json.dumps(manifest), encoding="utf-8")
        inventory_digest = DERIVE.root_inventory(generated)[1]
        ledger = root / "ledger.json"
        ledger.write_text(json.dumps({"schema_version": 1, "kind": "jfg-g2-trap-ledger", "source_inventory_sha256": inventory_digest, "records": [{"class": "checksum", "reachability": "unreachable", "behavior_sha256": "11" * 32, "provenance_sha256": "22" * 32}]}), encoding="utf-8")
        return generated, ledger, root / "case-input.bin"

    def test_derives_opaque_v2_case_and_keeps_zero_class_counts(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tools") as temp:
            generated, ledger, output = self.fixture(Path(temp))
            self.assertEqual(DERIVE.main.__name__, "main")
            with mock.patch("sys.argv", ["derive", "--generated-root", str(generated), "--ledger", str(ledger), "--output", str(output)]):
                self.assertEqual(DERIVE.main(), 0)
            payload = output.read_bytes()
            self.assertEqual(payload[:12], b"JFG2TRP1" + struct.pack("<I", 2))
            self.assertEqual(struct.unpack_from("<I", payload, 12)[0], 3)
            self.assertNotIn(b"do_break", payload)
            self.assertEqual(len(payload), 20 + 3 * 88 + 7 * 16)
            self.assertNotEqual(payload[20 + 24:20 + 56], payload[20 + 88 + 24:20 + 88 + 56])

    def test_rejects_malformed_ledger_and_nonignored_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tools") as temp:
            generated, ledger, output = self.fixture(Path(temp))
            ledger.write_text("{}", encoding="utf-8")
            with mock.patch("sys.argv", ["derive", "--generated-root", str(generated), "--ledger", str(ledger), "--output", str(output)]):
                self.assertEqual(DERIVE.main(), 1)

    def test_rejects_existing_output_and_stale_lineage(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tools") as temp:
            generated, ledger, output = self.fixture(Path(temp))
            output.write_bytes(b"existing")
            with mock.patch("sys.argv", ["derive", "--generated-root", str(generated), "--ledger", str(ledger), "--output", str(output)]):
                self.assertEqual(DERIVE.main(), 1)
            output.unlink()
            manifest = json.loads((generated / "sources.json").read_text(encoding="utf-8"))
            manifest["normalizer_revision_sha256"] = "00" * 32
            (generated / "sources.json").write_text(json.dumps(manifest), encoding="utf-8")
            with mock.patch("sys.argv", ["derive", "--generated-root", str(generated), "--ledger", str(ledger), "--output", str(output)]):
                self.assertEqual(DERIVE.main(), 1)

    def test_two_fresh_outputs_are_byte_identical_and_stale_inventory_rejects(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tools") as temp:
            generated, ledger, output = self.fixture(Path(temp))
            second = Path(temp) / "case-second.bin"
            for target in (output, second):
                with mock.patch("sys.argv", ["derive", "--generated-root", str(generated), "--ledger", str(ledger), "--output", str(target)]):
                    self.assertEqual(DERIVE.main(), 0)
            self.assertEqual(output.read_bytes(), second.read_bytes())
            manifest = json.loads((generated / "sources.json").read_text(encoding="utf-8"))
            manifest["symbol_inventory_sha256"] = "33" * 32
            (generated / "sources.json").write_text(json.dumps(manifest), encoding="utf-8")
            third = Path(temp) / "case-third.bin"
            with mock.patch("sys.argv", ["derive", "--generated-root", str(generated), "--ledger", str(ledger), "--output", str(third)]):
                self.assertEqual(DERIVE.main(), 1)
            with mock.patch("sys.argv", ["derive", "--generated-root", str(generated), "--ledger", str(ledger), "--output", str(ROOT / "case-input.bin")]):
                self.assertEqual(DERIVE.main(), 1)


if __name__ == "__main__":
    unittest.main()
