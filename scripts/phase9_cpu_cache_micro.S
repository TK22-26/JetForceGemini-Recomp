/* Independently authored private experiment; original OS routines stay local. */
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
    la $s1, functions
    or $s5, $zero, $zero
function_loop:
    or $s2, $zero, $zero
alignment_loop:
    or $s3, $zero, $zero
length_loop:
    la $t0, alignments
    addu $t0, $t0, $s2
    lw $t0, 0($t0)
    lui $a0, 0x8020
    addu $a0, $a0, $t0
    la $t0, lengths
    addu $t0, $t0, $s3
    lw $a1, 0($t0)
    lw $t9, 0($s1)
    mfc0 $s4, $9
    jalr $t9
    nop
    mfc0 $t0, $9
    subu $t0, $t0, $s4
    sw $t0, 0($s0)
    addiu $s0, $s0, 4
    addiu $s3, $s3, 4
    slti $t0, $s3, 64
    bnez $t0, length_loop
    nop
    addiu $s2, $s2, 4
    slti $t0, $s2, 16
    bnez $t0, alignment_loop
    nop
    addiu $s1, $s1, 4
    addiu $s5, $s5, 1
    slti $t0, $s5, 3
    bnez $t0, function_loop
    nop
    mfc0 $s4, $9
    jal 0x80098a10
    nop
    mfc0 $t0, $9
    subu $t0, $t0, $s4
    sw $t0, 0($s0)

    /* Observe data aliases before/after each original cache routine.
       These are measurements, not assumptions about real CPU caches. */
    la $s1, functions
    lui $s0, 0xa000
    ori $s0, $s0, 0x1010
    or $s5, $zero, $zero
alias_loop:
    lui $s6, 0x8020
    lui $s7, 0xa020
    lui $t0, 0x1357
    ori $t0, $t0, 0x9bdf
    sw $t0, 0($s6)
    lw $t1, 0($s7)
    sw $t1, 0($s0)
    lui $t0, 0x2468
    ori $t0, $t0, 0xace0
    sw $t0, 0($s7)
    lw $t1, 0($s6)
    sw $t1, 4($s0)
    or $a0, $s6, $zero
    addiu $a1, $zero, 17
    lw $t9, 0($s1)
    jalr $t9
    nop
    lw $t1, 0($s6)
    sw $t1, 8($s0)
    addiu $s0, $s0, 12
    addiu $s1, $s1, 4
    addiu $s5, $s5, 1
    slti $t0, $s5, 4
    bnez $t0, alias_loop
    nop
    lui $t1, 0xa000
    addiu $t0, $zero, 193
    sw $t0, 0x1004($t1)
    mfc0 $t0, $12
    sw $t0, 0x1008($t1)
    lui $t0, 0x4a46
    ori $t0, $t0, 0x474b
    sw $t0, 0x1000($t1)
done:
    b done
    nop
.align 2
functions:
    .word 0x80098050, 0x800980d0, 0x800982b0, 0x80098a10
alignments:
    .word 0, 1, 15, 31
lengths:
    .word -4, -1, 0, 1, 2, 15, 16, 17, 31, 32, 33, 8191, 8192, 8193, 16383, 16384
