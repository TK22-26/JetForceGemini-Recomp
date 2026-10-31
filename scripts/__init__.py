"""Project tools grouped on disk by responsibility.

The historical ``scripts.<tool>`` module API remains supported for existing
callers. Direct CLI paths use the domain folders; shared code uses
that stable API to avoid loading a tool under two module identities. Filenames are unique across tool domains.
"""
from pathlib import Path
_root = Path(__file__).resolve().parent
__path__ = [str(_root / name) for name in (
    "build", "release", "validation", "evidence", "diagnostics", "exploration", "verification"
)] + [str(_root)]
