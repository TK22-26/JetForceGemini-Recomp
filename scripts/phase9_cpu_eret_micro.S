/* Independent ERET Count probe, with an otherwise identical fallthrough control. */
.set noreorder
.set noat
.text
.globl _start
_start:
    lui $t8, 0x0400
    mtc0 $t8, $12
    nop
    nop
    nop
    lui $s0, 0xa000
    ori $s0, $s0, 0x1100
.macro sample kind, iterations
    addiu $t0, $zero, \iterations
    or $s1, $zero, $zero
    lui $t2, %hi(2f)
    addiu $t2, $t2, %lo(2f)
    mtc0 $t2, $14
    ori $t3, $t8, 2
    mfc0 $t1, $9
1:
    mtc0 $t3, $12
    nop
    nop
    nop
.if \kind == 1
    eret
.else
    nop
.endif
2:
    addiu $s1, $s1, 1
    addiu $t0, $t0, -1
    bnez $t0, 1b
    nop
    mfc0 $t4, $9
    subu $t4, $t4, $t1
    mfc0 $t5, $12
    addiu $t2, $zero, \kind
    sw $t2, 0($s0)
    addiu $t2, $zero, \iterations
    sw $t2, 4($s0)
    sw $s1, 8($s0)
    sw $t4, 12($s0)
    sw $t5, 16($s0)
    addiu $s0, $s0, 20
.endm
.irp kind,0,1
    sample \kind, 16
    sample \kind, 128
.endr
    lui $t0, 0xa000
    lui $t1, 0x4a46
    ori $t1, $t1, 0x4745
    sw $t1, 0x1000($t0)
done:
    b done
    nop
