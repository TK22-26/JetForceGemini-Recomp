"""Phase 6 policy tests for the signed native-M2 completion claim."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class Phase6SigningPolicy(unittest.TestCase):
    def test_signing_policy_is_pinned(self) -> None:
        policy = json.loads(
            (REPO_ROOT / "config" / "phase6-completion-signing.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(policy["kind"], "jfg-phase6-completion-signing-policy")
        self.assertEqual(policy["namespace"], "jfg-phase6-completion-v1")
        self.assertEqual(policy["algorithm"], "openssh-ed25519")
        self.assertEqual(
            policy["public_key_file"], "phase4-completion-signing-key.pub"
        )


class Phase6ManifestIsHonest(unittest.TestCase):
    def test_manifest_verifies_and_does_not_overclaim(self) -> None:
        manifest = REPO_ROOT / "evidence" / "phase6-completion.json"
        if not manifest.exists():
            self.skipTest("Phase 6 manifest not yet produced")
        from scripts.build_phase6_completion_manifest import verify

        self.assertEqual(verify(manifest), [])
        document = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(
            document["native_boot_status"]["state"], "complete-local-m2"
        )
        self.assertFalse(document["native_boot_status"]["distribution_authorized"])
        self.assertEqual(document["kind"], "jfg-phase6-completion")


class IndependentAuthorshipRuleIsStated(unittest.TestCase):
    def test_acceptance_doc_forbids_copy_and_relabel(self) -> None:
        text = (
            REPO_ROOT / "docs" / "planning" / "phase6-acceptance.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("no copy-and-relabel", text)
        self.assertIn("black box", text)

    def test_provenance_attests_no_third_party_copy(self) -> None:
        text = (REPO_ROOT / "src" / "boot" / "PROVENANCE.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("independently authored", text)
        self.assertIn("no source from", text)

    def test_native_boot_completion_boundary_is_tracked(self) -> None:
        text = (
            REPO_ROOT / "docs" / "planning" / "phase6-native-boot-remaining.md"
        ).read_text(encoding="utf-8").lower()
        normalized = " ".join(text.split())
        self.assertIn("complete locally and signed", normalized)
        self.assertIn("beyond phase 6", text)

    def test_native_addenda_are_present_and_honest(self) -> None:
        status = (REPO_ROOT / "docs/planning/phase6-native-boot-addendum.md").read_text(encoding="utf-8").lower()
        provenance = (REPO_ROOT / "src/boot/PHASE6_NATIVE_PROVENANCE.md").read_text(encoding="utf-8").lower()
        self.assertIn("clears the local phase 6", status)
        self.assertIn("watchdog", status)
        self.assertIn("three delivered vi retraces", status)
        self.assertIn("zero unsupported accesses", status)
        self.assertIn(
            "no third-party implementation source was copied",
            " ".join(provenance.split()),
        )
        self.assertIn("black box", provenance)

    def test_native_gate_defaults_off_and_requires_generated_code(self) -> None:
        cmake = (REPO_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn('option(JFG_BUILD_PHASE6_NATIVE_BOOT "Build the private Phase 6 native M2 runner" OFF)', cmake)
        self.assertIn("JFG_BUILD_PHASE6_NATIVE_BOOT requires JFG_ENABLE_GENERATED_CODE", cmake)


if __name__ == "__main__":
    unittest.main()
