import unittest
from pathlib import Path
from scripts.phase95_native_replay import trace_record_count
from scripts.compare_phase9_update_hashes import records


class FailureTraceTests(unittest.TestCase):
    def test_missing_trace_is_reported_not_raised(self):
        count, error = trace_record_count(records, Path("not-an-existing-trace.jsonl"))
        self.assertEqual(count, 0)
        self.assertIsNotNone(error)

    def test_malformed_tail_does_not_accept_partial_count(self):
        def broken(_):
            yield {"update": 1}
            raise ValueError("truncated record")
        self.assertEqual(trace_record_count(broken, None), (0, "truncated record"))

    def test_valid_reader_counts_and_forwards_arguments(self):
        def valid(path, mode):
            self.assertEqual((path, mode), ("trace", "native"))
            yield 1
            yield 2
        self.assertEqual(trace_record_count(valid, "trace", "native"), (2, None))
