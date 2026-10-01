/* Original benchmark driving the user's US ROM routines; private output only. */
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
    lui $sp, 0x803f
    ori $sp, $sp, 0xf000
    lui $s0, 0xa000
    ori $s0, $s0, 0x1000
    lui $s1, 0x8000
    ori $s1, $s1, 0x2000
    addiu $t0, $s1, 0x200
    sw $zero, 0($t0) /* empty thread-list sentinel */
    sw $t0, 0($s1)
    sw $t0, 4($s1)
    sw $zero, 8($s1)
    sw $zero, 12($s1)
    addiu $t0, $zero, 1
    sw $t0, 16($s1)
    addiu $t0, $s1, 0x100
    sw $t0, 20($s1)

.macro sample target, offset, argument
    or $a0, $s1, $zero
.if \argument == -1
    addiu $a1, $s1, 0x300
.else
    addiu $a1, $zero, \argument
.endif
    or $a2, $zero, $zero
    mfc0 $s2, $9
    jal \target
    nop
    mfc0 $t4, $9
    subu $t4, $t4, $s2
    sw $t4, \offset($s0)
    sw $v0, \offset+4($s0)
    lw $t4, 8($s1)
    sw $t4, \offset+8($s0)
.endm
    sample empty_leaf, 0, 0
    sample 0x80096910, 12, -1 /* empty recv */
    sample 0x80096f20, 24, 1234 /* send */
    sample 0x80096910, 36, -1 /* recv with output */
    sample 0x80096f20, 48, 1234 /* refill */
    sample 0x80096f20, 60, 5678 /* full send */
    sample 0x80096910, 72, 0 /* recv, discard output */
    lw $t4, 0x300($s1)
    sw $t4, 88($s0)
    lui $t5, 0x4a46
    ori $t5, $t5, 0x4751
    sw $t5, 84($s0)
1:
    b 1b
    nop
empty_leaf:
    or $v0, $zero, $zero
    jr $ra
    nop
