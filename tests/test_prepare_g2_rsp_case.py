from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_g2_rsp_case.py"


class PrepareG2RspCaseTests(unittest.TestCase):
    def test_real_program_bytes_are_packed_once_and_output_is_new_only(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="prepare-g2-rsp-", dir=ROOT / "tools"
        ) as temporary:
            root = Path(temporary)
            graphics = root / "graphics.bin"
            audio = root / "audio.bin"
            output = root / "case.bin"
            graphics.write_bytes(b"\x01\x02\x03\x04")
            audio.write_bytes(b"\x11\x12\x13\x14")
            command = [
                sys.executable,
                str(SCRIPT),
                "--graphics-program",
                str(graphics),
                "--audio-program",
                str(audio),
                "--output",
                str(output),
            ]
            result = subprocess.run(
                command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            payload = output.read_bytes()
            self.assertEqual(payload[:8], b"JFGRSP01")
            self.assertEqual(int.from_bytes(payload[8:10], "little"), 1)
            self.assertEqual(int.from_bytes(payload[10:12], "little"), 4)
            self.assertEqual(payload.count(audio.read_bytes()), 2)
            repeated = subprocess.run(
                command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(repeated.returncode, 0)


if __name__ == "__main__":
    unittest.main()
