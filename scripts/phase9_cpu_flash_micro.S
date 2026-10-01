/* Independent flash bus command/DMA experiment, isolated disposable save. */
.set noreorder
.set noat
.text
.globl _start
_start:
    mtc0 $zero, $12
    nop
    lui $s0, 0xa460
    lui $s1, 0xa430
    lui $s2, 0xa801
    or $s5, $zero, $zero
job:
    /* Input page is a changing byte pattern; output has sentinel bytes. */
    lui $t0, 0xa030
    or $t1, $s5, $zero
    addiu $t2, $zero, 128
fill:
    sb $t1, 0($t0)
    addiu $t3, $zero, 0xcc
    sb $t3, 0x1000($t0)
    addiu $t0, $t0, 1
    addiu $t1, $t1, 7
    addiu $t2, $t2, -1
    bnez $t2, fill
    nop
    or $s4, $zero, $zero
    lui $a0, 0xd200
    jal command
    nop
    lui $a0, 0xe100
    jal command
    nop
    lui $t0, 0x0030
    ori $t0, $t0, 0x1000
    sw $t0, 0($s0)
    lui $t0, 0x0800
    sw $t0, 4($s0)
    addiu $a0, $zero, 7
    addiu $a1, $s0, 12
    jal transfer
    nop
    addiu $s4, $zero, 1
    lui $a0, 0xf000
    jal command
    nop
    lui $t0, 0x0800
    sll $t1, $s5, 6
    addu $t0, $t0, $t1
    sw $t0, 4($s0)
    addiu $a0, $zero, 127
    addiu $a1, $s0, 12
    jal transfer
    nop
    addiu $s4, $zero, 2
    lui $a0, 0xb400
    jal command
    nop
    lui $t0, 0x0030
    sw $t0, 0($s0)
    lui $t0, 0x0800
    sw $t0, 4($s0)
    addiu $a0, $zero, 127
    addiu $a1, $s0, 8
    jal transfer
    nop
    lui $a0, 0xa500
    or $a0, $a0, $s5
    jal command
    nop
    andi $t0, $s5, 1
    beqz $t0, execute_write
    nop
    lui $t0, 0xa030
    lui $t1, 0x1234
    ori $t1, $t1, 0x5678
    sw $t1, 0($t0)
execute_write:
    lui $a0, 0xd200
    jal command
    nop
    addiu $s4, $zero, 3
    lui $a0, 0xf000
    jal command
    nop
    lui $t0, 0x0030
    ori $t0, $t0, 0x1000
    sw $t0, 0($s0)
    lui $t0, 0x0800
    sll $t1, $s5, 6
    addu $t0, $t0, $t1
    sw $t0, 4($s0)
    addiu $a0, $zero, 127
    addiu $a1, $s0, 12
    jal transfer
    nop
    lui $a0, 0x4b00
    or $a0, $a0, $s5
    jal command
    nop
    lui $a0, 0x7800
    jal command
    nop
    lui $a0, 0xd200
    jal command
    nop
    addiu $s4, $zero, 4
    lui $a0, 0xf000
    jal command
    nop
    addiu $a0, $zero, 127
    addiu $a1, $s0, 12
    jal transfer
    nop
    addiu $s5, $s5, 1
    slti $t0, $s5, 8
    bnez $t0, job
    nop
    lui $t0, 0xa000
    lui $t1, 0x4a46
    ori $t1, $t1, 0x4746
    sw $t1, 0x1000($t0)
done:
    b done
    nop
.org 0x400
command:
    lui $t8, 0xa800
    lw $v1, 0($t8)
    sw $a0, 0($s2)
    lw $v0, 0($t8)
    sw $zero, 0($t8)
    lw $a2, 0($t8)
    jr $ra
    nop
.org 0x420
transfer:
    addiu $t0, $zero, 2
    sw $t0, 16($s0)
    addiu $t4, $s5, 1
.org 0x43c
    mfc0 $t5, $9
    sw $a0, 0($a1)
delay:
    addiu $t4, $t4, -1
    bnez $t4, delay
    nop
    lui $t2, 0x0010
.org 0x480
poll:
    lw $t0, 8($s1)
    andi $t0, $t0, 16
    bnez $t0, complete
    nop
    addiu $t2, $t2, -1
    bnez $t2, poll
    nop
    b done
    nop
complete:
    jr $ra
    nop
