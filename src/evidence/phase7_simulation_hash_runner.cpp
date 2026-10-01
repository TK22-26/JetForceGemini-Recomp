#include "jfg/runtime/bounded_custom_graphics.hpp"
#include "jfg/runtime/graphics_task_bridge.hpp"
#include "jfg/testkernel/sha256.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <span>
#include <string>
#include <vector>

namespace {

[[nodiscard]] std::vector<std::byte> read_file(
    const std::filesystem::path& path) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream) {
        return {};
    }
    const std::streampos end = stream.tellg();
    if (end <= 0) {
        return {};
    }
    std::vector<std::byte> bytes(static_cast<std::size_t>(end));
    stream.seekg(0, std::ios::beg);
    stream.read(reinterpret_cast<char*>(bytes.data()),
        static_cast<std::streamsize>(bytes.size()));
    return stream ? bytes : std::vector<std::byte>{};
}

[[nodiscard]] std::uint32_t read_be32(
    const std::span<const std::byte> bytes,
    const std::size_t offset) noexcept {
    return
        (std::to_integer<std::uint32_t>(bytes[offset]) << 24U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 1U]) << 16U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 2U]) << 8U) |
        std::to_integer<std::uint32_t>(bytes[offset + 3U]);
}

class ExactOracle final : public jfg::GraphicsOutputOracle {
public:
    explicit ExactOracle(const std::span<const std::byte> expected) noexcept
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
        const std::size_t parsed) override {
        prepared_ = parsed != 0U;
        return prepared_;
    }

    void commit_renderer_complete(const std::size_t parsed) noexcept override {
        committed_ = prepared_ && parsed != 0U;
    }

    [[nodiscard]] bool committed() const noexcept {
        return committed_;
    }

private:
    bool prepared_ = false;
    bool committed_ = false;
};

}  // namespace

int main(const int argc, const char* const* argv) {
    if (argc != 4) {
        std::cerr << "usage: jfg-phase7-simulation-hash "
                     "<disabled|semantic> <capture-task-directory> "
                     "<independent-semantic-oracle>\n";
        return 2;
    }
    const std::string mode = argv[1];
    if (mode != "disabled" && mode != "semantic") {
        std::cerr << "simulation hash mode must be disabled or semantic\n";
        return 2;
    }

    const std::filesystem::path root = argv[2];
    const std::vector<std::byte> descriptor = read_file(root / "descriptor.bin");
    const std::vector<std::byte> commands = read_file(root / "commands.bin");
    const std::vector<std::byte> rdram = read_file(root / "rdram.bin");
    const std::vector<std::byte> active_program = read_file(root / "ucode.bin");
    const std::vector<std::byte> program_data = read_file(root / "ucode-data.bin");
    const std::vector<std::byte> expected = read_file(argv[3]);
    if (descriptor.size() != 64U || commands.empty() ||
        rdram.size() != jfg::kBoundedGraphicsAddressSpaceBytes ||
        active_program.empty() || program_data.empty() || expected.empty()) {
        std::cerr << "capture is incomplete or has invalid sizes\n";
        return 3;
    }

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

    const std::string hash_before = jfg::testkernel::hex_digest(
        jfg::testkernel::sha256_digest(rdram));
    std::size_t parsed_commands = 0U;
    bool oracle_match = false;
    bool completion_committed = false;
    if (mode == "semantic") {
        const std::array<jfg::BoundedGraphicsMemoryWindow, 1U> windows{
            jfg::BoundedGraphicsMemoryWindow{
                0U, 0U, jfg::kBoundedGraphicsAddressSpaceBytes},
        };
        const std::array<jfg::GraphicsReferencedMemoryRegion, 1U> regions{
            jfg::GraphicsReferencedMemoryRegion{0U, rdram},
        };
        jfg::BoundedGraphicsSemanticRenderer renderer;
        jfg::BoundedCustomGraphicsBackend backend(
            windows, command_address, renderer);
        ExactOracle oracle(expected);
        Completion completion;
        const jfg::GraphicsTaskResult result = jfg::GraphicsTaskBridge{}.submit(
            {
                jfg::GraphicsFamily::bounded_custom,
                active_program,
                program_data,
                commands,
            },
            regions,
            backend,
            oracle,
            completion);
        if (!result.ok() || !completion.committed()) {
            std::cerr << "semantic backend rejected captured task\n";
            return 5;
        }
        parsed_commands = result.parsed_command_count;
        oracle_match = true;
        completion_committed = true;
    }

    const std::string hash_after = jfg::testkernel::hex_digest(
        jfg::testkernel::sha256_digest(rdram));
    if (hash_after != hash_before) {
        std::cerr << "backend mutated the simulation-owned snapshot\n";
        return 6;
    }
    std::cout << "{\"status\":\"accepted\",\"mode\":\"" << mode
              << "\",\"parsed_commands\":" << parsed_commands
              << ",\"independent_semantic_oracle\":"
              << (oracle_match ? "true" : "false")
              << ",\"completion_committed\":"
              << (completion_committed ? "true" : "false")
              << ",\"simulation_hash\":\"" << hash_after << "\""
              << ",\"simulation_snapshot_unchanged\":true}\n";
    return 0;
}
