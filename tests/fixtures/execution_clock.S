/* Original ROM-free test. No game code. */
.set noreorder
.set noat
.text
.align 2
.globl clock_loop
.type clock_loop, @function
clock_loop:
    or      $v0, $zero, $zero
    or      $v1, $zero, $zero
    or      $t0, $a0, $zero
1:
    addiu   $v0, $v0, 1
    addiu   $t0, $t0, -1
    bgtz    $t0, 1b
    addiu   $v1, $v1, 1
    beql    $a0, $zero, 2f
    addiu   $v0, $v0, 100
2:
    jr      $ra
    nop
.size clock_loop, .-clock_loop

.globl clock_caller
.type clock_caller, @function
clock_caller:
    or      $t7, $ra, $zero
    jal     clock_loop
    nop
    or      $ra, $t7, $zero
    jr      $ra
    nop
.size clock_caller, .-clock_caller
