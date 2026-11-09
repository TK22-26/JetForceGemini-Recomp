/* Original SDK/CPU experiment: SP interrupt wakes a higher-priority worker while main
 * owns live HI/LO and FP condition/register state. OS bytes remain private. */
.set noreorder
.set noat
.text
.macro begin name
.globl \name
.type \name, @function
\name:
.endm
.macro create addr, ident, entry, stack, priority
    lui $a0, 0x8030
    ori $a0, $a0, \addr
    addiu $a1, $zero, \ident
    lui $a2, %hi(\entry)
    addiu $a2, $a2, %lo(\entry)
    or $a3, $zero, $zero
    lui $t0, 0x8030
    ori $t0, $t0, \stack
    sw $t0, 16($sp)
    addiu $t0, $zero, \priority
    sw $t0, 20($sp)
    jal 0x800759d0
    nop
.endm
begin _start
    lui $sp, 0x803f
    ori $sp, $sp, 0xefe0
    jal 0x80097520
    nop
    lui $t0, 0x0400
    mtc0 $t0, $12
    nop
    nop
    nop
    lui $t0, 0x8030
    addiu $t1, $zero, 0x1800
1:
    sw $zero, 0($t0)
    addiu $t1, $t1, -4
    bnez $t1, 1b
    addiu $t0, $t0, 4
    lui $a0, 0x8030
    ori $a0, $a0, 0x1000
    addiu $a1, $a0, 0x100
    jal 0x80096bb0
    addiu $a2, $zero, 1
    addiu $a0, $zero, 4
    lui $a1, 0x8030
    ori $a1, $a1, 0x1000
    jal 0x800978e0
    addiu $a2, $zero, 1234
    create 0, 1, main_thread, 0x8000, 30
    create 0x200, 2, worker_thread, 0xc000, 40
    lui $a0, 0x8030
    jal 0x80096be0
    nop
2:
    b 2b
    nop
.size _start, .-_start
begin main_thread
    lui $t0, 0x0400
    ori $t0, $t0, 0x0401
    mtc0 $t0, $12
    nop
    nop
    nop
    lui $a0, 0x8030
    ori $a0, $a0, 0x0200
    jal 0x80096be0
    nop
    lui $s0, 0x8030
    ori $s0, $s0, 0x1400
    addiu $s1, $zero, 1
main_loop:
    lui $t0, 0x3f80
    mtc1 $t0, $f0
    mtc1 $t0, $f2
    ctc1 $zero, $31
    c.eq.s $f0, $f2
    addiu $t0, $s1, 100
    mthi $t0
    addiu $t0, $s1, 200
    mtlo $t0
    mfc0 $s2, $9
.ifdef PENDING_MASK
    mfc0 $t2, $12
    xori $t3, $t2, 1
    mtc0 $t3, $12
.endif
    lui $t0, 0xa404
    addiu $t1, $zero, 0x4010
    sw $t1, 16($t0)
.ifdef PENDING_MASK
    mtc0 $t2, $12
.globl mask_enable_resume
mask_enable_resume:
.endif
.globl interrupt_resume
interrupt_resume:
    nop
    nop
    nop
    b interrupt_observe
    nop
.globl interrupt_observe
interrupt_observe:
    mfc0 $t0, $9
    subu $t0, $t0, $s2
    sw $s1, 0($s0)
    sw $t0, 4($s0)
    mfhi $t0
    sw $t0, 8($s0)
    mflo $t0
    sw $t0, 12($s0)
    mfc1 $t0, $f0
    sw $t0, 16($s0)
    cfc1 $t0, $31
    sw $t0, 20($s0)
    lui $t0, 0x8030
    lw $t1, 0x1700($t0)
    sw $t1, 24($s0)
    lw $t1, 0x1704($t0)
    sw $t1, 28($s0)
    addiu $s1, $s1, 1
    slti $t0, $s1, 9
    bnez $t0, main_loop
    addiu $s0, $s0, 32
    lui $t0, 0x8030
    lui $t1, 0x4a46
    ori $t1, $t1, 0x4749
    sw $t1, 0x1780($t0)
3:
    b 3b
    nop
.size main_thread, .-main_thread
begin worker_thread
    lui $t0, 0x0400
    mtc0 $t0, $12
    nop
    nop
    nop
    lui $s0, 0x8030
worker_loop:
    ori $a0, $s0, 0x1000
    ori $a1, $s0, 0x1704
    jal 0x80096910
    addiu $a2, $zero, 1
    lw $t0, 0x1700($s0)
    addiu $t0, $t0, 1
    sw $t0, 0x1700($s0)
    mthi $zero
    mtlo $zero
    mtc1 $zero, $f0
    lui $t0, 0x4000
    mtc1 $t0, $f2
    c.eq.s $f0, $f2
    b worker_loop
    nop
.size worker_thread, .-worker_thread
