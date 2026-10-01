import tempfile
import unittest
from pathlib import Path
from scripts.phase9_cpu_queue_threads_trace import NAMES, VALID, parse_trace


class QueueThreadMicroTests(unittest.TestCase):
    TEXT = ("case\tticks\tresult\tvalid\tstatus\n" + "".join(
        f"{name}\t100\t0x00000000\t{valid}\t0x3400ff00\n"
        for name, valid in zip(NAMES, VALID)) +
        "payloads\t1111\t2222\t3333\t4444\n"
        "result\ttrue\t0\t0\t0x3400ff00\t0x3400ff00\n")

    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.tsv"
            path.write_text(text)
            return parse_trace(path)

    def test_wait_intervals_not_cpu_costs(self):
        result = self.parse(self.TEXT)
        self.assertTrue(result["queue_semantics_pass"])
        self.assertFalse(result["hardware_qualified"])
        self.assertIn("worker_block_send", result["scheduling_or_wait_intervals"])
        self.assertIn("send_lower", result["uninterrupted_cases"])

    def test_rejects_broken_semantics_masks_and_exceptions(self):
        for text in ("", self.TEXT + "extra\n",
                     self.TEXT.replace("4444", "3333"),
                     self.TEXT.replace("true\t0\t0", "true\t1\t0"),
                     self.TEXT.replace("true\t0\t0", "true\t0\t1111"),
                     self.TEXT.replace("0x3400ff00", "0x3400ff01"),
                     self.TEXT.replace("0x3400ff00", "0x3400ff02"),
                     self.TEXT.replace("0x3400ff00", "0x2400ff00", 1),
                     self.TEXT.replace("\t100\t", "\t0\t", 1),
                     self.TEXT.replace("0x00000000", "0xffffffff", 1)):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse(text)

    def test_entry_status_distinct_from_saved_exception_status(self):
        text = self.TEXT.replace("result\ttrue", "entry-status\t0x3400ff01\t0x3400ff01\nresult\ttrue")
        self.assertEqual(self.parse(text)["entry_status"], [0x3400ff01, 0x3400ff01])
        self.assertIsNone(self.parse(self.TEXT)["entry_status"])
        for value in ("0x3400ff03", "0x3400ff05", "0x3400ff00"):
            with self.assertRaises(ValueError): self.parse(text.replace("0x3400ff01", value))

    def test_per_thread_rcp_restore_observation(self):
        text = self.TEXT.replace("result\ttrue", "entry-status\t0x3400ff01\t0x3400ff01\n"
            "mi-masks\t0x0000003f\t0x0000003f\t0x0000003f\t0x0000003e\t0x0000003e\nresult\ttrue")
        self.assertEqual(self.parse(text)["thread_mi_masks"], [63, 63, 63, 62, 62])
        with self.assertRaises(ValueError): self.parse(text.replace("0x0000003e", "0x0000003f"))
