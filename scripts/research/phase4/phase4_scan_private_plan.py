from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import itertools
import os
import re
import struct
import subprocess
import tempfile
from pathlib import Path


OLD_MODULE = struct.Struct("<QIIIII")
NEW_MODULE = struct.Struct("<QIIIIIIB3x")
SUITE = struct.Struct("<IHHI16s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("old_case", type=Path)
    parser.add_argument("lookup", type=Path)
    parser.add_argument("producer", type=Path)
    args = parser.parse_args()
    original = args.old_case.read_bytes()
    _version, _subjects, module_count, _guest, _token = SUITE.unpack_from(
        original, 8
    )
    if original[:8] != b"JFG2OVL3" or module_count != 2:
        raise SystemExit("unsupported diagnostic case")
    entries: dict[int, list[int]] = {}
    for section, offset in re.findall(
        r"\{(\d+)u,\s*UINT32_C\(0x([0-9A-Fa-f]{8})\),",
        args.lookup.read_text(encoding="utf-8"),
    ):
        entries.setdefault(int(section), []).append(int(offset, 16))

    cursor = 8 + SUITE.size
    records: list[tuple[tuple[int, ...], bytes]] = []
    for _ in range(module_count):
        fields = OLD_MODULE.unpack_from(original, cursor)
        cursor += OLD_MODULE.size
        image = original[cursor : cursor + fields[5]]
        cursor += fields[5]
        records.append((fields, image))
    suffix = original[cursor:]

    def payload(first: int, first_seed: int, second: int, second_seed: int) -> bytes:
        output = bytearray(original[: 8 + SUITE.size])
        for (fields, image), ordinal, seed in zip(
            records, (first, second), (first_seed, second_seed)
        ):
            offset = entries[fields[1]][ordinal - 1]
            output.extend(NEW_MODULE.pack(*fields, offset, seed))
            output.extend(image)
        output.extend(suffix)
        return bytes(output)

    nonce = "56" * 32
    passing: list[tuple[int, int, int, int]] = []
    with tempfile.TemporaryDirectory(prefix="jfg-phase4-plan-scan-") as temp:
        root = Path(temp)
        plans = (
            plan
            for plan in itertools.product(
                range(1, len(entries[records[0][0][1]]) + 1),
                range(5),
                range(1, len(entries[records[1][0][1]]) + 1),
                range(5),
            )
            # Exhaust every new-profile pairing, plus each new profile against
            # the prior trace's fixed control on the other module. These
            # controls diagnose profile viability only and are never emitted
            # as a production function plan.
            if (plan[1] >= 3 and plan[3] >= 3)
            or (plan[1] >= 3 and plan[2:] == (7, 1))
            or (plan[:2] == (2, 1) and plan[3] >= 3)
        )

        def run(candidate_plan: tuple[int, int, int, int], repeat: int) -> bool:
            candidate = payload(*candidate_plan)
            digest = hashlib.sha256(candidate).hexdigest()
            candidate_root = root / (
                "-".join(str(value) for value in candidate_plan) + f"-{repeat}"
            )
            candidate_root.mkdir()
            (candidate_root / "case-input.bin").write_bytes(candidate)
            return subprocess.run(
                (
                    args.producer,
                    "--g2-evidence-probe",
                    nonce,
                    "overlay-lifecycle",
                    "private-native-execution",
                    "--case-id",
                    "g2-custom-" + digest[:16],
                    "--subject-sha256",
                    digest,
                ),
                cwd=candidate_root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
            ).returncode == 0

        workers = min(8, os.cpu_count() or 1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(run, plan, 0): plan
                for plan in plans
            }
            for future in concurrent.futures.as_completed(futures):
                plan = futures[future]
                if future.result():
                    passing.append(plan)
        stable: list[tuple[int, int, int, int]] = []
        for candidate_plan in passing:
            if all(run(candidate_plan, repeat) for repeat in range(1, 11)):
                stable.append(candidate_plan)
    for first, first_seed, second, second_seed in stable:
        print(
            f"stable_plan=M1:{first}/{first_seed},M2:{second}/{second_seed}"
        )
    print(f"stable_plan_count={len(stable)}")
    return 0 if stable else 1


if __name__ == "__main__":
    raise SystemExit(main())
