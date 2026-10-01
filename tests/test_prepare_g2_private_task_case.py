from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_g2_private_task_case.py"


class PrepareG2PrivateTaskCaseTests(unittest.TestCase):
    def invoke(self, *arguments: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, arguments)],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )

    def test_graphics_and_audio_cases_are_bounded_v3_input_only_records(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="prepare-g2-private-task-", dir=ROOT / "tools"
        ) as temporary:
            root = Path(temporary)
            descriptor = root / "descriptor.bin"
            program = root / "program.bin"
            data = root / "data.bin"
            commands = root / "commands.bin"
            descriptor.write_bytes(bytes(64))
            program.write_bytes(b"\x01\x02\x03\x04")
            data.write_bytes(b"\x05\x06\x07\x08")
            commands.write_bytes(b"\xb8\0\0\0\0\0\0\0")

            memories = []
            for index in range(4):
                memory = root / f"memory-{index}.bin"
                memory.write_bytes(bytes([index]) * (2 * 1024 * 1024))
                memories.append(memory)
            graphics_output = root / "graphics-case.bin"
            arguments: list[object] = [
                "graphics",
                "--descriptor",
                descriptor,
                "--program",
                program,
                "--program-data",
                data,
                "--commands",
                commands,
            ]
            for memory in memories:
                arguments.extend(("--memory", memory))
            arguments.extend(("--output", graphics_output))
            result = self.invoke(*arguments)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            packed = graphics_output.read_bytes()
            self.assertEqual(packed[:8], b"JFG2PRD1")
            self.assertEqual(struct.unpack_from("<II", packed, 8), (3, 1))
            self.assertEqual(struct.unpack_from("<I", packed, 16)[0], len(packed) - 20)
            self.assertNotEqual(self.invoke(*arguments).returncode, 0)

            memory = root / "audio-memory.bin"
            index = root / "audio-index.tsv"
            output = root / "audio-case.bin"
            memory.write_bytes(b"\x10\x20\x30\x40\x50\x60\x70\x80")
            index.write_text("output\tmain\t00000200\t8\n", encoding="ascii")
            result = self.invoke(
                "audio",
                "--descriptor",
                descriptor,
                "--program",
                program,
                "--program-data",
                data,
                "--commands",
                commands,
                "--memory",
                memory,
                "--index",
                index,
                "--output",
                output,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            packed = output.read_bytes()
            self.assertEqual(struct.unpack_from("<II", packed, 8), (3, 2))
            self.assertEqual(struct.unpack_from("<II", packed, 20), (0x200, 8))


if __name__ == "__main__":
    unittest.main()
