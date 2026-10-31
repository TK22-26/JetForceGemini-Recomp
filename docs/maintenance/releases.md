# Windows release packaging and publication

The release is a playable Windows x64 bundle. Players import their own supported US ROM once;
no first-run compilation is required. The retired launcher-only packager is not part of this workflow.
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
4. Build the native game using the reviewed `cmake/native_release.cmake` policy and separately
   supplied private generated-code/dependency paths. Preserve the exact runtime identity; a
   launcher-only update may deliberately reuse an earlier reviewed runtime, with that identity
   disclosed in the inventory.
5. Package to a new output directory:

   ```powershell
   python scripts/release/package_beta.py --launcher <launcher> --runtime <runtime-dir> --vc-runtime <x64-VC143-redist-dir> --output <new-output-dir> --version <version>
   ```

   The historical `package_beta.py` name also accepts stable versions. Its allowlist includes
   the compiled game, host runtime libraries, guides and required notices. It excludes ROMs,
   extracted game assets, generated source, personal saves, recordings and debug symbols.
6. Verify the ZIP, inventory and SHA-256 file together. The source receipts must match the
   reviewed binaries; a dirty preview is not a clean release build.

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
