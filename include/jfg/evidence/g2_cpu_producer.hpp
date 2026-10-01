#pragma once

// A public, ROM-free inventory format for the CPU G2 producer.  It contains
// measured G3 compiler-product and audit records only; it has no pass bit or
// expected result and makes no claim that this producer used those compilers.
namespace jfg::evidence {
inline constexpr unsigned g2_cpu_case_version = 4;
}
