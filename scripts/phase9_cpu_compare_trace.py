"""Strict CP0 Compare observations including wrap and write acknowledgement."""
from pathlib import Path


def parse_trace(path):
    lines = Path(path).read_text().splitlines()
    if len(lines) != 66 or lines[0] != 'case\tphase\tcompare\tlast_pending\tfirst_complete' or lines[-1] != 'result\ttrue\t64':
        raise ValueError('incomplete Compare trace')
    rows = []
    for index, line in enumerate(lines[1:-1]):
        fields = line.split('\t')
        if len(fields) != 5 or any(not v.isdecimal() or int(v) > 0xffffffff for v in fields):
            raise ValueError('invalid Compare observation')
        case, phase, compare, low, high = map(int, fields)
        if (case, phase) != divmod(index, 8):
            raise ValueError('Compare coverage differs')
        signed = lambda value: (value + 0x80000000) % 0x100000000 - 0x80000000
        rows.append(dict(case=case, phase=phase, low=signed(low-compare), high=signed(high-compare)))
    return {'cases': rows, 'hardware_qualified': False}
