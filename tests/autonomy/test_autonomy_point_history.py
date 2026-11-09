import copy
import hashlib
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.autonomy import point_anchors, point_experiment, state_word_experiment as words
from scripts.autonomy import point_plan
from scripts.autonomy.supervisor import canonical_bytes, file_sha256, SupervisorError


def history_item():
    return {"observation_id": "old-observation", "source": {"path": "retained", "sha256": "1" * 64},
            "input_prefix_match": True,
            "plan": {"operation": "point-state", "probe": {"entry_pc": "0x80000200", "call_pc": "0x80000100"},
                     "prediction": {"kind": "event-count"}},
            "observation": {"qualification": {"passed": True, "scope": "local-only", "raw": "omit"},
                            "prediction_observed": True, "observations": [{"update": 7, "native": 2, "oracle": 3}]}}


def exhaustive_candidates(images, targets):
    """Independent reference: the previous word-by-word decoder, not find()."""
    first, candidates = images[0], []
    for offset in range(0, len(first) - 8, 4):
        call = int.from_bytes(first[offset:offset + 4], "big")
        if call >> 26 != 3 or first[offset + 4:offset + 8] != bytes(4):
            continue
        target = 0x80000000 | ((call & 0x3ffffff) << 2)
        if target not in targets:
            continue
        entry = target - 0x80000000
        if any(image[offset:offset + 8] != first[offset:offset + 8] or
               image[entry:entry + 4] != first[entry:entry + 4] for image in images):
            continue
        candidates.append({"entry_pc": f"0x{target:08x}", "call_pc": f"0x{0x80000000 + offset:08x}",
                           "return_pc": f"0x{0x80000008 + offset:08x}", "call_opcode": f"0x{call:08x}",
                           "delay_slot": "0x00000000", "entry_opcode": "0x" + first[entry:entry + 4].hex()})
        if len(candidates) > 64:
            raise ValueError("point anchor candidate inventory exceeds budget")
    return candidates


class CandidateSearchTests(unittest.TestCase):
    def test_point_producer_identity_includes_anchor_discovery_code(self):
        anchor = Path(point_anchors.__file__)
        def digest(path):
            return "1" * 64 if path == anchor else "0" * 64
        with patch.object(point_experiment, "file_sha256", side_effect=digest):
            first = point_experiment.tool_sha()
        with patch.object(point_experiment, "file_sha256", return_value="0" * 64):
            second = point_experiment.tool_sha()
        self.assertNotEqual(first, second)

    @staticmethod
    def put_call(image, offset, target):
        image[offset:offset + 8] = (0x0c000000 | ((target & 0x0fffffff) >> 2)).to_bytes(4, "big") + bytes(4)

    def test_equivalent_to_exhaustive_decoder_for_seeded_images(self):
        rng = random.Random(0x1291)
        for seed in range(40):
            image = bytearray(rng.randbytes(4096))
            targets = sorted({0x80000c00 + rng.randrange(64) * 4 for _ in range(12)})
            for _ in range(28):
                self.put_call(image, rng.randrange(700) * 4, rng.choice(targets))
            other = bytearray(image)
            for _ in range(6):
                offset = rng.randrange(len(other))
                other[offset] ^= 0xff
            images = [bytes(image), bytes(other), bytes(image)]
            with self.subTest(seed=seed):
                self.assertEqual(point_anchors.find_candidates(images, targets), exhaustive_candidates(images, targets))

    def test_unaligned_hits_non_nop_and_trailing_bound_keep_exact_semantics(self):
        image = bytearray(256)
        for offset in (1, 17, 36, 80, 120, 248):
            self.put_call(image, offset, 0x800000e0)
        image[84:88] = b"nop?"
        targets = [0x800000e0, 0x800000e1]
        result = point_anchors.find_candidates([bytes(image)] * 2, targets)
        self.assertEqual(result, exhaustive_candidates([bytes(image)] * 2, targets))
        self.assertEqual([row["call_pc"] for row in result], ["0x80000024", "0x80000078"])

    def test_all_snapshots_must_agree_on_call_delay_and_entry(self):
        image = bytearray(256)
        self.put_call(image, 32, 0x800000e0)
        for changed in (32, 36, 224):
            other = bytearray(image)
            other[changed] ^= 1
            with self.subTest(changed=changed):
                self.assertEqual(point_anchors.find_candidates([bytes(image), bytes(image), bytes(other)], [0x800000e0]), [])

    def test_order_is_callsite_order_not_target_order(self):
        image = bytearray(256)
        self.put_call(image, 16, 0x800000e4)
        self.put_call(image, 40, 0x800000e0)
        targets = [0x800000e0, 0x800000e4]
        self.assertEqual(point_anchors.find_candidates([bytes(image)], targets), exhaustive_candidates([bytes(image)], targets))

    def test_candidate_limit_and_no_targets(self):
        image = bytearray(4096)
        for offset in range(0, 65 * 12, 12):
            self.put_call(image, offset, 0x80000c00)
        for finder in (point_anchors.find_candidates, exhaustive_candidates):
            with self.assertRaisesRegex(ValueError, "exceeds budget"):
                finder([bytes(image)], [0x80000c00])
        self.assertEqual(point_anchors.find_candidates([bytes(image)], []), [])


class HistoryInventoryTests(unittest.TestCase):
    def inventory(self, history=None, changed=False):
        image = bytearray(4 * 1024 * 1024)
        image[0x100:0x104] = (0x0c000080).to_bytes(4, "big")
        image[0x200:0x204] = (0x27bdfff8).to_bytes(4, "big")
        other = bytearray(image)
        if changed:
            other[0x200] = 0
        with patch.object(point_anchors, "_records_at", return_value={7: {}}), \
                patch.object(point_anchors, "_snapshot", side_effect=[(bytes(image), {}), (bytes(other), {})]):
            return point_anchors.history_inventory(Path("reference"), [7, 7], {"next_test": "queue ordering"},
                [history_item()] if history is None else history,
                {"qualification": {"passed": True, "scope": "local-calibration"},
                 "summaries": {"native": [{"update": 7, "queue_valid_at_entry": 2, "receives": ["omit"]}],
                               "oracle": [{"update": 7, "queue_valid_at_entry": 3}]}},
                {"path": "calibration", "sha256": "2" * 64})

    def test_qualified_history_restores_target_missing_from_diagnosis(self):
        facts = self.inventory()
        self.assertEqual(facts["schema"], 2)
        self.assertEqual(len(facts["candidates"]), 1)
        self.assertEqual(facts["candidates"][0]["entry_pc"], "0x80000200")
        row = facts["prior_observations"][0]
        self.assertEqual(row["source"], history_item()["source"])
        self.assertTrue(row["input_prefix_match"])
        self.assertNotIn("raw", row["qualification"])
        self.assertEqual(facts["runtime_calibration"]["measurements"]["native"],
                         [{"update": 7, "queue_valid_at_entry": 2}])
        self.assertFalse(facts["alignment_validated"])
        self.assertFalse(facts["runtime_calibration"]["causal_fix_proved"])

    def test_unqualified_prior_probe_does_not_supply_instruction_target(self):
        item = history_item()
        item["observation"]["qualification"]["passed"] = False
        facts = self.inventory([item])
        self.assertEqual(facts["candidates"], [])
        self.assertFalse(facts["prior_observations"][0]["qualification"]["passed"])

    def test_restored_target_still_requires_matching_snapshot_instructions(self):
        self.assertEqual(self.inventory(changed=True)["candidates"], [])

    def test_unqualified_calibration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not qualified"):
            point_anchors.history_inventory(None, [7, 7], {}, [], {"qualification": {"passed": False}}, {})

    def test_new_prose_or_measurements_do_not_authorize_retry(self):
        facts = self.inventory()
        renamed = copy.deepcopy(facts)
        renamed["prior_observations"][0]["measurements"][0]["native"] = 100
        self.assertFalse(point_anchors.adds_candidates(facts, renamed))
        self.assertTrue(point_anchors.adds_candidates({"candidates": []}, facts))


class HistoryRefreshTests(unittest.TestCase):
    def test_consumer_recomputes_pinned_history_instead_of_trusting_fact_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            base = words.identity("point-plan-", "entry")
            binding = {"path": str(state / "runtime.json"), "sha256": "1" * 64}
            runtime = {"binding": binding}
            parent = {"plan_id": "entry", "plan": {"operation": "needs-instrumentation"},
                      "window": [7, 7], "history": [], "baseline_id": "baseline",
                      "baseline_packet": {"source_commit": "2" * 40, "pin_files": {}}}
            facts = {"schema": 2, "candidates": []}
            facts_path = point_experiment.anchor_path(state, "entry", history=True)
            facts_path.parent.mkdir()
            facts_path.write_bytes(canonical_bytes(facts))
            packet = {"job_id": base, "kind": "plan-point", "prerequisites": ["entry", "baseline"],
                      "source_commit": "2" * 40, "pin_files": {},
                      "experiment_contract": point_plan.contract([7, 7], binding["sha256"]),
                      "evidence_files": [binding, words.pin(facts_path)]}
            digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
            message = state / "last-message.txt"
            message.write_text(json.dumps({"operation": "needs-instrumentation", "hypothesis": "ordering",
                "alternative": "control flow", "reason": "before-call span required", "probe": None, "prediction": None}))
            job = {"spec": {"inputs": ["packet:" + digest], "prerequisites": packet["prerequisites"], "pins": {}}}
            result = {"packet_sha256": digest, "pins": {}, "experiment_plan_sha256": file_sha256(message),
                      "experiment_schema_sha256": file_sha256(point_plan.SCHEMA_FILE)}
            with patch.object(point_experiment, "_sealed_result", return_value=(job, result, state / "result.json")), \
                    patch.object(point_experiment, "read_packet", return_value=packet), \
                    patch.object(point_experiment.entry_experiment, "plan_context", return_value=parent), \
                    patch.object(point_experiment.point_runtime, "load", return_value=runtime), \
                    patch.object(point_experiment, "history_facts", return_value=facts):
                context = point_experiment.plan_context(None, None, state, base)
                self.assertEqual(context["plan"]["operation"], "needs-instrumentation")
                facts_path.write_bytes(canonical_bytes({"schema": 2, "candidates": ["invented"]}))
                # Even a freshly pinned altered file must not replace recomputed evidence.
                packet["evidence_files"][-1] = words.pin(facts_path)
                digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
                job["spec"]["inputs"] = ["packet:" + digest]
                result["packet_sha256"] = digest
                with self.assertRaisesRegex(SupervisorError, "contradict"):
                    point_experiment.plan_context(None, None, state, base)

    def test_paths_are_distinct_and_old_facts_stay_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            old = point_experiment.anchor_path(state, "entry")
            new = point_experiment.anchor_path(state, "entry", history=True)
            self.assertNotEqual(old, new)
            old.parent.mkdir()
            old.write_text(json.dumps({"candidates": []}))
            original = old.read_bytes()
            context = {"entry_plan_id": "entry", "plan": {"operation": "needs-instrumentation"},
                       "plan_packet": {"evidence_files": [{"path": str(old)}]}}
            facts = {"candidates": [{"entry_pc": "0x80000200", "call_pc": "0x80000100"}]}
            self.assertTrue(point_experiment.refresh_adds_evidence(context, state, facts))
            self.assertFalse(point_experiment.refresh_adds_evidence(context, state, {"candidates": []}))
            self.assertEqual(old.read_bytes(), original)
            context["plan_packet"]["evidence_files"].append({"path": str(new)})
            self.assertFalse(point_experiment.refresh_adds_evidence(context, state, facts))

    def test_supported_plan_is_not_refreshed(self):
        context = {"plan": {"operation": "point-state"}}
        self.assertFalse(point_experiment.refresh_adds_evidence(context, None, None))

    def test_history_version_is_selected_once_and_terminal_unsupported_stops(self):
        store = MagicMock()
        base = words.identity("point-plan-", "entry")
        store.status_projection.return_value = {"jobs": [
            {"job_id": job, "state": "passed"} for job in (base, base + "-anchors-v1", base + "-history-v2")]}
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(point_experiment, "plan_context", return_value={"plan": {"operation": "needs-instrumentation"}}) as context, \
                patch.object(point_experiment, "has_anchors", return_value=True), \
                patch.object(point_experiment, "queue_plan", side_effect=AssertionError("must not retry")):
            state = Path(temporary)
            self.assertEqual(point_experiment.next_job(store, None, state, None, "entry"), base + "-history-v2")
            context.assert_called_once_with(store, None, state, base + "-history-v2")

    def test_no_new_candidates_leaves_old_unsupported_plan_terminal(self):
        store = MagicMock()
        base = words.identity("point-plan-", "entry")
        store.status_projection.return_value = {"jobs": [{"job_id": base, "state": "passed"}]}
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(point_experiment, "plan_context", return_value={"plan": {"operation": "needs-instrumentation"}}), \
                patch.object(point_experiment, "has_anchors", return_value=False), \
                patch.object(point_experiment, "queue_plan", return_value=None) as queued:
            state = Path(temporary)
            self.assertEqual(point_experiment.next_job(store, None, state, None, "entry"), base)
            queued.assert_called_once_with(store, None, state, None, "entry", refresh_from=base)


if __name__ == "__main__":
    unittest.main()
