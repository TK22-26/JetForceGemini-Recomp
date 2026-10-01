/* Original ROM-free architectural link-register test. */
.set noreorder
.set noat
.text
.align 2
.globl link_direct
.type link_direct, @function
link_direct:
    or $t7, $ra, $zero
    jal link_leaf
    or $v0, $ra, $zero
    or $ra, $t7, $zero
    jr $ra
    nop
.size link_direct, .-link_direct

.globl link_indirect
.type link_indirect, @function
link_indirect:
    lui $t9, %hi(link_leaf)
    addiu $t9, $t9, %lo(link_leaf)
    or $t7, $ra, $zero
    jalr $t9
    or $v0, $ra, $zero
    or $ra, $t7, $zero
    jr $ra
    nop
.size link_indirect, .-link_indirect

.globl link_clobber
.type link_clobber, @function
link_clobber:
    lui $t9, %hi(link_leaf)
    addiu $t9, $t9, %lo(link_leaf)
    or $t7, $ra, $zero
    jalr $t9
    or $t9, $zero, $zero
    or $v0, $ra, $zero
    or $ra, $t7, $zero
    jr $ra
    nop
.size link_clobber, .-link_clobber

.globl link_conditional
.type link_conditional, @function
link_conditional:
    or $t7, $ra, $zero
    bgezal $a0, link_leaf
    or $v0, $ra, $zero
    or $ra, $t7, $zero
    jr $ra
    nop
.size link_conditional, .-link_conditional

.globl link_likely
.type link_likely, @function
link_likely:
    or $t7, $ra, $zero
    bgezall $a0, link_leaf
    or $v0, $ra, $zero
    or $a1, $ra, $zero
    or $ra, $t7, $zero
    jr $ra
    nop
.size link_likely, .-link_likely

.globl link_tail
.type link_tail, @function
link_tail:
    j link_leaf
    or $v0, $ra, $zero
.size link_tail, .-link_tail

.globl link_leaf
.type link_leaf, @function
link_leaf:
    jr $ra
    or $v1, $ra, $zero
.size link_leaf, .-link_leaf

.globl link_saved_return
.type link_saved_return, @function
link_saved_return:
    or $s2, $ra, $zero
    jal link_leaf
    nop
    jr $s2
    addiu $v0, $zero, 42
.size link_saved_return, .-link_saved_return

.globl link_register_tail
.type link_register_tail, @function
link_register_tail:
    jr $a0
    or $a0, $zero, $zero
.size link_register_tail, .-link_register_tail
