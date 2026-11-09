/* Independent direct-VI interval probe. IE disabled; acknowledge via VI_CURRENT.
 * Discard transition intervals after register changes before collecting samples.
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
    lui $s0, 0xa000
    ori $s0, $s0, 0x1100
    lui $s1, 0xa440
    lui $s2, 0xa430
    sw $zero, 0($s1) /* blank, retain interrupt timing */
    addiu $t0, $zero, 2
    sw $t0, 12($s1)
    or $s3, $zero, $zero
vertical_loop:
    or $s4, $zero, $zero
horizontal_loop:
    la $t0, verticals
    addu $t0, $t0, $s3
    lw $t1, 0($t0)
    sw $t1, 24($s1)
    sw $t1, 0($s0)
    la $t0, horizontals
    addu $t0, $t0, $s4
    lw $t1, 0($t0)
    sw $t1, 28($s1)
    sw $t1, 4($s0)
    or $s5, $zero, $zero
event_loop:
    sw $zero, 16($s1)
    lui $t2, 0x0040 /* bounded wait, ample for a whole VI */
wait_loop:
    lw $t0, 8($s2)
    andi $t0, $t0, 8
    bnez $t0, observed
    nop
    addiu $t2, $t2, -1
    bnez $t2, wait_loop
    nop
    b failed
    nop
observed:
    mfc0 $t0, $9
    subu $t1, $t0, $s6
    or $s6, $t0, $zero
    slti $t0, $s5, 2
    bnez $t0, next_event
    nop
    addiu $t0, $s5, -2
    sll $t0, $t0, 2
    addu $t0, $t0, $s0
    sw $t1, 8($t0)
next_event:
    addiu $s5, $s5, 1
    slti $t0, $s5, 34
    bnez $t0, event_loop
    nop
    addiu $s0, $s0, 136
    addiu $s4, $s4, 4
    slti $t0, $s4, 8
    bnez $t0, horizontal_loop
    nop
    addiu $s3, $s3, 4
    slti $t0, $s3, 24
    bnez $t0, vertical_loop
    nop
    lui $t0, 0xa000
    lui $t1, 0x4a46
    ori $t1, $t1, 0x4756
    sw $t1, 0x1000($t0)
done:
    b done
    nop
failed:
    lui $t0, 0xa000
    sw $s3, 0x1004($t0)
    sw $s4, 0x1008($t0)
    sw $s5, 0x100c($t0)
    b done
    nop
.balign 4
verticals:
    .word 261, 262, 525, 526, 624, 625
horizontals:
    .word 3093, 3177
