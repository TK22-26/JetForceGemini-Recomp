/* Original ROM-free jump-table loads, duplicate targets and delay-slot tests. */
.set noreorder
.set noat
.text
.align 2
.macro dispatch name, clobber
.globl \name
.type \name,@function
\name:
    lui $at, %hi(\name\()_table)
    addu $at, $at, $a0
    lw $t2, %lo(\name\()_table)($at)
    or $s0, $t2, $zero
    jr $t2
.if \clobber
    addiu $t2, $zero, 7
.else
    or $a1, $t2, $zero
.endif
\name\()_case0:
    addiu $v0, $zero, 10
    jr $ra
    nop
\name\()_case1:
    addiu $v0, $zero, 20
    jr $ra
    nop
\name\()_case2:
    addiu $v0, $zero, 30
    jr $ra
    nop
.size \name,.-\name
\name\()_table:
    .word \name\()_case0, \name\()_case1, \name\()_case1, \name\()_case2
    .word 0
.endm
dispatch table_observe, 0
dispatch table_clobber, 1
