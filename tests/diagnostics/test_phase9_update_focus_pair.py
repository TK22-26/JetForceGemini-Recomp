import tempfile
import hashlib
import json
import unittest
from pathlib import Path

from scripts.phase9_update_focus_pair import (
    SNAPSHOT_BYTES, compare_snapshots, focus_range,
    verified_alignment_sha,
)


class UpdateFocusPairTests(unittest.TestCase):
    def test_pinned_alignment_accepts_crlf_without_losing_byte_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "update-alignment.json"
            report = {"kind": "diagnostic", "matching_update_prefix": 567}
            encoded = (json.dumps(report, sort_keys=True, indent=2) +
                       "\n").replace("\n", "\r\n").encode("utf-8")
            path.write_bytes(encoded)
            pinned = hashlib.sha256(encoded).hexdigest()
            self.assertEqual(verified_alignment_sha(path, report, pinned),
                             pinned)
            with self.assertRaises(ValueError):
                verified_alignment_sha(path, report, "0" * 64)
            with self.assertRaises(ValueError):
                verified_alignment_sha(path, {"kind": "changed"}, pinned)

    def test_focus_is_derived_from_first_state_difference(self):
        report = {
            "first_semantic_difference": {
                "reason": "state-difference", "update": 568},
            "matching_update_prefix": 567,
            "alignment_validated": False, "parity_verified": False,
        }
        self.assertEqual(focus_range(report), (566, 569))
        report["matching_update_prefix"] = 566
        with self.assertRaises(ValueError):
            focus_range(report)

    def test_exact_game_visible_input_fields_are_compared(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native, oracle = root / "native", root / "oracle"
            native.mkdir()
            oracle.mkdir()
            baseline = bytearray(SNAPSHOT_BYTES)
            for side in (native, oracle):
                (side / "focus-update-3.rdram").write_bytes(baseline)
            changed = bytearray(baseline)
            changed[0xFB0C0] = 0x80
            (native / "focus-update-4.rdram").write_bytes(baseline)
            (oracle / "focus-update-4.rdram").write_bytes(changed)
            report = compare_snapshots(native, oracle, 3, 4)
        self.assertEqual(report["first_input_buffer_difference_update"], 4)
        self.assertEqual(report["rows"][0]["differing_fields"], [])
        self.assertEqual(report["rows"][1]["differing_fields"],
                         ["controller_current"])
        self.assertFalse(report["alignment_validated"])
        self.assertFalse(report["parity_verified"])


if __name__ == "__main__":
    unittest.main()
