"""Reject identity ambiguity and prevent catalog recognition from granting execution."""
import copy
import json
import unittest
from scripts import rom_profiles as rom

class RomCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(rom.CATALOG_PATH.read_text(encoding="utf-8"))
        self.admission = json.loads(rom.ADMISSION_PATH.read_text(encoding="utf-8"))

    def test_expected_revision_ids_and_admission_are_separate(self):
        self.assertEqual({p.revision_id for p in rom.parse_catalog(self.catalog)},
                         {"jfg-us-r0", "jfg-pal-r0", "star-twins-jp-r0"})
        self.assertNotIn("native_supported", self.catalog["revisions"][0])
        self.assertEqual([p.code for p in rom.ROM_PROFILES if p.native_supported], ["us"])

    def test_duplicate_identity_keys_are_rejected(self):
        for key in ("id", "code", "sha1"):
            candidate = copy.deepcopy(self.catalog)
            candidate["revisions"][1][key] = candidate["revisions"][0][key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "Duplicate"):
                rom.parse_catalog(candidate)

    def test_malformed_and_unknown_fields_are_rejected(self):
        for key, value in (("sha1", "A" * 40), ("country", "PAL"), ("revision", True),
                           ("size", -4), ("byte_order", "little-endian"), ("native_supported", True)):
            candidate = copy.deepcopy(self.catalog)
            candidate["revisions"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                rom.parse_catalog(candidate)

    def test_admission_must_cover_exact_catalog_and_explicit_boolean(self):
        for action in ("missing", "unknown", "truthy", "escape"):
            candidate = copy.deepcopy(self.admission)
            if action == "missing": del candidate["native_builds"]["jfg-pal-r0"]
            if action == "unknown": candidate["native_builds"]["unknown"] = {"admitted": True, "evidence": "docs/status.md"}
            if action == "truthy": candidate["native_builds"]["jfg-us-r0"]["admitted"] = "true"
            if action == "escape": candidate["native_builds"]["jfg-us-r0"]["evidence"] = "docs/../../outside"
            with self.subTest(action=action), self.assertRaises(ValueError):
                rom.parse_admission(candidate, rom.ROM_PROFILES)

    def test_admission_evidence_exists(self):
        for row in self.admission["native_builds"].values():
            self.assertTrue((rom.ROOT / row["evidence"]).is_file())

if __name__ == "__main__":
    unittest.main()
