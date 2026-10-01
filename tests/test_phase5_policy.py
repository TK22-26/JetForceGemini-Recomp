"""Phase 5 policy tests.

Discharges the master-plan obligation "private corpus cannot be uploaded by
CI" and pins the Phase 5 config artifacts required by
docs/planning/phase5-acceptance.md.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PRIVATE_CORPUS_PREFIXES = ("corpus/private/", "captures/private/")


def _load_gitignore_lines() -> list[str]:
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


class PrivateCorpusStaysLocal(unittest.TestCase):
    def test_gitignore_covers_private_corpus_trees(self) -> None:
        lines = _load_gitignore_lines()
        for required in ("/corpus/private/", "/captures/private/"):
            self.assertIn(required, lines)

    def test_no_private_corpus_file_is_tracked(self) -> None:
        for prefix in PRIVATE_CORPUS_PREFIXES:
            tree = REPO_ROOT / Path(prefix)
            if tree.exists():
                # Existing locally is fine; being tracked is not.  A tracked
                # file would survive a clean checkout, so assert the git
                # index knows nothing under the prefix.
                import subprocess

                listing = subprocess.run(
                    ["git", "ls-files", "--", prefix],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertEqual(listing.stdout.strip(), "")

    def test_ci_workflows_never_upload_private_corpus(self) -> None:
        workflows = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertTrue(workflows)
        for workflow in workflows:
            text = workflow.read_text(encoding="utf-8")
            for prefix in PRIVATE_CORPUS_PREFIXES:
                self.assertNotIn(
                    prefix,
                    text,
                    msg=f"{workflow.name} references {prefix}",
                )
            # Every artifact-upload step must name explicit paths, and none
            # of them may be a corpus/captures tree or a wildcard that could
            # swallow one.
            for match in re.finditer(
                r"uses:\s*actions/upload-artifact[^\n]*\n(?:.*\n)*?\s*path:\s*(.+)",
                text,
            ):
                uploaded = match.group(1).strip()
                self.assertNotIn("corpus", uploaded, msg=workflow.name)
                self.assertNotIn("captures", uploaded, msg=workflow.name)
                self.assertFalse(
                    uploaded in {".", "./", "**", "**/*"},
                    msg=f"{workflow.name} uploads an unbounded path",
                )


class PinnedPhase5Configs(unittest.TestCase):
    def test_state_hash_schema_is_pinned_v0(self) -> None:
        schema = json.loads(
            (REPO_ROOT / "config" / "state-hash-schema-v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(schema["version"], 1)
        self.assertEqual(schema["page_bytes"], 4096)
        self.assertTrue(schema["include_context"])
        # Kernel v0: no exclusions are approved.  Adding one is a new
        # human-approved revision, which must update this test knowingly.
        self.assertEqual(schema["exclusions"], [])
        self.assertEqual(schema["approval"]["owner_role"], "project-owner")

    def test_divergence_tolerance_is_exact(self) -> None:
        policy = json.loads(
            (REPO_ROOT / "config" / "divergence-tolerance-v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(policy["version"], 1)
        deterministic = policy["deterministic_mode"]
        self.assertEqual(
            deterministic["rdram_tolerated_byte_differences"], 0
        )
        self.assertEqual(
            deterministic["context_tolerated_slot_differences"], 0
        )
        self.assertEqual(
            deterministic["journal_tolerated_byte_differences"], 0
        )
        self.assertEqual(deterministic["checkpoint_hash_tolerance"], "exact")


class Phase5CompletionManifest(unittest.TestCase):
    def test_signing_policy_is_pinned(self) -> None:
        policy = json.loads(
            (REPO_ROOT / "config" / "phase5-completion-signing.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(policy["kind"], "jfg-phase5-completion-signing-policy")
        self.assertEqual(policy["namespace"], "jfg-phase5-completion-v1")
        self.assertEqual(policy["algorithm"], "openssh-ed25519")
        self.assertEqual(
            policy["public_key_file"], "phase4-completion-signing-key.pub"
        )

    def test_tracked_completion_manifest_verifies(self) -> None:
        manifest = REPO_ROOT / "evidence" / "phase5-completion.json"
        if not manifest.exists():
            self.skipTest("Phase 5 completion manifest not yet produced")
        from scripts.build_phase5_completion_manifest import verify

        self.assertEqual(verify(manifest), [])


if __name__ == "__main__":
    unittest.main()
