"""Qualify bounded reference-device observations, without altering the game."""
from itertools import groupby
from pathlib import Path
import argparse
import json

from scripts.phase9_cpu_vi_trace import parse_trace as parse_vi
from scripts.phase9_cpu_dma_trace import parse_trace as parse_dma


def qualify_vi(path):
    rows = parse_vi(Path(path))["cases"]
    groups = []
    for key, group in groupby(rows, key=lambda row: (row["v_sync"], row["h_sync"])):
        values = [row["ticks"] for row in group]
        if len(values) != 32:
            raise ValueError("32 consecutive VI intervals required")
        # Endpoint quantization is not accumulated once per interval: all
        # 32 differences telescope to two samples of a 7-instruction poll.
        total = sum(values)
        low = (total - 14 + 31) // 32
        high = (total + 14) // 32
        expected = (key[0] + 1) * 1500
        if low != high or low != expected or any(abs(value - expected) > 14 for value in values):
            raise ValueError("VI period rule not uniquely supported by bounded observations")
        groups.append({"v_sync": key[0], "h_sync": key[1], "period": low,
                       "intervals": 32, "total_ticks": total})
    return groups


def qualify_rsp(path):
    lines = Path(path).read_text().splitlines()
    header = "case launch last_running first_halted helper_entry before_start".split()
    if len(lines) != 18 or lines[0].split("\t") != header or lines[-1] != "result\ttrue\t16":
        raise ValueError("complete phased SP deadline trace required")
    windows = []
    for expected, line in enumerate(lines[1:-1], 1):
        fields = line.split("\t")
        if len(fields) != 6 or not all(value.isdecimal() and int(value) <= 0xffffffff for value in fields):
            raise ValueError("invalid SP deadline observation")
        case, launch, running, halted, helper, before = map(int, fields)
        delta = lambda value, origin: (value - origin) & 0xffffffff
        if case != expected or launch != helper or delta(launch, before) != 40 or delta(halted, running) != 14:
            raise ValueError("SP observation boundaries changed")
        # Independently generated original start: SW is instruction 20 of 24.
        # The measuring MFC0 plus JAL/delay add three instructions. The core's
        # exposed Count at helper entry and SW is lazy (unchanged for 3 ops).
        store_retired = (before + 2 * (3 + 20)) & 0xffffffff
        low, high = delta(running, store_retired), delta(halted, store_retired)
        if not 0 < low < high < 10000:
            raise ValueError("SP deadline not bounded after launch")
        windows.append((low, high))
    result = []
    for index, expected in ((0, 1000), (8, 4000)):
        low = max(row[0] for row in windows[index:index + 8])
        high = min(row[1] for row in windows[index:index + 8])
        # The qualified CPU profile observes two-tick boundaries. This is an
        # effective deadline at that resolution, not sub-instruction timing.
        first_even = (low // 2 + 1) * 2
        if first_even != expected or high != expected:
            raise ValueError("SP latency not uniquely supported at two-tick resolution")
        result.append({"task_type": 1 if index == 0 else 2,
                       "effective_latency": expected, "resolution": 2,
                       "last_running_exclusive": low, "first_halted_inclusive": high})
    return result


def qualify_dma(path):
    rows = parse_dma(Path(path))['cases']
    result = []
    for key, group in groupby(rows, key=lambda row: (row['kind'], row['length'])):
        phases = list(group)
        if len(phases) != 8:
            raise ValueError('eight DMA launch/poll phases required')
        # Launch callback is at the first instruction of the called helper.
        # Unlike the SP helper it has no preceding straight-line instructions:
        # its SW retires two ticks after the branch-updated exposed Count.
        low = max(row['exclusive_lower'] - 2 for row in phases)
        high = min(row['inclusive_upper'] - 2 for row in phases)
        first_even = (max(low, -1) // 2 + 1) * 2
        if high < first_even:
            raise ValueError('DMA observation windows have no shared deadline')
        unique = first_even == high
        result.append({'kind': key[0], 'length': key[1],
                       'exclusive_lower': low, 'inclusive_upper': high,
                       'unique_at_two_tick_resolution': unique,
                       'effective_latency': first_even if unique else None})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vi", type=Path, required=True)
    parser.add_argument("--rsp", type=Path, required=True)
    parser.add_argument("--dma", type=Path)
    args = parser.parse_args()
    print(json.dumps({"kind": "jfg-observed-reference-device-timing", "acceptance": False,
                      "hardware_qualified": False, "game_clock_integrated": False,
                      "vi": qualify_vi(args.vi), "rsp": qualify_rsp(args.rsp),
                      "dma": qualify_dma(args.dma) if args.dma else None}, indent=2))


if __name__ == "__main__":
    main()
