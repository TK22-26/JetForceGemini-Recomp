import json
from pathlib import Path
import tempfile
import unittest

from scripts.autonomy import execution_contract as execution
from scripts.autonomy.determinism_job import determinism_id
from scripts.phase95_bridge import digest, isolate_n64_bindings


class ExecutionContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.files = {}
        for name in ("native", "emulator"):
            directory = self.root / name
            directory.mkdir()
            binary = directory / (name + ".exe")
            binary.write_bytes(name.encode())
            (directory / "dependency.dll").write_bytes(b"first")
            self.files[name] = str(binary)
        self.config = self.root / "emulator/config.ini"
        self.config.write_text(json.dumps({
            "PreferredCores": {"N64": "Mupen64Plus"},
            "AllTrollers": {"Nintendo 64 Controller": {"A": "keyboard"}}}))
        self.packet = {"pin_files": self.files,
                       "execution": execution.capture(self.files, "original-os-probe")}

    def native(self):
        return {"execution_profile": "original-os-probe",
                "native_runtime_sha256": self.packet["execution"]["native_runtime_sha256"],
                "guest_os_probe": True, "guest_leaf_probe": True,
                "renderer_writeback_probe": True,
                "si_count_probe": False, "controller_guest_init_probe": False}

    def test_isolated_config_pin_matches_real_writer_including_newlines(self):
        config = self.root / "isolated.ini"
        config.write_text(json.dumps(isolate_n64_bindings(
            json.loads(self.config.read_text())), indent=2) + "\n", encoding="utf-8")
        self.assertEqual(digest(config), self.packet["execution"]["oracle_config_sha256"])
        execution.require_current(self.packet)

    def test_dll_change_is_detected_with_unchanged_executable(self):
        before = digest(Path(self.files["native"]))
        (self.root / "native/dependency.dll").write_bytes(b"changed")
        self.assertEqual(digest(Path(self.files["native"])), before)
        self.assertFalse(execution.current(self.packet))
        with self.assertRaisesRegex(ValueError, "runtime or oracle config"):
            execution.require_current(self.packet)

    def test_source_config_change_is_detected_even_if_bindings_are_removed(self):
        settings = json.loads(self.config.read_text())
        settings["AllTrollers"]["Nintendo 64 Controller"]["A"] = "different"
        self.config.write_text(json.dumps(settings))
        self.assertFalse(execution.current(self.packet))

    def test_result_cannot_silently_fall_back_to_another_profile(self):
        execution.check_native(self.packet, self.native())
        for key, value in (("guest_os_probe", False),
                           ("execution_profile", "cooperative"),
                           ("si_count_probe", True),
                           ("native_runtime_sha256", "0" * 64)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                execution.check_native(self.packet, dict(self.native(), **{key: value}))
        with self.assertRaises(ValueError):
            execution.check_native({}, self.native())

    def test_candidate_uses_its_own_runtime_with_the_same_profile(self):
        result = dict(self.native(), native_runtime_sha256="1" * 64)
        execution.check_native(self.packet, result, candidate_runtime="1" * 64)
        with self.assertRaises(ValueError):
            execution.check_native(self.packet, result, candidate_runtime="2" * 64)

    def test_oracle_config_and_runtime_cannot_change(self):
        contract = self.packet["execution"]
        result = {"runtime_sha256": contract["oracle_runtime_sha256"],
                  "config_sha256": contract["oracle_config_sha256"]}
        execution.check_oracle(self.packet, result)
        for key, value in (("runtime_sha256", "0" * 64),
                           ("config_sha256", "0" * 64),
                           ("mupen_cpu_core_override", 0)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                execution.check_oracle(self.packet, dict(result, **{key: value}))

    def test_identity_distinguishes_profiles_and_dlls(self):
        args = ("0" * 64, "1" * 64, "2" * 40, 3000, 2, 2)
        legacy = determinism_id(*args)
        original = determinism_id(*args, self.packet["execution"])
        cooperative = determinism_id(*args, dict(self.packet["execution"], profile="cooperative"))
        changed = determinism_id(*args, dict(self.packet["execution"], native_runtime_sha256="0" * 64))
        self.assertEqual(len({legacy, original, cooperative, changed}), 4)
        self.assertEqual(execution.cli({}), ["--execution-profile", "cooperative"])

    def test_incomplete_or_null_contract_rejected(self):
        for contract in (None, {}, {"profile": "original-os-probe"},
                         dict(self.packet["execution"], profile="unknown")):
            with self.subTest(contract=contract), self.assertRaises(ValueError):
                execution.validate({"execution": contract})


if __name__ == "__main__":
    unittest.main()
