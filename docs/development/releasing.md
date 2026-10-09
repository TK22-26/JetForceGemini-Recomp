# Publishing a launcher release

A Git tag identifies a source commit. A GitHub Release adds release notes and
downloadable assets to that tag. GitHub's `/releases/tag/v1.0.0` URL is normal;
the stable release should also appear as **Latest** and resolve at
`https://github.com/TK22-26/JetForceGemini-Recomp/releases/latest`.

The 2026-10-08 review found that all published releases were marked as
prereleases, `/releases/latest` returned 404, and no v1.0.0 release/tag existed.
The CI workflow built a package but did not publish one. Local version changes
and README announcements do not create a GitHub Release.

## When the release is ready

1. Set `AssemblyInformationalVersion` in `launcher/windows/Launcher.cs` to the
   intended version, for example `1.0.0`. Keep the assembly's numeric version
   and the root CMake project version consistent. Package names are derived
   from the informational version.
2. Merge the reviewed source, notices, and release workflow to `main` and wait
   for CI to pass. Finish gameplay acceptance separately; ROM-free CI does not
   establish campaign or original-console accuracy.
3. Create and push a tag on that main commit **only when publication is intended**:

   ```sh
   git switch main
   git pull --ff-only
   git tag v1.0.0
   git push origin v1.0.0
   ```

Pushing that tag starts **Publish launcher release**. The workflow verifies the
tag/version and main-branch ancestry, runs the full ROM-free CI workflow on
the tagged revision, then builds/tests/packages the Windows launcher. The
final job uploads a draft with the ZIP, checksums and package inventory, and
publishes it only after uploads succeed. A stable tag becomes a published,
non-prerelease **Latest** release. A version with a suffix, such as
`v1.1.0-rc.1`, is published as a prerelease without replacing Latest.

The release ZIP includes third-party notices and provenance. A standalone EXE
is not uploaded separately; users should extract the complete ZIP. Generated
game binaries, ROMs, saves and private diagnostic data are not release inputs.

## Retry and verification

If validation/building fails, no release is published. Inspect the Actions
failure before retrying. A failed upload can leave a draft for inspection.
The workflow refuses to replace any existing release or draft automatically.
Never move an already-published tag or replace published assets as a routine
retry; use a new version for changed source.

An existing tag can be retried through **Re-run all jobs**, or:

```sh
gh workflow run release.yml --ref v1.0.0
```

Manual dispatch on a branch is rejected. Manual dispatch also requires the
workflow to exist on the default branch. Only the publish job has
`contents: write`; checkout credentials are not persisted and the publishing
token is passed only to the final publishing step. PRs and ordinary main
pushes run CI without publishing anything.

After publication, the workflow verifies public flags, asset names and the
stable Latest endpoint. The source commit and checksums are recorded in the
package inventory. Existing preview releases retain their original labels;
they are not relabeled as the new v1.0.0 build.

References: [GitHub release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository),
[GitHub CLI release creation](https://cli.github.com/manual/gh_release_create),
[reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows).
