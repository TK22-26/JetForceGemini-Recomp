#include "jfg/renderer/rt64_shell.hpp"
#include "jfg/renderer/rt64_callbacks.hpp"
#include "jfg/testkernel/sha256.hpp"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <array>
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace {

[[nodiscard]] std::vector<std::byte> read_file(
    const std::filesystem::path& path) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream) {
        return {};
    }
    const std::streamoff length = stream.tellg();
    if (length <= 0) {
        return {};
    }
    std::vector<std::byte> bytes(static_cast<std::size_t>(length));
    stream.seekg(0);
    stream.read(reinterpret_cast<char*>(bytes.data()), length);
    return stream ? bytes : std::vector<std::byte>{};
}

[[nodiscard]] bool write_file(
    const std::filesystem::path& path,
    const std::span<const std::byte> bytes) {
    std::ofstream stream(path, std::ios::binary);
    if (!stream) {
        return false;
    }
    stream.write(
        reinterpret_cast<const char*>(bytes.data()),
        static_cast<std::streamsize>(bytes.size()));
    return static_cast<bool>(stream);
}

[[nodiscard]] std::uint32_t read_be32(
    const std::span<const std::byte> bytes,
    const std::size_t offset) noexcept {
    if (offset > bytes.size() || bytes.size() - offset < 4U) {
        return 0U;
    }
    return
        (std::to_integer<std::uint32_t>(bytes[offset]) << 24U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 1U]) << 16U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 2U]) << 8U) |
        std::to_integer<std::uint32_t>(bytes[offset + 3U]);
}

[[nodiscard]] bool write_ppm(
    const std::filesystem::path& path,
    const jfg::Rt64FrameView frame) {
    if (!frame.valid()) {
        return false;
    }
    std::ofstream stream(path, std::ios::binary);
    if (!stream) {
        return false;
    }
    stream << "P6\n" << frame.width << ' ' << frame.height << "\n255\n";
    for (std::size_t y = 0U; y < frame.height; ++y) {
        const std::size_t row = y * frame.row_pitch_bytes;
        for (std::size_t x = 0U; x < frame.width; ++x) {
            const std::size_t pixel = row + x * 4U;
            const std::array<char, 3U> rgb{
                static_cast<char>(std::to_integer<unsigned char>(
                    frame.bgra8[pixel + 2U])),
                static_cast<char>(std::to_integer<unsigned char>(
                    frame.bgra8[pixel + 1U])),
                static_cast<char>(std::to_integer<unsigned char>(
                    frame.bgra8[pixel])),
            };
            stream.write(rgb.data(), static_cast<std::streamsize>(rgb.size()));
        }
    }
    return static_cast<bool>(stream);
}

[[nodiscard]] bool read_vi_registers(
    const std::filesystem::path& path,
    jfg::Rt64ViRegisters& vi) {
    const std::vector<std::byte> bytes = read_file(path);
    if (bytes.size() != 14U * sizeof(std::uint32_t)) {
        return false;
    }
    vi = {
        read_be32(bytes, 0U * 4U),
        read_be32(bytes, 1U * 4U),
        read_be32(bytes, 2U * 4U),
        read_be32(bytes, 3U * 4U),
        read_be32(bytes, 4U * 4U),
        read_be32(bytes, 5U * 4U),
        read_be32(bytes, 6U * 4U),
        read_be32(bytes, 7U * 4U),
        read_be32(bytes, 8U * 4U),
        read_be32(bytes, 9U * 4U),
        read_be32(bytes, 10U * 4U),
        read_be32(bytes, 11U * 4U),
        read_be32(bytes, 12U * 4U),
        read_be32(bytes, 13U * 4U),
    };
    return true;
}

LRESULT CALLBACK window_proc(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam) {
    return DefWindowProcW(window, message, wparam, lparam);
}

class ExactOracle final : public jfg::GraphicsOutputOracle {
public:
    explicit ExactOracle(std::span<const std::byte> expected) noexcept
        : expected_(expected) {}

    [[nodiscard]] bool validate(
        const jfg::GraphicsOutputView& output) override {
        return output.kind == jfg::GraphicsOutputKind::semantic_submission &&
            output.bytes.size() == expected_.size() &&
            std::equal(output.bytes.begin(), output.bytes.end(), expected_.begin());
    }

private:
    std::span<const std::byte> expected_;
};

class Completion final : public jfg::GraphicsCompletionSink {
public:
    [[nodiscard]] bool prepare_renderer_complete(
        const std::size_t parsed_command_count) override {
        prepared_ = parsed_command_count != 0U;
        return prepared_;
    }

    void commit_renderer_complete(
        const std::size_t parsed_command_count) noexcept override {
        committed_ = prepared_ && parsed_command_count != 0U;
    }

    [[nodiscard]] bool committed() const noexcept {
        return committed_;
    }

private:
    bool prepared_ = false;
    bool committed_ = false;
};

class HiddenWindow final {
public:
    HiddenWindow() {
        instance_ = GetModuleHandleW(nullptr);
        WNDCLASSW window_class{};
        window_class.lpfnWndProc = &window_proc;
        window_class.hInstance = instance_;
        window_class.lpszClassName = class_name_;
        atom_ = RegisterClassW(&window_class);
        if (atom_ != 0U) {
            constexpr DWORD window_style = WS_OVERLAPPEDWINDOW;
            RECT window_rect{0, 0, 640, 480};
            if (AdjustWindowRectEx(
                    &window_rect, window_style, FALSE, 0U) == FALSE) {
                return;
            }
            window_ = CreateWindowExW(
                0U,
                class_name_,
                L"JFG Phase 7 RT64 task",
                window_style,
                CW_USEDEFAULT,
                CW_USEDEFAULT,
                window_rect.right - window_rect.left,
                window_rect.bottom - window_rect.top,
                nullptr,
                nullptr,
                instance_,
                nullptr);
        }
    }

    ~HiddenWindow() {
        if (window_ != nullptr) {
            DestroyWindow(window_);
        }
        if (atom_ != 0U) {
            UnregisterClassW(class_name_, instance_);
        }
    }

    HiddenWindow(const HiddenWindow&) = delete;
    HiddenWindow& operator=(const HiddenWindow&) = delete;

    [[nodiscard]] HWND get() const noexcept {
        return window_;
    }

private:
    static constexpr wchar_t class_name_[] = L"JfgPhase7Rt64TaskWindow";
    HINSTANCE instance_ = nullptr;
    ATOM atom_ = 0U;
    HWND window_ = nullptr;
};

[[nodiscard]] bool parse_hex_u32(
    const char* const text,
    std::uint32_t& output) noexcept {
    try {
        std::size_t parsed = 0U;
        const std::string input(text);
        const unsigned long value = std::stoul(input, &parsed, 16);
        if (parsed != input.size() || value > UINT32_MAX) {
            return false;
        }
        output = static_cast<std::uint32_t>(value);
        return true;
    }
    catch (...) {
        return false;
    }
}

[[nodiscard]] bool parse_hex_u32_list(
    const char* const text,
    std::vector<std::uint32_t>& output) noexcept {
    const std::string input(text);
    std::size_t begin = 0U;
    while (begin < input.size()) {
        const std::size_t separator = input.find(',', begin);
        const std::string value = input.substr(
            begin, separator == std::string::npos
                       ? std::string::npos
                       : separator - begin);
        std::uint32_t parsed = 0U;
        if (value.empty() || !parse_hex_u32(value.c_str(), parsed)) {
            return false;
        }
        output.push_back(parsed);
        if (separator == std::string::npos) {
            return true;
        }
        begin = separator + 1U;
    }
    return false;
}

[[nodiscard]] bool apply_word_patches(
    const char* const text,
    std::vector<std::byte>& rdram) noexcept {
    const std::string input(text);
    std::size_t begin = 0U;
    while (begin < input.size()) {
        const std::size_t separator = input.find(',', begin);
        const std::string item = input.substr(
            begin, separator == std::string::npos
                       ? std::string::npos
                       : separator - begin);
        const std::size_t equals = item.find('=');
        std::uint32_t address = 0U;
        std::uint32_t value = 0U;
        if (equals == std::string::npos ||
            !parse_hex_u32(item.substr(0U, equals).c_str(), address) ||
            !parse_hex_u32(item.substr(equals + 1U).c_str(), value) ||
            (address & 3U) != 0U || address > rdram.size() ||
            rdram.size() - address < sizeof(value)) {
            return false;
        }
        rdram[address] = static_cast<std::byte>(value >> 24U);
        rdram[address + 1U] = static_cast<std::byte>(value >> 16U);
        rdram[address + 2U] = static_cast<std::byte>(value >> 8U);
        rdram[address + 3U] = static_cast<std::byte>(value);
        if (separator == std::string::npos) {
            return true;
        }
        begin = separator + 1U;
    }
    return false;
}

int replay_live_snapshot(const int argc, const char* const* argv) {
    std::vector<std::byte> rdram = read_file(argv[2]);
    std::uint32_t ucode = 0U;
    std::uint32_t ucode_data = 0U;
    std::vector<std::uint32_t> command_addresses;
    std::uint32_t vi_origin = 0U;
    std::uint32_t vi_width = 320U;
    const std::string vi_spec(argv[6]);
    const std::size_t vi_separator = vi_spec.find(':');
    const std::string vi_origin_text = vi_spec.substr(0U, vi_separator);
    const std::string vi_width_text = vi_separator == std::string::npos
        ? std::string{}
        : vi_spec.substr(vi_separator + 1U);
    if (rdram.size() != jfg::kRt64RequiredRdramBytes ||
        !parse_hex_u32(argv[3], ucode) ||
        !parse_hex_u32(argv[4], ucode_data) ||
        !parse_hex_u32_list(argv[5], command_addresses) ||
        !parse_hex_u32(vi_origin_text.c_str(), vi_origin) ||
        (!vi_width_text.empty() &&
         !parse_hex_u32(vi_width_text.c_str(), vi_width)) ||
        vi_width == 0U || vi_width > 4096U) {
        std::cerr << "snapshot or hexadecimal argument is invalid\n";
        return 3;
    }
    if (argc >= 9 && !apply_word_patches(argv[8], rdram)) {
        std::cerr << "snapshot word patch is invalid\n";
        return 3;
    }

    HiddenWindow window;
    if (window.get() == nullptr) {
        std::cerr << "unable to create RT64 host window\n";
        return 5;
    }
    std::array<std::byte, jfg::kRt64RequiredHeaderBytes> header{};
    jfg::Rt64ViRegisters vi{
        0x0000'320EU, vi_origin, vi_width, 2U, 0U, 0x03E5'2239U,
        525U, 0x0000'0C15U, 0x0C15'0C15U, 0x006C'02ECU,
        0x0025'01FFU, 0x000E'0204U, 0x0000'0200U, 0x0000'0400U,
    };
    jfg::Rt64ShellError error = jfg::Rt64ShellError::none;
    std::unique_ptr<jfg::Rt64Shell> shell = jfg::Rt64Shell::create(
        {window.get(), GetCurrentThreadId(), header, rdram, &vi, true,
         jfg::Rt64MemoryLayout::big_endian},
        error);
    if (shell == nullptr) {
        std::cerr << "RT64 setup failed: "
                  << jfg::rt64_shell_error_message(error) << '\n';
        return 6;
    }
    for (std::size_t index = 0U; index < command_addresses.size(); ++index) {
        if (index != 0U) {
            error = shell->replace_rdram_snapshot(
                rdram, jfg::Rt64MemoryLayout::big_endian);
            if (error != jfg::Rt64ShellError::none) {
                break;
            }
        }
        const std::uint32_t commands = command_addresses[index];
        error = shell->submit({ucode, ucode_data, commands});
        if (error != jfg::Rt64ShellError::none) {
            break;
        }
    }
    if (error == jfg::Rt64ShellError::none && argc == 10) {
        std::vector<std::byte> private_rdram(jfg::kRt64RequiredRdramBytes);
        error = shell->copy_private_rdram_snapshot(
            private_rdram, jfg::Rt64MemoryLayout::big_endian);
        if (error == jfg::Rt64ShellError::none &&
            !write_file(argv[9], private_rdram)) {
            std::cerr << "unable to write private RDRAM snapshot\n";
            return 9;
        }
    }
    if (error == jfg::Rt64ShellError::none) {
        error = shell->present(false);
    }
    if (error == jfg::Rt64ShellError::none) {
        error = shell->present(true);
    }
    const jfg::Rt64FrameView frame = shell->last_presented_frame();
    if (error != jfg::Rt64ShellError::none || !frame.valid() ||
        !write_ppm(argv[7], frame)) {
        std::cerr << "RT64 snapshot replay failed: "
                  << jfg::rt64_shell_error_message(error) << '\n';
        return 9;
    }
    const jfg::Rt64GraphicsDiagnostics diagnostics =
        shell->last_graphics_diagnostics();
    std::cout << "{\"status\":\"accepted\",\"matrix_commands\":"
              << diagnostics.matrix_commands
              << ",\"vertex_batches\":" << diagnostics.vertex_batches
              << ",\"vertices_loaded\":" << diagnostics.vertices_loaded
              << ",\"triangle_batches\":" << diagnostics.triangle_batches
              << ",\"triangles_drawn\":" << diagnostics.triangles_drawn
              << ",\"color_image_address\":"
              << diagnostics.color_image_address
              << ",\"frame_width\":" << frame.width
              << ",\"frame_height\":" << frame.height << "}\n";
    return 0;
}

}  // namespace

int main(const int argc, const char* const* argv) {
    if ((argc == 8 || argc == 9 || argc == 10) &&
        std::string_view(argv[1]) == "--snapshot") {
        return replay_live_snapshot(argc, argv);
    }
    if (argc != 3 && argc != 5) {
        std::cerr << "usage: jfg-phase7-rt64-task "
                     "<capture-task-directory> <independent-semantic-oracle> "
                     "[vi-registers.bin-or-origin-hex output.ppm]\n"
                     "       jfg-phase7-rt64-task --snapshot "
                     "<rdram.bin> <ucode-hex> <ucode-data-hex> "
                     "<commands-hex-list> <vi-origin[:width]-hex> <output.ppm> "
                     "[address=word,...] [private-rdram-output]\n";
        return 2;
    }
    const std::filesystem::path root = argv[1];
    const std::vector<std::byte> descriptor = read_file(root / "descriptor.bin");
    const std::vector<std::byte> commands = read_file(root / "commands.bin");
    const std::vector<std::byte> rdram = read_file(root / "rdram.bin");
    const std::vector<std::byte> active_program = read_file(root / "ucode.bin");
    const std::vector<std::byte> program_data = read_file(root / "ucode-data.bin");
    const std::vector<std::byte> expected_semantics = read_file(argv[2]);
    if (descriptor.size() != 64U || commands.empty() ||
        rdram.size() != jfg::kRt64RequiredRdramBytes ||
        active_program.empty() || program_data.empty() ||
        expected_semantics.empty()) {
        std::cerr << "capture is incomplete or has invalid sizes\n";
        return 3;
    }
    const std::string simulation_hash_before =
        jfg::testkernel::hex_digest(
            jfg::testkernel::sha256_digest(rdram));

    constexpr std::uint32_t address_mask = 0x00FF'FFFFU;
    const std::uint32_t command_address =
        read_be32(descriptor, 0x30U) & address_mask;
    if (command_address > rdram.size() ||
        commands.size() > rdram.size() - command_address ||
        !std::equal(commands.begin(), commands.end(),
            rdram.begin() + static_cast<std::ptrdiff_t>(command_address))) {
        std::cerr << "captured command stream does not match RDRAM\n";
        return 4;
    }

    HiddenWindow window;
    if (window.get() == nullptr) {
        std::cerr << "unable to create RT64 host window\n";
        return 5;
    }
    std::array<std::byte, jfg::kRt64RequiredHeaderBytes> header{};
    jfg::Rt64ViRegisters vi;
    const bool present_frame = argc == 5;
    if (present_frame) {
        const std::filesystem::path vi_input = argv[3];
        if (std::filesystem::exists(vi_input)) {
            if (!read_vi_registers(vi_input, vi)) {
                std::cerr << "VI register body must contain fourteen big-endian words\n";
                return 6;
            }
        }
        else {
            try {
                vi.origin = static_cast<std::uint32_t>(
                    std::stoul(argv[3], nullptr, 16));
            }
            catch (...) {
                std::cerr << "VI origin is not a hexadecimal integer\n";
                return 6;
            }
            vi.status = 0x0000'320EU;
            vi.width = 320U;
            vi.vertical_sync = 525U;
            vi.horizontal_sync = 0x0000'0C15U;
            vi.horizontal_start = 0x006C'02ECU;
            vi.vertical_start = 0x0025'01FFU;
            vi.x_scale = 0x0000'0200U;
            vi.y_scale = 0x0000'0400U;
        }
    }
    jfg::Rt64ShellError error = jfg::Rt64ShellError::none;
    std::unique_ptr<jfg::Rt64Shell> shell = jfg::Rt64Shell::create(
        {
            window.get(),
            GetCurrentThreadId(),
            header,
            rdram,
            &vi,
            true,
            jfg::Rt64MemoryLayout::big_endian,
        },
        error);
    if (shell == nullptr) {
        std::cerr << "RT64 setup failed: "
                  << jfg::rt64_shell_error_message(error) << '\n';
        return 6;
    }

    const jfg::Rt64GraphicsTask rt64_task{
        read_be32(descriptor, 0x10U) & address_mask,
        read_be32(descriptor, 0x18U) & address_mask,
        command_address,
    };
    const std::array<jfg::BoundedGraphicsMemoryWindow, 1U> windows{
        jfg::BoundedGraphicsMemoryWindow{
            0U, 0U, jfg::kRt64RequiredRdramBytes},
    };
    const std::array<jfg::GraphicsReferencedMemoryRegion, 1U> regions{
        jfg::GraphicsReferencedMemoryRegion{0U, rdram},
    };
    jfg::Rt64GraphicsBackend backend(
        *shell,
        windows,
        0U,
        rt64_task,
        jfg::Rt64MemoryLayout::big_endian);
    ExactOracle oracle(expected_semantics);
    Completion completion;
    jfg::Rt64RendererCallbacks callbacks(
        *shell, backend, oracle, completion);
    jfg::RendererCallbackRuntime runtime;
    if (runtime.register_callbacks(callbacks) !=
        jfg::RendererCallbackError::none) {
        std::cerr << "unable to register renderer callbacks\n";
        return 7;
    }
    const jfg::RendererSubmissionResult submission = runtime.submit(
        {
            jfg::GraphicsFamily::bounded_custom,
            active_program,
            program_data,
            commands,
        },
        regions);
    if (!submission.ok() || !completion.committed()) {
        std::cerr << "RT64 bridge task failed: "
                  << jfg::graphics_task_error_message(submission.task.error)
                  << "; RT64: "
                  << jfg::rt64_shell_error_message(backend.last_rt64_error())
                  << '\n';
        return 8;
    }
    jfg::Rt64FrameView frame;
    if (present_frame) {
        const jfg::RendererCallbackError present_error = runtime.present();
        frame = shell->last_presented_frame();
        if (present_error != jfg::RendererCallbackError::none ||
            !frame.valid() || !write_ppm(argv[4], frame)) {
            std::cerr << "RT64 presentation or frame write failed: "
                      << jfg::renderer_callback_error_message(present_error)
                      << '\n';
            return 9;
        }
    }
    const jfg::Rt64GraphicsDiagnostics diagnostics =
        shell->last_graphics_diagnostics();
    const std::string simulation_hash_after =
        jfg::testkernel::hex_digest(
            jfg::testkernel::sha256_digest(rdram));
    if (simulation_hash_after != simulation_hash_before) {
        std::cerr << "renderer mutated the simulation-owned snapshot\n";
        return 10;
    }
    std::cout << "{\"status\":\"accepted\",\"parsed_commands\":"
              << submission.task.parsed_command_count
              << ",\"custom_commands\":"
              << shell->last_command_count()
              << ",\"unsupported_commands\":0"
              << ",\"matrix_commands\":" << diagnostics.matrix_commands
              << ",\"vertex_batches\":" << diagnostics.vertex_batches
              << ",\"vertices_loaded\":" << diagnostics.vertices_loaded
              << ",\"vertices_finite\":" << diagnostics.vertices_finite
              << ",\"vertices_in_clip\":" << diagnostics.vertices_in_clip
              << ",\"triangle_batches\":" << diagnostics.triangle_batches
              << ",\"triangles_drawn\":" << diagnostics.triangles_drawn
              << ",\"dma_display_lists\":"
              << diagnostics.dma_display_lists
              << ",\"independent_semantic_oracle\":true"
              << ",\"completion_committed\":true"
              << ",\"simulation_hash\":\"" << simulation_hash_after << "\""
              << ",\"simulation_snapshot_unchanged\":true"
              << ",\"developer_debugger\":"
              << (shell->developer_debugger_available() ? "true" : "false")
              << ",\"frame_presented\":"
              << (present_frame ? "true" : "false")
              << ",\"frame_width\":" << frame.width
              << ",\"frame_height\":" << frame.height
              << ",\"vi_framebuffer_width\":"
              << shell->last_framebuffer().width
              << ",\"vi_framebuffer_height\":"
              << shell->last_framebuffer().height
              << ",\"rt64_revision\":\"" << jfg::kPinnedRt64Revision
              << "\"}\n";
    return 0;
}
