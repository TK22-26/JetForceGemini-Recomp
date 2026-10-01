import unittest

from scripts.phase9_branch_count_check import compare_rows, extract, program


class BranchCountCheckTests(unittest.TestCase):
    def test_extracts_actual_statements_and_fails_if_anchors_change(self):
        block = "const auto previous_primary = state.guest_last_word >> 26U;\nstate.cpu_count += 2;\n"
        self.assertEqual(extract("prefix\n" + block + "mmio.guest_count = state.cpu_count;"), block)
        for source in ("", block, block + block + "mmio.guest_count = state.cpu_count;"):
            with self.assertRaises(ValueError):
                extract(source)
        self.assertIn(block, program(block))

    def test_reports_tick_mismatch_not_false_pass(self):
        reference = {"cases": [{"kind": 4, "taken": 0, "iterations": 16, "ticks": 162}]}
        self.assertEqual(compare_rows("4\t0\t16\t162\n", reference), [])
        self.assertEqual(compare_rows("4\t0\t16\t130\n", reference), [
            {"kind": 4, "taken": 0, "iterations": 16, "native_ticks": 130, "oracle_ticks": 162}])

    def test_rejects_missing_malformed_or_reordered_cases(self):
        reference = {"cases": [{"kind": 4, "taken": 0, "iterations": 16, "ticks": 162}]}
        for output in ("", "4\t0\t16\tbad\n", "4\t1\t16\t162\n",
                       "4\t0\t16\t162\n4\t0\t16\t162\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                compare_rows(output, reference)


if __name__ == "__main__":
    unittest.main()
