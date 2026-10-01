#pragma once

// The public RSP evidence case format is intentionally only an inventory
// format.  It contains no expected observations, exit status, or approval bit.
namespace jfg::evidence {
inline constexpr unsigned g2_rsp_case_version = 1;
}
