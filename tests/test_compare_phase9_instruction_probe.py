import json
from pathlib import Path
import tempfile
import unittest

from scripts.compare_phase9_instruction_probe import compare
from scripts.phase95_native_replay import (
    INSTRUCTION_PROBE_HEADER, INSTRUCTION_PROBE_PCS,
)


class InstructionProbeCompareTests(unittest.TestCase):
    def test_explicit_pair_finds_first_value_difference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native = root / "native"
            native.mkdir()
            (native / "native-result.json").write_text(json.dumps({
                "acceptance": False, "input_sha256": "a" * 64,
                "rom_sha256": "b" * 64, "initial_flash_sha256": "c" * 64,
                "instruction_probe_trace_complete": True,
            }))
            native_rows = ["\t".join(INSTRUCTION_PROBE_HEADER)]
            oracles = {}
            for index, pc in enumerate(INSTRUCTION_PROBE_PCS):
                values = dict.fromkeys(INSTRUCTION_PROBE_HEADER, "0x00000000")
                values.update(update_candidate="1265", vi_retraces="3000",
                              controller_polls="100", pc=f"0x{pc:08x}",
                              r4="0x80360138", host_fe_round="0")
                if index == len(INSTRUCTION_PROBE_PCS) - 1:
                    values["r15"] = "0x00000001"
                native_rows.append("\t".join(values[key] for key in
                                             INSTRUCTION_PROBE_HEADER))
                oracle = root / f"oracle-{index}"
                oracle.mkdir()
                oracles[pc] = oracle
                (oracle / "oracle-result.json").write_text(json.dumps({
                    "acceptance": False, "input_sha256": "a" * 64,
                    "rom_sha256": "b" * 64,
                    "oracle_initial_flash_sha256": "c" * 64,
                    "initial_flash_matches_candidate": True,
                    "emulator_sha256": "d" * 64,
                    "runtime_sha256": "e" * 64,
                    "config_sha256": "f" * 64,
                    "entry_pc": f"0x{pc:08x}",
                    "entry_gpr_trace_complete": True,
                    "entry_fpu_trace_complete": True,
                }))
                prefix = ["frame", "completed_updates", "controller_polls",
                          "consumed_vi", "pc"]
                gpr = {f"r{register}_lo": "0x00000000" for register in
                       (4, 5, 6, 7, 10, 15, 19, 20, 21, 23, 25)}
                gpr["r4_lo"] = "0x80360138"
                fpr = {name: "0x00000000" for name in
                       ("f4_lo", "f22_lo", "f23_lo")}
                metadata = dict(frame="3000", completed_updates="1260",
                                controller_polls="100", consumed_vi="2990",
                                pc=f"0x{pc:08x}")
                for filename, fields in (("entry-gpr.tsv", gpr),
                                         ("entry-fpu.tsv", fpr)):
                    header = [*prefix, *fields]
                    (oracle / filename).write_text(
                        "\t".join(header) + "\n" +
                        "\t".join({**metadata, **fields}[key] for key in header)
                        + "\n", encoding="utf-8")
            (native / "instruction-probe.tsv").write_text(
                "\n".join(native_rows) + "\n", encoding="utf-8")
            report = compare(native, oracles, native_update=1265,
                             oracle_completed_update=1260,
                             a0=0x80360138, occurrence=1)
            self.assertFalse(report["all_equal"])
            self.assertEqual([list(item["differences"]) for item in
                              report["comparisons"]], [[], [], [], ["r15"]])


if __name__ == "__main__":
    unittest.main()
