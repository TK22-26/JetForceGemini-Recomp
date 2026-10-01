"""Persistent, agent-neutral Phase 9.5 gameplay frontier graph.

IDs are stable semantic identifiers supplied by the caller (never heap pointers).
The graph records *declared* gameplay edges, not a complete-game denominator.
Evidence is a pointer to an external artifact, not copied private game data.
Lanes keep Japanese TAS observations, US oracle observations, and native runs
independent; a covered edge in one lane does not cover another lane.
"""

import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import tempfile


KIND = "jfg-phase95-gameplay-frontier"
SCHEMA = 1
NODE_KINDS = frozenset(("level", "checkpoint", "objective", "branch"))
EDGE_KINDS = frozenset(("transition", "progression", "branch", "objective"))
OUTCOMES = frozenset(("covered", "blocked"))
VARIANTS = frozenset(("jp", "us", "unknown"))


def _name(value, field):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field} must be a nonempty, trimmed string")
    return value


def _json_object(value, field):
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ValueError(f"{field} must be a JSON object")
    try:
        return json.loads(json.dumps(value, allow_nan=False, sort_keys=True))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must contain finite JSON values") from error


def _pointer(value, field):
    value = _name(value, field)
    if PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute():
        raise ValueError(f"{field} must be relative or redacted")
    return value


def _capabilities(values):
    if isinstance(values, str):
        raise ValueError("capabilities must be a sequence of names")
    try:
        return sorted({_name(value, "capability") for value in values})
    except TypeError as error:
        raise ValueError("capabilities must be a sequence of names") from error


class FrontierGraph:
    """Append-only graph facts with deterministic, lane-local frontier selection.

    `add_*` and `record` are idempotent for identical facts and reject conflicting
    facts. Blocked evidence remains in history even if later coverage supersedes
    it. `merge` is commutative for compatible graphs, so independent agents can
    produce fragments and combine them on resume.
    """

    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.entrypoints = {}  # lane -> set of explicitly seeded node IDs
        self.evidence = {}     # evidence ID -> immutable edge/lane/outcome/pointer

    def add_node(self, node_id, kind, *, label=None, metadata=None):
        node_id = _name(node_id, "node ID")
        if kind not in NODE_KINDS:
            raise ValueError("unknown node kind")
        item = {"id": node_id, "kind": kind,
                "label": _name(label, "label") if label is not None else node_id,
                "metadata": _json_object({} if metadata is None else metadata,
                                         "node metadata")}
        self._insert(self.nodes, node_id, item)
        return node_id

    def add_edge(self, edge_id, source, target, kind, *, priority=100,
                 source_variant="unknown", source_pointer=None,
                 required_capabilities=(), metadata=None):
        edge_id = _name(edge_id, "edge ID")
        if source not in self.nodes or target not in self.nodes:
            raise ValueError("edge endpoints must already exist")
        if kind not in EDGE_KINDS:
            raise ValueError("unknown edge kind")
        if type(priority) is not int or priority < 0:
            raise ValueError("priority must be a nonnegative integer")
        if source_variant not in VARIANTS:
            raise ValueError("unknown source variant")
        item = {"id": edge_id, "source": source, "target": target,
                "kind": kind, "priority": priority,
                "source_variant": source_variant,
                "source_pointer": (_pointer(source_pointer, "source pointer")
                                   if source_pointer is not None else None),
                "required_capabilities": _capabilities(required_capabilities),
                "metadata": _json_object({} if metadata is None else metadata,
                                         "edge metadata")}
        self._insert(self.edges, edge_id, item)
        return edge_id

    def add_entrypoint(self, lane, node_id):
        """Explicitly seed a lane from a known loadable start/checkpoint.

        This is scheduling configuration, not proof of gameplay coverage.
        """
        lane = _name(lane, "lane")
        if node_id not in self.nodes:
            raise ValueError("entrypoint node does not exist")
        self.entrypoints.setdefault(lane, set()).add(node_id)

    def record(self, evidence_id, edge_id, lane, outcome, pointer, *,
               reason=None, notes=None):
        """Attach one immutable result; pointer names a journal, movie, or replay.

        Use a unique stable evidence ID (for example a run ID plus event number).
        A failed attempt is `blocked`; a later success is `covered`. The graph
        does not infer oracle/native parity from TAS evidence.
        """
        evidence_id = _name(evidence_id, "evidence ID")
        lane = _name(lane, "lane")
        pointer = _pointer(pointer, "evidence pointer")
        if edge_id not in self.edges:
            raise ValueError("evidence edge does not exist")
        if outcome not in OUTCOMES:
            raise ValueError("unknown evidence outcome")
        if outcome == "blocked" and reason is None:
            raise ValueError("blocked evidence requires a reason")
        if outcome == "covered" and reason is not None:
            raise ValueError("covered evidence cannot carry a blocked reason")
        item = {"id": evidence_id, "edge": edge_id, "lane": lane,
                "outcome": outcome, "pointer": pointer,
                "reason": _name(reason, "blocked reason") if reason is not None else None,
                "notes": _name(notes, "notes") if notes is not None else None}
        self._insert(self.evidence, evidence_id, item)
        return evidence_id

    @staticmethod
    def _insert(collection, key, item):
        previous = collection.get(key)
        if previous is not None and previous != item:
            raise ValueError(f"conflicting fact for {key}")
        collection[key] = item

    def status(self, edge_id, lane):
        if edge_id not in self.edges:
            raise KeyError(edge_id)
        _name(lane, "lane")
        outcomes = {item["outcome"] for item in self.evidence.values()
                    if item["edge"] == edge_id and item["lane"] == lane}
        if "covered" in outcomes:
            return "covered"
        return "blocked" if "blocked" in outcomes else "unexplored"

    def reached_nodes(self, lane):
        """Nodes reachable from seeded entries through covered edges only."""
        _name(lane, "lane")
        reached = set(self.entrypoints.get(lane, ()))
        while True:
            expanded = reached | {edge["target"] for edge in self.edges.values()
                                  if edge["source"] in reached and
                                  self.status(edge["id"], lane) == "covered"}
            if expanded == reached:
                return tuple(sorted(reached))
            reached = expanded

    def frontier(self, lane, *, include_blocked=False, capabilities=(), limit=None):
        """Schedule only reachable, untested edges; lower priority then ID first."""
        _name(lane, "lane")
        if limit is not None and (type(limit) is not int or limit < 0):
            raise ValueError("limit must be a nonnegative integer")
        available = set(_capabilities(capabilities))
        reached = set(self.reached_nodes(lane))
        eligible = {"unexplored", "blocked"} if include_blocked else {"unexplored"}
        result = [edge for edge in self.edges.values()
                  if edge["source"] in reached and
                  set(edge["required_capabilities"]) <= available and
                  self.status(edge["id"], lane) in eligible]
        result.sort(key=lambda edge: (edge["priority"], edge["id"]))
        return [edge["id"] for edge in result[:limit]]

    def summary(self, lane):
        """Count declared edges only; unknown game branches are not a denominator."""
        _name(lane, "lane")
        counts = {status: 0 for status in ("covered", "unexplored", "blocked")}
        for edge_id in self.edges:
            counts[self.status(edge_id, lane)] += 1
        return {"lane": lane, "declared_edges": len(self.edges), **counts,
                "coverage_denominator": "declared edges only; full game unknown",
                "reachable_nodes": len(self.reached_nodes(lane)),
                "ready_edges": len(self.frontier(lane))}

    def merge(self, other):
        """Merge a compatible fragment in place; duplicate facts are no-ops."""
        if not isinstance(other, FrontierGraph):
            raise TypeError("expected FrontierGraph")
        # Validate before mutating, so a conflict cannot leave a partial merge.
        for current, incoming in ((self.nodes, other.nodes),
                                  (self.edges, other.edges),
                                  (self.evidence, other.evidence)):
            for key, item in incoming.items():
                if key in current and current[key] != item:
                    raise ValueError(f"conflicting fact for {key}")
        combined_nodes = self.nodes.keys() | other.nodes.keys()
        combined_edges = self.edges.keys() | other.edges.keys()
        for edge in other.edges.values():
            if edge["source"] not in combined_nodes or edge["target"] not in combined_nodes:
                raise ValueError("merged edge has missing endpoint")
        for item in other.evidence.values():
            if item["edge"] not in combined_edges:
                raise ValueError("merged evidence has missing edge")
        for nodes in other.entrypoints.values():
            if not nodes <= combined_nodes:
                raise ValueError("merged entrypoint has missing node")
        self.nodes.update(other.nodes)
        self.edges.update(other.edges)
        self.evidence.update(other.evidence)
        for lane, nodes in other.entrypoints.items():
            self.entrypoints.setdefault(lane, set()).update(nodes)
        return self

    def to_dict(self):
        return {"kind": KIND, "schema": SCHEMA, "acceptance": False,
                "nodes": [self.nodes[key] for key in sorted(self.nodes)],
                "edges": [self.edges[key] for key in sorted(self.edges)],
                "entrypoints": {lane: sorted(nodes)
                                for lane, nodes in sorted(self.entrypoints.items())},
                "evidence": [self.evidence[key] for key in sorted(self.evidence)]}

    @classmethod
    def from_dict(cls, document):
        if not isinstance(document, dict) or set(document) != {
                "kind", "schema", "acceptance", "nodes", "edges",
                "entrypoints", "evidence"}:
            raise ValueError("invalid frontier document")
        if document["kind"] != KIND or document["schema"] != SCHEMA or \
                document["acceptance"] is not False:
            raise ValueError("unsupported frontier schema")
        graph = cls()
        for key in ("nodes", "edges", "evidence"):
            if not isinstance(document[key], list):
                raise ValueError(f"{key} must be a list")
        if not isinstance(document["entrypoints"], dict):
            raise ValueError("entrypoints must be an object")
        for item in document["nodes"]:
            if not isinstance(item, dict) or set(item) != {"id", "kind", "label", "metadata"}:
                raise ValueError("invalid node")
            graph.add_node(item["id"], item["kind"], label=item["label"],
                           metadata=item["metadata"])
        for item in document["edges"]:
            if not isinstance(item, dict) or set(item) != {
                    "id", "source", "target", "kind", "priority", "metadata",
                    "source_variant", "source_pointer", "required_capabilities"}:
                raise ValueError("invalid edge")
            graph.add_edge(item["id"], item["source"], item["target"],
                           item["kind"], priority=item["priority"],
                           source_variant=item["source_variant"],
                           source_pointer=item["source_pointer"],
                           required_capabilities=item["required_capabilities"],
                           metadata=item["metadata"])
        for lane, nodes in document["entrypoints"].items():
            if not isinstance(nodes, list):
                raise ValueError("entrypoint lane must contain a list")
            for node in nodes:
                graph.add_entrypoint(lane, node)
        for item in document["evidence"]:
            if not isinstance(item, dict) or set(item) != {
                    "id", "edge", "lane", "outcome", "pointer", "reason",
                    "notes"}:
                raise ValueError("invalid evidence")
            graph.record(item["id"], item["edge"], item["lane"],
                         item["outcome"], item["pointer"],
                         reason=item["reason"], notes=item["notes"])
        return graph

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path):
        """Atomically replace one snapshot. Merge fragments before saving."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                             prefix=f".{path.name}.", suffix=".tmp",
                                             delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(self.to_dict(), stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
