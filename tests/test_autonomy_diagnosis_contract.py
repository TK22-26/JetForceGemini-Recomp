import json
from pathlib import Path
import tempfile
import unittest

from scripts.autonomy.supervisor import (
    BOUNDED_DIAGNOSIS_SCHEMA_FILE, DIAGNOSIS_SCHEMA_FILE, SupervisorError,
    bounded_diagnosis_contract, diagnosis_schema_file, file_sha256,
    validate_diagnosis, validate_diagnosis_format,
)


class DiagnosisContractTests(unittest.TestCase):
    def report(self):
        return {"classification": "insufficient_evidence", "alignment": "unvalidated",
                "first_supported_retrace": None, "confidence": "medium",
                "evidence": ["recorded observation"], "hypothesis": "unproved",
                "next_test": "bounded test"}

    def test_schema_exposes_existing_limits_without_changing_legacy_identity(self):
        legacy = json.loads(DIAGNOSIS_SCHEMA_FILE.read_text())
        schema = json.loads(BOUNDED_DIAGNOSIS_SCHEMA_FILE.read_text())
        self.assertNotIn("maxLength", legacy["properties"]["next_test"])
        for key in ("hypothesis", "next_test"):
            self.assertEqual(schema["properties"][key]["minLength"], 1)
            self.assertEqual(schema["properties"][key]["maxLength"], 1000)
        self.assertEqual(schema["properties"]["evidence"]["maxItems"], 12)
        self.assertEqual(schema["properties"]["evidence"]["items"]["maxLength"], 500)
        self.assertEqual(schema["properties"]["first_supported_retrace"]["minimum"], 0)

    def test_version_and_exact_schema_hash_are_pinned(self):
        self.assertEqual(diagnosis_schema_file({"kind": "diagnose"}), DIAGNOSIS_SCHEMA_FILE)
        packet = {"kind": "diagnose", "diagnosis_contract": bounded_diagnosis_contract()}
        self.assertEqual(diagnosis_schema_file(packet), BOUNDED_DIAGNOSIS_SCHEMA_FILE)
        for contract in (None, {"version": 3, "sha256": "a" * 64},
                         {"version": 2, "sha256": "a" * 64}):
            with self.assertRaises(SupervisorError):
                diagnosis_schema_file(dict(packet, diagnosis_contract=contract))
        with self.assertRaises(SupervisorError):
            diagnosis_schema_file(dict(packet, kind="implement"))

    def test_exact_runtime_bounds_are_not_relaxed(self):
        report = self.report()
        report.update(hypothesis="h" * 1000, next_test="t" * 1000, evidence=["e" * 500] * 12)
        validate_diagnosis(report)
        for key in ("hypothesis", "next_test"):
            with self.assertRaisesRegex(SupervisorError, "bounded"):
                validate_diagnosis(dict(report, **{key: "x" * 1001}))
        with self.assertRaisesRegex(SupervisorError, "evidence"):
            validate_diagnosis(dict(report, evidence=["x" * 501]))

    def test_format_recovery_preserves_evidence_and_certainty_and_source_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original.json"
            original = self.report()
            original["next_test"] = "t" * 1001
            source.write_text(json.dumps(original))
            packet = {"diagnosis_format_source": {"path": str(source), "sha256": file_sha256(source)}}
            shorter = dict(original, next_test="Same bounded proposal, compressed.")
            validate_diagnosis(shorter)
            validate_diagnosis_format(packet, shorter)
            for key, value in (("classification", "other"), ("alignment", "validated"),
                               ("first_supported_retrace", 1), ("confidence", "high"),
                               ("evidence", ["invented observation"])):
                with self.subTest(key=key), self.assertRaisesRegex(SupervisorError, "evidence or certainty"):
                    validate_diagnosis_format(packet, dict(shorter, **{key: value}))
            source.write_text("changed")
            with self.assertRaisesRegex(SupervisorError, "source changed"):
                validate_diagnosis_format(packet, shorter)


if __name__ == "__main__":
    unittest.main()
