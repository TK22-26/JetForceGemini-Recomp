/* Original timing probe; private ROM builder supplies locally owned IPL. */
.set noreorder
.set noat
.text
.globl _start
_start:
    mfc0 $t0, $12
    lui $t1, 0xffff
    ori $t1, $t1, 0xfffe
    and $t0, $t0, $t1
    mtc0 $t0, $12
    nop
    nop
    nop
    lui $s0, 0xa000
    ori $s0, $s0, 0x1000
    lui $t3, 0x8000
    ori $t3, $t3, 0x2000
    sw $zero, 0($t3)

.macro sample count, offset, load
    addiu $t0, $zero, \count
    mfc0 $t1, $9
1:
.if \load
    lw $t2, 0($t3)
.else
    addiu $t2, $t2, 1
.endif
    addiu $t0, $t0, -1
    bnez $t0, 1b
    nop
    mfc0 $t4, $9
    subu $t4, $t4, $t1
    sw $t4, \offset($s0)
.endm
    sample 100, 0, 0
    sample 1000, 4, 0
    sample 100, 8, 1
    sample 1000, 12, 1
    lui $t3, 0xa000
    ori $t3, $t3, 0x2000
    sample 100, 16, 1
    sample 1000, 20, 1
    lui $t5, 0x4a46
    ori $t5, $t5, 0x474b
    sw $t5, 24($s0)
2:
    b 2b
    nop
