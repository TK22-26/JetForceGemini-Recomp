"""Strict independent PI length/phase observations; retain unresolved bounds."""
from pathlib import Path
from itertools import product, groupby

LENGTHS = (
    *range(8, 65, 8),  # Eight short aligned transfers.
    80, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536, 262144,
)


def parse_trace(path):
    lines = Path(path).read_text().splitlines()
    if len(lines) != 154 or lines[0] != 'length\tphase\tlaunch\tlast_pending\tfirst_complete' or lines[-1] != 'result\ttrue\t152':
        raise ValueError('incomplete PI phase sweep')
    rows = []
    first_length = lines[1].split('\t')[0]
    offsets = {'4': -4, '8': 0, '12': 4}
    if first_length not in offsets and first_length != '1':
        raise ValueError('unknown PI length profile')
    lengths = tuple(range(1, 18)) + (754, 65535) if first_length == '1' else tuple(v + offsets[first_length] for v in LENGTHS)
    for line, expected in zip(lines[1:-1], product(lengths, range(8))):
        fields = line.split('\t')
        if len(fields) != 5 or any(not v.isdecimal() or int(v) > 0xffffffff for v in fields):
            raise ValueError('invalid PI observation')
        length, phase, launch, last, first = map(int, fields)
        low, high = (last - launch) & 0xffffffff, (first - launch) & 0xffffffff
        if (length, phase) != expected or not 0 <= low < high < 1000000:
            raise ValueError('PI coverage or bounds differ')
        rows.append(dict(length=length, phase=phase, low=low-4, high=high-4))
    if first_length == '1':
        copied = Path(path).with_name('pi-bytes.tsv').read_text().splitlines()
        if len(copied) != 153 or copied[0] != 'length\tphase\tcopied_mismatches\ttrailing_bytes':
            raise ValueError('incomplete PI byte-copy observations')
        for line, row in zip(copied[1:], rows):
            expected = [str(row['length']), str(row['phase']), '0', 'cc' * 16]
            if line.split('\t') != expected:
                raise ValueError('PI byte-copy or sentinel mismatch')
    return {'cases': rows, 'hardware_qualified': False}


def summarize(path):
    result = []
    for length, rows in groupby(parse_trace(path)['cases'], key=lambda row: row['length']):
        rows = list(rows)
        low, high = max(row['low'] for row in rows), min(row['high'] for row in rows)
        first_even = (max(low, -1) // 2 + 1) * 2
        if first_even > high:
            raise ValueError('PI observation windows contradict each other')
        result.append(dict(length=length, low=low, high=high,
                           unique=first_even == high, candidate=first_even if first_even == high else None))
    return result
