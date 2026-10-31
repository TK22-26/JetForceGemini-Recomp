# Prebuilt distribution: October 2026 qualification history

This is historical evidence from the owner-requested October 9 prebuilt beta. Current player
instructions are in [Getting started](../getting-started.md); maintainers use the
[release procedure](../maintenance/releases.md). The model was subsequently published in v1.1.0.

The first beta reused the reviewed v1.0.0 runtime from `d3b9d62`; packaging changes did not qualify
new gameplay. Generated binaries remained outside Git. The complete original beta note is retained
[at the audited revision](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/prebuilt-beta.txt).

## Failed attempts and remedies

- **Beta 1:** clean Windows startup failed with `0xC0000135` because Microsoft C++ runtime DLLs
  were absent. Beta 2 included the unmodified x64 VC143 runtime libraries beside the application.
  It did not install developer tools or alter Windows.
- **Beta 2:** a Hyper-V machine exposed Microsoft Basic Render Driver (`1414:008c`) twice,
  including an adapter without DXGI's software flag. Startup entered WARP pipeline compilation,
  stopped at the first frame and exceeded 10 GB resident RAM. Beta 3 checked the stable software
  adapter ID as well as DXGI flags before Play, including direct shortcuts. Zero dedicated VRAM
  alone does not reject an integrated GPU.
- **Host control:** the same game binary reached 180 retraces and 69 graphics tasks and rendered
  an image on the host RTX 5090. This established startup coverage, not a campaign playthrough.

The VM remained useful for extraction, ROM selection and file verification; it did not qualify
playable virtualized graphics. See the [platform investigation](../development/issues/github-steam-deck-proton-startup.md)
for the recorded host limitations and sources. A hardware-presence check cannot establish every
GPU/driver/gameplay combination. Preserve these distinctions when assessing future installer reports.

The embedded helper resolved package files beside the actual launcher rather than its extraction
cache. The package manifest checked the native program, game libraries and Microsoft runtimes;
ROM validation checked size, format and full SHA-1 locally. Those contracts continue in the current
packager and launcher. No ROMs, extracted game assets, saves, generated source or debug dumps
belong in the public bundle. The [asset policy](../legal/rom-and-assets-policy.md) remains authoritative.
