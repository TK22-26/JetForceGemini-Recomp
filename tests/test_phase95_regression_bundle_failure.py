import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.phase95_regression_bundle import bundle


class RegressionBundleFailureTests(unittest.TestCase):
    def test_native_crash_automatically_invokes_bounded_triage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario = root / "scenario"
            scenario.mkdir()
            (scenario / "scenario-result.json").write_text(json.dumps({
                "kind": "jfg-phase95-goldwood-south-scenario",
                "completed": True, "stages_completed": 7}))
            (scenario / "scenario-stages.jsonl").write_text(
                "".join(json.dumps({"frame": frame}) + "\n" for frame in range(7)))
            output = root / "bundle"

            def fake_export(scenario, selected, **kwargs):
                selected.mkdir()
                (selected / "export-manifest.json").write_text("{}")
                return {"input_sha256": "a" * 64, "controller_polls": 7}

            def fake_native(source, native, *args, **kwargs):
                native.mkdir()
                (native / "native-result.json").write_text("{}")
                raise RuntimeError("synthetic native crash")

            with mock.patch("scripts.phase95_regression_bundle.export", fake_export), \
                    mock.patch("scripts.phase95_regression_bundle.oracle_replay",
                               return_value={"final_rdram_sha256": "b" * 64,
                                             "target_frame": 6}), \
                    mock.patch("scripts.phase95_regression_bundle.repeat_audit",
                               return_value={"all_match": True, "repeat_count": 1}), \
                    mock.patch("scripts.phase95_regression_bundle.native_replay",
                               fake_native), \
                    mock.patch("scripts.phase95_regression_bundle.native_failure_triage",
                               return_value={"reproduced": True}) as triage:
                with self.assertRaisesRegex(RuntimeError, "synthetic native crash"):
                    bundle(scenario, output, "emulator", "rom", "digest",
                           "native", "flash", "pak", repeats=1, failure_trials=3)
            self.assertEqual(triage.call_args.kwargs["max_trials"], 3)
            failure = json.loads((output / "bundle-failure.json").read_text())
            self.assertEqual(failure["native_failure_triage"], {"reproduced": True})
            self.assertEqual(failure["classification"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
