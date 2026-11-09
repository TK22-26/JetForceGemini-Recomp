/* Independent PI length/phase sweep. The launch store is a JR delay slot;
 * the first MI poll can be only four ticks after its retirement. */
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
    lui $s1, 0xa460
    or $s2, $zero, $zero
length_loop:
    la $t0, lengths
    addu $t0, $t0, $s2
    lw $s4, 0($t0)
.ifdef PI_EXTRA_LENGTH
    addiu $s4, $s4, PI_EXTRA_LENGTH
.endif
    or $s3, $zero, $zero
phase_loop:
    addiu $t0, $zero, 2
    sw $t0, 16($s1)
.ifdef PI_HALF_ALIGNMENT
    andi $t3, $s3, 3
    sll $t3, $t3, 1
    srl $t6, $s2, 2
    andi $t6, $t6, 3
    sll $t6, $t6, 1
.else
    andi $t3, $s3, 1
    sll $t3, $t3, 2
    or $t6, $t3, $zero
.endif
    lui $t0, 0x0030
    addu $t0, $t0, $t6
    sw $t0, 0($s1)
    lui $t0, 0x1000
    addu $t0, $t0, $t3
    sw $t0, 4($s1)
    addiu $a0, $s4, -1
    addiu $a1, $s1, 12
    lui $t9, 0x8000
    ori $t9, $t9, 0x0810
    sll $t1, $s3, 2
    addu $t9, $t9, $t1
.ifndef PI_BRANCH_PHASE_ONLY
    slti $t1, $s3, 5
    bnez $t1, normal_phase
    nop
    lui $t9, 0x8000
    ori $t9, $t9, 0x0824
    sll $t1, $s3, 2
    addu $t9, $t9, $t1
.endif
normal_phase:
    lui $t1, 0xa030
.ifndef PI_HALF_ALIGNMENT
    addu $t1, $t1, $t3
.endif
.ifdef PI_BYTE_LENGTHS
    addiu $t4, $s4, 27
    srl $t4, $t4, 2
    lui $t5, 0xcccc
    ori $t5, $t5, 0xcccc
clear_destination:
    sw $t5, 0($t1)
    addiu $t1, $t1, 4
    addiu $t4, $t4, -1
    bnez $t4, clear_destination
    nop
.else
    sw $zero, 0($t1)
.endif
    lui $t0, 0xa430
    lui $t2, 0x0010
    jal launch
    nop
    sw $s4, 0($s0)
    sw $s3, 4($s0)
    lui $t0, 0xa030
.ifndef PI_HALF_ALIGNMENT
    addu $t0, $t0, $t3
.endif
    lw $t0, 0($t0)
    sw $t0, 8($s0)
    addiu $s0, $s0, 12
    addiu $s3, $s3, 1
    slti $t0, $s3, 8
    bnez $t0, phase_loop
    nop
    addiu $s2, $s2, 4
    slti $t0, $s2, 76
    bnez $t0, length_loop
    nop
    lui $t0, 0xa000
    lui $t1, 0x4a46
    ori $t1, $t1, 0x4751
    sw $t1, 0x1000($t0)
finished:
    b finished
    nop
.balign 4
lengths:
.ifdef PI_BYTE_LENGTHS
    .word 1,2,3,4,5,6,7,8,9
    .word 10,11,12,13,14,15,16
    .word 17,754,65535
.else
    .word 8,16,24,32,40,48,56,64
    .word 80,128,256,512,1024,2048,4096,8192,16384,65536,262144
.endif
.org 0x400
launch:
    jr $t9
    sw $a0, 0($a1)
.org 0x410
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    b poll
    nop
.org 0x440
poll:
    lw $t1, 8($t0)
    andi $t1, $t1, 16
    bnez $t1, complete
    nop
    addiu $t2, $t2, -1
    bnez $t2, poll
    nop
    b finished
    nop
complete:
    jr $ra
    nop
