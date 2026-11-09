import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.autonomy import device_observation as observation
from scripts import phase9_device_events as events, phase9_point_probe as points
from tests.test_autonomy_point_interval import PROBE, SELECT, trace


def fixture(side):
    point_rows, event_rows = [], []
    for point in trace(side == "oracle"):
        row = {**{key: 0 for key in events.REGISTERS}, **point, "opcode": 0}
        row.update(r29_hi=0xffffffff, r31_hi=0xffffffff)
        event = {key: 0 for key in events.BASE + events.REGISTERS}
        event.update({key: row[key] for key in ("pc", "opcode", *events.REGISTERS)})
        event.update(sequence=len(event_rows) + 1, phase="instruction", source="none",
                     invocation=row["completed_updates"] + 1 if side == "oracle" else row["update_candidate"],
                     thread=row["m800a9e90"])
        event_rows.append(event)
        # Different raw clock bases intentionally do not compare for equality.
        dispatch = {**event, "sequence": len(event_rows) + 1, "phase": "dispatch", "source": "vi",
                    "clock_raw": 100 if side == "native" else 7, "deadline_valid": 1, "deadline": 100}
        event_rows.append(dispatch)
        point_rows.append(row)
    return point_rows, event_rows


def write_events(path, rows, side):
    columns = events.BASE + events.REGISTERS
    strings = {"phase", "source"}
    decimals = {"sequence", "invocation", "deadline_valid"}
    lines = [f"jfg-phase9-device-events-v1\t{events.CLOCKS[side]}\t6\t9", "\t".join(columns)]
    lines += ["\t".join(str(row[key]) if key in strings | decimals else f"0x{row[key]:08x}"
                        for key in columns) for row in rows]
    path.write_text("\n".join(lines + [f"result\ttrue\t{len(rows)}"]) + "\n")


class DeviceObservationTests(unittest.TestCase):
    def test_exact_instruction_binding_preserves_raw_64_bit_values(self):
        for side in observation.TRACES:
            raw, rows = fixture(side)
            bound = observation.bind_instructions(rows, raw, side)
            self.assertEqual([r["device_sequence"] for r in bound], list(range(1, len(rows), 2)))
            self.assertEqual(bound[0]["r31_hi"], 0xffffffff)
            self.assertNotIn("device_sequence", raw[0])

    def test_binding_rejects_missing_reordered_or_changed_context(self):
        raw, rows = fixture("native")
        for field in ("pc", "opcode", "thread", "invocation", *events.REGISTERS):
            mutated = copy.deepcopy(rows)
            mutated[0][field] ^= 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                observation.bind_instructions(mutated, raw, "native")
        with self.assertRaises(ValueError):
            observation.bind_instructions(rows[2:], raw, "native")
        with self.assertRaises(ValueError):
            observation.bind_instructions(rows, raw[1:] + raw[:1], "native")

    def paired(self):
        raw, rows = {}, {}
        for side in observation.TRACES:
            points_, rows[side] = fixture(side)
            raw[side] = observation.bind_instructions(rows[side], points_, side)
        return raw, rows

    def test_all_thread_local_order_excludes_boundaries_and_keeps_clock_bases(self):
        raw, rows = self.paired()
        result = observation.summarize_intervals(raw, rows, PROBE, [7, 8], SELECT, 1)[0]
        self.assertEqual(result["update"], 8)
        for side in observation.TRACES:
            sample = result[side]
            self.assertEqual(sample["events"][0]["sequence"], sample["first_sequence_exclusive"] + 1)
            self.assertEqual(sample["events"][-1]["sequence"], sample["last_sequence_exclusive"] - 1)
        self.assertNotEqual(result["native"]["phase_source_counts"], result["oracle"]["phase_source_counts"])
        self.assertEqual(result["native"]["events"][0]["clock_raw"], 100)
        self.assertEqual(result["oracle"]["events"][0]["clock_raw"], 7)

    def test_raw_overlay_link_upper_bits_and_input_mismatches_are_rejected(self):
        for field in ("pc", "r29_hi", "r31_hi", "r31_lo", "controller_polls", "m800a9e90"):
            raw, rows = self.paired()
            raw["oracle"][3][field] ^= 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                observation.summarize_intervals(raw, rows, PROBE, [7, 8], SELECT, 1)
        raw, rows = self.paired()
        raw["oracle"][-3]["r31_hi"] = 0
        with self.assertRaises(ValueError):
            observation.summarize_intervals(raw, rows, PROBE, [7, 8], SELECT, 1)

    def test_missing_occurrences_and_invalid_bounds_are_rejected(self):
        raw, rows = self.paired()
        for occurrence in (0, True, 4097, 2):
            with self.subTest(occurrence=occurrence), self.assertRaises(ValueError):
                observation.summarize_intervals(raw, rows, PROBE, [7, 8], SELECT, occurrence)

    def qualify(self, mutation=None):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            capture, reference = base / "capture", base / "control"
            raw, event_rows = fixture("native")
            image = bytearray(4 * 1024 * 1024)
            image[0x100:0x108] = bytes.fromhex("0c00008000000000")
            for directory in (capture, reference):
                directory.mkdir()
                (directory / observation.TRACES["native"]).write_text("unchanged full update trace")
                for update in (7, 8):
                    (directory / f"focus-update-{update}.rdram").write_bytes(image)
            (capture / "point-probe.tsv").write_text("point fixture")
            write_events(capture / "device-events.tsv", event_rows, "native")
            spec = events.specification(True, [int(p, 16) for p in PROBE["pcs"]], [7, 8], side="native", qualified_engine=True)
            metadata = {key: "pin" for key in ("source_export", "input_sha256", "rom_sha256", "initial_flash_sha256", "initial_pak_sha256")}
            metadata.update(exit_code=0, completed_update_trace_complete=True, focused_update_capture_complete=True,
                probe_target_reached=True, focused_update_range=[7, 8], execution_profile="original-os-probe", target_retraces=100,
                point_probe={"pcs": spec["pcs"], "words": [0x800a9e90], "phase": points.PHASE, "complete": True,
                             "sha256": observation.digest(capture / "point-probe.tsv"), "events": len(raw)},
                device_events={**spec, **events.summary(capture / "device-events.tsv", spec, side="native"),
                               "sha256": observation.digest(capture / "device-events.tsv")})
            (reference / "native-result.json").write_text(json.dumps(metadata))
            if mutation == "trace":
                (capture / observation.TRACES["native"]).write_text("changed")
            if mutation == "snapshot":
                (capture / "focus-update-8.rdram").write_bytes(b"X" + image[1:])
            if mutation == "failed-contract": metadata["poll_semantic_hash_trace_complete"] = False
            if mutation == "input": metadata["input_sha256"] = "changed"
            if mutation == "declared-count": metadata["device_events"]["events"] += 1
            if mutation == "gpr": raw[0]["r3_hi"] ^= 1
            if mutation == "opcode":
                # Concordant probes with an opcode not present in the captured memory.
                raw[0]["opcode"] = event_rows[0]["opcode"] = 1
                write_events(capture / "device-events.tsv", event_rows, "native")
                metadata["device_events"]["sha256"] = observation.digest(capture / "device-events.tsv")
            if mutation == "trace-digest": metadata["device_events"]["sha256"] = "0" * 64
            (capture / "native-result.json").write_text(json.dumps(metadata))
            def read(*args, **kwargs):
                if mutation == "concurrent-change":
                    (reference / "native-result.json").write_text("changed during measurement")
                return raw
            with patch.object(observation.points, "read", side_effect=read), patch.object(observation, "_records_at",
                    return_value={u: {"update": u, "actors": []} for u in (7, 8)}):
                return observation.qualify_side(capture, reference, PROBE, [7, 8], "native")

    def test_side_qualification_checks_full_snapshots_and_raw_event_correspondence(self):
        raw, rows, evidence = self.qualify()
        self.assertEqual(evidence["instructions"], len(raw))
        self.assertEqual(evidence["events"], len(rows))
        self.assertEqual(len(evidence["snapshots"]), 2)

    def test_tampered_evidence_and_failed_capture_cannot_qualify(self):
        for mutation in ("trace", "snapshot", "failed-contract", "input", "declared-count", "gpr", "opcode", "trace-digest", "concurrent-change"):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.qualify(mutation)


if __name__ == "__main__":
    unittest.main()
