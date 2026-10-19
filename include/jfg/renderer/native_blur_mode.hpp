#pragma once
#include <cstdlib>
#include <atomic>
#include "blur_settings.hpp"
namespace jfg {
// Private A/B only: 1 GPU-only, 2 CPU-texture composite, 3 GPU composite, 4 interpolated blur history.
// Mode 5 is a private source-only visual comparison, not an effect-preserving fix.
// Zero means no private override: use the persisted production blur preference.
inline unsigned diagnostic_blur_mode() {
    static const unsigned mode=[] {
#if defined(_MSC_VER)
        char* value=nullptr;std::size_t length=0;
        (void)_dupenv_s(&value,&length,"JFG_DIAGNOSTIC_BLUR");
#else
        const char* value=std::getenv("JFG_DIAGNOSTIC_BLUR");
#endif
        const unsigned result=value && value[0] && value[1]=='\0' &&
            (value[0]=='1'||value[0]=='2'||value[0]=='3'||value[0]=='4'||value[0]=='5') ? unsigned(value[0]-'0') : 0U;
#if defined(_MSC_VER)
        std::free(value);
#endif
        return result;
    }();
    return mode;
}
// Configured before renderer threads start. Kept separate from private diagnostics
// so a normal launch always honors the saved preference.
inline std::atomic<BlurMode>& native_blur_preference() {
    static std::atomic<BlurMode> mode{BlurMode::reduced};
    return mode;
}
inline void configure_native_blur(BlurMode mode) noexcept {
    native_blur_preference().store(mode, std::memory_order_relaxed);
}
inline unsigned native_blur_render_mode() {
    const auto diagnostic = diagnostic_blur_mode();
    if (diagnostic) return diagnostic;
    return native_blur_preference().load(std::memory_order_relaxed) == BlurMode::off ? 5U : 4U;
}
inline std::uint32_t configured_blur_color(std::uint32_t color) {
    if (diagnostic_blur_mode()) return color;
    return blur_color_word(native_blur_preference().load(std::memory_order_relaxed), color);
}

}
