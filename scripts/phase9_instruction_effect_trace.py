"""Stream bounded native instruction effects without losing raw GPR bits.

Records are little-endian wire values, unrelated to RDRAM's word layout.
No PC aliases, Count alignment, full CPU state or memory-effect claims.
"""
from collections import Counter
import struct

MAGIC = b"JFGEFX1\x00"
WORDS = ("section", "pc", "opcode", "owner", "thread_word", "count", "status", "cause",
         "target", "selected_owner", "device_sequence")
MAX_ROWS = 4194304
MAX_BYTES = 512 * 1024 * 1024
LIMITS = {"clock_alignment_validated": False, "retirement_validated": False,
          "full_cpu_state_observed": False, "memory_effects_observed": False,
          "causal_fix_proved": False, "parity_verified": False}


def configure(environment, update, device_spec, eret_spec):
    environment.pop("JFG_PHASE9_INSTRUCTION_EFFECT_UPDATE", None)
    if update is None:
        return None
    window = device_spec.get("window") if isinstance(device_spec, dict) else None
    if (type(update) is not int or not 1 <= update <= 1000000 or
            not isinstance(window, (tuple, list)) or len(window) != 2 or
            any(type(value) is not int for value in window) or
            not 1 <= window[0] <= update <= window[1] <= 1000000 or
            window[1] - window[0] > 17 or
            device_spec.get("clock_basis") != "native-pre-instruction-count" or
            not isinstance(eret_spec, dict) or eret_spec.get("window") != list(window) or
            eret_spec.get("phase") != "after-cpu-eret-state-before-host-handoff"):
        raise ValueError("instruction effects require one invocation within native device and ERET capture")
    environment["JFG_PHASE9_INSTRUCTION_EFFECT_UPDATE"] = str(update)
    return {"schema": 1, "update": update, "observation_only": True,
            "phase": "entry-ordinary-effect-and-pre-handoff-eret",
            "clock_basis": "native-count-at-hook-not-aligned-to-oracle",
            "code_identity": "raw-generated-section-pc-and-opcode-not-alias-normalized",
            **LIMITS}


def records(path, update):
    """Validate every consumed row and footer; callers must exhaust the stream."""
    if type(update) is not int or not 1 <= update <= 1000000 or path.stat().st_size > MAX_BYTES:
        raise ValueError("instruction effect window or byte budget is invalid")
    with path.open("rb") as stream:
        def exact(size):
            data = stream.read(size)
            if len(data) != size:
                raise ValueError("instruction effect trace is truncated")
            return data

        if exact(12) != MAGIC + struct.pack("<I", update):
            raise ValueError("instruction effect header differs")
        gpr, pending, previous_device, sequence = [0] * 32, None, 0, 0
        while True:
            phase = exact(1)[0]
            if phase == 255:
                if not sequence or struct.unpack("<I", exact(4))[0] != sequence or pending is not None or stream.read(1):
                    raise ValueError("instruction effect footer, pending entry or trailing data differs")
                return
            if phase > 2 or sequence == MAX_ROWS:
                raise ValueError("instruction effect phase or row budget is invalid")
            values = struct.unpack("<12I", exact(48))
            row = dict(zip(WORDS, values[:11]))
            mask = values[11]
            if (not row["pc"] or any(row[key] % 4 for key in ("pc", "owner", "thread_word", "target", "selected_owner")) or
                    not previous_device <= row["device_sequence"] <= 65536 or
                    (sequence == 0 and mask != 0xffffffff)):
                raise ValueError("instruction effect alignment, device order or initial snapshot differs")
            for index in range(32):
                if mask & (1 << index):
                    value = struct.unpack("<Q", exact(8))[0]
                    if sequence and value == gpr[index]:
                        raise ValueError("instruction effect delta mask is not canonical")
                    gpr[index] = value
            if gpr[0] != 0:
                raise ValueError("instruction effect zero register is invalid")
            if phase == 0:
                if pending is not None or row["target"] or row["selected_owner"]:
                    raise ValueError("instruction entry overlaps a pending effect or has a transfer target")
                pending = row
            else:
                if pending is None or any(row[key] != pending[key] for key in ("section", "pc", "opcode", "owner")):
                    raise ValueError("instruction effect does not complete its exact entry")
                if phase == 1 and (row["opcode"] == 0x42000018 or row["target"] or row["selected_owner"]):
                    raise ValueError("ordinary effect cannot be an ERET transfer")
                if phase == 2 and (row["opcode"] != 0x42000018 or row["status"] & 6 or
                        not row["target"] or not row["selected_owner"] or row["thread_word"] != row["selected_owner"]):
                    raise ValueError("instruction ERET transfer boundary is invalid")
                pending = None
            sequence += 1
            previous_device = row["device_sequence"]
            yield {**row, "sequence": sequence, "invocation": update, "phase": phase, "gpr": tuple(gpr)}


def summary(path, update):
    try:
        phases = Counter(row["phase"] for row in records(path, update))
        return {"schema": 1, "update": update, "complete": True, "events": sum(phases.values()),
                "entries": phases[0], "effects": phases[1], "eret_transfers": phases[2], **LIMITS}
    except (OSError, ValueError) as error:
        return {"complete": False, "error": str(error)}
