"""Moved native code must remain part of current evidence identity."""
from pathlib import Path
import tempfile
import unittest
from scripts.native_source_files import NATIVE_MODULE_FILES, NATIVE_MODULE_CLOSURE
from scripts.autonomy import controller_return_job, event_pair_job, input_focus_job
from scripts import verify_phase6_native_boot, build_phase6_completion_manifest

ROOT = Path(__file__).resolve().parents[2]

class NativeSourceClosureTests(unittest.TestCase):
    def test_inventory_covers_every_private_module_and_build_input(self):
        actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / "src/boot/native").iterdir() if p.is_file()}
        self.assertEqual(set(NATIVE_MODULE_FILES), actual)
        self.assertEqual(len(NATIVE_MODULE_CLOSURE), len(set(NATIVE_MODULE_CLOSURE)))
        for name in NATIVE_MODULE_CLOSURE:
            self.assertTrue((ROOT / name).is_file(), name)

    def test_moved_implementation_and_header_change_all_capture_identities(self):
        jobs = (controller_return_job, event_pair_job, input_focus_job)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in set().union(*(set(job.TOOL_FILES) for job in jobs)):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name, encoding="utf-8")
            before = [job.tool_sha256(root) for job in jobs]
            for name in ("src/boot/native/guest_execution.cpp", "src/boot/native/runtime_state.hpp"):
                path = root / name
                path.write_text(name + " changed", encoding="utf-8")
                self.assertTrue(all(job.tool_sha256(root) != digest for job, digest in zip(jobs,before)))
                path.write_text(name, encoding="utf-8")
            (root / "src/boot/native/runtime_state.hpp").unlink()
            for job in jobs:
                with self.assertRaises(OSError):
                    job.tool_sha256(root)

    def test_current_native_producer_and_verifier_bind_the_same_modules(self):
        producer = verify_phase6_native_boot.SOURCE_CLOSURE
        verifier = build_phase6_completion_manifest.SOURCE_CLOSURE
        self.assertEqual(producer, verifier)
        for closure in (producer, build_phase6_completion_manifest.BOUND_FILES):
            self.assertTrue(set(NATIVE_MODULE_CLOSURE).issubset(closure))
            self.assertEqual(len(closure), len(set(closure)))
