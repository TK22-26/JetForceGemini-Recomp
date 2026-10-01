"""Bounded static operand context from matching retained RDRAM snapshots.

These are conditional proposal facts, never proof of execution, retirement,
caller equivalence or timing. Unknown instructions fail closed for data-flow
claims. Actual point captures must still pass the existing runtime checks.
"""
import hashlib
import json
import re

from scripts.compare_phase9_focus_rdram import _records_at, _snapshot

MAX_TARGETS = 64
MAX_SITES = 16
LOOKBACK = 12
MAX_LEAF_WORDS = 16


def decode(pc, opcode):
    primary, rs, rt, rd = opcode >> 26, (opcode >> 21) & 31, (opcode >> 16) & 31, (opcode >> 11) & 31
    offset = opcode & 0xffff
    offset = offset - 0x10000 if offset & 0x8000 else offset
    row = {"pc": f"0x{pc:08x}", "opcode": f"0x{opcode:08x}", "operation": "unknown",
           "writes": [], "flow": "unknown"}
    if opcode == 0:
        row.update(operation="nop", flow="linear")
    elif primary == 3:
        row.update(operation="jal", writes=[31], flow="call",
                   target=f"0x{((pc + 4) & 0xf0000000) | ((opcode & 0x3ffffff) << 2):08x}",
                   return_pc=f"0x{pc + 8:08x}")
    elif primary == 0 and opcode & 63 == 8 and rt == rd == 0 and (opcode >> 6) & 31 == 0:
        row.update(operation="jr", flow="jump", source_register=rs)
    elif primary in (4, 5):
        row.update(operation="beq" if primary == 4 else "bne", flow="branch", registers=[rs, rt])
    elif primary in (9, 12, 13, 15, 35, 43, 41):
        name = {9: "addiu", 12: "andi", 13: "ori", 15: "lui", 35: "lw", 43: "sw", 41: "sh"}[primary]
        row.update(operation=name, flow="linear", writes=[rt] if primary in (9, 12, 13, 15, 35) and rt else [],
                   source_register=rs, register=rt, offset=offset)
        if primary == 15 and rs != 0:
            row.update(operation="unknown", flow="unknown")
    elif primary == 0 and opcode & 63 in (36, 37) and (opcode >> 6) & 31 == 0:
        row.update(operation="and" if opcode & 63 == 36 else "or", flow="linear", writes=[rd] if rd else [])
    elif primary == 16 and rs in (0, 4) and opcode & 0x7ff == 0:
        row.update(operation="mfc0" if rs == 0 else "mtc0", flow="linear", writes=[rt] if rs == 0 and rt else [])
    return row


def matching_words(images, start, count):
    offset = start - 0x80000000
    if (not images or start % 4 or count < 1 or offset < 0 or
            any(offset + count * 4 > len(image) for image in images)):
        return None
    data = images[0][offset:offset + count * 4]
    if any(image[offset:offset + count * 4] != data for image in images[1:]):
        return None
    return [decode(start + n * 4, int.from_bytes(data[n * 4:n * 4 + 4], "big")) for n in range(count)]


def preserving_leaf(images, start):
    """A bounded linear body ending JR RA/NOP, with no RA writes or calls.

    Memory/CP0 operations can still trap or trigger runtime behavior. This
    only describes the ordinary instruction path if it reaches that return.
    """
    body = []
    for index in range(MAX_LEAF_WORDS):
        rows = matching_words(images, start + index * 4, 1)
        if rows is None:
            return None
        instruction = rows[0]
        body.append(instruction)
        if instruction["operation"] == "jr" and instruction["source_register"] == 31:
            delay = matching_words(images, start + (index + 1) * 4, 1)
            return body + delay if delay is not None and delay[0]["operation"] == "nop" else None
        if instruction["flow"] != "linear" or 31 in instruction["writes"]:
            return None
    return None


def sites(images, targets):
    targets = sorted(set(targets))
    if len(targets) > MAX_TARGETS:
        raise ValueError("instruction context target budget exceeded")
    found = []
    for pc in targets:
        tail = matching_words(images, pc - 4, 2)
        if tail is None:
            continue
        load, branch = tail
        if (load["operation"] != "lw" or branch["operation"] not in ("beq", "bne") or
                branch["registers"] != [load["register"], 0] or load["register"] in (0, 31)):
            continue
        for distance in range(3, LOOKBACK + 1):
            call_pc = pc - distance * 4
            corridor = matching_words(images, call_pc, distance + 1)
            if corridor is None or corridor[0]["operation"] != "jal":
                continue
            # Includes the call delay slot and every instruction after its
            # return. A different control transfer or RA writer invalidates
            # this conditional last-link fact.
            if any(row["flow"] != "linear" or 31 in row["writes"] for row in corridor[1:-1]):
                continue
            leaf = preserving_leaf(images, int(corridor[0]["target"], 16))
            if leaf is None:
                continue
            found.append({"pc": f"0x{pc:08x}", "operand_register": load["register"],
                          "load_base_register": load["source_register"], "load_offset": load["offset"],
                          "link_call_pc": f"0x{call_pc:08x}", "callee": corridor[0]["target"],
                          "conditional_raw_ra": corridor[0]["return_pc"],
                          "call_to_branch": corridor, "callee_body": leaf})
            break
        if len(found) > MAX_SITES:
            raise ValueError("instruction context site budget exceeded")
    return found


def inventory(reference, window, diagnosis):
    if (not isinstance(window, (list, tuple)) or len(window) != 2 or
            any(type(value) is not int for value in window) or
            not 1 <= window[0] <= window[1] <= 1_000_000 or window[1] - window[0] >= 16):
        raise ValueError("instruction context window must cover 1..16 bounded updates")
    targets = sorted({int(value, 16) for value in re.findall(r"0x80[0-3][0-9a-f]{5}\b", json.dumps(diagnosis), re.I)})
    if len(targets) > MAX_TARGETS:
        raise ValueError("instruction context target budget exceeded")
    images, snapshots = [], []
    for side, trace in (("native", "retrace-hashes.jsonl.updates.jsonl"), ("oracle", "update-hashes.jsonl")):
        records = _records_at(reference / side / trace, range(window[0], window[1] + 1))
        for update in range(window[0], window[1] + 1):
            data, _ = _snapshot(reference / side, records[update])
            images.append(data)
            snapshots.append({"side": side, "update": update, "sha256": hashlib.sha256(data).hexdigest()})
    return {"schema": 1, "kind": "retained-static-operand-context", "focus_updates": list(window),
            "snapshots": snapshots, "sites": sites(images, targets),
            "scope": "conditional-normal-path-register-effects-not-observed-execution",
            "execution_observed": False, "caller_equivalence_proved": False,
            "causal_fix_proved": False, "parity_verified": False}


def projection(facts):
    return [{key: row[key] for key in ("pc", "operand_register", "load_base_register", "load_offset",
                                      "link_call_pc", "callee", "conditional_raw_ra")} for row in facts["sites"]]
