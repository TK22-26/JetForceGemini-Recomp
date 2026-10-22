# The Tawfret chief's floating square: what we learned

The yellow square beside Tawfret's chief is a visible camera-helper model from
the original game. It is not corrupted texture data or a recompilation error.
The owner initially could not see it in the N64 reference, then found it on
reinspection: native resolution and television blur disguise it as background
detail. The separate rapid camera movement at shot changes was an interpolation
defect in the recomp. Both corrections are owner-verified and included in v1.4.0.

## Two symptoms, two causes

The first report showed a floating yellow square in three chief shots and what
looked like a white flash between shots. Frame inspection and the owner's
clarification showed that the latter was the camera crossing scenery at bad
angles for a few intermediate frames, rather than a white framebuffer.

A distant shape moved little on screen and incorrectly kept a shared scenery
transform eligible for interpolation despite a validated camera discontinuity.
The correction makes that camera-cut decision reject interpolation for the
same matrix cohort. Small continuous movements and independent cameras retain
their existing handling. A focused regression fails before the change and
passes after it; the owner confirmed the bad-angle cuts were gone.

The square remained after that correction, so it needed its own investigation.
An original-ROM capture replayed through our renderer also showed it. That
alone did not prove a renderer defect: EmuHawk with Angrylion and software RSP
showed it too, and the owner later confirmed it in the N64 reference.

## Following the square back to its owner

The yellow face consists of triangles 34 and 35 of a 36-triangle model named
`camera`, used by `AnimCamera` objects. A copied display-list experiment removed
the whole camera model and changed only the square and its dark surround:
120 pixels in the reference image. Removing a suspected `SteveLight` sprite
changed no pixels and ruled out that earlier explanation. These were private
identification experiments, not changes to shipping game data.

The original animation interpreter starts camera path 13 at 20 seconds. Starting
a path clears the object's hidden bit (`0x0400` at actor offset +6), making its
mesh drawable. Later commands select another camera without stopping path 13.
In the examined shot, path 20 supplies the active view while the older path 13
object remains drawable in the background. The original object draw gate then
submits its camera mesh exactly as the flags request.

Stopping a path sets the hidden bit again; selecting a camera does not hide all
previous camera objects. This explains why an inactive camera can appear in a
later shot. Clearing the widescreen preference did not remove the square in
the controlled reference comparison. Neither high FPS nor diagnostic logging
is necessary for it to exist.

Related Rare engine source was useful as a lead, not as a ready-made patch.
[Diddy Kong Racing explicitly hides animation cameras](https://github.com/DavidSM64/Diddy-Kong-Racing/blob/master/src/object_functions.c).
JFG's corresponding behavior dispatch is different, and the same behavior
number also belongs to visible animated props. Hiding every object with that
behavior would therefore remove legitimate scene content.

## The release correction

The correction recognizes the supported `AnimCamera` object by its exact object
and behavior identity, terminated header name and pinned native draw function
instructions. At that draw boundary only, it applies the game's existing hidden
flag and immediately restores the original byte. Restoration also occurs during
exception unwinding. The camera object continues to exist and run its animation
path; camera selection, positions, progression and simulation state are retained.

This is an intentional correction of an original-game visual artifact. It does
not erase yellow pixels, special-case Tawfret coordinates, or remove a live
camera actor. Unrecognized objects and incompatible instruction/header layouts
are left alone. The change is independent of frame rate and logging.

Source: [camera-helper draw scope](../../include/jfg/renderer/camera_helper_presentation.hpp),
[native dispatch integration](../../src/boot/native_boot.cpp), and
[semantic presentation tests](../../tests/semantic_presentation_tests.cpp).
The separate cut correction is in
[interpolation history](../../include/jfg/renderer/interpolation_history.hpp).

## Verification and lessons

The native Release build and four focused renderer/history suites pass. Tests
cover the native hidden-bit gate, exact byte restoration, nested scopes,
exception unwinding, visible same-behavior props and malformed or incompatible
inputs. The owner replayed the chief cinematic normally at 120 FPS with
diagnostics and FPS logging disabled and confirmed: "Square gone; scene looks
correct." That acceptance covers the reviewed sequence; it is not an exhaustive
claim about every cinematic or hardware configuration.

Higher resolution can expose an original defect that looked like harmless
background detail on a television. An original-ROM replay in a new renderer
does not, by itself, establish what N64 hardware displays. Matching reference
rendering, tracing draw ownership and checking the original state transitions
prevented us from calling this a recompilation failure or hiding the wrong
object. Camera simulation and camera-helper presentation also need separate
treatment: fixing a visible helper must not disable the camera it represents.

The [full investigation record](issues/tawfret-chief-camera-and-square.md)
retains the initial mistaken hardware comparison, failed hypotheses, build
compatibility findings and private evidence inventory. ROM data, generated game
code, memory captures and personal saves remain outside the public repository.
