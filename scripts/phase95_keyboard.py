"""Read relocated US overlay-42 menu state; never write guest memory."""
import struct

from scripts.phase95_observation import FRONT_MODE, RDRAM_SIZE, ObservationError, physical


def keyboard(memory: bytes) -> dict | None:
    if len(memory) != RDRAM_SIZE:
        raise ObservationError("incomplete keyboard observation")
    if memory[FRONT_MODE] != 24:
        return None
    u32 = lambda p: struct.unpack_from(">I", memory, p)[0]
    table = u32(0xFEAA0)
    if not table:
        return None
    slot = physical(table, 43 * 32) + 42 * 32
    base = u32(slot)
    if not base:
        return None
    code = physical(base, 0x2078)

    def address(hi, lo, hi_opcode, lo_opcode, size):
        first, second = u32(code + hi), u32(code + lo)
        if first >> 16 != hi_opcode or second >> 16 != lo_opcode:
            raise ObservationError("keyboard code identity mismatch")
        low = second & 0xFFFF
        target = ((first & 0xFFFF) << 16) + (low if low < 0x8000 else low - 0x10000)
        return physical(target, size, aligned=False)

    initialized = address(0, 4, 0x3C02, 0x2442, 4)
    if u32(initialized) != 1:
        return None
    pointer = address(0x84, 0x8C, 0x3C02, 0x2442, 4)
    label = address(0x88, 0x90, 0x3C08, 0x2508, 24)
    submode = address(0x9C, 0xA0, 0x3C01, 0xA020, 1)
    tilt = address(0x54, 0x58, 0x3C01, 0xA439, 2)
    key = address(0x206C, 0x2070, 0x3C18, 0x8F18, 4)
    selection = u32(key)
    if selection > 40:
        raise ObservationError("invalid keyboard selection")
    end = u32(pointer)
    if end == 0:
        return None  # initializer publishes its flag before setting the buffer
    # Input buffer cursor is bounded within the initializer's label buffer.
    offset = physical(end, 1, aligned=False) - label
    if not 0 <= offset <= 23:
        raise ObservationError("invalid label cursor")
    return dict(base=base, submode=memory[submode], key=selection,
                tilt=struct.unpack_from(">h", memory, tilt)[0],
                label_length=offset,
                label_hex=memory[label:label + offset].hex())
