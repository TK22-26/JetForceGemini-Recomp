#include <cstdio>
#include <exception>

extern "C" [[noreturn]] void __real___cxa_throw(
    void* exception_object, void* type_info, void (*destructor)(void*));

extern "C" [[noreturn]] void __wrap___cxa_throw(
    void* const exception_object,
    void* const type_info,
    void (*const destructor)(void*)) {
    const auto* const exception = static_cast<const std::exception*>(exception_object);
    std::fprintf(stderr, "phase4 throw: %s\n", exception->what());
    __real___cxa_throw(exception_object, type_info, destructor);
}
