import tempfile
import unittest
from pathlib import Path

from scripts.phase9_controller_return_pair import native_capable


class ControllerReturnPairTests(unittest.TestCase):
    def test_native_capability_marker_can_cross_a_read_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.exe"
            path.write_bytes(b"x" * (1024 * 1024 - 5) +
                             b"JFG_PHASE9_CONTROLLER_RETURN" + b"y")
            self.assertTrue(native_capable(path))
            path.write_bytes(b"JFG_PHASE9_CONTROLLER_RETUR_" + b"y")
            self.assertFalse(native_capable(path))


if __name__ == "__main__":
    unittest.main()
