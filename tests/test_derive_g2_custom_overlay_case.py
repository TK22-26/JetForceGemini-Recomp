from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "derive_g2_custom_overlay_case.py"
spec = importlib.util.spec_from_file_location("derive_custom", SCRIPT)
assert spec and spec.loader
derive = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = derive
spec.loader.exec_module(derive)


class DerivedCustomOverlaySuiteTests(unittest.TestCase):
    def private_root(self) -> tempfile.TemporaryDirectory[str]:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(prefix="g2-custom-derive-", dir=tools)

    @staticmethod
    def record(symbol: int, site: int, patch: int, source: int) -> bytes:
        return struct.pack(">II", symbol, (site << 8) | (patch << 4) | source)

    def inputs(
        self,
        root: Path,
        *,
        r32: tuple[int, int] | None = (5, 0),
        section_order: tuple[int, ...] = (1, 2, 3, 4, 5),
    ) -> tuple[Path, Path, Path, Path, Path]:
        """Build a ROM-free five-overlay suite.

        Slot 1 is a real provider.  Slots 2 and 5 are alternate static
        candidates; slot 5 has more records and therefore wins the exact
        minimum-subject selection.  Slot 3 provides jump + non-adjacent
        HI/LO self binding; slot 4 provides an external provider LO binding.
        No single subject contains all four relocation classes.
        """
        header_count = 5
        header_bytes = header_count * derive.HEADER.size
        layout = {
            "schema_version": 1,
            "main_relocation_start": 0,
            "overlay_reference_table_start": 12,
            "overlay_table_start": 24,
            "overlay_data_start": 24 + header_bytes,
            "main_text_size": 16,
            "main_data_size": 16,
        }
        (root / "layout.json").write_text(json.dumps(layout), encoding="utf-8")
        # [static, self (slot 3), provider (slot 1)]
        ort = struct.pack(">III", 0x00000011, 0x00300022, 0x00100033)
        provider = (16, 0, b"", bytes(16))
        alternate = (16, 8, self.record(0, 0, 2, 0) + self.record(0, 0, 6, 3), bytes(24))
        self_subject = (
            16,
            0,
            b"".join((
                self.record(0, 0, 4, 2),
                self.record(1, 4, 5, 0),
                self.record(1, 12, 6, 0),
            )),
            # HI=1 / LO=-2 is a non-adjacent pair with a precise addend.
            struct.pack(">I", 0) + struct.pack(">I", 1) + bytes(4) + struct.pack(">I", 0xFFFE),
        )
        provider_subject = (16, 0, self.record(2, 4, 6, 0), bytes(16))
        preferred = (
            16,
            8,
            b"".join((
                self.record(0, 0, 2, 0),
                self.record(0, 4, 2, 0),
                # Full-word patches may target initialized data even when the
                # source class is the ordinary external form.
                self.record(0, 20, 2, 0),
                self.record(0, 0, 6, 3),
            )),
            bytes(24),
        )
        modules = [provider, alternate, self_subject, provider_subject, preferred]
        offsets: list[int] = []
        cursor = 0
        for text, data, records, image in modules:
            offsets.append(cursor)
            cursor += len(image) + len(records)
        rom = bytearray(layout["overlay_data_start"] + cursor)
        rom[12:24] = ort
        for index, ((text, data, records, image), offset) in enumerate(zip(modules, offsets), 1):
            header = struct.pack(">iiiiiHHii", -0x80000000 + index * 0x1000, offset, text, data, 0, len(records), 0, -1, -1)
            begin = layout["overlay_table_start"] + (index - 1) * derive.HEADER.size
            rom[begin : begin + derive.HEADER.size] = header
            image_start = layout["overlay_data_start"] + offset
            rom[image_start : image_start + len(image)] = image
            rom[image_start + len(image) : image_start + len(image) + len(records)] = records
        rom_path = root / "input.rom"
        rom_path.write_bytes(rom)
        generated = root / "generated"
        generated.mkdir()
        (generated / "sources.json").write_text(json.dumps({"version": 2, "normalizer_revision_sha256": "0" * 64}), encoding="utf-8")
        runtime = {
            "schema_version": 1,
            "sections": [
                {
                    "section": 0,
                    "module": 0,
                    "kind": "main",
                    "rom": 0,
                    "linked_vram": 0x80000000,
                    "text_offset": 4,
                    "text_size": 64,
                    "data_size": 64,
                    "bss_size": 64,
                },
                *[
                    {
                        # The runtime table's section index is an ABI index,
                        # rather than the raw overlay-table module number.
                        "section": section_index,
                        "module": module_number,
                        "kind": "overlay",
                        "rom": 0,
                        "linked_vram": 0x80000000 + module_number * 0x1000,
                        "text_offset": 0,
                        "text_size": modules[module_number - 1][0],
                        "data_size": modules[module_number - 1][1],
                        "bss_size": 0,
                    }
                    for section_index, module_number in enumerate(section_order, 1)
                ],
            ],
            "r_mips_32": [] if r32 is None else [{
                "source_section": r32[0],
                "source_type": 0,
                "site_offset": r32[1],
                "target_class": "local-offset",
                "target_section": 0,
                "target_section_offset": 0x11,
            }],
        }
        runtime_path = root / "runtime.json"
        runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
        function_plan = root / "function-plan.json"
        function_plan.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "commitment_salt": bytes(range(32)).hex(),
                    "modules": [
                        {
                            "section": section["section"],
                            "function_offset": 0,
                            "context_seed": "zero",
                        }
                        for section in runtime["sections"]
                        if section["kind"] == "overlay"
                    ],
                }
            ),
            encoding="utf-8",
        )
        binding = hashlib.sha256(
            json.dumps(
                runtime,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()
        (generated / "runtime-manifest.canonical.sha256").write_bytes(
            (binding + "\n").encode("ascii")
        )
        return rom_path, root / "layout.json", generated, runtime_path, function_plan

    @staticmethod
    def unpack(payload: bytes) -> tuple[
        list[tuple[int, int, int, int, int, int, int, bytes]],
        list[
            tuple[
                int,
                list[tuple[int, int]],
                list[tuple[int, int, int, int, int]],
                list[tuple[int, int, int, int]],
            ]
        ],
    ]:
        assert payload[:8] == derive.MAGIC
        (
            version,
            subjects,
            module_count,
            _guest,
            static_size,
            _static_bss,
            _token,
            _commitment_salt,
            _function_plan_digest,
        ) = derive.SUITE_HEADER.unpack_from(payload, 8)
        assert version == 3
        cursor = 8 + derive.SUITE_HEADER.size + static_size
        modules = []
        for _ in range(module_count):
            token, slot, base, text, reserved, size, function, seed = (
                derive.MODULE_HEADER.unpack_from(payload, cursor)
            )
            cursor += derive.MODULE_HEADER.size
            image = payload[cursor : cursor + size]
            cursor += size
            modules.append((slot, base, text, reserved, size, function, seed, image))
        cases = []
        for _ in range(subjects):
            slot, r32_count = derive.SUBJECT_HEADER.unpack_from(payload, cursor)
            cursor += derive.SUBJECT_HEADER.size
            r32 = [struct.unpack_from("<IB3x", payload, cursor + index * 8) for index in range(r32_count)]
            cursor += r32_count * 8
            count = struct.unpack_from("<I", payload, cursor)[0]
            cursor += 4
            records = [derive.CUSTOM.unpack_from(payload, cursor + index * derive.CUSTOM.size) for index in range(count)]
            cursor += count * derive.CUSTOM.size
            binding_count = struct.unpack_from("<I", payload, cursor)[0]
            cursor += 4
            bindings = [derive.BINDING.unpack_from(payload, cursor + index * derive.BINDING.size) for index in range(binding_count)]
            cursor += binding_count * derive.BINDING.size
            cases.append((slot, r32, records, bindings))
        assert cursor == len(payload)
        return modules, cases

    def test_multimodule_fallback_is_exact_and_preserves_binding_classes(self) -> None:
        with self.private_root() as temp:
            payload, sidecar = derive.derive(*self.inputs(Path(temp)))
        self.assertEqual(struct.unpack_from("<I", payload, 8)[0], 3)
        modules, cases = self.unpack(payload)
        self.assertEqual([slot for slot, *_ in cases], [1, 5, 3, 4])
        self.assertEqual({slot for slot, *_ in modules}, {1, 3, 4, 5})
        self.assertTrue(all(module[5:7] == (0, 0) for module in modules))
        records = [record for _slot, _r32, group, _bindings in cases for record in group]
        self.assertEqual({record[2] for record in records}, derive.VALID_PATCHES)
        self.assertEqual(
            sum(len(r32) for _slot, r32, _records, _bindings in cases),
            1,
        )
        self.assertEqual(sidecar["subject_module_count"], 4)
        self.assertEqual(sidecar["custom_relocation_class_counts"], {"full-word": 2, "jump-target": 1, "hi16": 1, "lo16": 3})
        self.assertEqual(sidecar["binding_class_counts"], {"static": 1, "self": 1, "provider": 1})
        bindings = [binding for _slot, _r32, _records, group in cases for binding in group]
        self.assertIn((3, 0x33, derive.PROVIDER_BINDING, 1), bindings)
        self.assertIn((2, 0x22, derive.SELF_BINDING, 0), bindings)
        self.assertIn((1, 0x11, derive.STATIC_BINDING, 0), bindings)
        # The HI/LO relocation records are adjacent in the authoritative table
        # but intentionally use non-adjacent instruction locations.
        self.assertIn((4, 0, 5, 2, 65534), records)
        self.assertIn((12, 0, 6, 2, 65534), records)
        self.assertEqual(derive._addend(0x80000004, 1, 2), 4)
        self.assertEqual(sidecar["case_commitment_sha256"], hashlib.sha256(payload).hexdigest())
        encoded_sidecar = json.dumps(sidecar)
        self.assertNotIn("observation", encoded_sidecar)
        self.assertNotIn("function_offset", encoded_sidecar)
        self.assertNotIn("context_seed", encoded_sidecar)
        self.assertNotIn("commitment_salt", encoded_sidecar)
        self.assertNotIn(bytes(range(32)).hex(), encoded_sidecar)

    def test_static_initialized_image_and_bss_are_exactly_manifest_bound(self) -> None:
        with self.private_root() as temp:
            root = Path(temp)
            rom, layout, generated, runtime, plan = self.inputs(root)
            raw = rom.read_bytes()
            plan_bytes = plan.read_bytes()
            manifest = json.loads(runtime.read_text(encoding="utf-8"))
            payload, _sidecar = derive.derive(
                rom, layout, generated, runtime, plan
            )
        (
            _version,
            _subjects,
            _modules,
            _guest,
            static_size,
            static_bss,
            _token,
            salt,
            function_plan_digest,
        ) = derive.SUITE_HEADER.unpack_from(payload, 8)
        main = manifest["sections"][0]
        expected_size = (
            main["text_offset"] + main["text_size"] + main["data_size"]
        )
        self.assertEqual(static_size, expected_size)
        self.assertEqual(static_bss, main["bss_size"])
        start = 8 + derive.SUITE_HEADER.size
        self.assertEqual(
            payload[start : start + static_size],
            raw[main["rom"] : main["rom"] + expected_size],
        )
        self.assertEqual(salt, bytes(range(32)))
        self.assertEqual(function_plan_digest, hashlib.sha256(plan_bytes).digest())

    def test_private_salt_blinds_public_case_commitment(self) -> None:
        with self.private_root() as temp:
            root = Path(temp)
            inputs = self.inputs(root)
            first, first_sidecar = derive.derive(*inputs)
            plan = inputs[-1]
            document = json.loads(plan.read_text(encoding="utf-8"))
            document["commitment_salt"] = bytes(range(32, 64)).hex()
            plan.write_text(json.dumps(document), encoding="utf-8")
            second, second_sidecar = derive.derive(*inputs)
        self.assertNotEqual(first, second)
        self.assertNotEqual(
            first_sidecar["case_commitment_sha256"],
            second_sidecar["case_commitment_sha256"],
        )
        self.assertNotIn("commitment_salt", json.dumps(first_sidecar))
        self.assertNotIn("commitment_salt", json.dumps(second_sidecar))

    def test_exact_function_plan_file_bytes_are_privately_bound(self) -> None:
        with self.private_root() as temp:
            root = Path(temp)
            inputs = self.inputs(root)
            first, _first_sidecar = derive.derive(*inputs)
            plan = inputs[-1]
            document = json.loads(plan.read_text(encoding="utf-8"))
            plan.write_text(
                json.dumps(document, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            second, _second_sidecar = derive.derive(*inputs)
        self.assertNotEqual(first, second)
        first_header = list(derive.SUITE_HEADER.unpack_from(first, 8))
        second_header = list(derive.SUITE_HEADER.unpack_from(second, 8))
        self.assertEqual(first_header[:-1], second_header[:-1])
        self.assertNotEqual(first_header[-1], second_header[-1])

    def test_selection_is_deterministic_and_prefers_fewer_then_more_records(self) -> None:
        with self.private_root() as temp:
            inputs = self.inputs(Path(temp))
            first, first_sidecar = derive.derive(*inputs)
            second, second_sidecar = derive.derive(*inputs)
        self.assertEqual(first, second)
        self.assertEqual(first_sidecar, second_sidecar)
        _modules, cases = self.unpack(first)
        # Slot 5 replaces the smaller slot-2 static candidate without growing
        # the final subject closure, because it has more relocation records.
        self.assertNotIn(2, [slot for slot, *_ in cases])
        self.assertIn(5, [slot for slot, *_ in cases])

    def test_current_v3_normalized_root_manifest_is_accepted(self) -> None:
        with self.private_root() as temp:
            inputs = self.inputs(Path(temp))
            generated = inputs[2]
            source_manifest = json.loads(
                (generated / "sources.json").read_text(encoding="utf-8")
            )
            source_manifest["version"] = 3
            (generated / "sources.json").write_text(
                json.dumps(source_manifest), encoding="utf-8"
            )
            payload, _sidecar = derive.derive(*inputs)
        self.assertTrue(payload.startswith(derive.MAGIC))

    def test_generated_r32_is_translated_from_exact_full_word_record(self) -> None:
        with self.private_root() as temp:
            payload, sidecar = derive.derive(*self.inputs(Path(temp), r32=(5, 0)))
        _modules, cases = self.unpack(payload)
        preferred = next(case for case in cases if case[0] == 5)
        _slot, r32, custom, _bindings = preferred
        self.assertEqual(r32, [(0, 0)])
        self.assertNotIn(0, [record[0] for record in custom])
        self.assertEqual(sidecar["custom_relocation_class_counts"]["full-word"], 2)
        self.assertTrue(sidecar["contains_generated_r32"])

    def test_packed_slots_use_generated_section_indices_not_raw_module_ids(self) -> None:
        # The raw ROM modules retain their table slots, while the generated ABI
        # intentionally puts them in a different section order.
        with self.private_root() as temp:
            payload, _sidecar = derive.derive(*self.inputs(
                Path(temp), section_order=(5, 3, 1, 4, 2),
            ))
        modules, cases = self.unpack(payload)
        self.assertEqual({slot for slot, *_ in modules}, {2, 3, 4, 5})
        self.assertEqual([slot for slot, *_ in cases], [3, 5, 2, 4])
        # The provider binding is raw module 1 in the ROM, but section 3 in
        # the packed ABI because module 1 is the third generated section.
        bindings = [binding for _slot, _r32, _records, group in cases for binding in group]
        self.assertIn((3, 0x33, derive.PROVIDER_BINDING, 3), bindings)

    def test_r32_dependency_closure_is_transitive_even_without_custom_bindings(self) -> None:
        def candidate(slot: int, dependencies: tuple[int, ...]) -> derive.Candidate:
            return derive.Candidate(
                derive.Header(slot, 0x80000000 + slot * 0x1000, 0, 4, 0, 0, 0, 0),
                slot + 10,
                bytes(4),
                (0,),
                (),
                (),
                dependencies,
                1,
            )

        first = candidate(1, (2,))
        second = candidate(2, (3,))
        third = candidate(3, ())
        closure = derive._selection_closure(
            (first,), {1: first, 2: second, 3: third},
        )
        self.assertEqual([item.header.slot for item in closure], [1, 2, 3])
        self.assertTrue(derive._selection_is_acyclic(closure))
        cycle_first = candidate(1, (2,))
        cycle_second = candidate(2, (1,))
        cycle = derive._selection_closure(
            (cycle_first,), {1: cycle_first, 2: cycle_second},
        )
        self.assertFalse(derive._selection_is_acyclic(cycle))

    def test_geometry_reserves_uninitialized_bss_before_next_module(self) -> None:
        with self.private_root() as temp:
            root = Path(temp)
            rom, layout, generated, runtime, plan = self.inputs(root)
            raw = bytearray(rom.read_bytes())
            document = json.loads(layout.read_text(encoding="utf-8"))
            # Slot 1 is in the selected closure.  Give it two pages of BSS;
            # its next selected module must not overlap that reserved memory.
            header_offset = document["overlay_table_start"]
            struct.pack_into(">i", raw, header_offset + 16, 0x2000)
            rom.write_bytes(raw)
            payload, _sidecar = derive.derive(rom, layout, generated, runtime, plan)
        modules, _cases = self.unpack(payload)
        bases = {slot: base for slot, base, *_rest in modules}
        self.assertEqual(bases[1], 0x80010000)
        self.assertEqual(bases[3], 0x80013000)

    def test_geometry_starts_after_the_complete_static_mapping(self) -> None:
        with self.private_root() as temp:
            root = Path(temp)
            rom, layout, generated, runtime, plan = self.inputs(root)
            manifest = json.loads(runtime.read_text(encoding="utf-8"))
            manifest["sections"][0]["text_size"] = 0x24000
            runtime.write_text(json.dumps(manifest), encoding="utf-8")
            rebound = hashlib.sha256(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            (generated / "runtime-manifest.canonical.sha256").write_bytes(
                (rebound + "\n").encode("ascii")
            )
            raw = bytearray(rom.read_bytes())
            required = (
                manifest["sections"][0]["rom"]
                + manifest["sections"][0]["text_offset"]
                + manifest["sections"][0]["text_size"]
                + manifest["sections"][0]["data_size"]
            )
            raw.extend(bytes(max(0, required - len(raw))))
            rom.write_bytes(raw)
            payload, _sidecar = derive.derive(rom, layout, generated, runtime, plan)
        modules, _cases = self.unpack(payload)
        first_base = min(base for _slot, base, *_rest in modules)
        static = manifest["sections"][0]
        static_end = (
            static["linked_vram"]
            + static["text_offset"]
            + static["text_size"]
            + static["data_size"]
            + static["bss_size"]
        )
        self.assertGreaterEqual(first_base, static_end)
        self.assertEqual(first_base & 0xFFF, 0)

    def test_missing_exact_static_image_fails_closed(self) -> None:
        with self.private_root() as temp:
            root = Path(temp)
            rom, layout, generated, runtime, plan = self.inputs(root)
            manifest = json.loads(runtime.read_text(encoding="utf-8"))
            manifest["sections"][0]["rom"] = len(rom.read_bytes())
            runtime.write_text(json.dumps(manifest), encoding="utf-8")
            rebound = hashlib.sha256(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            (generated / "runtime-manifest.canonical.sha256").write_bytes(
                (rebound + "\n").encode("ascii")
            )
            with self.assertRaisesRegex(
                derive.DerivationError, "static initialized image"
            ):
                derive.derive(rom, layout, generated, runtime, plan)

    def test_zero_main_bss_fails_closed(self) -> None:
        with self.private_root() as temp:
            root = Path(temp)
            rom, layout, generated, runtime, plan = self.inputs(root)
            manifest = json.loads(runtime.read_text(encoding="utf-8"))
            manifest["sections"][0]["bss_size"] = 0
            runtime.write_text(json.dumps(manifest), encoding="utf-8")
            rebound = hashlib.sha256(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            (generated / "runtime-manifest.canonical.sha256").write_bytes(
                (rebound + "\n").encode("ascii")
            )
            with self.assertRaisesRegex(
                derive.DerivationError, "static initialized image"
            ):
                derive.derive(rom, layout, generated, runtime, plan)

    def test_main_mapping_beyond_eight_mib_fails_closed(self) -> None:
        with self.private_root() as temp:
            root = Path(temp)
            rom, layout, generated, runtime, plan = self.inputs(root)
            manifest = json.loads(runtime.read_text(encoding="utf-8"))
            manifest["sections"][0]["bss_size"] = 9 * 1024 * 1024
            runtime.write_text(json.dumps(manifest), encoding="utf-8")
            rebound = hashlib.sha256(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            (generated / "runtime-manifest.canonical.sha256").write_bytes(
                (rebound + "\n").encode("ascii")
            )
            with self.assertRaisesRegex(
                derive.DerivationError, "suite guest geometry"
            ):
                derive.derive(rom, layout, generated, runtime, plan)

    def test_selection_state_cap_fails_closed(self) -> None:
        with self.private_root() as temp:
            inputs = self.inputs(Path(temp))
            with mock.patch.object(derive, "MAX_SELECTION_STATES", 1):
                with self.assertRaisesRegex(derive.DerivationError, "state cap"):
                    derive.derive(*inputs)

    def test_reviewed_function_plan_rejects_missing_invalid_and_pass_fields(self) -> None:
        mutations = (
            ("missing-salt", lambda document: document.pop("commitment_salt")),
            (
                "zero-salt",
                lambda document: document.__setitem__("commitment_salt", "00" * 32),
            ),
            (
                "low-entropy-salt",
                lambda document: document.__setitem__("commitment_salt", "01" * 32),
            ),
            ("missing", lambda document: document["modules"].clear()),
            (
                "invalid-offset",
                lambda document: document["modules"][0].__setitem__(
                    "function_offset", 3
                ),
            ),
            (
                "pass-field",
                lambda document: document["modules"][0].__setitem__(
                    "expected_pass", True
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label), self.private_root() as temp:
                inputs = self.inputs(Path(temp))
                plan = inputs[-1]
                document = json.loads(plan.read_text(encoding="utf-8"))
                mutate(document)
                plan.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaisesRegex(
                    derive.DerivationError, "generated-body|reviewed"
                ):
                    derive.derive(*inputs)

    def test_malformed_selected_tables_and_r32_collisions_fail_closed(self) -> None:
        with self.private_root() as temp:
            with self.assertRaisesRegex(derive.DerivationError, "suite|unavailable"):
                derive.derive(*self.inputs(Path(temp), r32=None))
        with self.private_root() as temp:
            root = Path(temp)
            rom, layout, generated, runtime, plan = self.inputs(root, r32=(3, 0))
            with self.assertRaisesRegex(derive.DerivationError, "suite|unavailable"):
                derive.derive(rom, layout, generated, runtime, plan)
        with self.private_root() as temp:
            root = Path(temp)
            rom, layout, generated, runtime, plan = self.inputs(root, r32=(5, 0))
            manifest = json.loads(runtime.read_text(encoding="utf-8"))
            manifest["r_mips_32"].append(dict(manifest["r_mips_32"][0]))
            runtime.write_text(json.dumps(manifest), encoding="utf-8")
            rebound = hashlib.sha256(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            (generated / "runtime-manifest.canonical.sha256").write_bytes(
                (rebound + "\n").encode("ascii")
            )
            with self.assertRaisesRegex(derive.DerivationError, "duplicate R32"):
                derive.derive(rom, layout, generated, runtime, plan)
        with self.private_root() as temp:
            root = Path(temp)
            rom, layout, generated, runtime, plan = self.inputs(root)
            manifest = json.loads(runtime.read_text(encoding="utf-8"))
            manifest["r_mips_32"][0]["source_type"] = 1
            runtime.write_text(json.dumps(manifest), encoding="utf-8")
            rebound = hashlib.sha256(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            (generated / "runtime-manifest.canonical.sha256").write_bytes(
                (rebound + "\n").encode("ascii")
            )
            with self.assertRaisesRegex(derive.DerivationError, "suite|unavailable"):
                derive.derive(rom, layout, generated, runtime, plan)
        for label, slot, table_byte, replacement in (
            ("bad-hi-lo", 3, 2 * 8 + 6, 0x40),
            ("unknown-source", 4, 7, 0x29),
        ):
            with self.private_root() as temp:
                root = Path(temp)
                rom, layout, generated, runtime, plan = self.inputs(root)
                document = json.loads(layout.read_text(encoding="utf-8"))
                raw = bytearray(rom.read_bytes())
                header_offset = document["overlay_table_start"] + (slot - 1) * derive.HEADER.size
                _vram, offset, text, data, _bss, _primary, _secondary, _init, _resume = derive.HEADER.unpack_from(raw, header_offset)
                table_start = document["overlay_data_start"] + offset + text + data
                raw[table_start + table_byte] = replacement
                rom.write_bytes(raw)
                with self.subTest(label=label):
                    with self.assertRaises(derive.DerivationError):
                        derive.derive(rom, layout, generated, runtime, plan)

    def test_output_and_private_path_boundaries_fail_closed(self) -> None:
        with self.private_root() as temp:
            root = Path(temp)
            payload, sidecar = derive.derive(*self.inputs(root))
            out = root / "case.bin"
            safe = root / "safe.json"
            derive._new_output(out, payload)
            derive._new_output(safe, json.dumps(sidecar).encode())
            with self.assertRaises(derive.DerivationError):
                derive._new_output(out, payload)
            tracked = root / "outside.json"
            tracked.write_text("{}", encoding="utf-8")
            if hasattr(os, "symlink"):
                link = root / "link.json"
                try:
                    os.symlink(tracked, link)
                except OSError:
                    with mock.patch.object(derive.Path, "is_symlink", return_value=True):
                        with self.assertRaises(derive.DerivationError):
                            derive._file(tracked)
                        with self.assertRaises(derive.DerivationError):
                            derive._new_output(root / "blocked.bin", payload)
                else:
                    with self.assertRaises(derive.DerivationError):
                        derive._file(link)
                    with tempfile.TemporaryDirectory(prefix="g2-output-redirection-") as outside_temp:
                        redirect = root / "redirect"
                        try:
                            os.symlink(Path(outside_temp), redirect, target_is_directory=True)
                        except OSError:
                            pass
                        else:
                            with self.assertRaises(derive.DerivationError):
                                derive._new_output(redirect / "leak.bin", payload)


if __name__ == "__main__":
    unittest.main()
