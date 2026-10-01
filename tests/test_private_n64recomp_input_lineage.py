from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import prepare_n64recomp_context_dump as context_dump
from scripts import transform_private_n64recomp_inputs as transform


class ContextDumpConfigTests(unittest.TestCase):
    def test_config_uses_only_elf_derived_size_overrides(self) -> None:
        elf = Path("input.elf")
        generated = Path("private-generated")
        metadata = {
            "executable_function_symbol_count": 9,
            "uncovered_zero_size_function_count": 2,
        }
        inferred = [
            ("first", ".text", 0x1000, 0x20),
            ("second", ".text", 0x1020, 0x10),
        ]
        with (
            mock.patch.object(
                context_dump,
                "readelf",
                return_value="header",
            ),
            mock.patch.object(
                context_dump,
                "parse_header",
                return_value={
                    "class": "ELF32",
                    "endianness": "big",
                    "machine": "MIPS",
                    "type": "EXEC",
                },
            ),
            mock.patch.object(
                context_dump,
                "function_metadata",
                return_value=(metadata, inferred, {}),
            ),
            mock.patch.object(
                context_dump,
                "render_config",
                return_value="closed-config\n",
            ) as render,
        ):
            rendered, counts = context_dump.build_context_dump_config(elf, generated)

        self.assertEqual(rendered, "closed-config\n")
        self.assertEqual(
            counts,
            {
                "executable_function_symbols": 9,
                "inferred_size_overrides": 2,
                "uncovered_zero_size_functions": 2,
            },
        )
        render.assert_called_once_with(
            elf,
            generated.resolve(),
            function_sizes=[("first", 0x20), ("second", 0x10)],
        )

    def test_config_rejects_wrong_elf_shape(self) -> None:
        with (
            mock.patch.object(context_dump, "readelf", return_value="header"),
            mock.patch.object(
                context_dump,
                "parse_header",
                return_value={
                    "class": "ELF64",
                    "endianness": "little",
                    "machine": "x86-64",
                    "type": "DYN",
                },
            ),
        ):
            with self.assertRaisesRegex(ValueError, "ELF32 big-endian MIPS"):
                context_dump.build_context_dump_config(
                    Path("input.elf"),
                    Path("private-generated"),
                )

    def test_config_rejects_unclosed_zero_size_derivation(self) -> None:
        metadata = {
            "executable_function_symbol_count": 2,
            "uncovered_zero_size_function_count": 2,
        }
        with (
            mock.patch.object(context_dump, "readelf", return_value="header"),
            mock.patch.object(
                context_dump,
                "parse_header",
                return_value={
                    "class": "ELF32",
                    "endianness": "big",
                    "machine": "MIPS",
                    "type": "EXEC",
                },
            ),
            mock.patch.object(
                context_dump,
                "function_metadata",
                return_value=(metadata, [("only", ".text", 0x1000, 4)], {}),
            ),
            mock.patch.object(context_dump, "render_config", return_value="config"),
        ):
            with self.assertRaisesRegex(ValueError, "did not close"):
                context_dump.build_context_dump_config(
                    Path("input.elf"),
                    Path("private-generated"),
                )

    def test_cli_rejects_trackable_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            elf = root / "input.elf"
            elf.write_bytes(b"elf")
            with (
                mock.patch.object(
                    context_dump,
                    "verify_private_work_directory",
                    side_effect=ValueError("not ignored"),
                ),
                mock.patch(
                    "sys.argv",
                    [
                        "prepare_n64recomp_context_dump.py",
                        "--elf",
                        str(elf),
                        "--generated-output",
                        str(root / "generated"),
                        "--output-config",
                        str(root / "context.toml"),
                    ],
                ),
            ):
                self.assertEqual(context_dump.main(), 2)
            self.assertFalse((root / "context.toml").exists())


class PrivateInputTransformTests(unittest.TestCase):
    def test_main_bss_size_is_derived_from_the_authoritative_data_context(self) -> None:
        layout = transform.Layout(0, 0, 0, 0, 0x100, 0x80)
        self.assertEqual(
            transform.derive_main_bss_size(
                {"section": [{"name": "main_bss", "vram": 0x800011C0, "size": 0x240}]},
                0x80001000,
                layout,
                0x40,
            ),
            0x240,
        )

    def test_main_bss_size_rejects_unclosed_or_invalid_extents(self) -> None:
        layout = transform.Layout(0, 0, 0, 0, 0x100, 0x80)
        with self.assertRaisesRegex(ValueError, "context is not unique"):
            transform.derive_main_bss_size({"section": []}, 0x80001000, layout, 0x40)
        with self.assertRaisesRegex(ValueError, "context is not unique"):
            transform.derive_main_bss_size(
                {
                    "section": [
                        {"name": "main_bss", "vram": 0x800011C0, "size": 0x40},
                        {"name": "other_bss", "vram": 0x800011C0, "size": 0x40},
                    ]
                },
                0x80001000,
                layout,
                0x40,
            )
        with self.assertRaisesRegex(ValueError, "context is invalid"):
            transform.derive_main_bss_size(
                {"section": [{"name": "main_data", "vram": 0x800011C0, "size": 0x40}]},
                0x80001000,
                layout,
                0x40,
            )
        with self.assertRaisesRegex(ValueError, "BSS extent is invalid"):
            transform.derive_main_bss_size(
                {"section": [{"name": "main_bss", "vram": 0x800011C0, "size": 0x241}]},
                0x80001000,
                layout,
                0x40,
            )
        with self.assertRaisesRegex(ValueError, "BSS extent is invalid"):
            transform.derive_main_bss_size(
                {"section": [{"name": "main_bss", "vram": 0x807FF180, "size": 0x1000}]},
                0x807FF000,
                layout,
                0,
            )
        with self.assertRaisesRegex(ValueError, "runtime extent is invalid"):
            transform.derive_main_bss_size({"section": []}, 0x80001001, layout, 0x40)
        with self.assertRaisesRegex(ValueError, "runtime extent is invalid"):
            transform.derive_main_bss_size({"section": []}, 0x1000, layout, 0x40)
        with self.assertRaisesRegex(ValueError, "context is invalid"):
            transform.derive_main_bss_size(
                {"section": [{"name": "main_bss", "vram": 0x800011C0, "size": "576"}]},
                0x80001000,
                layout,
                0x40,
            )

    def test_explicit_relative_target_never_reclassified_by_address(self) -> None:
        sections = [
            {"vram": 0x1000, "relocation_size": 0x5000},
            {"vram": 0x2000, "relocation_size": 0x1000},
        ]
        self.assertEqual(
            transform.resolve_relative_target(sections, 0, 0x2000),
            (0, 0x2000, 0x3000),
        )

    def test_word_reader_rejects_unaligned_and_out_of_bounds_access(self) -> None:
        data = bytes(range(16))
        with self.assertRaisesRegex(ValueError, "out of bounds or unaligned"):
            transform.read_word(data, 1)
        with self.assertRaisesRegex(ValueError, "out of bounds or unaligned"):
            transform.read_word(data, 16)


if __name__ == "__main__":
    unittest.main()
