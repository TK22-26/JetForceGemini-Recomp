/* Independent back-to-back SI DMA experiment. No original game OS code. */
.set noreorder
.set noat
.text
.globl _start
_start:
    mtc0 $zero, $12
    nop
    lui $s0, 0xa000
    ori $s0, $s0, 0x1100
    lui $s1, 0xa480
    lui $s2, 0xa430
    lui $s3, 0x1fc0
    ori $s3, $s3, 0x07c0
    or $s4, $zero, $zero
case_loop:
    lui $t0, 0xa030
    addiu $t1, $zero, 16
clear:
    sw $zero, 0($t0)
    addiu $t0, $t0, 4
    addiu $t1, $t1, -1
    bnez $t1, clear
    nop
    sw $zero, 24($s1)
    lui $t0, 0x0030
    sw $t0, 0($s1)
    srl $t0, $s4, 3
    andi $t1, $t0, 2
    addiu $a0, $s1, 16
    beqz $t1, first_launch
    nop
    addiu $a0, $s1, 4
first_launch:
    jal launch
    nop
    or $s5, $v0, $zero
    andi $t0, $s4, 7
    sll $t0, $t0, 4
gap:
    addiu $t0, $t0, -1
    bgez $t0, gap
    nop
    srl $t0, $s4, 3
    andi $t0, $t0, 1
    addiu $a0, $s1, 4
    beqz $t0, second_launch
    nop
    addiu $a0, $s1, 16
second_launch:
    jal launch
    nop
    or $s6, $v0, $zero
    or $s7, $zero, $zero
poll:
    mfc0 $t2, $9
    lw $t0, 8($s2)
    andi $t0, $t0, 2
    bnez $t0, completed
    nop
    b poll
    or $s7, $t2, $zero
completed:
    sw $s4, 0($s0)
    sw $s5, 4($s0)
    sw $s6, 8($s0)
    sw $s7, 12($s0)
    sw $t2, 16($s0)
    sw $zero, 24($s1)
    addiu $t3, $t2, 6000
late_wait:
    mfc0 $t0, $9
    subu $t0, $t0, $t3
    bltz $t0, late_wait
    nop
    lw $t0, 8($s2)
    sw $t0, 20($s0)
    lw $t0, 24($s1)
    sw $t0, 24($s0)
    addiu $s0, $s0, 28
    addiu $s4, $s4, 1
    slti $t0, $s4, 32
    bnez $t0, case_loop
    nop
    lui $t0, 0xa000
    lui $t1, 0x4a46
    ori $t1, $t1, 0x474f
    sw $t1, 0x1000($t0)
done:
    b done
    nop
.org 0x400
launch:
    sw $s3, 0($a0)
    mfc0 $v0, $9
    jr $ra
    nop
