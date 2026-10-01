/* Independent Count/Compare pending and acknowledgement experiment. */
.set noreorder
.set noat
.text
.globl _start
_start:
    mtc0 $zero, $12
    nop
    nop
    nop
    lui $s0, 0xa000
    ori $s0, $s0, 0x1100
    or $s1, $zero, $zero
case_loop:
    lui $s4, 1
    andi $t0, $s1, 3
    sll $t0, $t0, 2
    la $t1, delays
    addu $t1, $t1, $t0
    lw $s4, 0($t1)
    slti $t0, $s1, 4
    bnez $t0, normal_epoch
    nop
    addiu $t0, $zero, -256
    mtc0 $t0, $9
normal_epoch:
    or $s2, $zero, $zero
phase_loop:
    mfc0 $t0, $9
    addu $a0, $t0, $s4
    jal arm
    nop
    or $t4, $s2, $zero
    beqz $t4, poll_call
    nop
phase_delay:
    nop
    nop
    addiu $t4, $t4, -1
    bnez $t4, phase_delay
    nop
poll_call:
    jal poll
    nop
    sw $s1, 0($s0)
    sw $s2, 4($s0)
    sw $t1, 8($s0)
    mtc0 $zero, $11
    mfc0 $t1, $13
    sw $t1, 12($s0)
    addiu $s0, $s0, 16
    addiu $s2, $s2, 1
    slti $t0, $s2, 8
    bnez $t0, phase_loop
    nop
    addiu $s1, $s1, 1
    slti $t0, $s1, 8
    bnez $t0, case_loop
    nop
    lui $t0, 0xa000
    lui $t1, 0x4a46
    ori $t1, $t1, 0x474d
    sw $t1, 0x1000($t0)
done:
    b done
    nop
delays:
    .word 64,256,4096,65536
.org 0x400
arm:
    mtc0 $a0, $11
    jr $ra
    nop
.org 0x440
poll:
    mfc0 $t1, $13
    andi $t1, $t1, 0x8000
    bnez $t1, complete
    nop
    b poll
    nop
complete:
    jr $ra
    nop
