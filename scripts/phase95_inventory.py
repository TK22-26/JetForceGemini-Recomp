"""Read-only single-player ammo and health-pickup evidence."""
import argparse
import json
from pathlib import Path
import struct

from scripts.phase95_observation import decode, physical, ObservationError


def eligible(pickup, current):
    weapon = pickup["weapon"]
    if not 0 <= weapon < 16 or not (current["owned_mask"] & (1 << weapon)):
        return False
    if pickup["kind"] == 0xE7:
        return (not pickup["collected"] and pickup["capacity_increment"] > 0 and
                current["capacity"][weapon] + pickup["capacity_increment"] <= pickup["capacity_limit"])
    if pickup["kind"] == 0xE8:
        return current["ammo"][weapon] < current["capacity"][weapon]
    return False


def capacity_collection_verified(before, after, pickup):
    if pickup["kind"] != 0xE7 or not eligible(pickup, before) or before["character"] != after["character"]:
        return False
    flag, weapon = pickup["flag"], pickup["weapon"]
    if type(flag) is not int or not 0 <= flag < 0x480:
        return False
    old, new = bytes.fromhex(before["flags_hex"]), bytes.fromhex(after["flags_hex"])
    if len(old) != 144 or len(new) != 144:
        return False
    mask = 1 << (flag % 8)
    return (not old[flag // 8] & mask and bool(new[flag // 8] & mask) and
            after["capacity"][weapon] == before["capacity"][weapon] + pickup["capacity_increment"])


def health_upgrade_collection_verified(before, after, pickup):
    """Require the character upgrade and its persistent flag to change together."""
    if (pickup.get("kind") != 0xE9 or not pickup.get("eligible") or
            before["character"] != after["character"] or
            before["health_upgrades"] >= 12):
        return False
    flag = pickup.get("flag")
    if type(flag) is not int or not 0 <= flag < 0x480:
        return False
    old, new = bytes.fromhex(before["flags_hex"]), bytes.fromhex(after["flags_hex"])
    if len(old) != 144 or len(new) != 144:
        return False
    mask = 1 << (flag % 8)
    return (not old[flag // 8] & mask and bool(new[flag // 8] & mask) and
            after["health_upgrades"] == before["health_upgrades"] + 1 and
            after["health_capacity_raw"] == before["health_capacity_raw"] + 0x500 and
            after["health_raw"] == after["health_capacity_raw"])


def health_refill_collection_verified(before, after, pickup):
    """Confirm a one-unit, non-respawning health pickup was consumed."""
    if (pickup.get("name") != "HealthPowerup" or pickup.get("kind") != 0xA9 or
            pickup.get("mode") != 0 or pickup.get("respawn_delay") != 0 or
            not pickup.get("eligible") or before["character"] != after["character"] or
            before["health_upgrades"] != after["health_upgrades"] or
            before["health_capacity_raw"] != after["health_capacity_raw"]):
        return False
    return (after["health_raw"] == min(before["health_raw"] + 0x100,
                                       before["health_capacity_raw"]) and
            all(item["actor"] != pickup["actor"] for item in after["health_pickups"]))


def weapon_stats(memory, metadata):
    """Read the original single-player per-weapon shot/hit/kill counters."""
    current = inventory(memory, metadata)
    # mainIncreaseWeaponKills/Shots/Hits, US retail. Each validates its slot
    # range and uses the same gameplay pointer, with a distinct counter offset.
    for code, load in ((0x47868, 0x944304F4),
                       (0x478A4, 0x8C430474),
                       (0x478E0, 0x8C4304B4)):
        if struct.unpack_from(">5I", memory, code) != (
                0x0480000C, 0x28810010, 0x1020000A,
                0x3C0E8010, 0x8DCED7D4) or \
                struct.unpack_from(">I", memory, code + 0x1C)[0] != load:
            raise ObservationError("weapon statistics counter profile mismatch")
    game = physical(current["game_pointer"], 0x514)
    return {"kind": "jfg-phase95-weapon-statistics", "acceptance": False,
            "character": current["character"],
            "shots": struct.unpack_from(">16I", memory, game + 0x474),
            "hits": struct.unpack_from(">16I", memory, game + 0x4B4),
            "kills": struct.unpack_from(">16H", memory, game + 0x4F4)}


def inventory(memory, metadata):
    state = decode(memory, sequence=metadata["sequence"], player_pointer=metadata["player"])
    if state.front_mode != 16 or state.player is None or memory[0xA4FC4] != 0:
        raise ObservationError("ammo inventory requires single-player gameplay")
    expected = (0x00085100, 0x01485023, 0x000A5080, 0x3C098010,
                0x8D29D7D4, 0x01485023, 0x000A5040, 0x012A1021, 0x2442015C)
    if struct.unpack_from(">9I", memory, 0x47C70) != expected:
        raise ObservationError("game-character accessor profile mismatch")
    if struct.unpack_from(">7I", memory, 0x3B500) != (
            0x00047080, 0x01C47023, 0x3C0F800A, 0x25EF1490, 0x000E7100, 0x03E00008, 0x01CF1021):
        raise ObservationError("weapon-definition accessor profile mismatch")
    u32 = lambda offset: struct.unpack_from(">I", memory, offset)[0]
    player = physical(state.player.address, 0x6C)
    control = physical(u32(player + 0x68), 4)
    character = memory[control + 1] & 3
    game_pointer = u32(0xFD7D4)
    game = physical(game_pointer, 0x400)
    character_offset = game + 0x15C + character * 0x76
    upgrades = struct.unpack_from(">h", memory, character_offset + 2)[0]
    if not 0 <= upgrades <= 12:
        raise ObservationError("health upgrade count outside supported range")
    properties = physical(u32(player + 0x4C), 8)
    health_raw = struct.unpack_from(">h", memory, properties + 6)[0]
    owned = struct.unpack_from(">H", memory, character_offset + 0xA)[0]
    ammo = struct.unpack_from(">16H", memory, character_offset + 0x14)
    capacity = struct.unpack_from(">16H", memory, character_offset + 0x34)
    pickups = []
    candidates = [a for a in state.actors if a.name in ("ammocapacity", "fullammo")]
    if candidates:
        table = physical(u32(0xFEAA0), 73 * 32)
        code = physical(u32(table + 72 * 32), 0x310)
        if u32(code + 0x64) != 0x27BDFF68 or u32(code + 0x1B4) != 0x0C011F07:
            raise ObservationError("ammo pickup overlay profile mismatch")
    for actor in candidates:
        data = physical(u32(physical(actor.address, 0x6C) + 0x68), 10)
        kind = struct.unpack_from(">h", memory, data)[0]
        weapon = memory[data + 3]
        if weapon >= 16 or kind not in (0xE7, 0xE8):
            raise ObservationError("unsupported ammo pickup layout")
        flag = struct.unpack_from(">H", memory, data + 8)[0] + 0x80
        if kind == 0xE7 and flag >= 0x480:
            raise ObservationError("capacity flag out of range")
        definition = 0xA1490 + weapon * 0x30
        increment, maximum = (struct.unpack_from(">h", memory, definition + offset)[0]
                              for offset in (0x26, 0x2E))
        pickups.append({"actor": actor.address, "name": actor.name, "position": actor.position,
                        "kind": kind, "weapon": weapon, "owned": bool(owned & (1 << weapon)),
                        "capacity_increment": increment, "capacity_limit": maximum,
                        "flag": flag if kind == 0xE7 else None,
                        "collected": bool(memory[game + 0x30 + flag // 8] & (1 << (flag % 8)))
                                     if kind == 0xE7 else None})
    result = {"kind": "jfg-phase95-ammo-inventory", "acceptance": False,
            "character": character, "game_pointer": game_pointer,
            "health_raw": health_raw, "health_units": health_raw / 256,
            "health_capacity_raw": (5 * upgrades + 4) * 256,
            "health_upgrades": upgrades,
            "flags_hex": memory[game + 0x30:game + 0xC0].hex(),
            "owned_mask": owned, "ammo": ammo, "capacity": capacity, "pickups": pickups}
    for pickup in pickups:
        pickup["eligible"] = eligible(pickup, result)
    health_pickups = []
    health_seen = [a for a in state.actors if a.name in ("GeminiPowerup", "HealthPowerup")]
    if health_seen:
        table = physical(u32(0xFEAA0), 105 * 32)
        code = physical(u32(table + 104 * 32), 0x694)
        if (u32(code + 0x1F0) != 0x27BDFF80 or u32(code + 0x2B8) != 0x15610015 or
                u32(code + 0x5FC) != 0xA44D0006):
            raise ObservationError("health pickup overlay profile mismatch")
        if u32(0xAB24C + (61 - 2) * 4) != 0x8000FFD0 or u32(0xFFD0) != (
                0x0C000000 | (((code + 0x1F0 + 0x80000000) >> 2) & 0x03FFFFFF)):
            raise ObservationError("health pickup dispatch profile mismatch")
    for actor in health_seen:
        base = physical(actor.address, 0x6C)
        if struct.unpack_from(">h", memory, base + 0x48)[0] != 61:
            raise ObservationError("health pickup actor control mismatch")
        data = physical(u32(base + 0x68), 0x15)
        kind = struct.unpack_from(">h", memory, data + 0x12)[0]
        if actor.name == "HealthPowerup":
            if kind != 0xA9:
                raise ObservationError("unsupported HealthPowerup layout")
            mode = u32(base + 0x88)
            respawn_delay = memory[data + 0xD]
            health_pickups.append({"actor": actor.address, "name": actor.name,
                                   "position": actor.position, "kind": kind,
                                   "mode": mode, "respawn_delay": respawn_delay,
                                   "eligible": mode == 0 and respawn_delay == 0 and
                                               health_raw <= (5 * upgrades + 4) * 256 - 256,
                                   "effect": "restore one health unit" if mode == 0 else None,
                                   "reachable": None})
            continue
        if kind != 0xE9:
            raise ObservationError("unsupported GeminiPowerup layout")
        flag = memory[data + 0x14] + 0x2F
        collected = bool(memory[game + 0x30 + flag // 8] & (1 << (flag % 8)))
        health_pickups.append({"actor": actor.address, "name": actor.name,
                               "position": actor.position, "kind": kind,
                               "flag": flag, "collected": collected,
                               "eligible": not collected and upgrades < 12,
                               "effect": "health upgrade plus five units; health refilled to new capacity",
                               "reachable": None})
    result["health_pickups"] = health_pickups
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rdram", type=Path)
    parser.add_argument("--player", type=lambda value: int(value, 0), required=True)
    args = parser.parse_args()
    print(json.dumps(inventory(args.rdram.read_bytes(), {"sequence": 0, "player": args.player}), indent=2))


if __name__ == "__main__":
    main()
