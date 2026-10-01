"""Independent link semantics, not Count or a hardware timing qualification.

Expected values follow NEC VR4300 manual U10504EJ7V0UM00, chapter 16:
JAL/JALR write the link before the delay instruction, which may read/overwrite
it. REGIMM link forms write it even when not taken; likely annuls the slot,
not the link. rs=rd JALR and exceptions are deliberately not part of this ROM.
"""
import re

HEADER = 'case pc slot_hi slot_lo link_hi link_lo taken'.split()
NAMES = ('jal-read', 'jal-write', 'jalr-read', 'jalr-alt-read',
         'bgezal-taken', 'bgezal-untaken', 'bltzal-taken', 'bltzal-untaken',
         'bgezall-taken', 'bgezall-untaken', 'bltzall-taken', 'bltzall-untaken')
SENTINEL = 0x24681357


def expected(case, pc):
    if type(case) is not int or not 0 <= case < 12 or type(pc) is not int or pc % 4 or not 0x80000400 <= pc < 0x80001000:
        raise ValueError('invalid link case address')
    link = 0xffffffff00000000 | pc + 8
    slot = SENTINEL if case in (1, 9, 11) else link
    if case == 1:
        link += 4
    return slot, link, int(case not in (5, 7, 9, 11))


def payload_words(case, pc):
    """Independently bind observations to the assembled probe, including stores."""
    expected(case, pc)
    target = pc + 16
    if case < 2:
        branch = 0x0c000000 | ((target >> 2) & 0x03ffffff)
    elif case < 4:
        branch = (25 << 21) | ((31 if case == 2 else 19) << 11) | 9
    else:
        # REGIMM rt encodings: BGEZAL, BLTZAL, BGEZALL, BLTZALL.
        branch = 0x04800003 | ([0x11, 0x11, 0x10, 0x10, 0x13, 0x13, 0x12, 0x12][case-4] << 16)
    slot = 0x27ff0004 if case == 1 else 0x02609025 if case == 3 else 0x03e09025
    register = 19 if case == 3 else 31
    # offsets are relative to the branch instruction, not a searched opcode.
    return {0:branch,4:slot,8:0x10000002,12:0,16:0x24140001,
            20:0x24080000 | case,24:0xae080000,28:0x3c080000 | (pc >> 16),
            32:0x25080000 | (pc & 0xffff),36:0xae080004,
            40:0x0012483e,44:0xae090008,48:0xae12000c,
            52:(register << 16) | 0x483e,56:0xae090010,60:0xae000014 | (register << 16),
            64:0xae140018,68:0xae00001c,72:0x26100020}


def verify_payload(rom, observed):
    if rom.stat().st_size != 2 * 1024 * 1024 or len(observed.get('cases', [])) != 12:
        raise ValueError('link payload or case inventory differs')
    data = rom.read_bytes()
    occupied = set()
    for case,row in enumerate(observed['cases']):
        if row['case'] != case:
            raise ValueError('link payload case order differs')
        pc = row['pc']
        for relative,word in payload_words(case, pc).items():
            offset = 0x1000 + pc - 0x80000400 + relative
            if offset in occupied or int.from_bytes(data[offset:offset+4], 'big') != word:
                raise ValueError('assembled link payload differs from independently required instructions')
            occupied.add(offset)
    return {'cases':12,'checked_instruction_words':len(occupied),
            'full_width_register_stores_verified':True,'hardware_tested':False}


def parse_trace(path):
    if path.stat().st_size > 16384:
        raise ValueError('link trace exceeds byte budget')
    lines = path.read_text().splitlines()
    if len(lines) != 14 or lines[0].split('\t') != HEADER or lines[-1] != 'result\ttrue\t12':
        raise ValueError('incomplete link microtest')
    rows, mismatches, seen = [], [], set()
    for case, line in enumerate(lines[1:-1]):
        words = line.split('\t')
        if len(words) != 7 or any(re.fullmatch('[0-9a-f]{8}', word) is None for word in words):
            raise ValueError('malformed link observation')
        values = tuple(int(word, 16) for word in words)
        if values[0] != case or values[1] in seen or values[6] not in (0, 1):
            raise ValueError('link case identity changed')
        seen.add(values[1])
        wanted = expected(case, values[1])
        actual = (values[2] << 32 | values[3], values[4] << 32 | values[5], values[6])
        row = dict(zip(HEADER, values))
        row.update(name=NAMES[case], matches_manual=actual == wanted)
        rows.append(row)
        if actual != wanted:
            mismatches.append({'case': case, 'name': NAMES[case], 'pc': values[1],
                'actual': list(actual), 'expected': list(wanted)})
    return {'cases': rows, 'matches_vr4300_manual': not mismatches, 'mismatches': mismatches,
            'hardware_tested': False, 'clock_alignment_validated': False, 'game_cause_proved': False}
