/* Independently authored SDK-call probe. Original routines stay private. */
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
    ori $s0, $s0, 0x1100
    lui $s1, 0xa430
    lw $t0, 12($s1)
    lui $t1, 0xa000
    sw $t0, 0x1004($t1)
    /* Explicit fixture global policy, not copied from oracle RAM. */
    lui $t0, 0x003f
    ori $t0, $t0, 0xff01
    lui $t1, 0x800b
    sw $t0, -0x6594($t1)
    or $s2, $zero, $zero
old_loop:
    or $s3, $zero, $zero
mask_loop:
    ori $t0, $zero, 0x0555
    beqz $s2, 1f
    nop
    ori $t0, $zero, 0x0aaa
1:
    sw $t0, 12($s1)
    lui $t0, 0x0400
    ori $t0, $t0, 0xff00
    mtc0 $t0, $12
    nop
    nop
    nop
    sll $a0, $s3, 16
    ori $a0, $a0, 0xff01
    mfc0 $s4, $9
    jal 0x80098ea0
    nop
    mfc0 $t0, $9
    subu $t0, $t0, $s4
    sw $t0, 0($s0)
    sw $v0, 4($s0)
    mfc0 $t0, $12
    sw $t0, 8($s0)
    lw $t0, 12($s1)
    sw $t0, 12($s0)
    addiu $s0, $s0, 16
    addiu $s3, $s3, 1
    slti $t0, $s3, 64
    bnez $t0, mask_loop
    nop
    addiu $s2, $s2, 1
    slti $t0, $s2, 2
    bnez $t0, old_loop
    nop
    lui $t1, 0xa000
    addiu $t0, $zero, 128
    sw $t0, 0x1008($t1)
    lui $t0, 0x4a46
    ori $t0, $t0, 0x474d
    sw $t0, 0x1000($t1)
done:
    b done
    nop
