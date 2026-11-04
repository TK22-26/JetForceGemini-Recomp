import math
import struct
import unittest
from tests.evidence.aim_release_trace import analyze, camera_position


def bits(value):
    return struct.unpack(">I", struct.pack(">f", value))[0]


def fixture(*, snap=False, delayed=False, marker=True, frames=50, movement=False):
    rows = []
    def event(name, words):
        rows.append("1\t"+name+"\t"+"\t".join(format(v, "x") for v in words)+"\n")
    for index in range(frames+1):
        vi = 100+index*2
        z = 0 if index == 0 else 100*(1-math.exp(-index/5))
        if snap and index > 0:
            z = 100
        if delayed:
            z = 0 if index < 10 else 100
        state = [vi, 0x80001000, 11 if index == 0 else 0, 0, 0, 0, 0,
                 bits(10 if movement and index > 2 else 0), 0, 0, 0, 0, 0, 0, 2]
        if index == 1 and marker:
            event("pc-aim-return-start", [vi, state[1], 0, 0, 0])
        matrix = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, -z, 1]
        if index > 0:
            event("pc-shoulder-camera", [vi, state[1], 0, 0, 0, 0, bits(z)])
        event("pc-shoulder", state)
        event("camera-emitted-pose", [vi, 92, 0x80002000, 0, 0, index]+
              [bits(x) for x in matrix]+[0]*32)
    return rows


class AimReleaseTraceTests(unittest.TestCase):
    def test_gradual_rendered_return(self):
        result = analyze(fixture(), minimum_releases=1)
        self.assertTrue(result["complete"], result)
        self.assertLess(result["maximum_adapter_error"], 0.001)

    def test_old_instant_return_fails_even_with_a_start_event(self):
        result = analyze(fixture(snap=True), minimum_releases=1)
        self.assertFalse(result["complete"])
        self.assertAlmostEqual(result["releases"][0]["first_step_fraction"], 1)

    def test_delaying_the_snap_is_not_a_sweep(self):
        self.assertFalse(analyze(fixture(delayed=True), minimum_releases=1)["complete"])

    def test_missing_ownership_event_and_insufficient_coverage_fail(self):
        self.assertFalse(analyze(fixture(marker=False), minimum_releases=1)["complete"])
        self.assertFalse(analyze(fixture())["complete"])

    def test_short_or_moving_fixture_is_not_qualified(self):
        self.assertFalse(analyze(fixture(frames=10), minimum_releases=1)["complete"])
        self.assertFalse(analyze(fixture(movement=True), minimum_releases=1)["complete"])

    def test_view_inverse_uses_rotation_and_rejects_projection(self):
        # Camera at (3,4,5), with a 90-degree Y rotation in the view basis.
        matrix = [0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0, -5, -4, 3, 1]
        self.assertEqual(camera_position([bits(x) for x in matrix]), (3, 4, 5))
        matrix[15] = 0
        with self.assertRaises(ValueError):
            camera_position([bits(x) for x in matrix])

    def test_vi_can_advance_between_update_and_camera_emission(self):
        rows = fixture()
        for index, line in enumerate(rows):
            if "\tcamera-emitted-pose\t" in line:
                cells = line.rstrip().split("\t")
                cells[2] = format(int(cells[2], 16)+1, "x")
                rows[index] = "\t".join(cells)+"\n"
        self.assertTrue(analyze(rows, minimum_releases=1)["complete"])

    def test_view_rotation_snap_cannot_pass_as_a_position_sweep(self):
        rows = fixture()
        for index, line in enumerate(rows):
            if "\tpc-shoulder\t" in line:
                cells = line.rstrip().split("\t")
                if int(cells[4], 16) == 0:
                    cells[14] = "1000"
                    rows[index] = "\t".join(cells)+"\n"
        self.assertFalse(analyze(rows, minimum_releases=1)["complete"])

    def test_malformed_observation_fails_closed(self):
        with self.assertRaises(ValueError):
            analyze(["1\tpc-shoulder\t0\n"])


if __name__ == "__main__":
    unittest.main()
