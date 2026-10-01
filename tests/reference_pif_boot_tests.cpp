#include "jfg/boot/reference_pif_boot.hpp"
#include <initializer_list>
int main() {
  jfg::boot::ReferencePifBoot boot;
  if (boot.read() != 0 || boot.acknowledged()) return 1;
  for (unsigned command : {0U, 1U, 2U, 4U, 9U, 16U, 32U, 64U, 0xffffffffU})
    if (boot.write(command) || boot.acknowledged()) return 2;
  if (!boot.write(8) || boot.read() != 0 || !boot.acknowledged()) return 3;
  if (!boot.write(8) || boot.write(1) || boot.read() != 0 || !boot.acknowledged()) return 4;
  return 0;
}
