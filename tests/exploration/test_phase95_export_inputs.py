import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.phase95_export_inputs import LineageError, export, selected_polls


def put(root, name, data):
    path = root / name
    path.write_text(data)
    return path


def checkpoint(root, slot, polls, session):
    path = put(root, f"checkpoint-{slot}.json", json.dumps({
        "kind": "jfg-phase95-checkpoint", "schema": 1,
        "observation": {"polls": polls}}))
    put(root, f"checkpoint-{slot}.side", f"{session} {polls} 1\n")
    return path


class SelectedInputExportTests(unittest.TestCase):
    def test_checkpoint_load_discards_speculative_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            put(root, "input-polls.tsv", "\n".join((
                "schema\t1\tsession\tabc", "1\t1\t0\t1\t0\t0",
                "checkpoint\t1\tsave\ta1", "2\t2\t2\t2\t0\t0",
                "3\t3\t2\t3\t0\t0", "checkpoint\t3\tload\ta1",
                "2\t4\t4\t4\t0\t0", "")))
            checkpoint(root, "a1", 1, "abc")
            put(root, "bridge-result.txt", "stopped\n")
            put(root, "observations.jsonl", json.dumps({"frame": 10, "polls": 2}) + "\n")
            samples, workers = selected_polls(root)
            self.assertEqual(samples, [(1, 0, 0), (4, 0, 0)])
            self.assertEqual(workers, [str(root.resolve())])
            result = export(root, root / "output")
            self.assertEqual(result["controller_polls"], 2)
            self.assertEqual(result["oracle_final_frame"], 10)
            self.assertEqual((root / "output/controller.input").read_text().splitlines(), [
                "jfg-phase8-input-v2", "0,1,1,0001,0,0", "1,10,1,0004,0,0"])

    def test_imported_checkpoint_grafts_exact_prefix(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            target = base / "target"
            source.mkdir()
            target.mkdir()
            put(source, "input-polls.tsv", "\n".join((
                "schema\t1\tsession\taaa", "1\t1\t0\t32768\t0\t0",
                "checkpoint\t1\tsave\tc1", "2\t2\t2\t0\t0\t0", "")))
            manifest = checkpoint(source, "c1", 1, "aaa")
            put(target, "import-lineage.json", json.dumps({
                "source_manifest": str(manifest),
                "source_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}))
            put(target, "checkpoint-f0.side", "bbb 1 1\n")
            put(target, "input-polls.tsv", "\n".join((
                "schema\t1\tsession\tbbb", "checkpoint\t0\tload\tf0",
                "2\t3\t1\t1\t-60\t60", "")))
            samples, workers = selected_polls(target)
            self.assertEqual(samples, [(32768, 0, 0), (1, -60, 60)])
            self.assertEqual(len(workers), 2)
            put(source, "checkpoint-c1.json", "tampered")
            with self.assertRaisesRegex(LineageError, "manifest changed"):
                selected_polls(target)

    def test_missing_saved_frontier_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            put(root, "input-polls.tsv", "schema\t1\tsession\tabc\n")
            with self.assertRaisesRegex(LineageError, "checkpoint save absent"):
                selected_polls(root, stop_slot="c1")


if __name__ == "__main__":
    unittest.main()
