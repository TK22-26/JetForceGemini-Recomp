/* Independent direct-register VI startup, mode-latch and scanline experiment. */
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
    lui $s1, 0xa440
    lui $s2, 0xa430
    sw $zero, 16($s1) /* discard pending IPL interrupt */
    or $s3, $zero, $zero
mode_loop:
    la $t0, modes
    addu $t0, $t0, $s3
    lw $s4, 0($t0)
    sw $s4, 24($s1)
    addiu $t0, $zero, 3093
    sw $t0, 28($s1)
    or $s5, $zero, $zero
edge_loop:
    lui $t2, 0x0040
wait_edge:
    lw $t0, 8($s2)
    andi $t0, $t0, 8
    bnez $t0, edge
    nop
    addiu $t2, $t2, -1
    bnez $t2, wait_edge
    nop
    b failed
    nop
edge:
    mfc0 $s6, $9
    sw $zero, 16($s1)
    or $s7, $zero, $zero
sample:
    lw $t0, 16($s1)
    mfc0 $t1, $9
    sw $s4, 0($s0)
    sll $t2, $s5, 3
    addu $t2, $t2, $s7
    sw $t2, 4($s0)
    sw $t1, 8($s0)
    sw $t0, 12($s0)
    sw $s6, 16($s0)
    addiu $s0, $s0, 20
    addiu $t0, $zero, 733
delay:
    addiu $t0, $t0, -1
    bnez $t0, delay
    nop
    addiu $s7, $s7, 1
    slti $t0, $s7, 8
    bnez $t0, sample
    nop
    addiu $s5, $s5, 1
    slti $t0, $s5, 4
    bnez $t0, edge_loop
    nop
    addiu $s3, $s3, 4
    slti $t0, $s3, 16
    bnez $t0, mode_loop
    nop
    lui $t0, 0xa000
    lui $t1, 0x4a46
    ori $t1, $t1, 0x4750
    sw $t1, 0x1000($t0)
failed:
    b failed
    nop
.balign 4
modes:
    .word 0, 525, 262, 625
