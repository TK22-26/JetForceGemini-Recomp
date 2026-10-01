/* Independent SDK/device probe. Original microcode/OS bytes remain private.
 * Exercise empty/no-op audio and graphics tasks with CPU interrupts disabled;
 * observe SP completion directly, not delayed OS interrupt-handler entry.
 */
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
    addiu $sp, $sp, -32
    lui $s0, 0xa000
    ori $s0, $s0, 0x1100
    addiu $s1, $zero, 1 /* task type: graphics, then audio */
kind_loop:
    or $s2, $zero, $zero
length_loop:
    or $s3, $zero, $zero /* DP wait flag: off, on */
flag_loop:
    la $s4, task
    sw $s1, 0($s4)
    sw $s3, 4($s4)
    lui $t0, 0x800a
    addiu $t0, $t0, -0x0c30 /* graphics ucode */
    lui $t1, 0x800b
    ori $t1, $t1, 0x0350
    addiu $t2, $zero, 1
    beq $s1, $t2, 1f
    nop
    lui $t0, 0x800a
    addiu $t0, $t0, -0x25f0 /* audio ucode */
    lui $t1, 0x800b
    addiu $t1, $t1, -0x03f0
1:
    sw $t0, 16($s4)
    sw $t1, 24($s4)
    la $t0, lengths
    addu $t0, $t0, $s2
    lw $s5, 0($t0)
    lui $t0, 0x8020
    ori $t0, $t0, 0x1000
    or $t1, $s5, $zero
2:
    sw $zero, 0($t0)
    sw $zero, 4($t0)
    addiu $t0, $t0, 8
    addiu $t1, $t1, -1
    bgtz $t1, 2b
    nop
    sll $t3, $s5, 3
    addiu $t2, $zero, 1
    bne $s1, $t2, 3f
    nop
    lui $t1, 0xe900 /* SDK full sync, then end display list */
    sw $t1, 0($t0)
    sw $zero, 4($t0)
    lui $t1, 0xb800
    sw $t1, 8($t0)
    sw $zero, 12($t0)
    addiu $t3, $t3, 16
3:
    sw $t3, 52($s4)
    lui $t0, 0xa404
    addiu $t1, $zero, 10 /* halt, clear SP interrupt */
    sw $t1, 16($t0)
    lui $t0, 0xa430
    ori $t1, $zero, 0x0800 /* clear DP interrupt */
    sw $t1, 0($t0)
    or $a0, $s4, $zero
    mfc0 $s6, $9
    jal 0x8009905c /* osSpTaskLoad */
    nop
    mfc0 $t0, $9
    subu $t0, $t0, $s6
    sw $t0, 12($s0)
    or $a0, $s4, $zero
    mfc0 $s6, $9
    jal 0x800991bc /* osSpTaskStartGo */
    nop
    mfc0 $t0, $9
    subu $t0, $t0, $s6
    sw $t0, 16($s0)
    /* Eight launch-to-poll phases; five instructions per delay iteration.
     * Against the seven-instruction polling loop this spans every even phase.
     */
    srl $t4, $s2, 1
    srl $t5, $s3, 1
    addu $t4, $t4, $t5
    beqz $t4, poll_now
    nop
phase_delay:
    nop
    nop
    addiu $t4, $t4, -1
    bnez $t4, phase_delay
    nop
poll_now:
    jal poll_task
    nop
    mfc0 $t3, $9
    subu $t3, $t3, $s6
    sw $t3, 20($s0)
    sw $t1, 24($s0)
    lui $t0, 0xa430
    lw $t1, 8($t0)
    sw $t1, 28($s0)
    sw $s1, 0($s0)
    sw $s5, 4($s0)
    sw $s3, 8($s0)
    addiu $s0, $s0, 32
    addiu $s3, $s3, 2
    slti $t0, $s3, 4
    bnez $t0, flag_loop
    nop
    addiu $s2, $s2, 4
    slti $t0, $s2, 16
    bnez $t0, length_loop
    nop
    addiu $s1, $s1, 1
    slti $t0, $s1, 3
    bnez $t0, kind_loop
    nop
    lui $t0, 0xa000
    lui $t1, 0x4a46
    ori $t1, $t1, 0x4752
    sw $t1, 0x1000($t0)
done:
    b done
    nop
failed:
    lui $t0, 0xa000
    sw $s1, 0x1004($t0)
    sw $s5, 0x1008($t0)
    sw $s3, 0x100c($t0)
    b done
    nop
.balign 16
lengths:
    .word 1, 8, 64, 256
task:
    .word 1, 2, 0x8009f250, 0x180
    .word 0x8009f3d0, 0x1000, 0x800b0350, 0x800
    .word 0x80202000, 0x400, 0, 0
    .word 0x80201000, 0, 0x80203000, 0xa00
/* Stable observation PC for the independently authored probe only. */
.org 0x400
poll_task:
    lui $t0, 0xa404
    lui $t2, 0x0010
poll_status:
    lw $t1, 16($t0)
    andi $t3, $t1, 1
    bnez $t3, poll_done
    nop
    addiu $t2, $t2, -1
    bnez $t2, poll_status
    nop
    b failed
    nop
poll_done:
    jr $ra
    nop
