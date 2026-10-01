ENTRY(clock_loop)
SECTIONS {
  . = 0x80000400;
  .text : AT(0) { *(.text) }
  /DISCARD/ : { *(.reginfo) *(.MIPS.abiflags) *(.pdr) *(.gnu.attributes) }
}
