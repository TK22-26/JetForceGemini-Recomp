"""Behavioral gates for private Phase 6 inputs and disabled native targets."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CMAKE = next(
    (
        candidate
        for candidate in (
            shutil.which("cmake"),
            Path("C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"),
            Path("C:/Program Files/Microsoft Visual Studio/2022/Professional/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"),
            Path("C:/Program Files/Microsoft Visual Studio/2022/Enterprise/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"),
        )
        if candidate and Path(candidate).is_file()
    ),
    None,
)


@unittest.skipUnless(CMAKE, "CMake is required")
class Phase6CmakeBehavior(unittest.TestCase):
    def configure(self, source: Path, build: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [CMAKE, "-S", str(source), "-B", str(build)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    def test_private_file_rejects_missing_directory_and_tracked_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            source = workspace / "source"
            source.mkdir()
            (source / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                "project(phase6_private_file_probe NONE)\n"
                f"include(\"{(ROOT / 'cmake/GeneratedCode.cmake').as_posix()}\")\n"
                "jfg_resolve_private_file(result \"${INPUT}\" INPUT)\n",
                encoding="utf-8",
            )
            directory = workspace / "directory"
            directory.mkdir()
            ignored = ROOT / "build-phase6-cmake-test"
            ignored.mkdir(exist_ok=True)
            # A failed assertion must not leave the scratch build directory
            # behind; the next run would otherwise see pre-existing state.
            self.addCleanup(shutil.rmtree, ignored, ignore_errors=True)
            identification = ignored / "identification.json"
            identification.write_text("{}", encoding="utf-8")
            link = workspace / "identification-link.json"
            try:
                link.symlink_to(identification)
            except OSError:
                link = None
            for name, value in {
                "missing": workspace / "missing.json",
                "directory": directory,
                "tracked": ROOT / "CMakeLists.txt",
                "ignored": identification,
                **({"symlink": link} if link is not None else {}),
            }.items():
                with self.subTest(name=name):
                    result = subprocess.run(
                        [CMAKE, "-S", str(source), "-B", str(workspace / f"build-{name}"),
                         f"-DINPUT={value}"],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=30,
                    )
                    if name == "ignored":
                        self.assertEqual(result.returncode, 0, result.stderr)
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn(
                            "regular file" if name in {"missing", "directory", "symlink"} else "ignored by git",
                            result.stderr.lower(),
                        )

    def test_native_gate_requires_generated_code_before_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [CMAKE, "-S", str(ROOT), "-B", str(Path(temporary) / "build"),
                 "-DJFG_BUILD_PHASE6_NATIVE_BOOT=ON", "-DJFG_ENABLE_GENERATED_CODE=OFF"],
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("JFG_BUILD_PHASE6_NATIVE_BOOT requires JFG_ENABLE_GENERATED_CODE", result.stderr)

    def test_native_target_is_absent_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            build = Path(temporary) / "build"
            result = self.configure(ROOT, build)
            self.assertEqual(result.returncode, 0, result.stderr)
            target = subprocess.run(
                [CMAKE, "--build", str(build), "--target", "jfg-native-boot"],
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            self.assertNotEqual(target.returncode, 0)


if __name__ == "__main__":
    unittest.main()
