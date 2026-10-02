# Boot state correction for health and ammunition

The native cartridge-entry runner omitted retained CIC-6105 boot state. The
original game checks consequently removed health while idle and could clear
the equipped weapon's ammunition. The correction initializes the missing
boot state once, before generated game execution.

## Cause and implementation

The generated player update calls the original RAM check at guest address
`0x09C00000`. It reads uncached RDRAM `0xA00002E8`; when the boot residue is
missing, the player update at `0x80032B8C` periodically subtracts `0x40` from
health. A separate check at `0x80033440` expects `osCicId` at `0x80000310` to
identify CIC 6105. A mismatch permits clearing the equipped ammo counter.
Both locations were zero in the preserved live session.

`initialize_6105_handoff` initializes the CIC ID and copies three four-byte
IPL3 residues from the already validated local ROM. The two high-RDRAM words
are consumed by the original startup RAM checks. The existing generated
checks continue to execute. The public adapter contains offsets and device
metadata; the IPL3 bytes remain in the user's ROM. This is a minimal supported
cartridge handoff model, not execution of the complete hardware IPL.

## Verification

The same 3,674-poll recording, initial save and Pak were run against both
binaries, ending at the same stationary player position in the training area.
The route includes 1,500 appended neutral polls. The old build ended with
8,192 raw health and `0/100` pistol ammo; the corrected build retained full
8,704 raw health and `100/100`. Both high-RDRAM startup checks reported success
with the correction. All 66 native tests and a replay containing six additional
Start presses passed. Synthetic tests cover byte order, bounded initialization,
and preservation of unrelated memory without shipping ROM data.

The original live process was left running. Its recording, saves and four
non-atomic memory snapshots were preserved privately. The running process
does not acquire this correction until restarted. Previously saved ammo or
health values are not rewritten by the boot adapter.

## Remaining visual issue

The reported Goldwood invasion stutter remains open. A separate paced,
unskipped intro observation reached 9,800 VI retraces without a trap. Of 4,545
presentation gaps, 4,533 spanned two VI retraces; larger gaps also occurred.
The existing actor sampler only recognizes `animBlue` and captured no matching
actors on this route. The final scene still contained the ship's animated
characters. These observations do not isolate the reported invasion moment or
distinguish its animation cadence from rendering delays.

An earlier paced diagnostic completed in the child but was rejected by the
parent because the optional final actor dump added a console record. That
rejection is retained separately and is not a passing regression result.
The boot correction has not been established as a fix for the visual issue.
