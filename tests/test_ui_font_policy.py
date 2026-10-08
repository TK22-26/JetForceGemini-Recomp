"""Licensed UI font allowlist remains exact and tamper-evident."""
import hashlib
import json
from pathlib import Path
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.check_repository_hygiene import scan_blob

class UiFontPolicyTests(unittest.TestCase):
    def test_reviewed_fonts_and_altered_binary(self):
        root = Path(__file__).resolve().parents[1] / "launcher/ui/fonts"
        manifest = json.loads((root / "manifest.json").read_text())
        for name, expected in manifest["files"].items():
            data = (root / name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected)
            self.assertEqual(scan_blob(data, name), [])
            if name.endswith(".ttf"):
                self.assertTrue(scan_blob(data + b"tampered", name))
        self.assertTrue(scan_blob(b"unreviewed font" + bytes([0]), "pretend.ttf"))

if __name__ == "__main__":
    unittest.main()
