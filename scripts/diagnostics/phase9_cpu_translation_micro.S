/* Original private experiment: boot TLB state and original OS translations. */
.set noreorder
.set noat
.text
.globl _start
_start:
    mfc0 $t0, $12
    addiu $t1, $zero, -2
    and $t0, $t0, $t1
    mtc0 $t0, $12
    nop
    nop
    nop
    lui $sp, 0x803f
    ori $sp, $sp, 0xf000
    lui $s0, 0xa000
    ori $s0, $s0, 0x1000
    mfc0 $s3, $10
    or $t0, $zero, $zero
    or $t1, $s0, $zero
1:
    mtc0 $t0, $0
    nop
    nop
    nop
    tlbr
    nop
    nop
    nop
    mfc0 $t2, $10
    mfc0 $t3, $2
    mfc0 $t4, $3
    mfc0 $t5, $5
    sw $t2, 0($t1)
    sw $t3, 4($t1)
    sw $t4, 8($t1)
    sw $t5, 12($t1)
    addiu $t0, $t0, 1
    slti $t2, $t0, 32
    bnez $t2, 1b
    addiu $t1, $t1, 16
    mtc0 $s3, $10
    nop
    nop
    nop
.macro sample value, offset
    lui $a0, ((\value >> 16) & 0xffff)
    ori $a0, $a0, (\value & 0xffff)
    mfc0 $s2, $9
    jal 0x80096ea0
    nop
    mfc0 $t4, $9
    subu $t4, $t4, $s2
    sw $t4, \offset($s0)
    sw $v0, \offset+4($s0)
.endm
    sample 0x00000000, 512
    mfc0 $t5, $0
    sw $t5, 540($s0)
    sample 0x80001234, 520
    sample 0xa0001234, 528
.macro entry slot, tag, lo0, lo1, mask
    addiu $t0, $zero, \slot
    mtc0 $t0, $0
    lui $t0, ((\tag >> 16) & 0xffff)
    ori $t0, $t0, (\tag & 0xffff)
    mtc0 $t0, $10
    addiu $t0, $zero, \lo0
    mtc0 $t0, $2
    addiu $t0, $zero, \lo1
    mtc0 $t0, $3
    ori $t0, $zero, \mask
    mtc0 $t0, $5
    nop
    nop
    nop
    tlbwi
    nop
    nop
    nop
.endm
.macro probe tag, offset
    lui $t0, ((\tag >> 16) & 0xffff)
    ori $t0, $t0, (\tag & 0xffff)
    mtc0 $t0, $10
    nop
    nop
    nop
    tlbp
    nop
    nop
    nop
    mfc0 $t1, $0
    sw $t1, \offset($s0)
.endm
    entry 17, 0x00200007, 0x106, 0x146, 0
    entry 5, 0x00200007, 0x206, 0x246, 0
    probe 0x00200007, 544 /* duplicate tag: observed reference policy only */
    probe 0x00200008, 548 /* different ASID, neither global */
    entry 5, 0x00200007, 0x207, 0x247, 0
    probe 0x00200008, 552 /* both G bits: global */
    entry 5, 0x00200007, 0x207, 0x246, 0
    probe 0x00200008, 556 /* only one G bit: not global */
    entry 17, 0x00400007, 0x406, 0x446, 0x6000
    probe 0x00406007, 560 /* masked VPN bits */
    probe 0x00408007, 564 /* next pair: miss */
    addiu $t0, $zero, 6
    sw $t0, 568($s0)
    lui $t0, 0x4a46
    ori $t0, $t0, 0x4754
    sw $t0, 536($s0)
2:
    b 2b
    nop
