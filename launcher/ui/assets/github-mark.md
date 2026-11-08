# GitHub project-link mark

The About window uses the official white GitHub Invertocat to link to the
project on GitHub. Downloaded 2026-11-07 from GitHub's
[brand toolkit](https://brand.github.com/foundations/logo):
[logo archive](https://brand.github.com/GitHub_Logos.zip), member
`GitHub Logos/SVG/GitHub_Invertocat_White.svg`.

`github-mark.svg` retains the upstream bytes unchanged (SHA-256 `ccd84c89b1056345608fc3489357f8acc7397e49a3cdc2d418b6c8016911d47b`).
GitHub owns this artwork and its trademarks; the project's MIT license does not
relicense them. GitHub permits its mark as a link to a GitHub profile/project.
See the linked brand toolkit for usage and trademark terms.

`github-mark.tga` is the transparent, uncompressed 32-bit native texture derived
from that SVG, using the established launcher DX11 image path. Its 98 x 96
pixels display at 24.5 x 24 dp, preserving the original aspect ratio with 4x
pixel density. The artwork is bundled; no network request occurs in About.
No extra runtime SVG library is required. SHA-256 `0be1ffb7bb69908b5f2d86b23618f5ad163116b9fe48763693738ad0484470ec`.

Regenerate with ImageMagick 7.1.1-34 (RSVG delegate), from this directory:

```text
magick -background none github-mark.svg -depth 8 -type TrueColorAlpha -compress none github-mark.tga
```

The exact reviewed texture hash is retained in
`scripts/validation/reviewed_hygiene_bodies.json`; review the new image before
updating that entry if regenerated. The SVG is the authoritative source.
