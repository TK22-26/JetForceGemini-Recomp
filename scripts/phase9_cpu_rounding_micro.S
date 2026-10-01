/* Private diagnostic payload. Link at the normal N64 ROM entry 0x80000400.
 * It stores the exact operand, cvt.w.s result, FCR31, and a completion marker
 * at physical RDRAM 0x1000. No game code or progression is executed.
 */
    .set noreorder
    .set noat
    .text
    .globl _start
_start:
    mfc0    $t0, $12
    lui     $t1, 0x2000
    or      $t0, $t0, $t1
    mtc0    $t0, $12
    nop
    nop
    nop
    nop

    /* FCR31 RM=0; 0x440ba000 is precisely 558.5f. */
    ctc1    $zero, $31
    lui     $t0, 0x440b
    ori     $t0, $t0, 0xa000
    mtc1    $t0, $f4
    nop
    cvt.w.s $f6, $f4
    nop
    mfc1    $t2, $f6
    cfc1    $t4, $31

    lui     $t3, 0xa000
    ori     $t3, $t3, 0x1000
    sw      $t0, 0($t3)
    sw      $t2, 4($t3)
    sw      $t4, 8($t3)
    lui     $t5, 0x4a46
    ori     $t5, $t5, 0x4743
    sw      $t5, 12($t3)
1:
    b       1b
    nop
