/* Original, ROM-free CPU state visibility across generated function boundaries. */
.set noreorder
.set noat
.text
.macro begin name
.globl \name
.type \name, @function
\name:
.endm
.macro end name
    jr $ra
    nop
.size \name, .-\name
.endm
begin state_read
    mfhi $v0
    mflo $v1
end state_read
begin state_write
    mthi $a0
    mtlo $a1
end state_write
.irp operation,mult,multu,dmult,dmultu
begin state_\operation
    \operation $a0, $a1
end state_\operation
.endr
.irp operation,div,divu,ddiv,ddivu
begin state_\operation
    \operation $zero, $a0, $a1
end state_\operation
.endr
begin state_fp_compare
    c.eq.s $f0, $f2
end state_fp_compare
begin state_fp_read
    cfc1 $v0, $31
end state_fp_read
begin state_fp_write
    ctc1 $a0, $31
end state_fp_write
begin state_fp_branch
    or $v0, $zero, $zero
    bc1t 1f
    nop
    jr $ra
    nop
1:
    addiu $v0, $zero, 1
end state_fp_branch
