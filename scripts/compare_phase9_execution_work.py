"""Compare diagnostic instruction entries to paired reference Count intervals.

Two ticks is an explicit hypothesis for the named reference, never hardware
qualification. Interrupt-spanning pairs are reported separately, not fitted.
"""
import argparse
import json
from pathlib import Path


def native_pairs(path, entry_event="entry", return_event="entry-return"):
    pairs, stack = [], []
    for line in Path(path).read_text().splitlines():
        fields = line.split("\t")
        if fields[0] != "execution-work":
            continue
        if len(fields) != 7:
            raise ValueError("malformed execution observation")
        _, update, poll, vi, event, pc, count = fields
        row = {"update": int(update), "poll": int(poll), "vi": int(vi),
               "pc": int(pc, 16), "count": int(count)}
        if event == entry_event:
            stack.append(row)
        elif event == return_event:
            if not stack:
                raise ValueError("native return without entry")
            start = stack.pop()
            if start["pc"] != row["pc"] or row["count"] < start["count"]:
                raise ValueError("native pairing mismatch")
            pairs.append({"update": start["update"], "poll": start["poll"],
                          "instructions": row["count"] - start["count"],
                          "vi_delta": row["vi"] - start["vi"]})
    if stack or not pairs:
        raise ValueError("incomplete native execution observation")
    return pairs


def oracle_pairs(path):
    lines = Path(path).read_text().splitlines()
    if len(lines) < 3 or lines[0] != "event\tframe\tupdate\tpoll\tvi\tcount\tepc\tcause" or \
            lines[-1] != f"result\ttrue\t{len(lines)-2}":
        raise ValueError("incomplete oracle execution observation")
    pairs, stack, exceptions = [], [], 0
    for line in lines[1:-1]:
        fields = line.split("\t")
        if len(fields) != 8:
            raise ValueError("malformed oracle clock row")
        event, _, update, poll, vi, count, _, _ = fields
        if event == "exception":
            exceptions += 1
        row = {"update": int(update), "poll": int(poll), "vi": int(vi),
               "count": int(count, 16), "exceptions": exceptions}
        if event == "entry":
            stack.append(row)
        elif event == "entry-return":
            if not stack:
                raise ValueError("oracle return without entry")
            start = stack.pop()
            pairs.append({"update": start["update"], "poll": start["poll"],
                          "ticks": (row["count"] - start["count"]) & 0xffffffff,
                          "exceptions": exceptions - start["exceptions"],
                          "vi_delta": row["vi"] - start["vi"]})
    if stack or not pairs:
        raise ValueError("incomplete oracle entry pairing")
    return pairs


def compare(native, oracle):
    if len(native) != len(oracle):
        raise ValueError("execution pair counts differ")
    result = []
    for left, right in zip(native, oracle):
        if (left["update"], left["poll"]) != (right["update"], right["poll"]):
            raise ValueError("execution pair update/poll alignment differs")
        result.append({**left, "oracle_ticks": right["ticks"],
                       "oracle_exceptions": right["exceptions"],
                       "oracle_vi_delta": right["vi_delta"],
                       "two_tick_residual": right["ticks"] - 2 * left["instructions"],
                       "uninterrupted_candidate": right["exceptions"] == 0 and
                           left["vi_delta"] == 0 and right["vi_delta"] == 0})
    return {"kind": "jfg-execution-work-comparison", "acceptance": False,
            "hardware_qualified": False, "pairs": result}


def graphics_to_pacing(native_path, oracle_path):
    """Strict US diagnostic interval; addresses select observations, not costs.

    Count only exceptions beginning AND resuming within this interval. Reject
    ambiguous or incomplete pairing rather than fitting the missing work.
    Overlapping interrupted intervals are unioned, never double-counted.
    """
    native, start = [], None
    for line in Path(native_path).read_text().splitlines():
        fields = line.split("\t")
        if fields[0] != "execution-work":
            continue
        if len(fields) != 7:
            raise ValueError("malformed native interval row")
        _, update, poll, _, event, pc, count = fields
        if (event, pc) == ("recv-return", "800fe8a8"):
            if start is not None:
                raise ValueError("duplicate native interval start")
            start = (int(update), int(poll), int(count))
        elif (event, pc) == ("entry", "80054fbc"):
            if start is None or start[:2] != (int(update), int(poll)):
                raise ValueError("unpaired native interval")
            work = int(count) - start[2]
            if work < 0:
                raise ValueError("native instruction counter moved backwards")
            native.append({"update": start[0], "poll": start[1], "instructions": work})
            start = None
    if start is not None or not native:
        raise ValueError("incomplete native intervals")

    lines = Path(oracle_path).read_text().splitlines()
    if len(lines) < 3 or lines[0] != "event\tframe\tupdate\tpoll\tvi\tcount\tepc\tcause" or \
            lines[-1] != f"result\ttrue\t{len(lines)-2}":
        raise ValueError("incomplete oracle intervals")
    oracle, start = [], None
    for line in lines[1:-1]:
        fields = line.split("\t")
        if len(fields) != 8:
            raise ValueError("malformed oracle interval row")
        event, _, update, poll, _, count, epc, _ = fields
        count = int(count, 16)
        if event == "return-80332240":
            if start is not None:
                raise ValueError("duplicate oracle interval start")
            start = (int(update), int(poll), count)
            pending, interruptions = {}, []
        elif start is not None:
            offset = (count - start[2]) & 0xffffffff
            if offset > 0x7fffffff:
                raise ValueError("ambiguous Count wrap or backwards interval")
            if event == "exception":
                pc = int(epc, 16)
                if pc in pending:
                    raise ValueError("ambiguous repeated exception PC")
                pending[pc] = offset
            elif event.startswith("exception-resume-"):
                pc = int(event.removeprefix("exception-resume-"), 16)
                if pc in pending:
                    interruptions.append((pending.pop(pc), offset))
            elif event == "entry":
                if pending or start[:2] != (int(update), int(poll)):
                    raise ValueError("incomplete exception or mismatched interval end")
                union_ticks, end = 0, 0
                for begin, finish in sorted(interruptions):
                    union_ticks += max(0, finish - max(begin, end))
                    end = max(end, finish)
                oracle.append({"update": start[0], "poll": start[1],
                               "oracle_ticks": offset,
                               "interrupted_wall_ticks": union_ticks,
                               "exception_intervals": interruptions})
                start = None
    if start is not None or len(native) != len(oracle):
        raise ValueError("incomplete or unequal interval counts")
    pairs = []
    for left, right in zip(native, oracle):
        if (left["update"], left["poll"]) != (right["update"], right["poll"]):
            raise ValueError("interval update/poll alignment differs")
        pairs.append({**left, **right, "guest_two_tick_residual":
                      right["oracle_ticks"] - right["interrupted_wall_ticks"] -
                      2 * left["instructions"]})
    return {"kind": "jfg-graphics-to-pacing-work", "acceptance": False,
            "hardware_qualified": False, "pairs": pairs}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("oracle", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--graphics-to-pacing", action="store_true")
    mode.add_argument("--guest-leaf", action="store_true")
    args = parser.parse_args()
    native_events = ("guest-leaf-entry", "guest-leaf-return") if args.guest_leaf else \
        ("entry", "entry-return")
    result = graphics_to_pacing(args.native, args.oracle) if args.graphics_to_pacing else \
        compare(native_pairs(args.native, *native_events), oracle_pairs(args.oracle))
    print(json.dumps(result, indent=2))
