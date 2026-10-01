"""Bind validated native instruction effects to independent local observers.

The input readers own schema/order/footer validation. This exhausts the effect
iterator and uses exact producer device sequence and ERET order, never a PC
search, Count alignment, or normalized register alias. It does not prove the
semantics of every effect or any native/oracle correspondence.
"""
from collections import Counter


def bind(rows, device_rows, eret_rows, update):
    if type(update) is not int or not 1 <= update <= 1000000:
        raise ValueError("instruction witness invocation is invalid")
    instructions = {row["sequence"]: row for row in device_rows
                    if row["invocation"] == update and row["phase"] == "instruction"}
    if not instructions:
        raise ValueError("instruction effects have no independent point witnesses")
    transfers = [row for row in eret_rows if row["invocation"] == update]
    seen, phases, owners = set(), Counter(), Counter()
    transfer_index = 0
    for row in rows:
        if row["invocation"] != update:
            raise ValueError("instruction witness invocation differs")
        phases[row["phase"]] += 1
        if row["phase"] == 0:
            owners[row["owner"]] += 1
            witness = instructions.get(row["device_sequence"])
            if witness is not None and witness["sequence"] not in seen:
                registers = tuple(witness[f"r{i}_lo"] | witness[f"r{i}_hi"] << 32 for i in range(32))
                if (row["pc"] != witness["pc"] or row["opcode"] != witness["opcode"] or
                        row["thread_word"] != witness["thread"] or row["gpr"] != registers or
                        row["status"] != witness["status"] or row["cause"] != witness["cause"]):
                    raise ValueError("instruction entry differs from its exact device witness")
                # Count is deliberately not equated: the existing device
                # witness precedes native instruction-entry Count accounting.
                seen.add(witness["sequence"])
        if row["phase"] == 2:
            if transfer_index >= len(transfers):
                raise ValueError("extra instruction-effect ERET")
            witness = transfers[transfer_index]
            fields = (("pc", "pc"), ("opcode", "opcode"), ("owner", "from_thread"),
                      ("selected_owner", "to_thread"), ("target", "target_pc"),
                      ("status", "status"), ("count", "count"))
            if (any(row[a] != witness[b] for a,b in fields) or
                    row["gpr"] != tuple(witness[f"r{i}"] for i in range(32))):
                raise ValueError("instruction-effect ERET differs from dedicated pre-handoff observer")
            transfer_index += 1
    if seen != set(instructions) or transfer_index != len(transfers):
        raise ValueError("instruction-effect capture omitted known boundaries")
    return {"phase_counts": dict(phases), "entry_owners": {f"0x{key:08x}": value for key,value in owners.items()},
            "device_instruction_witnesses": len(seen), "eret_witnesses": transfer_index,
            "clock_alignment_validated": False, "retirement_validated": False,
            "all_effect_semantics_proved": False, "oracle_effects_qualified": False}
