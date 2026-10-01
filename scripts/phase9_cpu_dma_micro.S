/* Independently authored PI/SI completion experiment; no game route/state. */
.set noreorder
.set noat
.text
.globl _start
_start:
    mtc0 $zero, $12
    nop
    nop
    nop
    lui $sp, 0x803f
    ori $sp, $sp, 0xf000
    lui $s0, 0xa000
    ori $s0, $s0, 0x1100
    or $s1, $zero, $zero /* PI read, SI write, SI read */
kind_loop:
    or $s2, $zero, $zero
length_loop:
    or $s3, $zero, $zero
phase_loop:
    lui $t0, 0xa030
    or $t1, $zero, $zero
clear:
    sw $zero, 0($t0)
    addiu $t0, $t0, 4
    addiu $t1, $t1, 4
    slti $t2, $t1, 4096
    bnez $t2, clear
    nop
    la $t0, lengths
    addu $t0, $t0, $s2
    lw $s4, 0($t0)
    bnez $s1, si_setup
    nop
    lui $s5, 0xa460
    addiu $t0, $zero, 2
    sw $t0, 16($s5) /* acknowledge */
    lui $t0, 0x0030
    sw $t0, 0($s5)
    lui $t0, 0x1000
    sw $t0, 4($s5) /* cartridge header */
    addiu $a0, $s4, -1
    addiu $a1, $s5, 12 /* cart to RDRAM */
    b launch
    nop
si_setup:
    lui $s5, 0xa480
    sw $zero, 24($s5)
    lui $t0, 0x0030
    sw $t0, 0($s5)
    slti $t0, $s1, 8
    bnez $t0, channel_setup
    nop
    lui $t0, 0xa030
    addiu $t0, $t0, 48
    or $t1, $s3, $zero
    addiu $t2, $zero, 15
cic_loop:
    sb $t1, 0($t0)
    addiu $t0, $t0, 1
    addiu $t2, $t2, -1
    bnez $t2, cic_loop
    addiu $t1, $t1, 17
    addiu $t1, $zero, 2
    sb $t1, 0($t0)
    b command_launch
    nop
channel_setup:
    slti $t0, $s1, 4
    bnez $t0, ordinary_si
    nop
    /* Four status or read-pad packets, then PIF command 1. */
    lui $t0, 0xa030
    slti $t1, $s1, 6
    addiu $t2, $zero, 4
packet_loop:
    addiu $t3, $zero, 1
    sb $t3, 0($t0)
    beqz $t1, read_packet
    nop
    addiu $t3, $zero, 3
    sb $t3, 1($t0)
    b next_packet
    addiu $t0, $t0, 6
read_packet:
    addiu $t3, $zero, 4
    sb $t3, 1($t0)
    addiu $t3, $zero, 1
    sb $t3, 2($t0)
    addiu $t0, $t0, 7
next_packet:
    addiu $t2, $t2, -1
    bnez $t2, packet_loop
    nop
    addiu $t2, $zero, 0xfe
    sb $t2, 0($t0)
    lui $t0, 0xa030
    addiu $t2, $zero, 1
    sb $t2, 63($t0)
command_launch:
    lui $a0, 0x1fc0
    ori $a0, $a0, 0x07c0
    addiu $a1, $s5, 16
    andi $t0, $s1, 1
    beqz $t0, launch
    nop
    b launch
    addiu $a1, $s5, 4
ordinary_si:
    addiu $t0, $zero, 3
    bne $s1, $t0, si_dma
    nop
    lui $a1, 0xbfc0
    ori $a1, $a1, 0x07fc
    b launch
    addiu $a0, $zero, 8
si_dma:
    lui $a0, 0x1fc0
    ori $a0, $a0, 0x07c0
    addiu $a1, $s5, 16
    addiu $t0, $zero, 1
    beq $s1, $t0, launch
    nop
    addiu $a1, $s5, 4
launch:
    jal launch_dma
    nop
    or $t4, $s3, $zero
    beqz $t4, polling
    nop
delay:
    nop
    nop
    addiu $t4, $t4, -1
    bnez $t4, delay
    nop
polling:
    jal poll_dma
    nop
    sw $s1, 0($s0)
    sw $s4, 4($s0)
    sw $s3, 8($s0)
    sw $t1, 12($s0)
    lui $t0, 0xa030
    lw $t0, 0($t0)
    sw $t0, 16($s0)
    addiu $s0, $s0, 20
    addiu $s3, $s3, 1
    slti $t0, $s3, 8
    bnez $t0, phase_loop
    nop
    addiu $s2, $s2, 4
    slti $t0, $s2, 16
    bnez $t0, length_loop
    nop
    addiu $s1, $s1, 1
    slti $t0, $s1, 10
    bnez $t0, kind_loop
    nop
    lui $t0, 0xa000
    lui $t1, 0x4a46
    ori $t1, $t1, 0x4744
    sw $t1, 0x1000($t0)
done:
    b done
    nop
.balign 4
lengths:
    .word 16, 64, 1024, 4096
.org 0x400
launch_dma:
    sw $a0, 0($a1)
    jr $ra
    nop
.org 0x440
poll_dma:
    lui $t0, 0xa430
    addiu $t3, $zero, 16
    beqz $s1, poll_setup
    nop
    addiu $t3, $zero, 2
poll_setup:
    lui $t2, 0x0010
poll_status:
    lw $t1, 8($t0)
    and $t1, $t1, $t3
    bnez $t1, poll_done
    nop
    addiu $t2, $t2, -1
    bnez $t2, poll_status
    nop
    b done
    nop
poll_done:
    jr $ra
    nop
