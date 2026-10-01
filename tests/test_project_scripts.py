from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.check_repository_hygiene as hygiene
from scripts.check_repository_hygiene import (
    MAX_TRACKED_BYTES,
    check_repository,
    scan_blob,
    scan_path,
    scan_relative_path,
)


def git_environment(**overrides: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_NAME": hygiene.ALLOWED_GIT_IDENTITY_NAME,
            "GIT_AUTHOR_EMAIL": hygiene.ALLOWED_GIT_IDENTITY_EMAIL,
            "GIT_COMMITTER_NAME": hygiene.ALLOWED_GIT_IDENTITY_NAME,
            "GIT_COMMITTER_EMAIL": hygiene.ALLOWED_GIT_IDENTITY_EMAIL,
            "GIT_AUTHOR_DATE": "1704067200 +0000",
            "GIT_COMMITTER_DATE": "1704067200 +0000",
        }
    )
    environment.update(overrides)
    return environment


def commit_fixture(root: Path, message: str, **environment: str) -> None:
    subprocess.run(
        ["git", "commit", "--quiet", "-m", message],
        cwd=root,
        check=True,
        env=git_environment(**environment),
    )


class RepositoryHygieneTests(unittest.TestCase):
    def test_rom_magic_is_rejected(self) -> None:
        errors = scan_blob(bytes.fromhex("80371240") + b"safe", "fixture")
        self.assertTrue(any("N64 ROM" in error for error in errors))

    def test_prefixed_rom_magic_is_rejected(self) -> None:
        errors = scan_blob(b"synthetic-prefix" + bytes.fromhex("80371240"), "fixture")
        self.assertTrue(any("N64 ROM" in error for error in errors))

    def test_late_binary_nul_is_rejected(self) -> None:
        errors = scan_blob((b"a" * 9000) + b"\0", "fixture")
        self.assertTrue(any("binary content" in error for error in errors))

    def test_long_opaque_base64_is_rejected(self) -> None:
        errors = scan_blob(b"Q" * 300, "fixture")
        self.assertTrue(any("opaque base64" in error for error in errors))

    def test_chunked_opaque_and_spaced_hex_payloads_are_rejected(self) -> None:
        chunked = (("Q" * 64) + " " + ("R" * 64)).encode()
        errors = scan_blob(chunked, "fixture")
        self.assertTrue(any("chunked opaque" in error for error in errors))

        spaced_hex = " ".join(["ab"] * 8).encode()
        errors = scan_blob(spaced_hex, "fixture")
        self.assertTrue(any("spaced hexadecimal" in error for error in errors))

    def test_json_body_cannot_hide_chunked_digest_sized_payloads(self) -> None:
        body = ('{"body":"' + ("a" * 64) + " " + ("b" * 64) + '"}').encode()
        errors = scan_blob(body, "fixture")
        self.assertTrue(any("chunked opaque" in error for error in errors))

    def test_repeated_small_opaque_chunks_are_rejected(self) -> None:
        for width in (16, 15):
            with self.subTest(width=width):
                body = (" ".join(["G" * width] * 5)).encode()
                errors = scan_blob(body, "fixture")
                self.assertTrue(any("repeated" in error for error in errors))

    def test_json_private_body_keys_and_byte_arrays_are_rejected(self) -> None:
        forbidden_key = "bo" + "dy"
        body_document = json.dumps({forbidden_key: "redacted"}).encode()
        errors = scan_blob(body_document, "fixture")
        self.assertTrue(any("private-body JSON field" in error for error in errors))

        byte_array = json.dumps({"values": [index % 256 for index in range(4096)]}).encode()
        errors = scan_blob(byte_array, "fixture")
        self.assertTrue(any("byte-range integer array" in error for error in errors))

        nested = json.dumps(
            {"values": [[index % 256 for index in range(63)] for _ in range(70)]}
        ).encode()
        errors = scan_blob(nested, "fixture")
        self.assertTrue(any("byte-range integer array" in error for error in errors))

    def test_raw_symbol_exports_are_rejected(self) -> None:
        readelf = "\n".join(
            f"{index}: 80000000 4 FUNC GLOBAL DEFAULT 1 synthetic_{index}"
            for index in range(4)
        ).encode()
        map_export = "\n".join(
            f"0x8000000{index} synthetic_{index}" for index in range(4)
        ).encode()
        self.assertTrue(
            any("raw readelf symbol export" in error for error in scan_blob(readelf, "fixture"))
        )
        self.assertTrue(
            any("raw linker-map symbol export" in error for error in scan_blob(map_export, "fixture"))
        )

    def test_private_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "roms" / "game.z64"
            path.parent.mkdir()
            path.write_bytes(b"text")
            errors = scan_path(root, path)
        self.assertTrue(any("may not be tracked" in error for error in errors))
        self.assertTrue(any("forbidden" in error for error in errors))

    def test_generated_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "generated" / "output.txt"
            path.parent.mkdir()
            path.write_text("synthetic", encoding="utf-8")
            errors = scan_path(root, path)
        self.assertTrue(any("may not be tracked" in error for error in errors))

    def test_marker_free_src_generated_support_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "src" / "generated" / "support_table.c"
            path.parent.mkdir(parents=True)
            path.write_text(
                "static const unsigned synthetic_table[] = {1U, 2U};\n",
                encoding="utf-8",
            )
            errors = scan_path(root, path)
        self.assertTrue(any("may not be tracked" in error for error in errors))
        self.assertFalse(any("generated-recompilation marker" in error for error in errors))

    def test_gitmodules_path_is_rejected(self) -> None:
        for path in (".gitmodules", "nested/.gitmodules"):
            with self.subTest(path=path):
                errors = scan_relative_path(path)
                self.assertTrue(
                    any("submodule configuration" in error for error in errors)
                )

    def test_archive_extension_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "evidence.zip"
            path.write_text("not really an archive", encoding="utf-8")
            errors = scan_path(root, path)
        self.assertTrue(any("archive file extension" in error for error in errors))

    def test_normal_text_is_accepted(self) -> None:
        self.assertEqual(scan_blob(b"ordinary project text\n", "fixture"), [])

    def test_local_user_path_is_rejected(self) -> None:
        path = b"C:\\" + b"Users\\Example\\file.txt"
        errors = scan_blob(path, "fixture")
        self.assertTrue(any("user-specific" in error for error in errors))

    def test_wsl_user_path_is_rejected(self) -> None:
        path = b"/mnt/c/" + b"Users/Example/file.txt"
        errors = scan_blob(path, "fixture")
        self.assertTrue(any("user-specific" in error for error in errors))

    def test_json_escaped_user_path_is_rejected(self) -> None:
        separator = b"\\" * 2
        path = b"C:" + separator + b"Users" + separator + b"Private" + separator
        errors = scan_blob(path + b"file.txt", "fixture")
        self.assertTrue(any("user-specific" in error for error in errors))

    def test_secret_is_rejected(self) -> None:
        token = ("gh" + "o_" + ("A" * 30)).encode()
        errors = scan_blob(token, "fixture")
        self.assertTrue(any("credential" in error for error in errors))

    def test_additional_secret_family_is_rejected(self) -> None:
        token = ("sk" + "-proj-" + ("A" * 30)).encode()
        errors = scan_blob(token, "fixture")
        self.assertTrue(any("credential" in error for error in errors))

    def test_descriptive_task_and_mask_labels_are_not_key_prefixes(self) -> None:
        for label in ("jfg-private-task-helper-symbol-recovery",
                      "execution-mask-thread-native-experiment"):
            with self.subTest(label=label):
                self.assertEqual(scan_blob(label.encode(), "fixture"), [])

    def test_delimited_keys_remain_rejected(self) -> None:
        for prefix in ("sk" + "-", "sk" + "-proj-"):
            token = prefix + "A" * 30
            for text in (token, 'key="' + token + '"', "Bearer " + token,
                         "OPENAI_API_KEY=" + token):
                with self.subTest(prefix=prefix, context=text[:8]):
                    self.assertTrue(any("credential" in error
                                        for error in scan_blob(text.encode(), "fixture")))

    def test_binary_is_rejected(self) -> None:
        errors = scan_blob(b"text\0binary", "fixture")
        self.assertTrue(any("binary content" in error for error in errors))

    def test_oversized_file_is_rejected(self) -> None:
        errors = scan_blob(b"x" * (MAX_TRACKED_BYTES + 1), "fixture")
        self.assertTrue(any("limit" in error for error in errors))

    def test_archive_signatures_are_rejected(self) -> None:
        fixtures = {
            "zip": bytes.fromhex("504b0304") + b"synthetic",
            "7zip": bytes.fromhex("377abcaf271c") + b"synthetic",
            "rar": bytes.fromhex("526172211a0700") + b"synthetic",
            "gzip": bytes.fromhex("1f8b") + b"synthetic",
            "bzip2": b"BZh" + b"synthetic",
            "xz": bytes.fromhex("fd377a585a00") + b"synthetic",
            "lz4": bytes.fromhex("04224d18") + b"synthetic",
            "zstandard": bytes.fromhex("28b52ffd") + b"synthetic",
            "cab": b"MSCF" + b"synthetic",
            "tar": (b"x" * 257) + b"ustar" + b"synthetic",
            "iso9660": (b"x" * 0x8001) + b"CD001" + b"synthetic",
        }
        for name, data in fixtures.items():
            with self.subTest(name=name):
                errors = scan_blob(data, "fixture")
                self.assertTrue(any("archive signature" in error for error in errors))

    def test_known_protected_hash_is_rejected(self) -> None:
        body = b"synthetic protected body"
        synthetic_hash = hashlib.sha1(body).hexdigest()
        with mock.patch.object(
            hygiene, "KNOWN_PROTECTED_SHA1", frozenset({synthetic_hash})
        ):
            errors = scan_blob(body, "fixture")
        self.assertTrue(any("known protected ROM hash" in error for error in errors))

    def test_private_corpus_marker_is_rejected(self) -> None:
        body = b"JFG_" + b"PRIVATE_CORPUS_V1"
        errors = scan_blob(body, "fixture")
        self.assertTrue(any("private-corpus" in error for error in errors))

    def test_generated_recompilation_marker_is_rejected(self) -> None:
        body = ("RECOMP" + "_FUNC void generated_fixture(void) {").encode()
        errors = scan_blob(body, "fixture")
        self.assertTrue(any("generated-recompilation" in error for error in errors))

    def test_forbidden_historical_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            generated = root / "generated" / "private.txt"
            generated.parent.mkdir()
            generated.write_text("synthetic", encoding="utf-8")
            archive = root / "old-evidence.zip"
            archive.write_text("synthetic", encoding="utf-8")
            subprocess.run(["git", "add", "--all"], cwd=root, check=True)
            commit_fixture(root, "add synthetic fixtures")
            generated.unlink()
            generated.parent.rmdir()
            archive.unlink()
            subprocess.run(["git", "add", "--all"], cwd=root, check=True)
            commit_fixture(root, "remove synthetic fixtures")

            self.assertEqual(check_repository(root, history=False), [])
            errors = check_repository(root, history=True)

        self.assertTrue(any("git-history:generated/private.txt" in e for e in errors))
        self.assertTrue(any("git-history:old-evidence.zip" in e for e in errors))

    def test_current_and_historical_gitlinks_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            fixture = root / "README.md"
            fixture.write_text("synthetic\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            commit_fixture(root, "initial fixture")
            commit_id = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            subprocess.run(
                [
                    "git",
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"160000,{commit_id},vendor/dependency",
                ],
                cwd=root,
                check=True,
            )

            current_errors = check_repository(root, history=False)
            self.assertTrue(any("gitlinks/submodules" in e for e in current_errors))

            commit_fixture(root, "add synthetic gitlink")
            subprocess.run(
                ["git", "rm", "--quiet", "--cached", "vendor/dependency"],
                cwd=root,
                check=True,
            )
            commit_fixture(root, "remove synthetic gitlink")
            historical_errors = check_repository(root, history=True)

        self.assertTrue(
            any("git-history:vendor/dependency" in e for e in historical_errors)
        )

    def test_non_generic_commit_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            (root / "README.md").write_text("synthetic\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            commit_fixture(
                root,
                "synthetic identity fixture",
                GIT_AUTHOR_NAME="Synthetic Contributor",
                GIT_AUTHOR_EMAIL="contributor@example.invalid",
            )
            errors = check_repository(root, history=True)

        self.assertTrue(any("generic no-reply identity" in e for e in errors))

    def test_commit_message_with_local_profile_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            (root / "README.md").write_text("synthetic\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            separator = "\\"
            message = separator.join(("C:", "Users", "SyntheticProfile", "fixture"))
            commit_fixture(root, message)
            errors = check_repository(root, history=True)

        self.assertTrue(any("user-specific local path" in e for e in errors))

    def test_non_utc_annotated_tag_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            (root / "README.md").write_text("synthetic\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            commit_fixture(root, "initial fixture")
            subprocess.run(
                ["git", "tag", "--annotate", "synthetic-v1", "-m", "fixture"],
                cwd=root,
                check=True,
                env=git_environment(GIT_COMMITTER_DATE="1704067200 -0500"),
            )
            errors = check_repository(root, history=True)

        self.assertTrue(any("tagger timestamp must use UTC" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
