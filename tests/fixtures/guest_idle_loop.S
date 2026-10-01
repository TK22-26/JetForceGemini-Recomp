.set noreorder
.set noat
.text
.globl idle_branch
.type idle_branch, @function
idle_branch:
    b idle_branch
    addiu $v0, $v0, 1
.size idle_branch, .-idle_branch
.globl idle_jump
.type idle_jump, @function
idle_jump:
    j idle_jump
    addiu $v0, $v0, 1
.size idle_jump, .-idle_jump
