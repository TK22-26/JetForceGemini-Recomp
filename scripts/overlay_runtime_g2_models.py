#!/usr/bin/env python3
"""ROM-free overlay lifecycle and trap-classification contract models.

These models deliberately stop at the Phase 4/feasibility boundary.  They make
ordering, invalidation, replay, and classification rules executable without
claiming that a real target overlay or trap path has run through the native
runtime.  Detailed target coordinates and trace bodies never enter this file.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
import re
from typing import Callable, Iterable, Mapping

if __package__:
    from .analyze_phase3_overlays import (
        ActiveOverlay,
        ActiveOverlayRegistry,
        OverlayPointer,
    )
    from .runtime_spike_models import TrapInventory, TrapRecord
else:
    from analyze_phase3_overlays import (
        ActiveOverlay,
        ActiveOverlayRegistry,
        OverlayPointer,
    )
    from runtime_spike_models import TrapInventory, TrapRecord


OPAQUE_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")

RELOCATION_CLASSES = (
    "full-word",
    "jump-target",
    "hi16",
    "lo16",
)
LIFECYCLE_EVENT_KINDS = (
    "load_begin",
    "copy_complete",
    "bss_cleared",
    "relocation_applied",
    "instruction_cache_invalidated",
    "module_published",
    "callback_enter",
    "callback_complete",
    "lookup",
    "unpublish",
    "external_invalidated",
    "unload_complete",
    "external_rebound",
    "stale_pointer_rejected",
    "reload_verified",
)
TRAP_KINDS = (
    "cpu-break",
    "cpu-syscall",
    "switch-bounds",
    "boot-self-check",
    "dangling-jump-workaround",
    "checksum",
    "anti-tamper",
)
RUNTIME_DISPATCH_KINDS = frozenset(
    {"cpu-break", "cpu-syscall", "switch-bounds", "boot-self-check"}
)
TRAP_DISPOSITIONS = (
    "abort",
    "emulate",
    "defer-to-reviewed-handler",
    "not-applicable",
)
TRAP_REACHABILITY = ("unclassified", "reachable", "unreachable")
TRACE_SOURCES = (
    "synthetic",
    "private-static-reviewed",
    "private-oracle",
    "private-native",
)
ESTIMATE_CLASSES = ("small", "medium", "large", "architecture-change")


class OverlayLifecycleError(RuntimeError):
    """Raised when the lifecycle or scheduler boundary fails closed."""


class TrapClassificationError(RuntimeError):
    """Raised when the trap denominator or classification is incomplete."""


def _require_opaque_id(value: str, label: str) -> None:
    if not isinstance(value, str) or OPAQUE_ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a project-owned opaque identifier")


def _require_digest(value: str, label: str) -> None:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a SHA-256 digest")
    if len(set(value)) == 1:
        raise ValueError(f"{label} must not be an obvious placeholder")


def _canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class OverlayModuleSpec:
    """Public-safe description of one synthetic populated overlay.

    Addresses and source symbols are intentionally absent.  Export and
    reference IDs are project-owned opaque labels used only by the contract
    harness.
    """

    overlay_id: str
    text_size: int
    data_size: int
    bss_size: int
    relocation_counts: Mapping[str, int]
    exports: Mapping[str, int]
    external_references: Mapping[str, tuple[str, str]]
    callback_kind: str
    semantic_seed_sha256: str

    def __post_init__(self) -> None:
        _require_opaque_id(self.overlay_id, "overlay ID")
        if type(self.text_size) is not int or not 0 < self.text_size <= 0xFFFFFFFF:
            raise ValueError("overlay text size must be a positive 32-bit extent")
        if self.text_size % 4 != 0:
            raise ValueError("overlay text size must be word-aligned")
        for extent, label in (
            (self.data_size, "data"),
            (self.bss_size, "BSS"),
        ):
            if type(extent) is not int or not 0 <= extent <= 0xFFFFFFFF:
                raise ValueError(
                    f"overlay {label} size must be a non-negative 32-bit extent"
                )
            if extent % 4 != 0:
                raise ValueError(f"overlay {label} size must be word-aligned")
        if self.memory_size > 0xFFFFFFFF:
            raise ValueError("overlay text, data, and BSS extents exceed 32-bit bounds")

        relocations = dict(self.relocation_counts)
        if tuple(sorted(relocations)) != tuple(sorted(RELOCATION_CLASSES)):
            raise ValueError("relocation counts must cover the exact supported classes")
        if any(
            type(value) is not int or not 0 <= value <= 0xFFFFFFFF
            for value in relocations.values()
        ):
            raise ValueError("relocation counts must be bounded non-negative integers")

        exports = dict(self.exports)
        if not exports:
            raise ValueError("a populated lifecycle fixture needs at least one export")
        for export_id, offset in exports.items():
            _require_opaque_id(export_id, "export ID")
            if type(offset) is not int or offset < 0 or offset % 4 != 0:
                raise ValueError("export offsets must be non-negative and word-aligned")
            if offset >= self.text_size:
                raise ValueError("export offset is outside overlay text")

        references = dict(self.external_references)
        for reference_id, target in references.items():
            _require_opaque_id(reference_id, "reference ID")
            if not isinstance(target, tuple) or len(target) != 2:
                raise ValueError("external reference target must be an overlay/export pair")
            _require_opaque_id(target[0], "target overlay ID")
            _require_opaque_id(target[1], "target export ID")
            if target[0] == self.overlay_id:
                raise ValueError("self references are local relocations, not external references")

        if self.callback_kind not in {"none", "initialize", "resume"}:
            raise ValueError("callback kind is not recognized")
        _require_digest(self.semantic_seed_sha256, "semantic seed")

        object.__setattr__(self, "relocation_counts", MappingProxyType(relocations))
        object.__setattr__(self, "exports", MappingProxyType(exports))
        object.__setattr__(
            self,
            "external_references",
            MappingProxyType(references),
        )

    def semantic_digest(self) -> str:
        """Digest state that must remain identical across same-input reloads."""

        return _canonical_digest(
            {
                "overlay_id": self.overlay_id,
                "text_size": self.text_size,
                "data_size": self.data_size,
                "bss_size": self.bss_size,
                "relocation_counts": dict(self.relocation_counts),
                "exports": dict(self.exports),
                "external_references": {
                    key: list(value)
                    for key, value in sorted(self.external_references.items())
                },
                "callback_kind": self.callback_kind,
                "semantic_seed_sha256": self.semantic_seed_sha256,
            }
        )

    @property
    def memory_size(self) -> int:
        return self.text_size + self.data_size + self.bss_size


@dataclass(frozen=True)
class LifecycleEvent:
    sequence: int
    operation_token: int
    kind: str
    overlay_id: str
    generation: int
    status: str
    relocation_class: str | None = None

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence <= 0:
            raise ValueError("event sequence must be positive")
        if type(self.operation_token) is not int or self.operation_token <= 0:
            raise ValueError("operation token must be positive")
        if self.kind not in LIFECYCLE_EVENT_KINDS:
            raise ValueError("lifecycle event kind is not recognized")
        _require_opaque_id(self.overlay_id, "event overlay ID")
        if type(self.generation) is not int or self.generation <= 0:
            raise ValueError("event generation must be positive")
        _require_opaque_id(self.status, "event status")
        if self.relocation_class is not None and (
            self.relocation_class not in RELOCATION_CLASSES
        ):
            raise ValueError("event relocation class is not recognized")
        if (self.kind == "relocation_applied") != (
            self.relocation_class is not None
        ):
            raise ValueError("only relocation events carry a relocation class")

    def public_record(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "operation_token": self.operation_token,
            "kind": self.kind,
            "overlay_id": self.overlay_id,
            "generation": self.generation,
            "status": self.status,
            "relocation_class": self.relocation_class,
        }


@dataclass
class _LoadedOverlay:
    spec: OverlayModuleSpec
    active: ActiveOverlay
    semantic_state_sha256: str
    references: dict[str, OverlayPointer]


class OverlayLifecycleHarness:
    """Synchronous, caller-ordered lifecycle harness.

    The harness does not own virtual time, threads, or a production scheduler.
    A caller must provide consecutive operation tokens.  That narrow boundary
    makes ordering replayable without claiming the Phase 5 deterministic
    scheduler exists.
    """

    def __init__(self) -> None:
        self._registry = ActiveOverlayRegistry()
        self._loaded: dict[str, _LoadedOverlay] = {}
        self._last_unloaded_digest: dict[str, str] = {}
        self._last_unloaded_generation: dict[str, int] = {}
        self._events: list[LifecycleEvent] = []
        self._next_operation_token = 1
        self._callback_active = False

    @property
    def events(self) -> tuple[LifecycleEvent, ...]:
        return tuple(self._events)

    def _require_operation(self, token: int) -> None:
        if type(token) is not int or token != self._next_operation_token:
            raise OverlayLifecycleError("scheduler operation token is out of order")
        self._next_operation_token += 1

    def _reject_callback_reentry(self) -> None:
        if self._callback_active:
            raise OverlayLifecycleError("overlay lifecycle callback re-entry is forbidden")

    def _require_mapped_extent(self, spec: OverlayModuleSpec, guest_base: int) -> None:
        if (
            type(guest_base) is not int
            or not 0 <= guest_base <= 0xFFFFFFFF
            or guest_base % 4 != 0
        ):
            raise OverlayLifecycleError("overlay mapped extent is invalid")
        guest_end = guest_base + spec.memory_size
        if guest_end > 0x1_0000_0000:
            raise OverlayLifecycleError("overlay mapped extent is invalid")
        for current in self._loaded.values():
            current_start = current.active.guest_base
            current_end = current_start + current.spec.memory_size
            if guest_base < current_end and current_start < guest_end:
                raise OverlayLifecycleError("overlay mapped extents overlap")

    def _record(
        self,
        token: int,
        kind: str,
        active: ActiveOverlay,
        status: str,
        relocation_class: str | None = None,
    ) -> None:
        self._events.append(
            LifecycleEvent(
                len(self._events) + 1,
                token,
                kind,
                active.overlay_id,
                active.generation,
                status,
                relocation_class,
            )
        )

    def _export_pointer(self, overlay_id: str, export_id: str) -> OverlayPointer:
        loaded = self._loaded.get(overlay_id)
        if loaded is None:
            raise OverlayLifecycleError("external target overlay is not active")
        if export_id not in loaded.spec.exports:
            raise OverlayLifecycleError("external target export is not declared")
        offset = loaded.spec.exports[export_id]
        pointer = self._registry.resolve_address(loaded.active.guest_base + offset)
        if pointer is None:
            raise OverlayLifecycleError("active export did not resolve through the registry")
        return pointer

    def _resolved_references(self, spec: OverlayModuleSpec) -> dict[str, OverlayPointer]:
        return {
            reference_id: self._export_pointer(*target)
            for reference_id, target in spec.external_references.items()
        }

    def _rebind_dependents(self, target_overlay_id: str, token: int) -> None:
        for loaded in tuple(self._loaded.values()):
            if loaded.active.overlay_id == target_overlay_id:
                continue
            for reference_id, target in loaded.spec.external_references.items():
                if target[0] != target_overlay_id:
                    continue
                loaded.references[reference_id] = self._export_pointer(*target)
                self._record(
                    token,
                    "external_rebound",
                    loaded.active,
                    "resolved",
                )

    def _invalidate_dependents(self, target_overlay_id: str, token: int) -> None:
        for loaded in tuple(self._loaded.values()):
            if loaded.active.overlay_id == target_overlay_id:
                continue
            for reference_id, target in loaded.spec.external_references.items():
                if target[0] != target_overlay_id:
                    continue
                if loaded.references.pop(reference_id, None) is not None:
                    self._record(
                        token,
                        "external_invalidated",
                        loaded.active,
                        "fail-closed",
                    )

    def _rollback_published_load(
        self,
        loaded: _LoadedOverlay,
        token: int,
        status: str,
    ) -> None:
        self._registry.unpublish(
            loaded.active.overlay_id,
            loaded.active.generation,
        )
        self._invalidate_dependents(loaded.active.overlay_id, token)
        del self._loaded[loaded.active.overlay_id]
        self._record(token, "unpublish", loaded.active, status)
        self._record(token, "unload_complete", loaded.active, status)

    def load(
        self,
        spec: OverlayModuleSpec,
        guest_base: int,
        *,
        operation_token: int,
        callback: Callable[[str, int], None] | None = None,
    ) -> _LoadedOverlay:
        self._reject_callback_reentry()
        if spec.overlay_id in self._loaded:
            raise OverlayLifecycleError("overlay is already loaded")
        if spec.overlay_id in self._last_unloaded_digest:
            raise OverlayLifecycleError("a prior overlay lifetime must use reload")
        if spec.callback_kind == "none" and callback is not None:
            raise OverlayLifecycleError("callback supplied for an overlay without a callback")
        if spec.callback_kind != "none" and callback is None:
            raise OverlayLifecycleError("declared overlay callback is missing")

        self._require_mapped_extent(spec, guest_base)
        references = self._resolved_references(spec)
        self._require_operation(operation_token)
        active: ActiveOverlay | None = None
        try:
            active = self._registry.publish(spec.overlay_id, guest_base, spec.text_size)
        except ValueError:
            pass
        if active is None:
            raise OverlayLifecycleError("overlay publish failed")

        loaded = _LoadedOverlay(spec, active, spec.semantic_digest(), references)
        self._loaded[spec.overlay_id] = loaded
        self._record(operation_token, "load_begin", active, "accepted")
        self._record(operation_token, "copy_complete", active, "bounded")
        self._record(operation_token, "bss_cleared", active, "cleared")
        for relocation_class in RELOCATION_CLASSES:
            if spec.relocation_counts[relocation_class] > 0:
                self._record(
                    operation_token,
                    "relocation_applied",
                    active,
                    "applied",
                    relocation_class,
                )
        self._record(
            operation_token,
            "instruction_cache_invalidated",
            active,
            "invalidated",
        )
        self._record(operation_token, "module_published", active, "active")
        self._rebind_dependents(spec.overlay_id, operation_token)

        if callback is not None:
            self._record(operation_token, "callback_enter", active, spec.callback_kind)
            callback_failed = False
            self._callback_active = True
            try:
                callback(spec.overlay_id, active.generation)
            except BaseException:
                callback_failed = True
            finally:
                self._callback_active = False
            if callback_failed:
                self._rollback_published_load(loaded, operation_token, "rolled-back")
                raise OverlayLifecycleError("overlay callback failed; load rolled back")
            self._record(operation_token, "callback_complete", active, "returned")
        return loaded

    def lookup_export(
        self,
        overlay_id: str,
        export_id: str,
        *,
        operation_token: int,
    ) -> OverlayPointer:
        self._reject_callback_reentry()
        pointer = self._export_pointer(overlay_id, export_id)
        self._require_operation(operation_token)
        loaded = self._loaded[overlay_id]
        self._registry.resolve_pointer(pointer)
        self._record(operation_token, "lookup", loaded.active, "resolved")
        return pointer

    def resolve_external(
        self,
        overlay_id: str,
        reference_id: str,
        *,
        operation_token: int,
    ) -> int:
        self._reject_callback_reentry()
        loaded = self._loaded.get(overlay_id)
        if loaded is None:
            raise OverlayLifecycleError("overlay is not active")
        if reference_id not in loaded.references:
            raise OverlayLifecycleError("external reference is unresolved")
        pointer = loaded.references[reference_id]
        self._registry.resolve_pointer(pointer)
        self._require_operation(operation_token)
        self._record(operation_token, "lookup", loaded.active, "external-resolved")
        return pointer.offset

    def unload(self, overlay_id: str, *, operation_token: int) -> str:
        self._reject_callback_reentry()
        loaded = self._loaded.get(overlay_id)
        if loaded is None:
            raise OverlayLifecycleError("overlay is not active")
        self._require_operation(operation_token)
        unpublished = False
        try:
            self._registry.unpublish(overlay_id, loaded.active.generation)
            unpublished = True
        except ValueError:
            pass
        if not unpublished:
            raise OverlayLifecycleError("overlay unpublish failed")
        self._record(operation_token, "unpublish", loaded.active, "inactive")
        self._invalidate_dependents(overlay_id, operation_token)
        del self._loaded[overlay_id]
        self._last_unloaded_digest[overlay_id] = loaded.semantic_state_sha256
        self._last_unloaded_generation[overlay_id] = loaded.active.generation
        self._record(operation_token, "unload_complete", loaded.active, "cleared")
        return loaded.semantic_state_sha256

    def reload(
        self,
        spec: OverlayModuleSpec,
        guest_base: int,
        stale_pointer: OverlayPointer,
        *,
        operation_token: int,
        callback: Callable[[str, int], None] | None = None,
    ) -> _LoadedOverlay:
        self._reject_callback_reentry()
        prior_digest = self._last_unloaded_digest.get(spec.overlay_id)
        prior_generation = self._last_unloaded_generation.get(spec.overlay_id)
        if prior_digest is None:
            raise OverlayLifecycleError("overlay has no prior unloaded lifetime")
        if prior_digest != spec.semantic_digest():
            raise OverlayLifecycleError("reload semantic state differs before publication")
        if (
            not isinstance(stale_pointer, OverlayPointer)
            or stale_pointer.overlay_id != spec.overlay_id
            or stale_pointer.generation != prior_generation
            or not 0 <= stale_pointer.offset < spec.text_size
        ):
            raise OverlayLifecycleError("reload pointer does not identify the prior lifetime")
        del self._last_unloaded_digest[spec.overlay_id]
        del self._last_unloaded_generation[spec.overlay_id]
        try:
            loaded = self.load(
                spec,
                guest_base,
                operation_token=operation_token,
                callback=callback,
            )
        except BaseException:
            self._last_unloaded_digest[spec.overlay_id] = prior_digest
            assert prior_generation is not None
            self._last_unloaded_generation[spec.overlay_id] = prior_generation
            raise
        try:
            self._registry.resolve_pointer(stale_pointer)
        except ValueError:
            self._record(
                operation_token,
                "stale_pointer_rejected",
                loaded.active,
                "rejected",
            )
        else:
            self._rollback_published_load(
                loaded,
                operation_token,
                "contract-failed",
            )
            self._last_unloaded_digest[spec.overlay_id] = prior_digest
            assert prior_generation is not None
            self._last_unloaded_generation[spec.overlay_id] = prior_generation
            raise OverlayLifecycleError("stale native pointer survived overlay reload")
        self._record(operation_token, "reload_verified", loaded.active, "identical")
        return loaded

    def journal_digest(self) -> str:
        return _canonical_digest([event.public_record() for event in self._events])

    def coverage_summary(self) -> dict[str, object]:
        event_counts = Counter(event.kind for event in self._events)
        relocation_counts = Counter(
            event.relocation_class
            for event in self._events
            if event.relocation_class is not None
        )
        return {
            "event_count": len(self._events),
            "event_kind_counts": {
                key: event_counts.get(key, 0) for key in LIFECYCLE_EVENT_KINDS
            },
            "relocation_class_counts": {
                key: relocation_counts.get(key, 0) for key in RELOCATION_CLASSES
            },
            "active_overlay_count": len(self._loaded),
            "journal_sha256": self.journal_digest(),
            "synthetic_contract_only": True,
            "phase5_scheduler_provided": False,
            "g2_complete": False,
        }

    def require_closed_synthetic_scenario(self) -> None:
        summary = self.coverage_summary()
        event_counts = summary["event_kind_counts"]
        relocation_counts = summary["relocation_class_counts"]
        assert isinstance(event_counts, dict)
        assert isinstance(relocation_counts, dict)
        if any(event_counts[event] == 0 for event in LIFECYCLE_EVENT_KINDS):
            raise OverlayLifecycleError("synthetic lifecycle event coverage is incomplete")
        if any(relocation_counts[kind] == 0 for kind in RELOCATION_CLASSES):
            raise OverlayLifecycleError("synthetic relocation-class coverage is incomplete")
        if summary["active_overlay_count"] != 0:
            raise OverlayLifecycleError("synthetic lifecycle ended with active overlays")


@dataclass(frozen=True)
class TrapSiteClassification:
    """One opaque trap candidate and its reviewed classification shape."""

    site_id: str
    kind: str
    reachability: str
    disposition: str | None = None
    owner_id: str | None = None
    estimate_class: str | None = None
    behavior_evidence_sha256: str | None = None
    trace_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_opaque_id(self.site_id, "trap site ID")
        if self.kind not in TRAP_KINDS:
            raise ValueError("trap kind is not recognized")
        if self.reachability not in TRAP_REACHABILITY:
            raise ValueError("trap reachability is not recognized")
        if tuple(sorted(set(self.trace_sources))) != self.trace_sources:
            raise ValueError("trap trace sources must be sorted and unique")
        if any(source not in TRACE_SOURCES for source in self.trace_sources):
            raise ValueError("trap trace source is not recognized")

        if self.reachability == "unclassified":
            if any(
                value is not None
                for value in (
                    self.disposition,
                    self.owner_id,
                    self.estimate_class,
                    self.behavior_evidence_sha256,
                )
            ) or self.trace_sources:
                raise ValueError("unclassified traps cannot carry a disposition or evidence")
            return

        if self.disposition not in TRAP_DISPOSITIONS:
            raise ValueError("classified trap disposition is missing or invalid")
        if self.reachability == "reachable" and self.disposition == "not-applicable":
            raise ValueError("reachable trap needs a non-stub disposition")
        if self.reachability == "unreachable" and self.disposition != "not-applicable":
            raise ValueError("unreachable trap disposition must be not-applicable")
        if self.owner_id is None:
            raise ValueError("classified trap needs an owner")
        _require_opaque_id(self.owner_id, "trap owner ID")
        if self.estimate_class not in ESTIMATE_CLASSES:
            raise ValueError("classified trap needs a bounded estimate class")
        if self.behavior_evidence_sha256 is None:
            raise ValueError("classified trap needs behavior evidence")
        _require_digest(self.behavior_evidence_sha256, "trap behavior evidence")
        if not self.trace_sources:
            raise ValueError("classified trap needs at least one trace source")

    def required_private_trace_classes_declared(self) -> bool:
        sources = set(self.trace_sources)
        if self.reachability == "reachable":
            return {"private-oracle", "private-native"}.issubset(sources)
        if self.reachability == "unreachable":
            return "private-static-reviewed" in sources
        return False

    def private_record(self) -> dict[str, object]:
        return {
            "site_id": self.site_id,
            "kind": self.kind,
            "reachability": self.reachability,
            "disposition": self.disposition,
            "owner_id": self.owner_id,
            "estimate_class": self.estimate_class,
            "behavior_evidence_sha256": self.behavior_evidence_sha256,
            "trace_sources": list(self.trace_sources),
        }


class TrapClassificationLedger:
    """Close an opaque candidate denominator without exposing site details."""

    def __init__(self, candidate_counts: Mapping[str, int]) -> None:
        counts = dict(candidate_counts)
        if tuple(sorted(counts)) != tuple(sorted(TRAP_KINDS)):
            raise ValueError("trap denominator must contain the exact required kinds")
        if any(
            type(value) is not int or not 0 <= value <= 0xFFFFFFFF
            for value in counts.values()
        ):
            raise ValueError("trap candidate counts must be bounded non-negative integers")
        self._candidate_counts = MappingProxyType(counts)
        self._records: dict[str, TrapSiteClassification] = {}

    def add(self, record: TrapSiteClassification) -> None:
        if not isinstance(record, TrapSiteClassification):
            raise TrapClassificationError("trap classification record is invalid")
        if record.site_id in self._records:
            raise TrapClassificationError("duplicate opaque trap site")
        self._records[record.site_id] = record

    def _require_denominator(self) -> None:
        observed = Counter(record.kind for record in self._records.values())
        if any(observed[kind] != self._candidate_counts[kind] for kind in TRAP_KINDS):
            raise TrapClassificationError("trap classifications do not close the denominator")
        if any(record.reachability == "unclassified" for record in self._records.values()):
            raise TrapClassificationError("one or more trap sites remain unclassified")

    def summary(self) -> dict[str, object]:
        self._require_denominator()
        reachability = Counter(record.reachability for record in self._records.values())
        dispositions = Counter(
            record.disposition
            for record in self._records.values()
            if record.disposition is not None
        )
        private_trace_classes_declared = bool(self._records) and all(
            record.required_private_trace_classes_declared()
            for record in self._records.values()
        )
        private_records = [
            self._records[key].private_record() for key in sorted(self._records)
        ]
        return {
            "candidate_count": sum(self._candidate_counts.values()),
            "classified_count": len(self._records),
            "kind_counts": dict(self._candidate_counts),
            "reachability_counts": {
                key: reachability.get(key, 0) for key in TRAP_REACHABILITY
            },
            "disposition_counts": {
                key: dispositions.get(key, 0) for key in TRAP_DISPOSITIONS
            },
            "classification_sha256": _canonical_digest(private_records),
            "required_private_trace_classes_declared": private_trace_classes_declared,
            "synthetic_contract_is_g2_proof": False,
        }

    def runtime_inventory(self) -> TrapInventory:
        self._require_denominator()
        records: list[TrapRecord] = []
        for record in self._records.values():
            if record.reachability != "reachable":
                continue
            if record.kind not in RUNTIME_DISPATCH_KINDS:
                raise TrapClassificationError(
                    "reachable control-integrity path lacks a runtime-dispatch bridge"
                )
            assert record.disposition is not None
            records.append(TrapRecord(record.site_id, record.kind, record.disposition))
        inventory = TrapInventory(records)
        reachable_kinds = {record.kind for record in records}
        inventory.require_kinds(reachable_kinds)
        return inventory
