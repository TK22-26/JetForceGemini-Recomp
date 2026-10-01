from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("producer", type=Path)
    parser.add_argument("--runs", type=int, default=20)
    args = parser.parse_args()
    if args.runs < 1 or args.runs > 100:
        raise SystemExit("invalid run count")
    payload = args.case.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    command = (
        args.producer,
        "--g2-evidence-probe",
        "56" * 32,
        "overlay-lifecycle",
        "private-native-execution",
        "--case-id",
        "g2-custom-" + digest[:16],
        "--subject-sha256",
        digest,
    )
    passed = 0
    for _ in range(args.runs):
        result = subprocess.run(
            command,
            cwd=args.case.parent,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
        passed += result.returncode == 0
    print(f"private_stress={passed}/{args.runs}")
    return 0 if passed == args.runs else 1


if __name__ == "__main__":
    raise SystemExit(main())
