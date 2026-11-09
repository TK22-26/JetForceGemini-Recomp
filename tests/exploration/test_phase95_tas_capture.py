import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from scripts import phase95_tas_capture as capture


class TasCaptureTests(unittest.TestCase):
    def test_movie_metadata_and_frame_count(self):
        with tempfile.TemporaryDirectory() as directory:
            movie = Path(directory) / "sample.bk2"
            with zipfile.ZipFile(movie, "w") as archive:
                archive.writestr("Header.txt", "\n".join((
                    "MovieVersion BizHawk v2.0.0", "emuVersion Version 2.9.1",
                    "Platform N64", "Core Mupen64Plus",
                    f"SHA1 {capture.JP_ROM_SHA1.upper()}")))
                archive.writestr("Input Log.txt", "[Input]\nLogKey:x\n|a|\n|b|\n[/Input]\n")
            info = capture.inspect_movie(movie)
            self.assertEqual(info["frames"], 2)
            self.assertEqual(len(info["movie_sha256"]), 64)

    def test_wrapper_and_wrong_build_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            movie = Path(directory) / "sample.bk2"
            with zipfile.ZipFile(movie, "w") as archive:
                archive.writestr("nested.bk2", b"not an extracted BK2")
            with self.assertRaisesRegex(ValueError, "direct BK2"):
                capture.inspect_movie(movie)
            with zipfile.ZipFile(movie, "w") as archive:
                archive.writestr("Header.txt", "SHA1 0000\nemuVersion Version 2.9.1\n"
                                 "Platform N64\nCore Mupen64Plus\n")
                archive.writestr("Input Log.txt", "|a|\n")
            with self.assertRaisesRegex(ValueError, "pinned Japanese"):
                capture.inspect_movie(movie)

    def test_trace_requires_contiguous_unverified_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "frames.tsv"
            trace.write_text("schema\t1\nprobe_status\tunverified-jp\n"
                             "frame\tmovie_mode\tinput_polls_since_worker_start\traw\n"
                             "3\tPLAY\t1\t00\n4\tPLAY\t2\t01\n")
            self.assertEqual(capture.parse_trace(trace, 3, 4)["captured_frames"], 2)
            with self.assertRaisesRegex(ValueError, "interval"):
                capture.parse_trace(trace, 3, 5)
            trace.write_text(trace.read_text().replace("4\tPLAY", "5\tPLAY"))
            with self.assertRaisesRegex(ValueError, "missing"):
                capture.parse_trace(trace, 3, 4)

    def test_resume_requires_matching_identity_and_state_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            prior = Path(directory)
            state = prior / "continuation.State"
            state.write_bytes(b"synthetic state")
            identity = {key: "pin" for key in
                        ("rom_sha1", "rom_sha256", "movie_sha256",
                         "movie_frames", "emulator_sha256", "runtime_sha256",
                         "script_sha256")}
            result = {**identity, "complete": True, "last": 99,
                      "continuation_sha256": capture.digest(state)}
            (prior / "result.json").write_text(json.dumps(result))
            self.assertEqual(capture.validate_resume(prior, identity, 100),
                             (state, result["continuation_sha256"]))
            with self.assertRaisesRegex(ValueError, "noncontiguous"):
                capture.validate_resume(prior, identity, 101)
            state.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                capture.validate_resume(prior, identity, 100)

    def test_invalid_bounds_do_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            emulator = root / "EmuHawk.exe"
            emulator.write_bytes(b"synthetic")
            output = root / "output"
            with self.assertRaisesRegex(ValueError, "bounded"):
                capture.capture(output, emulator, root / "rom", root / "movie",
                                first=0, last=capture.MAX_SEGMENT_FRAMES)
            self.assertFalse(output.exists())

    def test_capture_records_parent_continuation_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            emulator = source / "EmuHawk.exe"
            emulator.write_bytes(b"synthetic emulator")
            rom = root / "rom.z64"
            rom.write_bytes(b"synthetic rom")
            movie = root / "movie.bk2"
            movie.write_bytes(b"synthetic movie")
            prior = root / "prior"
            prior.mkdir()
            state = prior / "continuation.State"
            state.write_bytes(b"synthetic state")
            script_hash = capture.digest(Path(capture.__file__).with_suffix(".lua"))
            pins = {"rom_sha1": capture.JP_ROM_SHA1,
                    "rom_sha256": capture.digest(rom),
                    "movie_sha256": capture.digest(movie),
                    "movie_frames": 2,
                    "emulator_sha256": capture.digest(emulator),
                    "runtime_sha256": "synthetic-runtime",
                    "script_sha256": script_hash}
            parent_hash = capture.digest(state)
            (prior / "result.json").write_text(json.dumps({**pins,
                "complete": True, "last": 0,
                "continuation_sha256": parent_hash}))

            class FakeProcess:
                pid = 42

                def __init__(self, command, *, cwd, **kwargs):
                    output = cwd.parent
                    (output / "frames.tsv").write_text(
                        "schema\t1\nprobe_status\tunverified-jp\n"
                        "frame\tmovie_mode\tinput_polls_since_worker_start\traw\n"
                        "1\tPLAY\t0\t00\n")
                    (output / "done.tsv").write_text(
                        "schema\t1\nfirst\t1\nlast\t1\nmovie_length\t2\n")
                    (output / "continuation.State").write_bytes(b"next state")

                def wait(self, timeout):
                    return 0

            with mock.patch.object(capture, "inspect_movie", return_value={
                    "frames": 2, "movie_sha256": pins["movie_sha256"]}), \
                    mock.patch.object(capture, "sha1", return_value=capture.JP_ROM_SHA1), \
                    mock.patch.object(capture, "runtime_digest", return_value="synthetic-runtime"), \
                    mock.patch.object(capture, "MOVIE_SHA256", pins["movie_sha256"]), \
                    mock.patch.object(capture, "JP_ROM_SHA256", pins["rom_sha256"]), \
                    mock.patch.object(capture, "BIZHAWK_291_EXE_SHA256", pins["emulator_sha256"]), \
                    mock.patch.object(capture, "BIZHAWK_291_RUNTIME_SHA256", "synthetic-runtime"), \
                    mock.patch.object(capture, "MOVIE_FRAMES", 2), \
                    mock.patch.object(capture.subprocess, "Popen", FakeProcess):
                result = capture.capture(root / "out", emulator, rom, movie,
                                         first=1, last=1, resume_from=prior)
            manifest = json.loads((root / "out" / "manifest.json").read_text())
            self.assertEqual(manifest["parent_continuation_sha256"], parent_hash)
            self.assertEqual(result["parent_continuation_sha256"], parent_hash)


if __name__ == "__main__":
    unittest.main()
