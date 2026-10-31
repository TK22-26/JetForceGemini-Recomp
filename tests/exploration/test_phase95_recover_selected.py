import hashlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock
from scripts.phase95_recover_selected import recover
from scripts.phase95_observation import ObservationError


class RecoveryTests(unittest.TestCase):
    def test_exact_and_mismatching_recovery(self):
        memory = bytes(0x400000)
        metadata = {"sequence": 1, "frame": 24, "polls": 12, "player": 123}
        for matches in (True, False):
            with tempfile.TemporaryDirectory() as directory:
                worker = Mock(root=Path(directory))
                worker.observe.return_value = metadata, memory
                selected = {"actions": [{"frames": 24}], "trajectory": [{**metadata,
                    "sha256": hashlib.sha256(memory).hexdigest() if matches else "0" * 64}]}
                if matches:
                    recover(worker, selected)
                    worker.checkpoint.assert_called_once_with("save", "f1")
                else:
                    with self.assertRaises(ObservationError):
                        recover(worker, selected)
                    worker.checkpoint.assert_not_called()
                    self.assertFalse((worker.root / "recovery-result.json").exists())

    def test_invalid_actions_do_not_execute(self):
        for actions, trajectory in (([], []), ([{"frames": 0}], [{}]),
                                    ([{"frames": 121}], [{}]), ([{"frames": 1}], []),
                                    ([{"frames": 1}], [{}])):
            worker = Mock()
            with self.assertRaises(ValueError):
                recover(worker, {"actions": actions, "trajectory": trajectory})
            worker.act.assert_not_called()


if __name__ == "__main__":
    unittest.main()
