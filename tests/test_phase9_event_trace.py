from pathlib import Path
import tempfile
import unittest

from scripts.phase9_event_trace import HEADER, analyze, read, spec, validate_windows


class EventTraceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def trace(self, side, *, extra_update=False, bad_sample=False):
        rows = []

        def add(event, poll, updates, start, get, buttons=0):
            rows.append((len(rows) + 1, event, poll, updates, poll + 40,
                         poll, start, get, 1, buttons, 0, 0))

        for poll in (13, 14):
            add("update-begin", poll, poll - 13, poll - 12, poll - 13)
            add("update-end", poll, poll - 12, poll - 12, poll - 13)
            if extra_update and poll == 14:
                add("update-begin", poll, poll - 12, poll - 12, poll - 13)
                add("update-end", poll, poll - 11, poll - 12, poll - 13)
            add("vi-consumed", poll, poll - 12 + int(extra_update and poll == 14),
                poll - 12, poll - 13)
            add("start-entry", poll, poll - 12 + int(extra_update and poll == 14),
                poll - 12 + 1, poll - 13)
            add("input-poll", poll, poll - 12 + int(extra_update and poll == 14),
                poll - 12 + 1, poll - 13,
                0x8000 if bad_sample and poll == 14 else 0)
            if side == "native":
                add("start-exit", poll, poll - 12 + int(extra_update and poll == 14),
                    poll - 12 + 1, poll - 13)
            add("get-entry", poll, poll - 12 + int(extra_update and poll == 14),
                poll - 12 + 1, poll - 12)
            if side == "native":
                add("get-exit", poll, poll - 12 + int(extra_update and poll == 14),
                    poll - 12 + 1, poll - 12)
        path = self.root / f"{side}.tsv"
        path.write_text("\t".join(HEADER) + "\n" +
                        "\n".join("\t".join(map(str, row)) for row in rows) +
                        "\n", encoding="utf-8")
        return path

    def test_window_bounds_and_specification(self):
        windows = validate_windows(((13, 21), (566, 577)),
                                   poll_hashes=True, update_hashes=True)
        self.assertEqual(spec(windows), "13:21,566:577")
        for invalid in (((13, 45),), ((13, 21), (20, 27)),
                        ((13, 21), (566, 577), (800, 801))):
            with self.assertRaises(ValueError):
                validate_windows(invalid, poll_hashes=True, update_hashes=True)
        with self.assertRaises(ValueError):
            validate_windows(((13, 21),), poll_hashes=False,
                             update_hashes=True)

    def test_matching_event_order_is_not_parity(self):
        report = analyze(self.trace("native"), self.trace("oracle"), ((13, 14),))
        self.assertIsNone(report["first_input_mismatch_poll"])
        self.assertIsNone(report["first_update_count_mismatch_poll"])
        self.assertIsNone(report["windows"][0]["first_order_difference"])
        self.assertEqual(report["interval_differences"], [])
        self.assertFalse(report["alignment_validated"])
        self.assertFalse(report["parity_verified"])

    def test_extra_update_and_input_mismatch_are_reported(self):
        report = analyze(self.trace("native", extra_update=True),
                         self.trace("oracle", bad_sample=True), ((13, 14),))
        self.assertEqual(report["first_input_mismatch_poll"], 14)
        self.assertEqual(report["first_update_count_mismatch_poll"], 14)
        self.assertIsNotNone(report["windows"][0]["first_order_difference"])
        self.assertEqual(report["interval_differences"][0]["after_poll"], 13)
        self.assertEqual(report["interval_differences"][0]["native"]["update-end"], 2)

    def test_incomplete_or_malformed_trace_fails_closed(self):
        path = self.trace("native")
        rows = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(row for row in rows
                                  if "\tinput-poll\t14\t" not in row) + "\n",
                        encoding="utf-8")
        with self.assertRaises(ValueError):
            read(path, ((13, 14),), "native")
        path = self.trace("oracle")
        path.write_text(path.read_text(encoding="utf-8").replace(
            "\tinput-poll\t14\t", "\tget-exit\t14\t"), encoding="utf-8")
        with self.assertRaises(ValueError):
            read(path, ((13, 14),), "oracle")


if __name__ == "__main__":
    unittest.main()
