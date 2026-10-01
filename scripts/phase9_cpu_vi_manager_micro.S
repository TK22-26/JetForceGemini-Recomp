/* Independent original-OS VI-manager experiment. OS bytes stay private.
 * A low-priority runnable idle thread permits real interrupts while the
 * main thread blocks for retrace messages. No synthetic queue wakeups. */
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
    create 0, 1, main_thread, 0x8000, 30
    create 0x200, 2, idle_thread, 0xc000, 1
    lui $a0, 0x8030
    jal 0x80096be0
    nop
2:
    b 2b
    nop
.size _start, .-_start
begin main_thread
    lui $a0, 0x8030
    ori $a0, $a0, 0x0200
    jal 0x80096be0
    nop
    jal 0x80098a40
    addiu $a0, $zero, 254
    lui $a0, 0x8030
    ori $a0, $a0, 0x1000
    addiu $a1, $a0, 0x100
    jal 0x80096bb0
    addiu $a2, $zero, 4
    lui $a0, 0x8030
    ori $a0, $a0, 0x1000
    addiu $a1, $zero, 1234
    jal 0x80098e30
    addiu $a2, $zero, 1
    lui $s0, 0x8030
    ori $s0, $s0, 0x1400
    or $s1, $zero, $zero
vi_loop:
    lui $a0, 0x8030
    ori $a0, $a0, 0x1000
    addiu $a1, $s0, 4
    jal 0x80096910
    addiu $a2, $zero, 1
    mfc0 $t0, $9
    sw $t0, 0($s0)
    lui $t0, 0x8010
    lw $t1, 0x598c($t0)
    sw $t1, 8($s0)
    lw $t1, 0x5980($t0)
    sw $t1, 12($s0)
    lw $t1, 0x5984($t0)
    sw $t1, 16($s0)
    mfc0 $t1, $12
    sw $t1, 20($s0)
    sw $s1, 24($s0)
    addiu $s0, $s0, 28
    addiu $s1, $s1, 1
    slti $t0, $s1, 24
    bnez $t0, vi_loop
    nop
    lui $t0, 0x8030
    lui $t1, 0x4a46
    ori $t1, $t1, 0x4756
    sw $t1, 0x1780($t0)
finished:
    b finished
    nop
.size main_thread, .-main_thread
begin idle_thread
    addiu $t0, $t0, 1
    b idle_thread
    nop
.size idle_thread, .-idle_thread
