/* ROM-free payload: architectural link value at the delay slot and target.
 * Output uses uncached RDRAM. No return through a tested link is required. */
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
.macro sample id, kind, argument
    lui $ra, 0x1357
    ori $ra, $ra, 0x2468
    or $s3, $ra, $zero
    lui $s2, 0x2468
    ori $s2, $s2, 0x1357
    or $s4, $zero, $zero
    addiu $a0, $zero, \argument
    lui $t9, %hi(2f)
    addiu $t9, $t9, %lo(2f)
1:
.if \kind == 0 || \kind == 1
    jal 2f
.elseif \kind == 2
    jalr $ra, $t9
.elseif \kind == 3
    jalr $s3, $t9
.elseif \kind == 4
    bgezal $a0, 2f
.elseif \kind == 5
    bltzal $a0, 2f
.elseif \kind == 6
    bgezall $a0, 2f
.else
    bltzall $a0, 2f
.endif
.if \kind == 1
    addiu $ra, $ra, 4
.elseif \kind == 3
    or $s2, $s3, $zero
.else
    or $s2, $ra, $zero
.endif
    b 3f
    nop
2:
    addiu $s4, $zero, 1
3:
    addiu $t0, $zero, \id
    sw $t0, 0($s0)
    lui $t0, %hi(1b)
    addiu $t0, $t0, %lo(1b)
    sw $t0, 4($s0)
    /* Store each architectural 64-bit value explicitly. Under the O32
     * assembler ABI, an sd pseudo-op otherwise expands into register-pair
     * stores, which would not observe this GPR's upper half. */
    dsrl32 $t1, $s2, 0
    sw $t1, 8($s0)
    sw $s2, 12($s0)
.if \kind == 3
    dsrl32 $t1, $s3, 0
    sw $t1, 16($s0)
    sw $s3, 20($s0)
.else
    dsrl32 $t1, $ra, 0
    sw $t1, 16($s0)
    sw $ra, 20($s0)
.endif
    sw $s4, 24($s0)
    sw $zero, 28($s0)
    addiu $s0, $s0, 32
.endm
    sample 0, 0, 0
    sample 1, 1, 0
    sample 2, 2, 0
    sample 3, 3, 0
    sample 4, 4, 0
    sample 5, 4, -1
    sample 6, 5, -1
    sample 7, 5, 0
    sample 8, 6, 0
    sample 9, 6, -1
    sample 10, 7, -1
    sample 11, 7, 0
    lui $t0, 0xa000
    lui $t1, 0x4a46
    ori $t1, $t1, 0x474c
    sw $t1, 0x1000($t0)
done:
    b done
    nop
