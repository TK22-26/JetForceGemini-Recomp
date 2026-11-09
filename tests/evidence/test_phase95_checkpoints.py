import json
from pathlib import Path
import tempfile
import unittest

from scripts.phase95_bridge import digest, validate_checkpoint, runtime_digest, isolate_n64_bindings


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "checkpoint-a1.json"
        self.path.with_suffix(".State").write_bytes(b"test core state")
        self.path.with_suffix(".side").write_text("abc 10 0\n")
        self.identity = {key: "a" * 64 for key in (
            "rom_sha256", "runtime_sha256", "config_sha256", "script_sha256")}
        self.manifest = {"kind": "jfg-phase95-checkpoint", "schema": 1,
                         "identity": self.identity,
                         "digests": {suffix: digest(self.path.with_suffix("." + suffix))
                                     for suffix in ("State", "side")}}
        self.write()

    def write(self):
        self.path.write_text(json.dumps(self.manifest))

    def test_valid(self):
        self.assertEqual(validate_checkpoint(self.path, self.identity), self.manifest)

    def test_incompatible_identity(self):
        for key in self.identity:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "incompatible"):
                validate_checkpoint(self.path, {**self.identity, key: "b" * 64})

    def test_tampered_state(self):
        self.path.with_suffix(".State").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            validate_checkpoint(self.path, self.identity)

    def test_tampered_side_state(self):
        self.path.with_suffix(".side").write_text("abc 11 0\n")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            validate_checkpoint(self.path, self.identity)

    def test_old_unsealed_format(self):
        self.manifest.pop("kind")
        self.write()
        with self.assertRaisesRegex(ValueError, "unsupported"):
            validate_checkpoint(self.path, self.identity)

    def test_runtime_hash_covers_dll_not_logs(self):
        (self.root / "core.dll").write_bytes(b"core1")
        first = runtime_digest(self.root)
        (self.root / "stdout.log").write_text("a log")
        self.assertEqual(runtime_digest(self.root), first)
        (self.root / "core.dll").write_bytes(b"core2")
        self.assertNotEqual(runtime_digest(self.root), first)

    def test_worker_bindings_are_empty_without_mutating_source(self):
        original = {"AllTrollers": {"Nintendo 64 Controller": {"P1 A": "X1 A"}},
                    "AllTrollersAnalog": {"Nintendo 64 Controller": {
                        "P1 X Axis": {"Value": "X1 LeftThumbX Axis", "Mult": 1,
                                      "ButtonBindPositive": "Right"}}}}
        result = isolate_n64_bindings(original)
        self.assertEqual(original["AllTrollers"]["Nintendo 64 Controller"]["P1 A"], "X1 A")
        self.assertEqual(result["AllTrollers"]["Nintendo 64 Controller"]["P1 A"], "")
        axis = result["AllTrollersAnalog"]["Nintendo 64 Controller"]["P1 X Axis"]
        self.assertEqual(axis["Value"], "")
        self.assertIsNone(axis["ButtonBindPositive"])


if __name__ == "__main__":
    unittest.main()
