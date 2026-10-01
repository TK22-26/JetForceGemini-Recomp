from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phase95_tas_index", ROOT / "scripts" / "phase95_tas_index.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def controller(x: int = 0, y: int = 0, buttons: str = "") -> str:
    markers = "".join("X" if name in buttons.split("+") else "." for name in MODULE.BUTTON_NAMES)
    return f"{x:5d},{y:5d},{markers}"


def row(flags: str = "..", p1: str | None = None, p2: str | None = None) -> str:
    return f"|{flags}|{p1 or controller()}|{p2 or controller()}|"


def make_bk2(path: Path, *, rows: list[str] | None = None, sha1: str = MODULE.EXPECTED_SHA1,
             version: str = MODULE.EXPECTED_VERSION, connections: list[bool] | None = None,
             close: bool = True, log_key: str | None = None) -> None:
    if rows is None:
        rows = [row(), row("R.", controller(12, -34, "A+Start")),
                row("..", controller(12, -34, "A+Start"), controller(0, 1, "B")),
                row(".P", controller(), controller())]
    header = (
        "MovieVersion BizHawk v2.0.0\n"
        "Author Fixture\n"
        f"emuVersion Version {version}\n"
        f"OriginalEmuVersion Version {version}\n"
        "Platform N64\n"
        "GameName Star Twins (Japan)\n"
        f"SHA1 {sha1}\n"
        "Core Mupen64Plus\n"
        "rerecordCount 42\n"
    )
    sync = {"o": {"Core": 1, "Rsp": 0, "VideoPlugin": 5,
                  "DisableExpansionSlot": True,
                  "Controllers": [{"PakType": 1, "IsConnected": value} for value in
                                  (connections or [True, True, False, False])]}}
    log = "[Input]\nLogKey:" + (log_key or "|".join(MODULE.LOG_FIELDS) + "|") + "\n"
    log += "\n".join(rows) + "\n"
    if close:
        log += "[/Input]\n"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BizVersion.txt", f"Version {version}\n")
        archive.writestr("Header.txt", header)
        archive.writestr("SyncSettings.json", json.dumps(sync))
        archive.writestr("Input Log.txt", log)


class Phase95TasIndexTests(unittest.TestCase):
    def test_indexes_frames_windows_events_and_controller_activity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.bk2"
            make_bk2(path)
            result = MODULE.index_movie(path, window_size=2, expected_frames=4)
        self.assertEqual(result["schema"], MODULE.SCHEMA)
        self.assertEqual(result["movie"]["rom_sha1"], MODULE.EXPECTED_SHA1)
        self.assertEqual(result["movie"]["sync"]["controller_connected"],
                         [True, True, False, False])
        data = result["input"]
        self.assertEqual(data["frame_count"], 4)
        self.assertEqual(data["reset_power_events"], [
            {"frame": 1, "events": ["reset"]}, {"frame": 3, "events": ["power"]},
        ])
        self.assertEqual([(w["start_frame"], w["end_frame"]) for w in data["windows"]],
                         [(0, 2), (2, 4)])
        self.assertEqual(data["controllers"][0]["active_frames"], 2)
        self.assertEqual(data["controllers"][0]["button_frames"]["A"], 2)
        self.assertEqual(data["controllers"][0]["button_press_edges"]["A"], 1)
        self.assertEqual(data["controllers"][0]["button_press_edges"]["Start"], 1)
        self.assertEqual(data["controllers"][0]["analog_x_min"], 0)
        self.assertEqual(data["controllers"][0]["analog_y_min"], -34)
        self.assertEqual(data["controllers"][1]["button_frames"]["B"], 1)
        self.assertEqual(data["windows"][1]["controllers"][0]["button_press_edges"], {})
        self.assertNotIn("    12", json.dumps(result))

    def test_partial_window_and_cli_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.bk2"
            output = Path(temporary) / "index.json"
            make_bk2(path, rows=[row(), row(), row()])
            self.assertEqual(MODULE.main([str(path), "--output", str(output),
                                          "--window-size", "2", "--expected-frames", "3"]), 0)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["input"]["windows"][-1]["end_frame"], 3)
            self.assertEqual(data["input"]["windows"][-1]["start_frame"], 2)

    def test_rejects_wrong_identity_and_invalid_input(self) -> None:
        cases = [
            {"sha1": "0" * 40},
            {"version": "2.9.2"},
            {"connections": [True, False, False, False]},
            {"close": False},
            {"log_key": "wrong|"},
            {"rows": [row(p1=controller(128))]},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.bk2"
            for options in cases:
                with self.subTest(options=options):
                    make_bk2(path, **options)
                    with self.assertRaises(MODULE.TasIndexError):
                        MODULE.index_movie(path)

    def test_rejects_duplicate_archive_entry_and_frame_count(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.bk2"
            make_bk2(path)
            with self.assertRaisesRegex(MODULE.TasIndexError, "frame count mismatch"):
                MODULE.index_movie(path, expected_frames=5)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(path, "a") as archive:
                    archive.writestr("Header.txt", "duplicate")
            with self.assertRaisesRegex(MODULE.TasIndexError, "duplicate entry"):
                MODULE.index_movie(path)


if __name__ == "__main__":
    unittest.main()
