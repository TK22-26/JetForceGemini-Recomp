/* Independent AI length/status/deadline sweep; no host audio clock. */
.set noreorder
.set noat
.text
.globl _start
_start:
    mtc0 $zero, $12
    nop
    lui $s0, 0xa000
    ori $s0, $s0, 0x1100
    lui $s1, 0xa450
    lui $s2, 0xa430
    lui $t0, 0xa440
    addiu $t1, $zero, 525
    sw $t1, 24($t0)
    sw $zero, 16($t0)
vi_wait:
    lw $t1, 8($s2)
    andi $t1, $t1, 8
    beqz $t1, vi_wait
    nop
    addiu $t1, $zero, 1
    sw $t1, 8($s1)
    addiu $t1, $zero, 15
    sw $t1, 20($s1)
    or $s3, $zero, $zero
frequency:
    la $t0, rates
    addu $t0, $t0, $s3
    lw $s6, 0($t0)
    sw $s6, 16($s1)
    or $s4, $zero, $zero
size:
    la $t0, lengths
    addu $t0, $t0, $s4
    lw $s7, 0($t0)
    or $s5, $zero, $zero
phase:
    la $t0, acknowledgements
    sll $t7, $s5, 2
    addu $t0, $t0, $t7
    lw $t7, 0($t0)
    sw $t7, 12($s1)
    lui $t0, 0x0030
    sw $t0, 0($s1)
    mfc0 $t1, $9
    sw $s7, 4($s1)
    lw $t2, 4($s1)
.ifdef AI_FIFO
    srl $a0, $s7, 1
    sw $a0, 4($s1)
.endif
    lw $t3, 12($s1)
    sw $s6, 0($s0)
    sw $s7, 4($s0)
    sw $s5, 8($s0)
    sw $t1, 12($s0)
    sw $t2, 16($s0)
    sw $t3, 20($s0)
    /* Sample remaining length near halfway, without assuming a read value. */
    srl $t7, $s7, 3
    addiu $t8, $s6, 1
    multu $t7, $t8
    mflo $t7
    addu $t7, $t7, $t1
half_wait:
    mfc0 $t4, $9
    subu $t8, $t4, $t7
    bltz $t8, half_wait
    nop
    mfc0 $t4, $9
    lw $t8, 4($s1)
    sw $t4, 40($s0)
    sw $t8, 44($s0)
    or $t2, $s5, $zero
delay:
    addiu $t2, $t2, -1
    bgez $t2, delay
    nop
    or $t4, $zero, $zero
poll:
    mfc0 $t2, $9
    lw $t3, 8($s2)
    andi $t3, $t3, 4
    bnez $t3, complete
    nop
    b poll
    or $t4, $t2, $zero
complete:
    lw $t5, 4($s1)
    lw $t6, 12($s1)
    sw $t4, 24($s0)
    sw $t2, 28($s0)
    sw $t5, 32($s0)
    sw $t6, 36($s0)
.ifdef AI_FIFO
    la $t0, acknowledgements
    sll $t7, $s5, 2
    addu $t0, $t0, $t7
    lw $t7, 0($t0)
    sw $t7, 12($s1)
second_poll:
    mfc0 $t2, $9
    lw $t3, 8($s2)
    andi $t3, $t3, 4
    bnez $t3, second_complete
    nop
    b second_poll
    or $t4, $t2, $zero
second_complete:
    lw $t5, 4($s1)
    lw $t6, 12($s1)
    sw $t4, 48($s0)
    sw $t2, 52($s0)
    sw $t5, 56($s0)
    sw $t6, 60($s0)
    addiu $s0, $s0, 64
.else
    addiu $s0, $s0, 48
.endif
    addiu $s5, $s5, 1
    slti $t0, $s5, 8
    bnez $t0, phase
    nop
    addiu $s4, $s4, 4
    slti $t0, $s4, 12
    bnez $t0, size
    nop
    addiu $s3, $s3, 4
    slti $t0, $s3, 12
    bnez $t0, frequency
    nop
    lui $t0, 0xa000
.ifdef AI_FIFO
    addiu $t1, $zero, 16
.else
    addiu $t1, $zero, 12
.endif
    sw $t1, 0x1004($t0)
    lui $t1, 0x4a46
    ori $t1, $t1, 0x4741
    sw $t1, 0x1000($t0)
done:
    b done
    nop
rates:
    .word 1103,2209,4419
lengths:
    .word 32,128,4096
acknowledgements:
    .word 0,1,2,4,8,0x40000000,0x80000000,0xffffffff
