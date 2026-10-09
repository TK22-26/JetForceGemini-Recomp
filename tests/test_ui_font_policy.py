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

class UiAssetPolicyTests(unittest.TestCase):
    def test_reviewed_images_are_exact(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("docs/images/live-map.png", "launcher/ui/assets/app.ico"):
            data = (root / name).read_bytes()
            self.assertEqual(scan_blob(data, name), [])
            self.assertTrue(scan_blob(data + b"changed", name))

    def test_inventory_identifiers_do_not_hide_other_hex(self):
        ids = (0, 1, 2, 3, 9, 16, 17, *range(20, 28))
        for declaration in ("int ids[]", "int[] itemIds"):
            data = (declaration + "={" + ",".join(map(str, ids)) + "};").encode()
            self.assertEqual(scan_blob(data, "fixture"), [])
            self.assertTrue(scan_blob(data + b"\n" + b" ".join([b"ab"] * 8), "fixture"))

    def test_historical_path_exception_is_scoped(self):
        from unittest import mock
        import scripts.check_repository_hygiene as policy
        data = ("C:" + "/Users/" + "FixturePerson/project").encode()
        digest = hashlib.sha256(data).hexdigest()
        with mock.patch.object(policy, "HISTORICAL_CHECKOUT_PATH_SHA256", {digest}):
            self.assertEqual(scan_blob(data, "git-blob:fixture"), [])
            self.assertTrue(scan_blob(data, "current.md"))
            self.assertTrue(scan_blob(data + b"changed", "git-blob:fixture"))

if __name__ == "__main__":
    unittest.main()
