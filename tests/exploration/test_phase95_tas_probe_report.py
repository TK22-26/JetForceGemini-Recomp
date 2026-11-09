import json
from pathlib import Path
import tempfile
import unittest

from scripts.phase95_tas_probe_report import PINS, summarize


def segment(root: Path, name: str, first: int, rows: list[tuple[int, str, str]],
            *, complete: bool = True, pin: str = "same", parent: Path | None = None) -> Path:
    directory = root / name
    directory.mkdir()
    result = {key: pin for key in PINS}
    result.update(first=first, last=rows[-1][0], complete=complete,
                  semantic_status="raw-unverified-jp", captured_frames=len(rows),
                  continuation_sha256=f"state-{name}",
                  resume_from=str(parent) if parent else None,
                  parent_continuation_sha256=f"state-{parent.name}" if parent else None)
    (directory / "result.json").write_text(json.dumps(result))
    header = ("schema\t1\nprobe_status\tunverified-jp\n"
              "frame\tmovie_mode\tinput_polls_since_worker_start\t"
              "raw_0xA51B0_u8\traw_0xFB114_u32be\t"
              "raw_0xA33E4_u32be\traw_0x1BD150_u32be\n")
    lines = [f"{frame}\tPLAY\t0\t{mode}\t{level}\t00000000\t80000000\n"
             for frame, mode, level in rows]
    (directory / "frames.tsv").write_text(header + "".join(lines))
    return directory


class TasProbeReportTests(unittest.TestCase):
    def test_contiguous_segments_and_bounded_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            one = segment(root, "one", 0, [(0, "00", "00000000"),
                                            (1, "01", "00000000")])
            two = segment(root, "two", 2, [(2, "01", "00000001"),
                                            (3, "02", "00000001")], parent=one)
            report = summarize([one, two], event_limit=1)
            self.assertEqual((report["first"], report["last"]), (0, 3))
            self.assertFalse(report["acceptance"])
            self.assertTrue(report["lineage_verified"])
            self.assertEqual(report["changes"]["raw_0xA51B0_u8"]["count"], 2)
            self.assertEqual(report["changes"]["raw_0xA51B0_u8"]["first_value"], "00")
            self.assertEqual(report["changes"]["raw_0xA51B0_u8"]["last_value"], "02")
            self.assertTrue(report["changes"]["raw_0xA51B0_u8"]["truncated"])
            self.assertEqual(report["changes"]["raw_0xFB114_u32be"]["events"][0]["frame"], 2)

    def test_rejects_gaps_wrong_pin_and_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            one = segment(root, "one", 0, [(0, "00", "00000000")])
            gap = segment(root, "gap", 2, [(2, "00", "00000000")])
            with self.assertRaisesRegex(ValueError, "noncontiguous"):
                summarize([one, gap])
            wrong = segment(root, "wrong", 1, [(1, "00", "00000000")], pin="other")
            with self.assertRaisesRegex(ValueError, "pin mismatch"):
                summarize([one, wrong])
            incomplete = segment(root, "incomplete", 1, [(1, "00", "00000000")],
                                 complete=False)
            with self.assertRaisesRegex(ValueError, "incomplete"):
                summarize([one, incomplete])
            stale = segment(root, "stale", 1, [(1, "00", "00000000")], parent=gap)
            with self.assertRaisesRegex(ValueError, "resume source mismatch"):
                summarize([one, stale])


if __name__ == "__main__":
    unittest.main()
