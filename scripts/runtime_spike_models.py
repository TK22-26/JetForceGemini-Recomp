#!/usr/bin/env python3
"""Synthetic, ROM-free contracts for Phase 3 native-runtime fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Callable, Iterable


class GapModelError(RuntimeError):
    """Base class for a rejected synthetic runtime operation."""


class UnmappedAddress(GapModelError):
    """Raised when an address has no approved translation."""


class UnknownRegister(GapModelError):
    """Raised when direct-register access is not allowlisted."""


class DmaBoundsError(GapModelError):
    """Raised when a synthetic DMA transfer leaves either buffer."""


class SaveDeviceError(GapModelError):
    """Raised when a synthetic save-device operation is invalid."""


class TrapInventoryError(GapModelError):
    """Raised when a trap site is missing, duplicated, or unclassified."""


class TrapAbort(GapModelError):
    """Raised when an inventoried trap has a fail-closed disposition."""


@dataclass(frozen=True)
class AddressMapping:
    virtual_start: int
    physical_start: int
    size: int

    def __post_init__(self) -> None:
        if self.virtual_start < 0 or self.physical_start < 0 or self.size <= 0:
            raise ValueError("address mappings require nonnegative starts and positive size")
        if (
            self.virtual_start + self.size > 0x1_0000_0000
            or self.physical_start + self.size > 0x1_0000_0000
        ):
            raise ValueError("address mapping exceeds the 32-bit guest address space")


class AddressTranslator:
    """Translate direct-mapped aliases plus explicit synthetic TLB ranges."""

    KSEG0_START = 0x80000000
    KSEG1_START = 0xA0000000
    KSEG2_START = 0xC0000000
    DIRECT_PHYSICAL_MASK = 0x1FFFFFFF

    def __init__(self, mappings: Iterable[AddressMapping] = ()) -> None:
        self._mappings = tuple(mappings)
        ordered = sorted(
            self._mappings,
            key=lambda item: (item.virtual_start, item.virtual_start + item.size),
        )
        for mapping in ordered:
            mapping_end = mapping.virtual_start + mapping.size
            if (
                mapping.virtual_start < self.KSEG2_START
                and self.KSEG0_START < mapping_end
            ):
                raise ValueError(
                    "explicit address mapping overlaps a direct-mapped KSEG window"
                )
        for left, right in zip(ordered, ordered[1:]):
            if right.virtual_start < left.virtual_start + left.size:
                raise ValueError("explicit address mappings overlap")

    def to_physical(self, address: int) -> int:
        if self.KSEG0_START <= address < self.KSEG2_START:
            return address & self.DIRECT_PHYSICAL_MASK
        for mapping in self._mappings:
            if mapping.virtual_start <= address < mapping.virtual_start + mapping.size:
                return mapping.physical_start + address - mapping.virtual_start
        raise UnmappedAddress("address is outside direct aliases and explicit mappings")


class RegisterBroker:
    """Fail-closed broker keyed by project-owned opaque register IDs."""

    def __init__(self, register_ids: Iterable[str]) -> None:
        ids = tuple(register_ids)
        if len(ids) != len(set(ids)) or not ids:
            raise ValueError("register IDs must be a nonempty unique set")
        self._values = {register_id: 0 for register_id in ids}

    def read(self, register_id: str) -> int:
        try:
            return self._values[register_id]
        except KeyError as error:
            raise UnknownRegister("direct-register read is not allowlisted") from error

    def write(self, register_id: str, value: int) -> None:
        if register_id not in self._values:
            raise UnknownRegister("direct-register write is not allowlisted")
        self._values[register_id] = value & 0xFFFFFFFF


class CacheCoherencyGate:
    """Require an explicit host invalidation after each synthetic code write."""

    def __init__(self) -> None:
        self._write_counts: dict[str, int] = {}
        self._invalidation_counts: dict[str, int] = {}

    def record_code_write(self, region_id: str) -> int:
        if not region_id:
            raise ValueError("region ID must not be empty")
        version = self._write_counts.get(region_id, 0) + 1
        self._write_counts[region_id] = version
        return version

    def record_host_invalidation(self, region_id: str) -> int:
        write_count = self._write_counts.get(region_id, 0)
        invalidation_count = self._invalidation_counts.get(region_id, 0)
        if invalidation_count >= write_count:
            raise GapModelError("host invalidation does not match a pending code write")
        invalidation_count += 1
        self._invalidation_counts[region_id] = invalidation_count
        return invalidation_count

    def require_coherent(self) -> None:
        if any(
            self._invalidation_counts.get(region_id, 0) != write_count
            for region_id, write_count in self._write_counts.items()
        ):
            raise GapModelError("code writes remain without host invalidation")


class BoundedDmaBroker:
    """Copy synthetic bytes with strict bounds and one completion event."""

    @staticmethod
    def copy(
        source: bytes,
        target: bytearray,
        *,
        source_offset: int,
        target_offset: int,
        length: int,
        completions: list[str],
        completion_id: str,
    ) -> None:
        if source_offset < 0 or target_offset < 0 or length < 0:
            raise DmaBoundsError("DMA offsets and length must be nonnegative")
        if source_offset + length > len(source) or target_offset + length > len(target):
            raise DmaBoundsError("DMA transfer exceeds a synthetic buffer")
        if not completion_id:
            raise ValueError("completion ID must not be empty")
        target[target_offset : target_offset + length] = source[
            source_offset : source_offset + length
        ]
        completions.append(completion_id)


class DecompressionGateway:
    """Bound an independently supplied decompressor callback."""

    def __init__(self, *, max_input_bytes: int, max_output_bytes: int) -> None:
        if max_input_bytes <= 0 or max_output_bytes <= 0:
            raise ValueError("maximum input and output sizes must be positive")
        self._max_input_bytes = max_input_bytes
        self._max_output_bytes = max_output_bytes
        self._handler: Callable[[bytes], bytes] | None = None

    def register(self, handler: Callable[[bytes], bytes]) -> None:
        self._handler = handler

    def decompress(self, payload: bytes) -> bytes:
        if not isinstance(payload, bytes):
            raise GapModelError("decompression input is not a byte string")
        if len(payload) > self._max_input_bytes:
            raise GapModelError("decompression input exceeds the configured bound")
        if self._handler is None:
            raise GapModelError("no decompression callback is registered")
        result = self._handler(payload)
        if not isinstance(result, bytes):
            raise GapModelError("decompression callback returned a non-byte result")
        if len(result) > self._max_output_bytes:
            raise GapModelError("decompression output exceeds the configured bound")
        return result


class SyntheticControllerPak:
    """Logical note store; it intentionally models no proprietary disk format."""

    def __init__(self, *, capacity_bytes: int, max_notes: int) -> None:
        if capacity_bytes <= 0 or max_notes <= 0:
            raise ValueError("capacity and note count must be positive")
        self._capacity_bytes = capacity_bytes
        self._max_notes = max_notes
        self._notes: dict[str, bytearray] = {}

    @property
    def free_bytes(self) -> int:
        return self._capacity_bytes - sum(len(note) for note in self._notes.values())

    def allocate(self, note_id: str, size: int) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", note_id):
            raise SaveDeviceError("note ID is not a project-owned opaque identifier")
        if note_id in self._notes:
            raise SaveDeviceError("note already exists")
        if size <= 0 or size > self.free_bytes or len(self._notes) >= self._max_notes:
            raise SaveDeviceError("note cannot be allocated")
        self._notes[note_id] = bytearray(size)

    def delete(self, note_id: str) -> None:
        if self._notes.pop(note_id, None) is None:
            raise SaveDeviceError("note does not exist")

    def write(self, note_id: str, offset: int, data: bytes) -> None:
        note = self._get_note(note_id)
        if not isinstance(data, bytes):
            raise SaveDeviceError("note write data must be a byte string")
        if offset < 0 or offset + len(data) > len(note):
            raise SaveDeviceError("write exceeds note bounds")
        note[offset : offset + len(data)] = data

    def read(self, note_id: str, offset: int, length: int) -> bytes:
        note = self._get_note(note_id)
        if offset < 0 or length < 0 or offset + length > len(note):
            raise SaveDeviceError("read exceeds note bounds")
        return bytes(note[offset : offset + length])

    def enumerate_notes(self) -> tuple[tuple[str, int], ...]:
        """Return deterministic opaque IDs and sizes without exposing note bodies."""
        return tuple(
            (note_id, len(note))
            for note_id, note in sorted(self._notes.items())
        )

    def export_logical_snapshot(self) -> tuple[tuple[str, bytes], ...]:
        """Export independently authored logical state, not a native Pak format."""
        return tuple(
            (note_id, bytes(note))
            for note_id, note in sorted(self._notes.items())
        )

    @classmethod
    def from_logical_snapshot(
        cls,
        snapshot: tuple[tuple[str, bytes], ...],
        *,
        capacity_bytes: int,
        max_notes: int,
    ) -> SyntheticControllerPak:
        """Reload a bounded logical snapshot into a fresh synthetic store."""
        if not isinstance(snapshot, tuple) or len(snapshot) > max_notes:
            raise SaveDeviceError("logical snapshot has an invalid note collection")
        device = cls(capacity_bytes=capacity_bytes, max_notes=max_notes)
        for record in snapshot:
            if not isinstance(record, tuple) or len(record) != 2:
                raise SaveDeviceError("logical snapshot note record is malformed")
            note_id, body = record
            if not isinstance(note_id, str) or not isinstance(body, bytes):
                raise SaveDeviceError("logical snapshot note record has invalid types")
            device.allocate(note_id, len(body))
            device.write(note_id, 0, body)
        return device

    def _get_note(self, note_id: str) -> bytearray:
        try:
            return self._notes[note_id]
        except KeyError as error:
            raise SaveDeviceError("note does not exist") from error


@dataclass(frozen=True)
class TrapRecord:
    trap_id: str
    kind: str
    disposition: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", self.trap_id):
            raise ValueError("trap ID must be a project-owned opaque identifier")
        if self.kind not in {
            "cpu-break",
            "cpu-syscall",
            "switch-bounds",
            "boot-self-check",
        }:
            raise ValueError("trap kind is not recognized")
        if self.disposition not in {
            "abort",
            "emulate",
            "defer-to-reviewed-handler",
        }:
            raise ValueError("trap disposition is not recognized")


class TrapInventory:
    """Require explicit classification and fail closed on unknown trap IDs."""

    def __init__(self, records: Iterable[TrapRecord]) -> None:
        self._records: dict[str, TrapRecord] = {}
        for record in records:
            if record.trap_id in self._records:
                raise TrapInventoryError("duplicate trap ID")
            self._records[record.trap_id] = record

    def require_kinds(self, required_kinds: Iterable[str]) -> None:
        observed = {record.kind for record in self._records.values()}
        missing = set(required_kinds) - observed
        if missing:
            raise TrapInventoryError("one or more required trap kinds are missing")

    def dispatch(
        self,
        trap_id: str,
        *,
        reviewed_handler: Callable[[str], None] | None = None,
    ) -> str:
        try:
            record = self._records[trap_id]
        except KeyError as error:
            raise TrapInventoryError("unknown trap ID") from error
        if record.disposition == "abort":
            raise TrapAbort("inventoried trap is configured to abort")
        if record.disposition == "defer-to-reviewed-handler":
            if reviewed_handler is None:
                raise TrapInventoryError(
                    "deferred trap has no explicitly supplied reviewed handler"
                )
            reviewed_handler(trap_id)
        return record.disposition


@dataclass(frozen=True)
class FallbackContractBinding:
    """Bind a public contract ID to its executable model and ROM-free test."""

    implementation: type[object]
    test_id: str


FALLBACK_CONTRACT_REGISTRY = MappingProxyType(
    {
        "strict-register-broker": FallbackContractBinding(
            RegisterBroker, "unknown-register-fails-closed"
        ),
        "central-address-translator": FallbackContractBinding(
            AddressTranslator, "kseg-alias-translation"
        ),
        "explicit-static-mappings": FallbackContractBinding(
            AddressTranslator, "explicit-tlb-mapping"
        ),
        "host-code-coherency-gate": FallbackContractBinding(
            CacheCoherencyGate, "cache-coherency-gate"
        ),
        "bounded-dma-broker": FallbackContractBinding(
            BoundedDmaBroker, "bounded-dma-copy"
        ),
        "bounded-decompression-callback": FallbackContractBinding(
            DecompressionGateway, "decompressor-callback-boundary"
        ),
        "native-controller-pak-layer": FallbackContractBinding(
            SyntheticControllerPak, "synthetic-controller-pak-lifecycle"
        ),
        "strict-trap-manifest": FallbackContractBinding(
            TrapInventory, "trap-inventory-completeness"
        ),
    }
)

TESTED_FALLBACK_TESTS = frozenset(
    binding.test_id for binding in FALLBACK_CONTRACT_REGISTRY.values()
)
