from __future__ import annotations

import unittest

from scripts.doctor import (
    PHASE1_LINUX_PROBES,
    PHASE1_WSL_DISTRIBUTIONS,
    phase1_linux_dependency_failures,
    windows_phase1_dependency_failures,
)


class Phase1LinuxDependencyTests(unittest.TestCase):
    def test_all_required_commands_and_venv_are_probed(self) -> None:
        commands: list[list[str]] = []

        def succeeds(command: list[str]) -> bool:
            commands.append(command)
            return True

        failures = phase1_linux_dependency_failures(
            "fixture-linux",
            runner=succeeds,
        )

        self.assertEqual(failures, [])
        self.assertEqual(len(commands), len(PHASE1_LINUX_PROBES))
        executables = {command[0] for command in commands}
        self.assertTrue(
            {
                "git",
                "make",
                "gcc",
                "pkg-config",
                "wget",
                "readelf",
                "mips-linux-gnu-as",
                "mips-linux-gnu-ld",
                "mips-linux-gnu-objcopy",
                "python3",
            }.issubset(executables)
        )
        venv_command = next(command for command in commands if command[0] == "python3")
        self.assertEqual(venv_command[1], "-c")
        self.assertIn("EnvBuilder(with_pip=True)", venv_command[2])

    def test_missing_linux_dependency_is_named(self) -> None:
        failures = phase1_linux_dependency_failures(
            "fixture-linux",
            runner=lambda command: command[0] != "mips-linux-gnu-ld",
        )

        self.assertEqual(
            failures,
            ["fixture-linux: MIPS linker is missing or unusable"],
        )

    def test_wsl_prefix_is_applied_to_every_linux_probe(self) -> None:
        commands: list[list[str]] = []
        prefix = ("wsl", "--distribution", "fixture", "--exec")

        failures = phase1_linux_dependency_failures(
            "fixture",
            prefix=prefix,
            runner=lambda command: commands.append(command) is None,
        )

        self.assertEqual(failures, [])
        self.assertTrue(all(tuple(command[: len(prefix)]) == prefix for command in commands))


class Phase1WindowsWslTests(unittest.TestCase):
    def test_both_required_distributions_and_their_tools_are_probed(self) -> None:
        commands: list[list[str]] = []

        def succeeds(command: list[str]) -> bool:
            commands.append(command)
            return True

        failures = windows_phase1_dependency_failures(runner=succeeds)

        self.assertEqual(failures, [])
        for distribution in PHASE1_WSL_DISTRIBUTIONS:
            prefix = ["wsl", "--distribution", distribution, "--exec"]
            self.assertIn([*prefix, "sh", "-lc", "true"], commands)
            self.assertIn([*prefix, "mips-linux-gnu-ld", "--version"], commands)
            self.assertTrue(
                any(
                    command[: len(prefix) + 1] == [*prefix, "python3"]
                    for command in commands
                )
            )

    def test_missing_distribution_is_reported_without_noisy_tool_failures(self) -> None:
        missing = PHASE1_WSL_DISTRIBUTIONS[0]

        def fails_one_distribution(command: list[str]) -> bool:
            return not (
                command[:4] == ["wsl", "--distribution", missing, "--exec"]
                and command[4:] == ["sh", "-lc", "true"]
            )

        failures = windows_phase1_dependency_failures(runner=fails_one_distribution)

        self.assertEqual(
            [failure for failure in failures if failure.startswith(f"{missing}:")],
            [f"{missing}: required WSL distribution is missing or unusable"],
        )

    def test_unavailable_wsl_stops_before_distribution_probes(self) -> None:
        commands: list[list[str]] = []

        def unavailable(command: list[str]) -> bool:
            commands.append(command)
            return False

        failures = windows_phase1_dependency_failures(runner=unavailable)

        self.assertEqual(failures, ["WSL2 is not enabled or ready"])
        self.assertEqual(commands, [["wsl", "--status"]])


if __name__ == "__main__":
    unittest.main()
