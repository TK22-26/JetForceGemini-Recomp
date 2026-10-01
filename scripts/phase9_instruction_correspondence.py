"""Bounded instruction correspondence, not Count alignment or game parity.

No searching/skipping to a matching PC. A single explicit return epilogue
accounts for the differing invocation markers. The only copied-code rule is
the independently checked four-instruction US installed exception vector.
Unknown overlays, exception-effect boundaries and idle spans stop comparison.
Both supplied, validating readers are exhausted even after the first difference.
"""
from collections import Counter, deque
from dataclasses import dataclass
import hashlib

VECTOR_SOURCE = 0x80075020
VECTOR_INSTALLED = 0x80000180
VECTOR_TARGET = 0x80075030
VECTOR_WORDS = (0x3c1a8007, 0x275a5030, 0x03400008, 0)
COMMON = ('opcode', 'gpr', 'status', 'cause', 'thread_word')


@dataclass(frozen=True)
class VectorEvidence:
    snapshots: tuple


def qualify_vector_snapshots(native, oracle):
    """Snapshot bytes are supporting code evidence, not live memory tracing."""
    if not native or native.keys() != oracle.keys() or len(native) > 16:
        raise ValueError('copied-vector snapshot inventory differs')
    expected = b''.join(word.to_bytes(4,'big') for word in VECTOR_WORDS)
    evidence = []
    for side, snapshots in (('native',native),('oracle',oracle)):
        for update,data in sorted(snapshots.items()):
            if type(update) is not int or not 1 <= update <= 1000000 or len(data) != 4*1024*1024:
                raise ValueError('copied-vector snapshot shape differs')
            for address in (VECTOR_SOURCE,VECTOR_INSTALLED):
                offset = address & 0x1fffffff
                if data[offset:offset+16] != expected:
                    raise ValueError('copied-vector snapshot instructions differ')
            evidence.append((side,update,hashlib.sha256(data).hexdigest()))
    return VectorEvidence(tuple(evidence))


def differences(left, right):
    values = {key:{'native':left[key],'oracle':right[key]} for key in COMMON if left[key] != right[key]}
    if 'gpr' in values:
        values['gpr'] = {str(index):{'native':left['gpr'][index],'oracle':right['gpr'][index]}
                         for index in range(32) if left['gpr'][index] != right['gpr'][index]}
    return values


def _take(iterator, count):
    rows = []
    for _ in range(count):
        row = next(iterator,None)
        if row is None: raise ValueError('correspondence boundary is truncated')
        rows.append(row)
    return rows


def return_anchor(lead, native, oracle):
    if len(lead) != 4 or [row['phase'] for row in lead] != ['entry','branch','entry','ordinary']:
        raise ValueError('invocation lead-in is not one paired return and slot')
    entry, effect, slot, after = lead
    pc = entry['pc']; target = entry['gpr'][31] & 0xffffffff
    if (entry['opcode'] != 0x03e00008 or effect['opcode'] != entry['opcode'] or effect['pc'] != pc or
            slot['pc'] != pc+4 or after['pc'] != pc+4 or slot['opcode'] or after['opcode'] or
            effect['flags'] != 1 or effect['target'] != target or entry['delay_slot'] != 0 or
            effect['delay_slot'] != 0 or slot['delay_slot'] != 1 or after['delay_slot'] != 1 or
            any(row['gpr'] != entry['gpr'] or any(row[key] != entry[key] for key in
                    ('status','cause','thread_word')) for row in lead) or
            native['phase'] != 0 or oracle['phase'] != 'entry' or native['pc'] != target or oracle['pc'] != target or
            native['gpr'] != entry['gpr'] or oracle['gpr'] != entry['gpr'] or differences(native,oracle)):
        raise ValueError('invocation return/slot/caller continuity differs')
    return {'oracle_epilogue':lead,'caller_native_sequence':native['sequence'],
            'caller_oracle_sequence':oracle['sequence'],'caller_pc':target}


def vector_mapping(native, oracle, following_native, following_oracle, evidence):
    if not isinstance(evidence,VectorEvidence) or not evidence.snapshots or len(native) != 8 or len(oracle) != 8:
        raise ValueError('copied-vector evidence is missing')
    initial = native[0]['gpr']
    wanted = list(initial)
    raw = []
    for instruction,word in enumerate(VECTOR_WORDS):
        entry_index = instruction*2
        for effect in (False,True):
            index = entry_index+int(effect); a,b = native[index],oracle[index]
            if effect and instruction == 0: wanted[26] = 0xffffffff80070000
            if effect and instruction == 1: wanted[26] = 0xffffffff80075030
            oracle_phase = 'entry' if not effect else 'branch' if instruction == 2 else 'ordinary'
            if (a['section'] != 0 or a['pc'] != VECTOR_SOURCE+instruction*4 or
                    b['pc'] != VECTOR_INSTALLED+instruction*4 or a['opcode'] != word or b['opcode'] != word or
                    a['phase'] != int(effect) or b['phase'] != oracle_phase or
                    not a['status'] & 2 or a['status'] & 4 or differences(a,b) or
                    a['gpr'] != tuple(wanted) or
                    any(a[key] != native[0][key] for key in ('status','cause','thread_word','owner')) or
                    b['delay_slot'] != (1 if instruction == 3 else 0)):
                raise ValueError('copied-vector instruction/order/register effect differs')
            if instruction == 2 and effect and (b['flags'] != 1 or b['target'] != VECTOR_TARGET):
                raise ValueError('copied-vector indirect target differs')
            raw.append({'native_sequence':a['sequence'],'oracle_sequence':b['sequence'],
                        'native_pc':a['pc'],'oracle_pc':b['pc'],'opcode':word})
    if (following_native['phase'] != 0 or following_oracle['phase'] != 'entry' or
            following_native['pc'] != VECTOR_TARGET or following_oracle['pc'] != VECTOR_TARGET or
            following_native['gpr'] != tuple(wanted) or differences(following_native,following_oracle)):
        raise ValueError('copied-vector following handler is not the observed indirect target')
    return {'kind':'checked-installed-vector','rows':raw,'target':VECTOR_TARGET,
            'gpr_effects_independently_checked':True,'hardware_retirement_validated':False}


def compare(native_rows, oracle_rows, update, vector_evidence):
    if type(update) is not int or not 1 <= update <= 1000000:
        raise ValueError('correspondence invocation is invalid')
    if not isinstance(vector_evidence,VectorEvidence) or not vector_evidence.snapshots:
        raise ValueError('correspondence requires independently checked vector snapshots')
    counts = {'native':Counter(),'oracle':Counter()}
    def checked(rows, side):
        for row in rows:
            if row['invocation'] != update: raise ValueError('correspondence invocation differs')
            counts[side][str(row['phase'])] += 1
            yield row
    native,oracle = checked(native_rows,'native'),checked(oracle_rows,'oracle')
    lead = _take(oracle,4)
    a,b = _take(native,1)[0],_take(oracle,1)[0]
    anchor = return_anchor(lead,a,b)
    matched, mapped, first = 0, [], None
    history = deque(maxlen=6)
    while a is not None and b is not None:
        if a['pc'] == VECTOR_SOURCE and b['pc'] == VECTOR_INSTALLED:
            left,right = [a,*_take(native,7)],[b,*_take(oracle,7)]
            following_a,following_b = _take(native,1)[0],_take(oracle,1)[0]
            try:
                mapping = vector_mapping(left,right,following_a,following_b,vector_evidence)
            except ValueError as error:
                first = {'kind':'unqualified-code-mapping','error':str(error),'native':left,'oracle':right}
                break
            mapped.append(mapping); matched += 8
            history.extend({'native':x,'oracle':y} for x,y in zip(left,right))
            a,b = following_a,following_b
            continue
        if a['pc'] != b['pc'] or a['opcode'] != b['opcode']:
            first = {'kind':'raw-code-identity','native':a,'oracle':b}; break
        if (a['phase'],b['phase']) not in ((0,'entry'),(1,'ordinary'),(1,'branch'),(2,'eret')):
            first = {'kind':'effect-boundary','native':a,'oracle':b}; break
        different = differences(a,b)
        if different:
            first = {'kind':'shared-state','fields':different,'native':a,'oracle':b}; break
        history.append({'native':a,'oracle':b}); matched += 1
        a,b = next(native,None),next(oracle,None)
    if first is None:
        first = {'kind':'window-end','native':a,'oracle':b}
    # Prefix findings cannot hide a corrupt or incomplete tail.
    for _ in native: pass
    for _ in oracle: pass
    return {'schema':1,'kind':'jfg-bounded-instruction-correspondence','update':update,
        'streams_complete':True,'matching_rows':matched,'return_anchor':anchor,
        'vector_mappings':mapped,'vector_snapshot_evidence':vector_evidence.snapshots,
        'first_difference':first,'preceding_context':list(history),'validated_phase_counts':
            {side:dict(value) for side,value in counts.items()},
        'comparison_fields':['pc/opcode identity','effect phase',*COMMON],
        'raw_clocks_retained':True,'clock_alignment_validated':False,
        'all_code_identity_qualified':False,'full_cpu_state_compared':False,
        'causal_fix_proved':False,'parity_verified':False}
