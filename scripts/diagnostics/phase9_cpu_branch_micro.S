/* Independent reference Count probe: executed and annulled branch slots. */
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
.macro sample kind, taken, count
    addiu $t0, $zero, \count
    or $s1, $zero, $zero
.if (\kind == 0) || (\kind == 2) || (\kind == 6)
    addiu $t5, $zero, (1 - \taken)
.elseif (\kind == 1) || (\kind == 3)
    addiu $t5, $zero, \taken
.elseif \kind == 4
    addiu $t5, $zero, -\taken
.else
    addiu $t5, $zero, (\taken - 1)
.endif
    mfc0 $t1, $9
1:
.if \kind == 0
    beql $t5, $zero, 2f
.elseif \kind == 1
    bnel $t5, $zero, 2f
.elseif \kind == 2
    blezl $t5, 2f
.elseif \kind == 3
    bgtzl $t5, 2f
.elseif \kind == 4
    bltzl $t5, 2f
.elseif \kind == 5
    bgezl $t5, 2f
.else
    beq $t5, $zero, 2f
.endif
    addiu $s1, $s1, 1
2:
    addiu $t0, $t0, -1
    bnez $t0, 1b
    nop
    mfc0 $t4, $9
    subu $t4, $t4, $t1
    addiu $t2, $zero, \kind
    sw $t2, 0($s0)
    addiu $t2, $zero, \taken
    sw $t2, 4($s0)
    addiu $t2, $zero, \count
    sw $t2, 8($s0)
    sw $s1, 12($s0)
    sw $t4, 16($s0)
    addiu $s0, $s0, 20
.endm
.irp kind,0,1,2,3,4,5,6
.irp taken,0,1
    sample \kind, \taken, 16
    sample \kind, \taken, 128
.endr
.endr
    lui $t0, 0xa000
    lui $t1, 0x4a46
    ori $t1, $t1, 0x4742
    sw $t1, 0x1000($t0)
done:
    b done
    nop
