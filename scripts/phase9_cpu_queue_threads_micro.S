/* Original black-box SDK API experiment. Original OS bytes stay private.
 * Threads and queue are constructed by the ROM, never fabricated by the test.
 * US addresses are pinned by the private builder's source ROM digest.
 */
.set noreorder
.set noat
.text
.globl _start
.type _start, @function
.macro disable_interrupts
    mfc0 $t0, $12
    addiu $t1, $zero, -2
    and $t0, $t0, $t1
    mtc0 $t0, $12
    nop
    nop
    nop
.endm
.macro create_thread addr, ident, entry, stack, priority
    lui $a0, 0x8030
    ori $a0, $a0, \addr
    addiu $a1, $zero, \ident
    lui $a2, %hi(\entry)
    addiu $a2, $a2, %lo(\entry)
    or $a3, $zero, $zero
    lui $t0, 0x8030
    ori $t0, $t0, \stack
    sw $t0, 16($sp)
    addiu $t0, $zero, \priority
    sw $t0, 20($sp)
    jal 0x800759d0 /* osCreateThread */
    nop
.endm
.macro sample target, offset, argument, block
    or $a0, $s1, $zero
.if \argument == -1
    addiu $a1, $s0, 0x200
.else
    addiu $a1, $zero, \argument
.endif
    addiu $a2, $zero, \block
    mfc0 $s2, $9
    jal \target
    nop
    mfc0 $t4, $9
    subu $t4, $t4, $s2
    sw $t4, \offset($s0)
    sw $v0, \offset+4($s0)
    lw $t4, 8($s1)
    sw $t4, \offset+8($s0)
    mfc0 $t4, $12
    sw $t4, \offset+12($s0)
.endm
_start:
    lui $sp, 0x803f
    ori $sp, $sp, 0xf000
    addiu $sp, $sp, -32
    jal 0x80097520 /* osInitialize */
    nop
    disable_interrupts
    /* Clear only our private fixture storage, outside original static code. */
    lui $t0, 0x8030
    addiu $t1, $zero, 0x1800
1:
    sw $zero, 0($t0)
    addiu $t1, $t1, -4
    bnez $t1, 1b
    addiu $t0, $t0, 4
    lui $a0, 0x8030
    ori $a0, $a0, 0x1000
    addiu $a1, $a0, 0x100
    addiu $a2, $zero, 1
    jal 0x80096bb0 /* osCreateMesgQueue */
    nop
    create_thread 0, 1, main_thread, 0x8000, 30
    create_thread 0x200, 2, worker_thread, 0xc000, 40
    lui $a0, 0x8030
    jal 0x80096be0 /* osStartThread(main) */
    nop
2:
    b 2b
    nop
.size _start, .-_start
.globl main_thread
.type main_thread, @function
main_thread:
    mfc0 $t2, $12
    disable_interrupts
    lui $s0, 0x8030
    ori $s0, $s0, 0x1400
    sw $t2, 0x190($s0)
    lui $t0, 0xa430
    lw $t0, 12($t0)
    sw $t0, 0x198($s0)
    lui $s1, 0x8030
    ori $s1, $s1, 0x1000
    mfc0 $t0, $12
    sw $t0, 0x180($s0)
    lui $a0, 0x8030
    ori $a0, $a0, 0x200
    jal 0x80096be0 /* worker runs first, blocks on receive */
    nop
    lui $t0, 0xa430
    lw $t0, 12($t0)
    sw $t0, 0x1a0($s0)
    or $a0, $zero, $zero
    addiu $a1, $zero, 50
    jal 0x80097800 /* osSetThreadPri(main, 50) */
    nop
    sample 0x80096f20, 0, 1111, 0 /* wake lower-priority waiter */
    lw $t0, 0x100($s0)
    sw $t0, 0x184($s0) /* must still be zero: worker has not resumed */
    or $a0, $zero, $zero
    addiu $a1, $zero, 30
    jal 0x80097800 /* worker receives then blocks on its second receive */
    nop
    sample 0x80096f20, 16, 2222, 0 /* higher worker runs, then blocks sending */
    sample 0x80096910, 32, -1, 0 /* wakes full-queue sender */
    lw $t0, 0x200($s0)
    sw $t0, 0x108($s0)
    sample 0x80096910, 48, -1, 0
    lw $t0, 0x200($s0)
    sw $t0, 0x10c($s0)
    lui $t0, 0x4a46
    ori $t0, $t0, 0x4754
    sw $t0, 0x188($s0)
3:
    b 3b
    nop
.size main_thread, .-main_thread
.globl worker_thread
.type worker_thread, @function
worker_thread:
    mfc0 $t2, $12
    disable_interrupts
    lui $s0, 0x8030
    ori $s0, $s0, 0x1400
    sw $t2, 0x194($s0)
    lui $t0, 0xa430
    lw $t1, 12($t0)
    sw $t1, 0x19c($s0)
    addiu $t1, $zero, 1 /* clear only SP mask in this thread */
    sw $t1, 12($t0)
    lui $s1, 0x8030
    ori $s1, $s1, 0x1000
    mfc0 $t0, $12
    sw $t0, 0x18c($s0)
    sample 0x80096910, 64, -1, 1
    lui $t0, 0xa430
    lw $t0, 12($t0)
    sw $t0, 0x1a4($s0)
    lw $t0, 0x200($s0)
    sw $t0, 0x100($s0)
    sample 0x80096910, 80, -1, 1
    lui $t0, 0xa430
    lw $t0, 12($t0)
    sw $t0, 0x1a8($s0)
    lw $t0, 0x200($s0)
    sw $t0, 0x104($s0)
    sample 0x80096f20, 96, 3333, 0
    sample 0x80096f20, 112, 4444, 1
    or $a0, $zero, $zero
    jal 0x80096d30 /* osStopThread(self), main resumes */
    nop
4:
    b 4b
    nop
.size worker_thread, .-worker_thread
