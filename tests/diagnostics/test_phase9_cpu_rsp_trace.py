from itertools import product
from pathlib import Path
import tempfile
import unittest
from scripts.phase9_cpu_rsp_trace import HEADER, parse_trace


class RspTraceTests(unittest.TestCase):
    def trace(self):
        return "\n".join(["\t".join(HEADER), *[
            "\t".join(map(str, (*case, 890, 54, 1066 if case[0] == 1 else 4062,
                                579, 41 if case[0] == 1 else 9)))
            for case in product((1, 2), (1, 8, 64, 256), (0, 2))], "result\ttrue\t16"]) + "\n"

    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace"
            path.write_text(text)
            return parse_trace(path)

    def test_complete(self):
        result = self.parse(self.trace())
        self.assertEqual(len(result["cases"]), 16)
        self.assertFalse(result["latency_model_qualified"])

    def test_reject_missing_completion_and_invalid_order(self):
        trace = self.trace()
        for text in (trace.replace("579\t41", "578\t41", 1),
                     trace.replace("579\t9", "579\t8", 1),
                     trace.replace("1\t1\t0", "1\t8\t0", 1),
                     trace.replace("result\ttrue\t16", "result\tfalse\t16")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse(text)


if __name__ == "__main__":
    unittest.main()
