/* Original, ROM-free post-effect observation fixtures. */
.set noreorder
.set noat
.text
.align 2
.globl effect_store
.type effect_store, @function
effect_store:
    addiu $v0, $zero, 7
    sw $v0, 0($a0)
    addiu $v0, $v0, 1
    jr $ra
    nop
.size effect_store, .-effect_store

.globl effect_branch
.type effect_branch, @function
effect_branch:
    beq $a1, $zero, 1f
    addiu $v0, $v0, 1
    addiu $v0, $v0, 2
1:  addiu $v0, $v0, 4
    jr $ra
    nop
.size effect_branch, .-effect_branch

.globl effect_likely
.type effect_likely, @function
effect_likely:
    beql $a1, $zero, 1f
    addiu $v0, $v0, 1
    addiu $v0, $v0, 2
1:  addiu $v0, $v0, 4
    jr $ra
    nop
.size effect_likely, .-effect_likely

.globl effect_caller
.type effect_caller, @function
effect_caller:
    or $s0, $ra, $zero
    jal effect_leaf
    addiu $v0, $v0, 1
    or $ra, $s0, $zero
    jr $ra
    nop
.size effect_caller, .-effect_caller

.globl effect_regcaller
.type effect_regcaller, @function
effect_regcaller:
    lui $t9, %hi(effect_leaf)
    addiu $t9, $t9, %lo(effect_leaf)
    or $s0, $ra, $zero
    jalr $t9
    or $t9, $zero, $zero
    or $ra, $s0, $zero
    jr $ra
    nop
.size effect_regcaller, .-effect_regcaller

.globl effect_tail
.type effect_tail, @function
effect_tail:
    jr $a2
    or $a2, $zero, $zero
.size effect_tail, .-effect_tail

.globl effect_condlink
.type effect_condlink, @function
effect_condlink:
    or $s0, $ra, $zero
    bgezal $a1, effect_leaf
    addiu $v0, $v0, 1
    or $ra, $s0, $zero
    jr $ra
    nop
.size effect_condlink, .-effect_condlink

.globl effect_likelylink
.type effect_likelylink, @function
effect_likelylink:
    or $s0, $ra, $zero
    bgezall $a1, effect_leaf
    addiu $v0, $v0, 1
    or $ra, $s0, $zero
    jr $ra
    nop
.size effect_likelylink, .-effect_likelylink

.globl effect_leaf
.type effect_leaf, @function
effect_leaf:
    jr $ra
    addiu $v0, $v0, 4
.size effect_leaf, .-effect_leaf
