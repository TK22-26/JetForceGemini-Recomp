/* Original, ROM-free interior-entry instruction-hook qualification. */
.set noreorder
.set noat
.text
.align 2
.globl continuation_effect
.type continuation_effect, @function
continuation_effect:
    addiu $v0, $v0, 1
    addiu $v0, $v0, 2
    addiu $v0, $v0, 4
    jr $ra
    nop
.size continuation_effect, .-continuation_effect
