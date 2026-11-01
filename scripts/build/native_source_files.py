"""Private native module inputs shared by current evidence producers.

Historical signed records retain their original inventories. This explicit list
binds current captures and rejects missing inputs rather than silently globbing.
"""

NATIVE_MODULE_FILES = (
    'src/boot/native/controller_input.cpp',
    'src/boot/native/event_journal.hpp',
    'src/boot/native/gameplay_scopes.hpp',
    'src/boot/native/generated_overlay_table.cpp',
    'src/boot/native/generated_overlay_table.hpp',
    'src/boot/native/guest_execution.cpp',
    'src/boot/native/guest_memory.cpp',
    'src/boot/native/guest_memory.hpp',
    'src/boot/native/host_audio_device.cpp',
    'src/boot/native/host_audio_device.hpp',
    'src/boot/native/live_frontend.cpp',
    'src/boot/native/live_tasks.cpp',
    'src/boot/native/live_window.cpp',
    'src/boot/native/live_window.hpp',
    'src/boot/native/overlay_loading.cpp',
    'src/boot/native/process_supervisor.cpp',
    'src/boot/native/process_supervisor.hpp',
    'src/boot/native/rom_image.cpp',
    'src/boot/native/runtime_constants.hpp',
    'src/boot/native/runtime_diagnostics.cpp',
    'src/boot/native/runtime_reports.cpp',
    'src/boot/native/runtime_services.hpp',
    'src/boot/native/runtime_state.hpp',
    'src/boot/native/save_storage.cpp',
)

NATIVE_MODULE_CLOSURE = (
    "scripts/build/native_source_files.py",
    "cmake/NativeTargets.cmake",
    "src/boot/flying_motion.inl",
) + NATIVE_MODULE_FILES
