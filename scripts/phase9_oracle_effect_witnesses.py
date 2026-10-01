"""Bind oracle effects to exact local device and CPU-boundary witnesses.

Readers must validate their inputs. This consumes the effect iterator fully;
it never aligns native clocks, searches ahead by PC, or certifies all effects.
"""
from collections import Counter


def bind(rows, device_rows, cpu_rows, update):
    if type(update) is not int or not 1 <= update <= 1000000:
        raise ValueError('oracle witness invocation is invalid')
    instructions = {row['sequence']:row for row in device_rows
                    if row['invocation'] == update and row['phase'] == 'instruction'}
    erets = [row for row in cpu_rows if row['invocation'] == update and row['kind'] == 'eret']
    idles = [row for row in cpu_rows if row['invocation'] == update and row['kind'] == 'count' and row['reason'] == 'idle']
    if not instructions:
        raise ValueError('oracle effects lack independent instruction witnesses')
    seen, phases = set(), Counter()
    eret_index = idle_index = 0
    for row in rows:
        if row['invocation'] != update:
            raise ValueError('oracle effect invocation differs')
        phases[row['phase']] += 1
        if row['phase'] == 'entry':
            witness = instructions.get(row['device_sequence'])
            if witness is not None and witness['sequence'] not in seen:
                fields = (('pc','pc'),('opcode','opcode'),('thread_word','thread'),
                          ('count','clock_raw'),('anchor','clock_anchor_pc'),('status','status'),('cause','cause'))
                if (any(row[a] != witness[b] for a,b in fields) or
                        row['gpr'] != tuple(witness[f'r{i}_lo'] | witness[f'r{i}_hi'] << 32 for i in range(32))):
                    raise ValueError('oracle entry differs from its exact device witness')
                seen.add(witness['sequence'])
        elif row['phase'] == 'eret':
            if eret_index == len(erets):
                raise ValueError('extra oracle ERET effect')
            witness = erets[eret_index]
            fields = (('pc','pc'),('target','target_pc'),('live_pc','target_pc'),('count','count_after'),
                      ('anchor','anchor_after'),('status','status_after'),('epc','epc_after'),
                      ('llbit','llbit_after'),('thread_word','thread_word_after'),('device_sequence','device_sequence'))
            if (any(row[a] != witness[b] for a,b in fields) or
                    row['gpr'] != tuple(witness[f'r{i}'] for i in range(32))):
                raise ValueError('oracle ERET differs from its dedicated boundary witness')
            eret_index += 1
        elif row['phase'] == 'idle':
            if idle_index == len(idles):
                raise ValueError('extra oracle idle effect')
            witness = idles[idle_index]
            fields = (('pc','pc'),('count','count_after'),('anchor','anchor_after'),('idle_ticks','operand'),
                      ('status','status'),('cause','cause'),('thread_word','thread_word'),('device_sequence','device_sequence'))
            if any(row[a] != witness[b] for a,b in fields):
                raise ValueError('oracle idle differs from its Count witness')
            idle_index += 1
    if seen != set(instructions) or eret_index != len(erets) or idle_index != len(idles):
        raise ValueError('oracle effects omitted independently observed boundaries')
    return {'phase_counts':dict(phases),'device_instruction_witnesses':len(seen),
            'eret_witnesses':eret_index,'idle_witnesses':idle_index,
            'clock_alignment_validated':False,'retirement_validated':False,
            'all_effect_semantics_proved':False,'cross_engine_correspondence_validated':False}
