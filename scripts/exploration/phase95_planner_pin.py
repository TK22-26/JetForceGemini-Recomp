"""Pin the Python control and verification code used by a frontier job."""

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"

import hashlib
import json
from pathlib import Path


SOURCES = (
    "phase95_bridge.py",
    "phase95_exit.py",
    "phase95_explore.py",
    "phase95_export_inputs.py",
    "phase95_frontier_cycle.py",
    "phase95_frontier_discover.py",
    "phase95_frontier_graph.py",
    "phase95_frontier_job.py",
    "phase95_frontier_salvage.py",
    "phase95_frontier_verify_node.py",
    "phase95_navigation.py",
    "phase95_observation.py",
    "phase95_planner_pin.py",
    "phase95_poll_compare.py",
    "phase95_route_verifier.py",
    "phase95_world.py",
)


def source_pin(paths=None):
    paths = ([Path(__file__).with_name(name) for name in SOURCES]
             if paths is None else [Path(path) for path in paths])
    entries = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
               for path in paths}
    if len(entries) != len(paths):
        raise ValueError("planner source names must be unique")
    return {"sha256": hashlib.sha256(json.dumps(
                entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "files": dict(sorted(entries.items()))}
