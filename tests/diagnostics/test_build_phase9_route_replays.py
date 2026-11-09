from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_phase9_route_replays import (
    Event,
    RouteError,
    ambassador_dialogue_exit_route,
    canonical_route,
    cold_boot_ambassador_exit_route,
    cold_boot_ambassador_probe_route,
    cold_boot_magnus_forest_combat_route,
    cold_boot_door_alignment_probe_route,
    cold_boot_hub_entry_route,
    cold_boot_hub_direction_probe_route,
    cold_boot_jeff_door_probe_route,
    cold_boot_jeff_approach_probe_route,
    cold_boot_jeff_dialogue_probe_route,
    cold_boot_jeff_contact_probe_route,
    cold_boot_jeff_close_probe_route,
    cold_boot_jeff_face_probe_route,
    cold_boot_jeff_turn_action_probe_route,
    cold_boot_jeff_target_action_probe_route,
    cold_boot_jeff_target_close_probe_route,
    cold_boot_jeff_hut_exit_probe_route,
    cold_boot_jeff_dialogue_exit_probe_route,
    cold_boot_jeff_dialogue_complete_probe_route,
    cold_boot_jeff_post_dialogue_fire_probe_route,
    cold_boot_jeff_post_dialogue_exit_probe_route,
    cold_boot_life_force_direction_probe_route,
    cold_boot_life_force_door_probe_route,
    cold_boot_life_force_candidate_probe_route,
    cold_boot_life_force_bridge_probe_route,
    cold_boot_life_force_combat_probe_route,
    cold_boot_life_force_magnus_probe_route,
    cold_boot_life_force_magnus_contact_probe_route,
    cold_boot_life_force_drone_approach_probe_route,
    cold_boot_life_force_drone_forward_probe_route,
    cold_boot_life_force_drone_door_probe_route,
    cold_boot_jeff_hut_route,
    cold_boot_post_ambassador_direction_probe_route,
    cold_boot_shoreline_direction_probe_route,
    cold_boot_startup_cutscene_probe_route,
    cold_boot_to_gameplay_probe_route,
    combat_probe_route,
    controller_disconnect_route,
    jeff_dialogue_exit_fire_probe_route,
    jeff_hut_fire_probe_route,
    load_replay,
    write_replay,
)


class BuildPhase9RouteReplayTests(unittest.TestCase):
    def test_canonical_route_is_bounded_after_the_save_transaction(self) -> None:
        route = canonical_route([Event(0, 35000, 1, 0x2000, 10, -10)])
        self.assertEqual(route, [Event(0, 29600, 1, 0x2000, 10, -10)])

    def test_short_source_cannot_claim_persistent_save_coverage(self) -> None:
        with self.assertRaisesRegex(RouteError, "persistent-save route"):
            canonical_route([Event(0, 100, 1, 0, 0, 0)])

    def test_cold_boot_route_covers_name_entry_and_gameplay_confirmation(self) -> None:
        route = cold_boot_to_gameplay_probe_route()
        self.assertEqual(route[0], Event(1820, 1840, 1, 0x1000, 0, 0))
        self.assertEqual(route[12], Event(4800, 4820, 1, 0x8000, 0, 0))
        self.assertEqual(route[-1], Event(17800, 17810, 1, 0x8000, 0, 0))
        self.assertTrue(all(current.first >= previous.last
                            for previous, current in zip(route, route[1:])))

    def test_startup_cutscene_probe_stops_after_new_name_confirmation(self) -> None:
        route = cold_boot_startup_cutscene_probe_route()
        self.assertEqual(route[-1], Event(4800, 4820, 1, 0x8000, 0, 0))
        self.assertTrue(all(event.last <= 4820 for event in route))

    def test_cold_boot_ambassador_route_waits_for_shared_gameplay_gate(self) -> None:
        route = cold_boot_ambassador_probe_route()
        self.assertEqual(
            route[-3:],
            [
                Event(18120, 18140, 1, 0x8000, 0, 0),
                Event(18200, 19000, 1, 0x0000, 0, 100),
                Event(19050, 19300, 1, 0x2010, 0, 100),
            ],
        )
        self.assertGreaterEqual(route[-3].first, 18000)

    def test_cold_boot_ambassador_exit_uses_mode_specific_page_edges(self) -> None:
        route = cold_boot_ambassador_exit_route()
        self.assertEqual(
            route[-3:],
            [
                Event(19700, 19760, 1, 0x4000, 0, 0),
                Event(20500, 20560, 1, 0x8000, 0, 0),
                Event(21300, 21360, 1, 0x8000, 0, 0),
            ],
        )

    def test_cold_boot_magnus_forest_combat_route_uses_bounded_dialogue_envelope(self) -> None:
        route = cold_boot_magnus_forest_combat_route()
        dialogue_edges = [event for event in route if event.buttons == 0xC000]
        self.assertEqual(dialogue_edges[0], Event(19600, 19612, 1, 0xC000, 0, 0))
        self.assertEqual(dialogue_edges[-1], Event(24900, 24912, 1, 0xC000, 0, 0))
        self.assertEqual(route[-4:], [
            Event(31600, 31620, 1, 0x8000, 0, 0),
            Event(31650, 31680, 1, 0x0010, 80, 40),
            Event(31700, 31740, 1, 0x2010, 80, 0),
            Event(31750, 32000, 1, 0x2010, 0, 0),
        ])
        self.assertTrue(all(current.first >= previous.last
                            for previous, current in zip(route, route[1:])))

    def test_cold_boot_hub_route_preserves_weapon_and_navigation_order(self) -> None:
        route = cold_boot_hub_entry_route()
        self.assertEqual(route[-3], Event(21900, 22300, 1, 0, 20, 100))
        self.assertEqual(route[-2], Event(22350, 22430, 1, 0, 100, 0))
        self.assertEqual(route[-1], Event(22480, 22780, 1, 0, 0, 100))

    def test_cold_boot_jeff_route_enters_then_approaches_inside_hut(self) -> None:
        route = cold_boot_jeff_hut_route()
        self.assertEqual(route[-3], Event(23320, 23720, 1, 0x0000, 0, 100))
        self.assertEqual(route[-2], Event(23800, 23810, 1, 0x0000, 100, 0))
        self.assertEqual(route[-1], Event(23860, 24100, 1, 0x0000, 0, 100))

    def test_cold_boot_hub_heading_probe_starts_after_loaded_hub(self) -> None:
        short_forward = cold_boot_hub_direction_probe_route("forward-200")
        self.assertEqual(
            short_forward[-1], Event(23250, 23450, 1, 0, 0, 100)
        )
        diagonal = cold_boot_hub_direction_probe_route(
            "diagonal-left-20-200"
        )
        self.assertEqual(diagonal[-1], Event(23250, 23450, 1, 0, -20, 100))
        route = cold_boot_hub_direction_probe_route("right-40")
        self.assertEqual(route[-2], Event(23250, 23290, 1, 0, 100, 0))
        self.assertEqual(route[-1], Event(23340, 23740, 1, 0, 0, 100))
        camera_route = cold_boot_hub_direction_probe_route("camera-right-80")
        self.assertEqual(
            camera_route[-2], Event(23250, 23330, 1, 0x0001, 0, 0)
        )
        self.assertEqual(
            camera_route[-1], Event(23380, 23620, 1, 0, 0, 100)
        )

    def test_cold_boot_jeff_door_probe_follows_confirmed_bridge_heading(self) -> None:
        route = cold_boot_jeff_door_probe_route("right-10")
        self.assertEqual(route[-3], Event(23320, 23720, 1, 0, 0, 100))
        self.assertEqual(route[-2], Event(23800, 23810, 1, 0, 100, 0))
        self.assertEqual(route[-1], Event(23860, 24100, 1, 0, 0, 100))

    def test_cold_boot_jeff_approach_starts_after_hut_load(self) -> None:
        route = cold_boot_jeff_approach_probe_route("right-40")
        self.assertEqual(route[-2], Event(24400, 24440, 1, 0, 100, 0))
        self.assertEqual(route[-1], Event(24490, 24790, 1, 0, 0, 100))
        short = cold_boot_jeff_approach_probe_route("left-5-100")
        self.assertEqual(short[-2], Event(24400, 24405, 1, 0, -100, 0))
        self.assertEqual(short[-1], Event(24455, 24555, 1, 0, 0, 100))
        strafe = cold_boot_jeff_approach_probe_route("strafe-right-80")
        self.assertEqual(strafe[-1], Event(24400, 24480, 1, 0x0001, 0, 0))
        dialogue = cold_boot_jeff_dialogue_probe_route()
        self.assertEqual(dialogue[-1], Event(24600, 24620, 1, 0x8000, 0, 0))
        contact = cold_boot_jeff_contact_probe_route(40)
        self.assertEqual(contact[-2], Event(24600, 24640, 1, 0x0001, 0, 0))
        self.assertEqual(contact[-1], Event(24800, 24820, 1, 0x8000, 0, 0))
        close = cold_boot_jeff_close_probe_route(60)
        self.assertEqual(close[-2], Event(24700, 24760, 1, 0, 0, 100))
        self.assertEqual(close[-1], Event(24900, 24920, 1, 0x8000, 0, 0))
        face = cold_boot_jeff_face_probe_route("left-5")
        self.assertEqual(face[-3], Event(24900, 24905, 1, 0, -100, 0))
        self.assertEqual(face[-2], Event(24955, 24965, 1, 0, 0, 100))
        self.assertEqual(face[-1], Event(25200, 25220, 1, 0x8000, 0, 0))
        turn_action = cold_boot_jeff_turn_action_probe_route("right-40")
        self.assertEqual(turn_action[-2], Event(24800, 24840, 1, 0, 100, 0))
        self.assertEqual(turn_action[-1], Event(25000, 25020, 1, 0x8000, 0, 0))
        target_action = cold_boot_jeff_target_action_probe_route()
        self.assertEqual(target_action[-2], Event(24900, 24940, 1, 0x0010, 0, 0))
        self.assertEqual(target_action[-1], Event(25000, 25020, 1, 0x8000, 0, 0))
        target_close = cold_boot_jeff_target_close_probe_route()
        self.assertEqual(target_close[-2], Event(25100, 25105, 1, 0, 0, 100))
        self.assertEqual(target_close[-1], Event(25200, 25220, 1, 0x8000, 0, 0))
        target_closer = cold_boot_jeff_target_close_probe_route(100, 25)
        self.assertEqual(
            target_closer[-2], Event(25100, 25125, 1, 0, 0, 100)
        )
        hut_exit = cold_boot_jeff_hut_exit_probe_route()
        self.assertEqual(hut_exit[-1], Event(24400, 24800, 1, 0, 0, -100))
        short_exit = cold_boot_jeff_hut_exit_probe_route(150)
        self.assertEqual(short_exit[-1], Event(24400, 24550, 1, 0, 0, -100))
        dialogue_exit = cold_boot_jeff_dialogue_exit_probe_route()
        self.assertEqual(
            dialogue_exit[-1], Event(25300, 25450, 1, 0, 0, -100)
        )
        completed_dialogue = cold_boot_jeff_dialogue_complete_probe_route()
        self.assertEqual(
            completed_dialogue[-2], Event(29600, 29612, 1, 0x8000, 0, 0)
        )
        self.assertEqual(
            completed_dialogue[-1], Event(30200, 30400, 1, 0, 0, -100)
        )
        post_dialogue_fire = cold_boot_jeff_post_dialogue_fire_probe_route()
        self.assertEqual(
            post_dialogue_fire[-2], Event(34000, 34200, 1, 0x0010, 0, 0)
        )
        self.assertEqual(
            post_dialogue_fire[-1], Event(34250, 34850, 1, 0x2010, 0, 0)
        )
        post_dialogue_exit = cold_boot_jeff_post_dialogue_exit_probe_route()
        self.assertEqual(
            post_dialogue_exit[-1], Event(34000, 34010, 1, 0, 0, -100)
        )
        life_force = cold_boot_life_force_direction_probe_route("right-20")
        self.assertEqual(life_force[-2], Event(24800, 24820, 1, 0, 100, 0))
        self.assertEqual(life_force[-1], Event(24870, 25270, 1, 0, 0, 100))
        short_right = cold_boot_life_force_direction_probe_route("right-5-150")
        self.assertEqual(short_right[-1], Event(24855, 25005, 1, 0, 0, 100))
        door = cold_boot_life_force_door_probe_route("right-10")
        self.assertEqual(door[-2], Event(25400, 25410, 1, 0, 100, 0))
        self.assertEqual(door[-1], Event(25460, 25960, 1, 0, 0, 100))
        strafe_door = cold_boot_life_force_door_probe_route("strafe-right-40")
        self.assertEqual(strafe_door[-2], Event(25400, 25440, 1, 0x0001, 0, 0))
        self.assertEqual(strafe_door[-1], Event(25490, 25990, 1, 0, 0, 100))
        candidate = cold_boot_life_force_candidate_probe_route("right-10")
        self.assertEqual(candidate[-2], Event(25400, 25410, 1, 0, 100, 0))
        self.assertEqual(candidate[-1], Event(25460, 25610, 1, 0, 0, 100))
        bridge = cold_boot_life_force_bridge_probe_route(40)
        self.assertEqual(bridge[-2], Event(25800, 25840, 1, 0x0001, 0, 0))
        self.assertEqual(bridge[-1], Event(25890, 26190, 1, 0, 0, 100))
        combat = cold_boot_life_force_combat_probe_route()
        self.assertEqual(combat[-4], Event(25600, 25620, 1, 0x8000, 0, 0))
        self.assertEqual(combat[-1], Event(25750, 26000, 1, 0x2010, 0, 0))
        magnus = cold_boot_life_force_magnus_probe_route("right-10")
        self.assertEqual(magnus[-2], Event(26200, 26210, 1, 0, 100, 0))
        self.assertEqual(magnus[-1], Event(26260, 26410, 1, 0, 0, 100))
        contact_magnus = cold_boot_life_force_magnus_contact_probe_route(40)
        self.assertEqual(contact_magnus[-3], Event(25600, 25640, 1, 0x0001, 0, 0))
        self.assertEqual(contact_magnus[-2], Event(25700, 25720, 1, 0, 0, 100))
        self.assertEqual(contact_magnus[-1], Event(25800, 25820, 1, 0x8000, 0, 0))
        drone = cold_boot_life_force_drone_approach_probe_route(80)
        self.assertEqual(drone[-1], Event(25100, 25180, 1, 0x0001, 0, 0))
        forward_drone = cold_boot_life_force_drone_forward_probe_route(200)
        self.assertEqual(forward_drone[-1], Event(25100, 25300, 1, 0, 0, 100))
        drone_door = cold_boot_life_force_drone_door_probe_route("right-10")
        self.assertEqual(drone_door[-2], Event(25300, 25310, 1, 0, 100, 0))
        self.assertEqual(drone_door[-1], Event(25360, 25560, 1, 0, 0, 100))

    def test_post_ambassador_direction_probes_share_the_cold_prefix(self) -> None:
        forward = cold_boot_post_ambassador_direction_probe_route("forward")
        backward = cold_boot_post_ambassador_direction_probe_route("backward")
        self.assertEqual(forward[:-1], backward[:-1])
        self.assertEqual(forward[-1], Event(21900, 22700, 1, 0, 0, 100))
        self.assertEqual(backward[-1], Event(21900, 22700, 1, 0, 0, -100))
        short_backward = cold_boot_post_ambassador_direction_probe_route(
            "backward-200"
        )
        self.assertEqual(
            short_backward[-1], Event(21900, 22100, 1, 0, 0, -100)
        )
        targeted = cold_boot_post_ambassador_direction_probe_route(
            "target-backward-right"
        )
        self.assertEqual(targeted[-1], Event(21900, 22300, 1, 0x0010, 40, -100))
        camera = cold_boot_post_ambassador_direction_probe_route(
            "camera-right-80"
        )
        self.assertEqual(camera[-2], Event(21900, 21980, 1, 0x0001, 0, 0))
        self.assertEqual(camera[-1], Event(22030, 22430, 1, 0, 0, 100))
        diagonal = cold_boot_post_ambassador_direction_probe_route(
            "diagonal-backward-20"
        )
        self.assertEqual(diagonal[-1], Event(21900, 22100, 1, 0, 20, -100))
        diagonal_forward = cold_boot_post_ambassador_direction_probe_route(
            "diagonal-forward--40"
        )
        self.assertEqual(
            diagonal_forward[-1], Event(21900, 22300, 1, 0, -40, 100)
        )
        shoreline = cold_boot_shoreline_direction_probe_route("right-80")
        self.assertEqual(shoreline[-2], Event(22500, 22580, 1, 0, 100, 0))
        self.assertEqual(shoreline[-1], Event(22630, 23030, 1, 0, 0, 100))
        doorway = cold_boot_door_alignment_probe_route("turn-right")
        self.assertEqual(doorway[-2], Event(22350, 22390, 1, 0, 100, 0))
        self.assertEqual(doorway[-1], Event(22440, 22740, 1, 0, 0, 100))
        swept = cold_boot_post_ambassador_direction_probe_route("turn-left-140")
        self.assertEqual(swept[-2], Event(21900, 22040, 1, 0, -100, 0))
        self.assertEqual(swept[-1], Event(22090, 22490, 1, 0, 0, 100))
        shortened = cold_boot_post_ambassador_direction_probe_route(
            "turn-left-140-forward-120"
        )
        self.assertEqual(shortened[-2], Event(21900, 22040, 1, 0, -100, 0))
        self.assertEqual(shortened[-1], Event(22090, 22210, 1, 0, 0, 100))

    def test_disconnect_scenario_preserves_route_then_reconnects(self) -> None:
        route = controller_disconnect_route([Event(0, 35000, 1, 0, 0, 0)])
        self.assertEqual(route[-3], Event(0, 29581, 1, 0, 0, 0))
        self.assertEqual(route[-2], Event(29582, 29590, 0, 0, 0, 0))
        self.assertEqual(route[-1], Event(29590, 29598, 1, 0, 0, 0))

    def test_combat_probe_fires_after_the_loaded_gameplay_prefix(self) -> None:
        route = combat_probe_route([Event(0, 35000, 1, 0, 0, 0)])
        self.assertEqual(route[0], Event(0, 8100, 1, 0, 0, 0))
        self.assertEqual(route[1], Event(8120, 8140, 1, 0x8000, 0, 0))
        self.assertEqual(route[2], Event(8200, 9000, 1, 0, 0, 100))
        self.assertEqual(route[3], Event(9050, 9300, 1, 0x2000, 0, 100))

    def test_ambassador_dialogue_exit_uses_mode_specific_page_edges(self) -> None:
        route = ambassador_dialogue_exit_route(
            [Event(0, 35000, 1, 0, 0, 0)]
        )
        self.assertEqual(
            route[-3:],
            [
                Event(9700, 9760, 1, 0x4000, 0, 0),
                Event(10500, 10560, 1, 0x8000, 0, 0),
                Event(11300, 11360, 1, 0x8000, 0, 0),
            ],
        )

    def test_jeff_hut_fire_waits_for_post_dialogue_control(self) -> None:
        route = jeff_hut_fire_probe_route(
            [Event(0, 35000, 1, 0, 0, 0)]
        )
        self.assertEqual(route[-2], Event(34000, 34500, 1, 0, 0, 100))
        self.assertEqual(route[-1], Event(35000, 35300, 1, 0x2010, 0, 0))

    def test_jeff_dialogue_exit_fire_uses_distinct_edges_before_firing(self) -> None:
        route = jeff_dialogue_exit_fire_probe_route(
            [Event(0, 35000, 1, 0, 0, 0)]
        )
        dialogue_edges = [event for event in route if 35000 <= event.first <= 39000]
        self.assertEqual(len(dialogue_edges), 11)
        self.assertTrue(all(event.buttons == 0x8000 for event in dialogue_edges))
        self.assertEqual(route[-2], Event(40000, 40400, 1, 0x0010, 0, 0))
        self.assertEqual(route[-1], Event(40450, 41050, 1, 0x2010, 0, 0))

    def test_round_trip_and_overlap_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "route.input"
            events = [Event(0, 10, 1, 0x8000, 20, -30)]
            write_replay(path, events)
            self.assertEqual(load_replay(path), events)
            with self.assertRaisesRegex(RouteError, "overlaps"):
                write_replay(
                    path,
                    [Event(0, 10, 1, 0, 0, 0), Event(9, 11, 1, 0, 0, 0)],
                )


if __name__ == "__main__":
    unittest.main()
