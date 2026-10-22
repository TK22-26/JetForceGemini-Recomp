# Launcher file verification has no visible progress

Status: open; owner-reported 2026-10-20 during cutscene checklist review.
Affected: current Windows preview launcher, both owner-visible Verify files
actions. The owner reports no indication that work is running, leaving the
window looking frozen until the eventual result. The report followed a local
preview manifest correction; actual file integrity validation must remain.

Reproduction: use Verify files in the two launcher entry points and observe
the interval before completion. Investigate UI-thread work as well as missing
busy feedback; one must not be mistaken for the other. Candidate and validation
are pending. Preserve current profile and checklist while staging any launcher
replacement. Keep errors actionable and re-enable controls on every completion
path. Record screenshots/source/test evidence and owner review as work proceeds.


Candidate cause/remedy: verification already runs in the external helper, but
the modal retained a Ready to play heading and unchanged Verify files label,
with no activity display. The UI timer could also restore the previous result
while the helper imported the ROM before publishing its first message.
Publish the initial status immediately, report each package member, keep the
modal button visibly busy and disabled, and show a moving activity bar plus
elapsed time. The home footer also shows elapsed time. Reduced motion keeps
the bar static while text/time remain active. Hash validation is unchanged;
startup package validation is also dispatched to the helper's background task.
Build and owner UI verification are pending.


Implementation note: first source edit step712 stopped at an assertion because
the existing decoration timer is declared differently than expected. The
backend/launch-status changes were already written; no preview was replaced.
Step714 completed the UI changes using the actual per-surface state declaration
and corrected startup ordering so a fast helper result cannot be overwritten.


The native launcher and managed package tests built successfully. The UI fixture
initially used the unprefixed button ID, then an artificial timestamp before
process startup; those test errors were corrected. Offscreen native checks now
exercise the actual button, disabled repeat submission, elapsed activity in the
modal and home footer, reduced motion, success, failure/retry, and menu routing.
Candidate awaits owner UI review; no package verification check was bypassed.


Installed preview: cutscene-selector-20261020, launcher SHA256
82e09b09f1031dfa6ec9b26facb2dc6f69c3868b18d502b7534a8be141355bfc.
81 native UI assertions pass. Activity appears in the modal and home status;
the modal adds a moving bar and elapsed time. The button is visibly busy,
disabled during the job, and available again after success or failure.
All package integrity checks remain enforced. Owner appearance review pending.
