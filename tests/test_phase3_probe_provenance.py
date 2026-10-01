from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.probe_n64recomp_cpu as cpu_probe
from scripts.analyze_phase3_overlays import validate_phase3_evidence
from scripts.probe_n64recomp_cpu import (
    tracked_cpu_fragment,
    validate_public_cpu_aggregate,
    verify_tracked_cpu_fragment,
)


ROOT = Path(__file__).resolve().parents[1]


class CpuProbeProvenanceTests(unittest.TestCase):
    @staticmethod
    def create_source_repository(path: Path) -> str:
        path.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=path, check=True)
        (path / "fixture.txt").write_text("synthetic\n", encoding="utf-8")
        subprocess.run(["git", "add", "fixture.txt"], cwd=path, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=TK22-26 Automation",
                "-c",
                "user.email=automation@users.noreply.github.com",
                "commit",
                "--quiet",
                "-m",
                "synthetic fixture",
            ],
            cwd=path,
            check=True,
        )
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def test_pinned_source_commit_uses_the_real_repository_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            head = self.create_source_repository(source)

            with mock.patch.object(cpu_probe, "EXPECTED_N64RECOMP_COMMIT", head):
                self.assertEqual(cpu_probe.pinned_source_commit(source), head)
                (source / "fixture.txt").write_text("tracked mutation\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "tracked changes"):
                    cpu_probe.pinned_source_commit(source)
            with mock.patch.object(cpu_probe, "EXPECTED_N64RECOMP_COMMIT", "0" * 40):
                with self.assertRaisesRegex(ValueError, "pinned commit"):
                    cpu_probe.pinned_source_commit(source)

    def test_probe_input_verification_binds_every_local_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rom = root / "supported.rom"
            elf = root / "phase1.elf"
            executable = root / "recompiler"
            source = root / "source"
            rom.write_bytes(b"synthetic-rom")
            elf.write_bytes(b"synthetic-elf")
            executable.write_bytes(b"synthetic-executable")
            source_commit = self.create_source_repository(source)

            rom_sha1 = hashlib.sha1(rom.read_bytes()).hexdigest()
            elf_sha256 = hashlib.sha256(elf.read_bytes()).hexdigest()
            executable_sha256 = hashlib.sha256(executable.read_bytes()).hexdigest()
            patches = (
                mock.patch.object(cpu_probe, "EXPECTED_ROM_SIZE", rom.stat().st_size),
                mock.patch.object(cpu_probe, "EXPECTED_ROM_SHA1", rom_sha1),
                mock.patch.object(cpu_probe, "EXPECTED_ELF_SHA256", elf_sha256),
                mock.patch.object(
                    cpu_probe, "EXPECTED_N64RECOMP_SHA256", executable_sha256
                ),
                mock.patch.object(
                    cpu_probe, "EXPECTED_N64RECOMP_COMMIT", source_commit
                ),
            )
            for patch in patches:
                patch.start()
                self.addCleanup(patch.stop)

            verified = cpu_probe.verify_probe_inputs(
                executable,
                elf,
                rom,
                source,
                executable_sha256,
            )
            self.assertEqual(verified["supported_rom_size"], rom.stat().st_size)
            self.assertEqual(verified["supported_rom_sha1"], rom_sha1)
            self.assertEqual(verified["elf_sha256"], elf_sha256)
            self.assertEqual(
                verified["n64recomp_executable_sha256"], executable_sha256
            )
            self.assertEqual(
                verified["n64recomp_identity_methods"],
                ["source-commit", "executable-sha256"],
            )

            with self.assertRaisesRegex(ValueError, "pinned build"):
                cpu_probe.verify_probe_inputs(
                    executable,
                    elf,
                    rom,
                    source,
                    "0" * 64,
                )

    def test_probe_input_verification_rejects_unreadable_executable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rom = root / "supported.rom"
            elf = root / "phase1.elf"
            missing = root / "missing-recompiler"
            source = root / "source"
            rom.write_bytes(b"synthetic-rom")
            elf.write_bytes(b"synthetic-elf")
            source_commit = self.create_source_repository(source)
            with mock.patch.object(cpu_probe, "EXPECTED_ROM_SIZE", rom.stat().st_size), mock.patch.object(
                cpu_probe, "EXPECTED_ROM_SHA1", hashlib.sha1(rom.read_bytes()).hexdigest()
            ), mock.patch.object(
                cpu_probe, "EXPECTED_ELF_SHA256", hashlib.sha256(elf.read_bytes()).hexdigest()
            ), mock.patch.object(
                cpu_probe, "EXPECTED_N64RECOMP_COMMIT", source_commit
            ):
                with self.assertRaises(OSError):
                    cpu_probe.verify_probe_inputs(
                        missing,
                        elf,
                        rom,
                        source,
                        "0" * 64,
                    )

    def test_every_public_evidence_leaf_is_bound_to_the_reviewed_pin(self) -> None:
        evidence = json.loads(
            (ROOT / "docs/feasibility/phase3-cpu-overlay-evidence.json").read_text(
                encoding="utf-8"
            )
        )

        def leaves(value: object, path: tuple[object, ...] = ()):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield from leaves(child, (*path, key))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    yield from leaves(child, (*path, index))
            else:
                yield path, value

        for path, original in leaves(evidence):
            with self.subTest(path="/".join(map(str, path))):
                mutated = copy.deepcopy(evidence)
                parent = mutated
                for component in path[:-1]:
                    parent = parent[component]
                if type(original) is bool:
                    replacement = not original
                elif type(original) is int:
                    replacement = original + 1
                elif isinstance(original, str):
                    replacement = f"{original}-mutated"
                else:
                    self.fail(f"unhandled evidence primitive at {path}: {type(original)}")
                parent[path[-1]] = replacement
                with self.assertRaises((KeyError, TypeError, ValueError)):
                    validate_phase3_evidence(mutated)

    def test_cpu_probe_has_a_closed_exact_transform_to_tracked_evidence(self) -> None:
        evidence = json.loads(
            (ROOT / "docs/feasibility/phase3-cpu-overlay-evidence.json").read_text(
                encoding="utf-8"
            )
        )
        inputs = evidence["inputs"]
        cpu = evidence["cpu"]
        functions = cpu["functions"]
        data = cpu["data"]
        context = cpu["context_dump"]
        generation = cpu["conservative_generation_probe"]
        aggregate = {
            "schema_version": 1,
            "kind": "jfg-phase3-cpu-probe-aggregate",
            "privacy": "public-safe-aggregate-only",
            "input_verification": {
                "supported_rom_size": inputs["supported_rom_size"],
                "supported_rom_sha1": inputs["supported_rom_sha1"],
                "elf_sha256": inputs["elf_sha256"],
                "n64recomp_source_commit": evidence["pins"]["n64recomp"],
                "n64recomp_executable_sha256": inputs[
                    "n64recomp_executable_sha256"
                ],
                "n64recomp_identity_methods": inputs[
                    "n64recomp_identity_methods"
                ],
            },
            "elf_sha256": inputs["elf_sha256"],
            "boot_entry_probe": {
                "private_input_supplied": cpu["boot_entry_probe"][
                    "private_input_supplied"
                ],
                "elf_header_entry_present": cpu["boot_entry_probe"][
                    "elf_header_entry_present"
                ],
                "n64recomp_direct_probe_passed": cpu["boot_entry_probe"][
                    "direct_n64recomp_probe_passed"
                ],
                "manual_fallback_generated": cpu["boot_entry_probe"][
                    "manual_fallback_generated"
                ],
            },
            "metadata": {
                "executable_function_symbol_count": functions[
                    "executable_symbol_count"
                ],
                "sized_function_count": functions["sized_count"],
                "zero_size_function_symbol_count": functions["zero_size_count"],
                "covered_zero_size_alias_count": functions[
                    "covered_zero_size_alias_count"
                ],
                "uncovered_zero_size_function_count": functions[
                    "uncovered_zero_size_count"
                ],
                "inferred_function_size_count": functions[
                    "inferred_size_override_count"
                ],
                "unaligned_function_address_count": functions[
                    "unaligned_address_count"
                ],
                "unaligned_function_size_count": functions["unaligned_size_count"],
                "candidate_data_symbol_count": data["candidate_symbol_count"],
                "valid_section_data_symbol_count": data[
                    "valid_section_symbol_count"
                ],
                "invalid_section_range_data_symbol_count": data[
                    "invalid_section_range_count"
                ],
                "zero_size_data_symbol_count": data["zero_size_symbol_count"],
                "conflicting_data_symbol_name_count": data[
                    "conflicting_name_count"
                ],
                "standard_elf_relocation_section_count": data[
                    "standard_elf_relocation_section_count"
                ],
                "standard_elf_relocation_entry_count": data[
                    "standard_elf_relocation_entry_count"
                ],
                "absolute_or_special_data_symbol_count": data[
                    "absolute_or_special_symbol_count"
                ],
                "invalid_data_all_zero_size": data[
                    "invalid_ranges_all_zero_size"
                ],
                "dump_executable_section_count": context[
                    "executable_section_count"
                ],
                "dump_function_count": context[
                    "function_count_after_size_overrides"
                ],
                "dump_data_section_count": context["data_section_count"],
                "dump_data_symbol_count": context[
                    "data_symbol_count_after_size_overrides"
                ],
            },
            "recompilation": {
                "placeholder_jal_site_count": generation[
                    "placeholder_jal_site_count"
                ],
                "placeholder_function_count": generation[
                    "placeholder_function_count"
                ],
                "indirect_transfer_site_count": generation[
                    "indirect_transfer_candidate_site_count"
                ],
                "indirect_transfer_function_count": generation[
                    "indirect_transfer_candidate_function_count"
                ],
                "transfer_inventory_sha256": generation[
                    "transfer_inventory_sha256"
                ],
                "additional_failed_function_count": generation[
                    "additional_missing_direct_target_function_count"
                ]
                + generation["additional_out_of_range_branch_function_count"],
                "additional_failure_kind_counts": {
                    "missing-direct-call-target": generation[
                        "additional_missing_direct_target_function_count"
                    ],
                    "out-of-range-branch": generation[
                        "additional_out_of_range_branch_function_count"
                    ],
                },
                "unavailable_stub_count": 0,
                "excluded_n64recomp_builtin_count": generation[
                    "excluded_n64recomp_builtin_count"
                ],
                "total_stubbed_function_count": generation[
                    "total_stubbed_function_count"
                ],
                "final_probe_passed": generation["final_probe_passed"],
                "final_probe_returncode": 0,
                "final_probe_crashed": False,
                "generated_c_file_count": generation["generated_c_file_count"],
            },
            "coverage_gate": copy.deepcopy(cpu["coverage_gate"]),
        }
        validate_public_cpu_aggregate(aggregate)
        expected = {
            "inputs": copy.deepcopy(inputs),
            "cpu": copy.deepcopy(cpu),
        }
        expected["inputs"].pop("initial_config_pinned_parse_passed")
        expected["cpu"].pop("unbounded_jump_table_probe")
        self.assertEqual(tracked_cpu_fragment(aggregate), expected)

        forged_aggregate = copy.deepcopy(aggregate)
        forged_evidence = copy.deepcopy(evidence)
        forged_aggregate["recompilation"]["placeholder_jal_site_count"] += 1
        forged_evidence["cpu"]["conservative_generation_probe"][
            "placeholder_jal_site_count"
        ] += 1
        with self.assertRaisesRegex(ValueError, "reviewed canonical lock"):
            verify_tracked_cpu_fragment(forged_aggregate, forged_evidence)

        unavailable_stub = copy.deepcopy(aggregate)
        unavailable_stub["recompilation"]["unavailable_stub_count"] = 1
        self.assertNotEqual(tracked_cpu_fragment(unavailable_stub), expected)

        private_channel = copy.deepcopy(aggregate)
        private_channel["metadata"]["inferred_functions"] = ["private"]
        with self.assertRaisesRegex(ValueError, "unreviewed public fields"):
            validate_public_cpu_aggregate(private_channel)

        float_count = copy.deepcopy(aggregate)
        float_count["metadata"]["dump_function_count"] = 2905.0
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            validate_public_cpu_aggregate(float_count)

        integer_boolean = copy.deepcopy(aggregate)
        integer_boolean["boot_entry_probe"]["elf_header_entry_present"] = 0
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            validate_public_cpu_aggregate(integer_boolean)

        direct_overclaim = copy.deepcopy(aggregate)
        direct_overclaim["boot_entry_probe"]["n64recomp_direct_probe_passed"] = True
        with self.assertRaisesRegex(ValueError, "current-pin baseline"):
            validate_public_cpu_aggregate(direct_overclaim)

        coverage_overclaim = copy.deepcopy(aggregate)
        coverage_overclaim["coverage_gate"][
            "all_candidate_functions_individually_classified"
        ] = True
        with self.assertRaisesRegex(ValueError, "conservative baseline"):
            validate_public_cpu_aggregate(coverage_overclaim)

        chunked_digest = copy.deepcopy(aggregate)
        chunked_digest["recompilation"]["transfer_inventory_sha256"] = (
            ("a" * 64) + " " + ("b" * 64)
        )
        with self.assertRaisesRegex(ValueError, "digest is malformed"):
            validate_public_cpu_aggregate(chunked_digest)

        oversized_count = copy.deepcopy(aggregate)
        oversized_count["metadata"]["dump_function_count"] = 10**30
        with self.assertRaisesRegex(ValueError, "public aggregate limit"):
            validate_public_cpu_aggregate(oversized_count)


if __name__ == "__main__":
    unittest.main()
