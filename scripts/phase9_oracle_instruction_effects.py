"""Strict streaming reader for cached-oracle effects, not hardware retirement.

Branches finish their register/decision phase before the delay slot. Idle
fast-forward and exceptions are explicit alternatives, never ordinary effects.
"""
from collections import Counter
import struct

MAGIC = b'JFGOFX1\0'
WORDS = ('pc', 'opcode', 'thread_word', 'count', 'anchor', 'status', 'cause',
         'live_pc', 'delay_slot', 'device_sequence', 'target', 'flags', 'idle_ticks', 'epc', 'llbit')
PHASES = ('entry', 'ordinary', 'branch', 'eret', 'exception', 'idle')
MAX_ROWS = 4194304
MAX_BYTES = 512*1024*1024
LIMITS = dict(clock_alignment_validated=False, retirement_validated=False,
              full_cpu_state_observed=False, memory_effects_observed=False,
              causal_fix_proved=False, parity_verified=False)


def branch_word(word):
    op, rt = word >> 26, (word >> 16) & 31
    return ((op == 0 and word & 63 in (8, 9)) or
            (op == 1 and rt in (0, 1, 2, 3, 16, 17, 18, 19)) or
            2 <= op <= 7 or 20 <= op <= 23 or (op == 17 and (word >> 21) & 31 == 8))


def specification(update, cpu_spec):
    if update is None:
        return None
    if (type(update) is not int or not 1 <= update <= 1000000 or
            not isinstance(cpu_spec, dict) or cpu_spec.get('update') != update or
            cpu_spec.get('count_basis') != 'original-oracle-count-mutations'):
        raise ValueError('oracle effects require the same bounded cached-interpreter CPU capture')
    return {'schema': 1, 'update': update, 'observation_only': True,
            'opcode_basis': 'cached-decoder-word-not-refetched-ram',
            'phase': 'entry-paired-effects-with-explicit-branch-eret-exception-idle', **LIMITS}


def configure(environment, spec):
    environment.pop('JFG_PHASE9_ORACLE_EFFECT_UPDATE', None)
    if spec is not None:
        environment['JFG_PHASE9_ORACLE_EFFECT_UPDATE'] = str(spec['update'])


def records(path, update):
    if type(update) is not int or not 1 <= update <= 1000000 or path.stat().st_size > MAX_BYTES:
        raise ValueError('oracle effect window or byte budget differs')
    with path.open('rb') as stream:
        def exact(size):
            data = stream.read(size)
            if len(data) != size:
                raise ValueError('oracle effect stream truncated')
            return data
        if exact(12) != MAGIC + struct.pack('<I', update):
            raise ValueError('oracle effect header differs')
        sequence, previous_device, gpr, pending = 0, 0, [0]*32, None
        while True:
            phase = exact(1)[0]
            if phase == 255:
                if not sequence or struct.unpack('<I', exact(4))[0] != sequence or pending or stream.read(1):
                    raise ValueError('oracle effect footer/pending entry/trailing bytes differ')
                return
            if phase >= len(PHASES) or sequence == MAX_ROWS:
                raise ValueError('oracle effect phase or row budget differs')
            values = struct.unpack('<16I', exact(64))
            row, mask = dict(zip(WORDS, values[:15])), values[15]
            if (not row['pc'] or any(row[k] % 4 for k in ('pc', 'live_pc', 'thread_word', 'anchor', 'target')) or
                    row['delay_slot'] > 3 or row['llbit'] not in (0, 1) or
                    not previous_device <= row['device_sequence'] <= 65536 or
                    (sequence == 0 and mask != 0xffffffff)):
                raise ValueError('oracle effect row fields or first GPR mask differ')
            for index in range(32):
                if mask & (1 << index):
                    value = struct.unpack('<Q', exact(8))[0]
                    if sequence and value == gpr[index]:
                        raise ValueError('oracle effect GPR delta is not canonical')
                    gpr[index] = value
            if gpr[0] != 0:
                raise ValueError('oracle effect r0 is not zero')
            if phase == 0:
                if pending or row['live_pc'] != row['pc'] or row['target'] or row['flags'] or row['idle_ticks'] or (
                        row['delay_slot'] and branch_word(row['opcode'])):
                    raise ValueError('oracle effect entry overlaps or is malformed')
                pending = row
            else:
                if not pending or any(row[k] != pending[k] for k in ('pc', 'opcode')):
                    raise ValueError('oracle effect does not pair with its exact entry')
                if phase != 2 and row['flags'] or phase != 5 and row['idle_ticks']:
                    raise ValueError('oracle effect phase metadata differs')
                if phase == 1 and (branch_word(row['opcode']) or row['opcode'] == 0x42000018 or row['target'] or
                                  ((row['status'] ^ pending['status']) & 2 and
                                   row['opcode'] & 0xffe0ffff != 0x40806000)):
                    raise ValueError('oracle ordinary effect masks a transfer or exception')
                if phase == 2 and (not branch_word(row['opcode']) or row['flags'] > 3 or row['live_pc'] != row['pc']):
                    raise ValueError('oracle branch decision boundary differs')
                if phase == 3 and (row['opcode'] != 0x42000018 or pending['status'] & 6 != 2 or
                        row['status'] != pending['status'] & ~2 or row['target'] != row['epc'] or
                        row['live_pc'] != row['epc'] or row['anchor'] != row['epc'] or row['llbit']):
                    raise ValueError('oracle ERET boundary differs')
                if phase == 4 and (not row['status'] & 2 or row['live_pc'] not in (0x80000000, 0x80000180) or
                                   row['target'] != row['live_pc']):
                    raise ValueError('oracle exception boundary differs')
                if phase == 5 and (not branch_word(row['opcode']) or row['live_pc'] != row['pc'] or
                        row['target'] != row['pc'] or not row['idle_ticks'] or row['idle_ticks'] % 4):
                    raise ValueError('oracle idle boundary differs')
                pending = None
            previous_device = row['device_sequence']; sequence += 1
            yield {**row, 'phase': PHASES[phase], 'sequence': sequence, 'invocation': update, 'gpr': tuple(gpr)}


def summary(path, spec):
    try:
        counts = Counter(row['phase'] for row in records(path, spec['update']))
        return {'complete': True, 'events': sum(counts.values()), 'phases': dict(counts), **LIMITS}
    except (OSError, ValueError) as error:
        return {'complete': False, 'error': str(error)}
