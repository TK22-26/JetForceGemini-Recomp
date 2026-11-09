# Windows release packaging and publication

A release is a playable Windows x64 bundle. Players import their own exact supported ROM once;
no first-run compilation is required. Published v1.4.0 supports US only. Development packaging can
include independently qualified US, PAL and Japanese runtimes. Build admission does not replace
owner feature/campaign acceptance or authorize a release. The retired launcher-only packager is
not part of this workflow.
The last recorded publication is [v1.4.0 qualification](../releases/qualification-1.4.0.md).

## Prepare the source and binaries

1. Qualify the runtime against the relevant issue records and owner gameplay review. Retain its
   actual clean source identity, `.support` file and private symbols. ROM-free CI alone does not
   establish gameplay correctness.
2. Set the launcher informational version, numeric assembly version and CMake project version
   consistently. Update the changelog and qualification record, then commit the reviewed source.
3. Build the launcher from that clean revision:

   ```powershell
   powershell -NoProfile -File scripts/build/build_launcher.ps1 -Test
   ```

   `-OutputDirectory` and `-NativeBuildDirectory` select separate build locations.
4. Build each selected revision through the shared [ROM pipeline](../development/rom-bootstrap.md)
   and reviewed `cmake/native_release.cmake` policy. Keep its generated corpus, immutable descriptor,
   native input receipt and verified `jfg-program.json` together. Preserve the exact runtime identity; a
   launcher-only update may deliberately reuse an earlier reviewed runtime, with that identity
   disclosed in the inventory.
5. Package to a new output directory:

   ```powershell
   python scripts/release/package_beta.py --launcher <launcher> --runtime <runtime-dir> --vc-runtime <x64-VC143-redist-dir> --output <new-output-dir> --version <version>
   ```

   Repeat `--runtime <runtime-dir>` for each additional qualified revision (one to three). The
   schema-2 package index pins each `runtimes/<revision-id>/jfg-program.json`; every regional
   program manifest includes the complete game and CRT inventory. The ZIP inventory keeps a
   separate runtime source identity per revision. Missing, duplicated or mismatched revisions
   reject packaging and verification; the selected ROM cannot fall back to another runtime.

   The historical `package_beta.py` name also accepts stable versions. Its allowlist includes
   the compiled game, host runtime libraries, guides and required notices. It excludes ROMs,
   extracted game assets, generated source, personal saves, recordings and debug symbols.
6. Verify the ZIP, inventory and SHA-256 file together. The source receipts must match the
   reviewed binaries; a dirty preview is not a clean release build. The same regional schema is
   consumed by the launcher and the [release verifier](../development/issues/regional-package-verifier.md).

## Publish an approved release

The [release workflow](../../.github/workflows/release.yml) is the executable authority.
After owner authorization, merge the reviewed source to `main`, create the matching version tag
and prepare a draft containing the three prebuilt assets. The workflow:

- checks the tag, launcher/CMake version, checked-out commit and `origin/main` ancestry using
  `scripts/release/release_metadata.py check`;
- runs the reusable ROM-free CI workflow on that tagged revision;
- downloads the maintainer-built draft and validates its playable bundle through
  `scripts/release/release_prebuilt.py publish --output build/release` before publication.

A stable version becomes Latest; a prerelease does not replace Latest. Ordinary branch pushes do
not publish. Never move a published tag or overwrite published assets. Inspect failed uploads and
drafts before retrying; use a new version for changed source. After publication verify public asset
names, hashes, release flags and stable Latest status, and record the actual commit and release URL.

The release ZIP's launcher and ROM build guides must retain working absolute links. Keep the
four public guide paths listed in [documentation ownership](../README.md#fixed-paths-and-immutable-evidence).
