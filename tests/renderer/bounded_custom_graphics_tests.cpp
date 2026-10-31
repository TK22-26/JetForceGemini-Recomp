#include "jfg/runtime/bounded_custom_graphics.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <span>
#include <stdexcept>
#include <string_view>
#include <vector>

namespace {

[[noreturn]] void fail(const std::string_view message) {
    std::cerr << message << '\n';
    std::exit(EXIT_FAILURE);
}

void expect(const bool condition, const std::string_view message) {
    if (!condition) {
        fail(message);
    }
}

void append_be32(std::vector<std::byte>& bytes, const std::uint32_t value) {
    bytes.push_back(static_cast<std::byte>(value >> 24U));
    bytes.push_back(static_cast<std::byte>(value >> 16U));
    bytes.push_back(static_cast<std::byte>(value >> 8U));
    bytes.push_back(static_cast<std::byte>(value));
}

void append_command(
    std::vector<std::byte>& bytes,
    const std::uint32_t word0,
    const std::uint32_t word1) {
    append_be32(bytes, word0);
    append_be32(bytes, word1);
}

void store_command(
    std::vector<std::byte>& bytes,
    const std::size_t offset,
    const std::uint32_t word0,
    const std::uint32_t word1) {
    if (offset > bytes.size() || 8U > bytes.size() - offset) {
        fail("test command write is out of bounds");
    }
    for (std::size_t index = 0U; index < 4U; ++index) {
        const std::size_t shift = (3U - index) * 8U;
        bytes[offset + index] = static_cast<std::byte>(word0 >> shift);
        bytes[offset + 4U + index] = static_cast<std::byte>(word1 >> shift);
    }
}

[[nodiscard]] std::uint32_t read_be32(
    const std::span<const std::byte> bytes,
    const std::size_t offset) {
    return
        (std::to_integer<std::uint32_t>(bytes[offset]) << 24U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 1U]) << 16U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 2U]) << 8U) |
        std::to_integer<std::uint32_t>(bytes[offset + 3U]);
}

[[nodiscard]] std::uint64_t read_be64(
    const std::span<const std::byte> bytes,
    const std::size_t offset) {
    std::uint64_t value = 0U;
    for (std::size_t index = 0U; index < 8U; ++index) {
        value = (value << 8U) |
            std::to_integer<std::uint8_t>(bytes[offset + index]);
    }
    return value;
}

struct Fixture {
    std::array<std::byte, 64U> active_program{};
    std::array<std::byte, 64U> program_data{};
    std::vector<std::byte> command_stream;
    std::vector<std::byte> memory = std::vector<std::byte>(2048U);

    [[nodiscard]] jfg::GraphicsTaskView task() const noexcept {
        return {
            jfg::GraphicsFamily::bounded_custom,
            active_program,
            program_data,
            command_stream,
        };
    }
};

class CapturingOracle final : public jfg::GraphicsOutputOracle {
public:
    [[nodiscard]] bool validate(
        const jfg::GraphicsOutputView& output) override {
        ++calls;
        bytes.assign(output.bytes.begin(), output.bytes.end());
        kind = output.kind;
        width = output.width;
        height = output.height;
        return accept;
    }

    bool accept = true;
    jfg::GraphicsOutputKind kind = jfg::GraphicsOutputKind::unknown;
    std::size_t calls = 0U;
    std::size_t width = 0U;
    std::size_t height = 0U;
    std::vector<std::byte> bytes;
};

class Completion final : public jfg::GraphicsCompletionSink {
public:
    [[nodiscard]] bool prepare_renderer_complete(
        const std::size_t count) override {
        ++prepare_calls;
        prepared_count = count;
        return accept;
    }

    void commit_renderer_complete(const std::size_t count) noexcept override {
        ++commit_calls;
        committed_count = count;
    }

    bool accept = true;
    std::size_t prepare_calls = 0U;
    std::size_t commit_calls = 0U;
    std::size_t prepared_count = 0U;
    std::size_t committed_count = 0U;
};

class RejectingRenderer final : public jfg::BoundedCustomGraphicsRenderer {
public:
    [[nodiscard]] bool begin() override {
        if (throw_from_begin) {
            throw std::runtime_error("synthetic renderer begin failure");
        }
        return begin_accepts;
    }

    [[nodiscard]] bool submit(
        const jfg::BoundedGraphicsRendererEvent&,
        std::span<const std::byte>,
        jfg::BoundedGraphicsMemoryReader& memory) override {
        ++submit_calls;
        if (throw_from_submit) {
            throw std::runtime_error("synthetic renderer submit failure");
        }
        if (invalid_memory_read) {
            static_cast<void>(memory.read(0x7FFFFFU, 2U));
        }
        return submit_accepts;
    }

    [[nodiscard]] jfg::GraphicsOutputView finish(std::size_t) override {
        return {};
    }

    void abort() noexcept override {
        ++abort_calls;
    }

    bool begin_accepts = true;
    bool submit_accepts = false;
    bool invalid_memory_read = false;
    bool throw_from_begin = false;
    bool throw_from_submit = false;
    std::size_t submit_calls = 0U;
    std::size_t abort_calls = 0U;
};

[[nodiscard]] jfg::GraphicsTaskResult submit(
    const Fixture& fixture,
    jfg::BoundedCustomGraphicsRenderer& renderer,
    CapturingOracle& oracle,
    Completion& completion,
    const std::span<const jfg::BoundedGraphicsMemoryWindow> windows = {}) {
    const std::array<jfg::BoundedGraphicsMemoryWindow, 1U> default_windows{
        jfg::BoundedGraphicsMemoryWindow{7U, 0U, fixture.memory.size()},
    };
    const std::span<const jfg::BoundedGraphicsMemoryWindow> selected_windows =
        windows.empty() ?
            std::span<const jfg::BoundedGraphicsMemoryWindow>(default_windows) :
            windows;
    constexpr std::uint32_t command_address = 0x500U;
    std::vector<std::byte> memory = fixture.memory;
    if (fixture.command_stream.size() > memory.size() - command_address) {
        fail("test command stream does not fit memory");
    }
    std::copy(
        fixture.command_stream.begin(),
        fixture.command_stream.end(),
        memory.begin() + command_address);
    const std::array<jfg::GraphicsReferencedMemoryRegion, 1U> regions{
        jfg::GraphicsReferencedMemoryRegion{7U, memory},
    };
    jfg::BoundedCustomGraphicsBackend backend(
        selected_windows, command_address, renderer);
    return jfg::GraphicsTaskBridge{}.submit(
        fixture.task(), regions, backend, oracle, completion);
}

[[nodiscard]] Fixture complete_fixture() {
    Fixture fixture;
    append_command(fixture.command_stream, 0xBF000000U, 0U);
    append_command(fixture.command_stream, 0xBC000002U, 1U);
    append_command(fixture.command_stream, 0xBC00000AU, 2U << 6U);
    append_command(fixture.command_stream, 0x01820040U, 0x00000100U);
    append_command(fixture.command_stream, 0x02000000U, 0x00000180U);
    append_command(fixture.command_stream, 0x04100000U, 0x00000200U);
    append_command(fixture.command_stream, 0x05010000U, 0x00000300U);
    append_command(fixture.command_stream, 0x07010008U, 0x00000400U);
    append_command(fixture.command_stream, 0xB8000000U, 0U);
    store_command(fixture.memory, 0x400U, 0xE7000000U, 0U);
    for (std::size_t index = 0U; index < 64U; ++index) {
        fixture.memory[0x100U + index] = static_cast<std::byte>(index);
    }
    return fixture;
}

void test_complete_surface_and_variant() {
    Fixture fixture = complete_fixture();
    jfg::BoundedGraphicsSemanticRenderer renderer;
    CapturingOracle oracle;
    Completion completion;
    const jfg::GraphicsTaskResult result =
        submit(fixture, renderer, oracle, completion);
    expect(result.ok(), "complete bounded custom surface must pass");
    expect(result.parsed_command_count == 10U,
        "complete surface parsed count mismatch");
    expect(oracle.calls == 1U && completion.prepare_calls == 1U &&
        completion.commit_calls == 1U,
        "success must validate and complete exactly once");
    expect(oracle.kind == jfg::GraphicsOutputKind::semantic_submission &&
        oracle.width == jfg::kBoundedGraphicsSemanticRecordBytes &&
        oracle.height >= result.parsed_command_count,
        "semantic output shape mismatch");
    expect(oracle.bytes.size() ==
        oracle.height * jfg::kBoundedGraphicsSemanticRecordBytes,
        "semantic output byte count mismatch");

    std::array<std::size_t, 12U> event_counts{};
    bool saw_variant_count = false;
    bool saw_exact_matrix_payload = false;
    bool saw_matrix_slot = false;
    bool saw_matrix_multiply = false;
    std::size_t offset = 0U;
    while (offset < oracle.bytes.size()) {
        const std::size_t kind =
            std::to_integer<std::uint8_t>(oracle.bytes[offset]);
        const std::size_t command_count =
            std::to_integer<std::uint8_t>(oracle.bytes[offset + 3U]);
        const std::uint64_t payload_bytes =
            read_be64(oracle.bytes, offset + 16U);
        expect(command_count != 0U && command_count <= 4U,
            "semantic event command count is invalid");
        if (kind < event_counts.size()) {
            ++event_counts[kind];
        }
        if (kind == static_cast<std::size_t>(
                jfg::BoundedGraphicsEventKind::dma_vertex)) {
            saw_variant_count = read_be32(oracle.bytes, offset + 8U) == 2U;
        }
        if (kind == static_cast<std::size_t>(
                jfg::BoundedGraphicsEventKind::dma_matrix)) {
            saw_matrix_slot = read_be32(oracle.bytes, offset + 4U) == 2U;
            saw_matrix_multiply = read_be32(oracle.bytes, offset + 8U) == 1U;
            const std::size_t payload_offset = offset + command_count *
                jfg::kBoundedGraphicsSemanticRecordBytes;
            saw_exact_matrix_payload = payload_bytes == 64U &&
                payload_offset <= oracle.bytes.size() &&
                64U <= oracle.bytes.size() - payload_offset &&
                std::equal(
                    fixture.memory.begin() + 0x100U,
                    fixture.memory.begin() + 0x140U,
                    oracle.bytes.begin() +
                        static_cast<std::ptrdiff_t>(payload_offset));
        }
        const std::size_t payload_records =
            static_cast<std::size_t>(payload_bytes / 32U) +
            ((payload_bytes % 32U) != 0U ? 1U : 0U);
        offset += (command_count + payload_records) *
            jfg::kBoundedGraphicsSemanticRecordBytes;
    }
    expect(offset == oracle.bytes.size(),
        "semantic event framing is inconsistent");
    expect(event_counts[static_cast<std::size_t>(
        jfg::BoundedGraphicsEventKind::dma_matrix)] == 1U,
        "matrix handler was not observed");
    expect(saw_exact_matrix_payload && saw_matrix_slot &&
        saw_matrix_multiply,
        "matrix slot, multiply flag, and exact payload must be retained");
    expect(event_counts[static_cast<std::size_t>(
        jfg::BoundedGraphicsEventKind::dma_texture_offset)] == 1U,
        "texture-offset handler was not observed");
    expect(event_counts[static_cast<std::size_t>(
        jfg::BoundedGraphicsEventKind::dma_vertex)] == 1U &&
        saw_variant_count,
        "vertex count must decode JFG's direct encoded count field");
    expect(event_counts[static_cast<std::size_t>(
        jfg::BoundedGraphicsEventKind::dma_triangles)] == 1U,
        "triangle handler was not observed");
    expect(event_counts[static_cast<std::size_t>(
        jfg::BoundedGraphicsEventKind::dma_display_list)] == 1U,
        "counted-list handler was not observed");
    expect(event_counts[static_cast<std::size_t>(
        jfg::BoundedGraphicsEventKind::dma_offsets)] == 1U,
        "offset handler was not observed");
    expect(event_counts[static_cast<std::size_t>(
        jfg::BoundedGraphicsEventKind::billboard)] == 1U &&
        event_counts[static_cast<std::size_t>(
            jfg::BoundedGraphicsEventKind::model_matrix_select)] == 1U,
        "custom move-word semantics were not observed");
}

void test_jfg_vertex_cursor_and_encoded_start() {
    Fixture fixture;
    append_command(fixture.command_stream, 0xBF000000U, 0U);
    append_command(fixture.command_stream, 0x04080000U, 0x00000100U);
    append_command(fixture.command_stream, 0xBC000002U, 1U);
    append_command(fixture.command_stream, 0x04210400U, 0x00000120U);
    append_command(fixture.command_stream, 0x05000000U, 0x00000300U);
    append_command(fixture.command_stream, 0xBC000002U, 0U);
    append_command(fixture.command_stream, 0x04110200U, 0x00000160U);
    append_command(fixture.command_stream, 0xB8000000U, 0U);

    jfg::BoundedGraphicsSemanticRenderer renderer;
    CapturingOracle oracle;
    Completion completion;
    const jfg::GraphicsTaskResult result =
        submit(fixture, renderer, oracle, completion);
    expect(result.ok(), "JFG vertex cursor fixture must pass");

    std::vector<std::array<std::uint32_t, 3U>> vertices;
    std::size_t offset = 0U;
    while (offset < oracle.bytes.size()) {
        const std::size_t kind =
            std::to_integer<std::uint8_t>(oracle.bytes[offset]);
        const std::size_t command_count =
            std::to_integer<std::uint8_t>(oracle.bytes[offset + 3U]);
        const std::uint64_t payload_bytes =
            read_be64(oracle.bytes, offset + 16U);
        if (kind == static_cast<std::size_t>(
                jfg::BoundedGraphicsEventKind::dma_vertex)) {
            vertices.push_back({
                read_be32(oracle.bytes, offset + 4U),
                read_be32(oracle.bytes, offset + 8U),
                read_be32(oracle.bytes, offset + 12U),
            });
        }
        const std::size_t payload_records =
            static_cast<std::size_t>(payload_bytes / 32U) +
            ((payload_bytes % 32U) != 0U ? 1U : 0U);
        offset += (command_count + payload_records) *
            jfg::kBoundedGraphicsSemanticRecordBytes;
    }
    expect(vertices.size() == 3U,
        "JFG vertex fixture must emit three DMA vertex events");
    expect(vertices[0U][0U] == 0U && vertices[0U][1U] == 1U,
        "non-append JFG vertex load must reset to slot zero");
    expect(vertices[1U][0U] == 3U && vertices[1U][1U] == 4U,
        "billboard append must combine slot-one cursor and encoded start");
    expect(vertices[2U][0U] == 1U && vertices[2U][1U] == 2U,
        "triangle DMA must reset the JFG append cursor");
}

void test_unknown_command_fails_closed() {
    Fixture fixture;
    append_command(fixture.command_stream, 0x08000000U, 0U);
    append_command(fixture.command_stream, 0xB8000000U, 0U);
    jfg::BoundedGraphicsSemanticRenderer renderer;
    CapturingOracle oracle;
    Completion completion;
    const jfg::GraphicsTaskResult result =
        submit(fixture, renderer, oracle, completion);
    expect(result.error == jfg::GraphicsTaskError::unsupported_commands,
        "unknown opcode must be reported as unsupported");
    expect(oracle.calls == 0U && completion.commit_calls == 0U,
        "unknown opcode must not validate output or complete");
}

void test_malformed_matrix_fails_closed() {
    Fixture fixture;
    append_command(fixture.command_stream, 0x0100003FU, 0U);
    append_command(fixture.command_stream, 0xB8000000U, 0U);
    jfg::BoundedGraphicsSemanticRenderer renderer;
    CapturingOracle oracle;
    Completion completion;
    const jfg::GraphicsTaskResult result =
        submit(fixture, renderer, oracle, completion);
    expect(result.error == jfg::GraphicsTaskError::backend_rejected,
        "malformed matrix length must reject");
    expect(oracle.calls == 0U && completion.commit_calls == 0U,
        "malformed matrix must not complete");
}

void test_invalid_window_map_fails_closed() {
    Fixture fixture = complete_fixture();
    const std::array<jfg::BoundedGraphicsMemoryWindow, 2U> overlapping{
        jfg::BoundedGraphicsMemoryWindow{7U, 0U, 1024U},
        jfg::BoundedGraphicsMemoryWindow{8U, 512U, 1024U},
    };
    jfg::BoundedGraphicsSemanticRenderer renderer;
    CapturingOracle oracle;
    Completion completion;
    const jfg::GraphicsTaskResult result =
        submit(fixture, renderer, oracle, completion, overlapping);
    expect(result.error == jfg::GraphicsTaskError::backend_rejected,
        "overlapping address windows must reject");
}

void test_missing_end_and_trailing_commands_fail_closed() {
    Fixture missing_end;
    append_command(missing_end.command_stream, 0xE7000000U, 0U);
    jfg::BoundedGraphicsSemanticRenderer renderer;
    CapturingOracle oracle;
    Completion completion;
    expect(submit(missing_end, renderer, oracle, completion).error ==
        jfg::GraphicsTaskError::backend_rejected,
        "missing end must reject");

    Fixture trailing;
    append_command(trailing.command_stream, 0xB8000000U, 0U);
    append_command(trailing.command_stream, 0xE7000000U, 0U);
    expect(submit(trailing, renderer, oracle, completion).error ==
        jfg::GraphicsTaskError::backend_rejected,
        "commands after the top-level end must reject");
}

void test_counted_list_and_packet_bounds_fail_closed() {
    Fixture bad_count;
    append_command(bad_count.command_stream, 0x07010010U, 0x100U);
    append_command(bad_count.command_stream, 0xB8000000U, 0U);
    jfg::BoundedGraphicsSemanticRenderer renderer;
    CapturingOracle oracle;
    Completion completion;
    expect(submit(bad_count, renderer, oracle, completion).error ==
        jfg::GraphicsTaskError::backend_rejected,
        "inconsistent counted-list length must reject");

    Fixture short_rectangle;
    append_command(short_rectangle.command_stream, 0xE4000000U, 0U);
    append_command(short_rectangle.command_stream, 0xB4000000U, 0U);
    append_command(short_rectangle.command_stream, 0xB8000000U, 0U);
    expect(submit(short_rectangle, renderer, oracle, completion).error ==
        jfg::GraphicsTaskError::backend_rejected,
        "invalid texture-rectangle continuation must reject");
}

void test_unknown_shared_subtypes_fail_closed() {
    Fixture move_word;
    append_command(move_word.command_stream, 0xBC000003U, 0U);
    append_command(move_word.command_stream, 0xB8000000U, 0U);
    jfg::BoundedGraphicsSemanticRenderer renderer;
    CapturingOracle oracle;
    Completion completion;
    expect(submit(move_word, renderer, oracle, completion).error ==
        jfg::GraphicsTaskError::unsupported_commands,
        "unknown shared move-word subtype must reject");

    Fixture move_memory;
    append_command(move_memory.command_stream, 0x037F0000U, 0U);
    append_command(move_memory.command_stream, 0xB8000000U, 0U);
    expect(submit(move_memory, renderer, oracle, completion).error ==
        jfg::GraphicsTaskError::unsupported_commands,
        "unknown shared move-memory subtype must reject");
}

void test_renderer_and_renderer_memory_fail_closed() {
    Fixture fixture = complete_fixture();
    RejectingRenderer renderer;
    CapturingOracle oracle;
    Completion completion;
    const jfg::GraphicsTaskResult rejected =
        submit(fixture, renderer, oracle, completion);
    expect(rejected.error == jfg::GraphicsTaskError::backend_rejected &&
        renderer.abort_calls != 0U,
        "renderer rejection must abort the transaction");

    RejectingRenderer invalid_reader;
    invalid_reader.submit_accepts = true;
    invalid_reader.invalid_memory_read = true;
    const jfg::GraphicsTaskResult invalid =
        submit(fixture, invalid_reader, oracle, completion);
    expect(invalid.error == jfg::GraphicsTaskError::backend_rejected,
        "renderer out-of-bounds memory read must reject");

    RejectingRenderer throwing_begin;
    throwing_begin.throw_from_begin = true;
    const jfg::GraphicsTaskResult begin_exception =
        submit(fixture, throwing_begin, oracle, completion);
    expect(begin_exception.error == jfg::GraphicsTaskError::backend_exception &&
        throwing_begin.abort_calls == 1U,
        "renderer begin exception must abort the transaction");

    RejectingRenderer throwing_submit;
    throwing_submit.throw_from_submit = true;
    const jfg::GraphicsTaskResult submit_exception =
        submit(fixture, throwing_submit, oracle, completion);
    expect(submit_exception.error == jfg::GraphicsTaskError::backend_exception &&
        throwing_submit.abort_calls == 1U,
        "renderer submit exception must abort the transaction");
}

void test_oracle_rejection_prevents_completion() {
    Fixture fixture = complete_fixture();
    jfg::BoundedGraphicsSemanticRenderer renderer;
    CapturingOracle oracle;
    oracle.accept = false;
    Completion completion;
    const jfg::GraphicsTaskResult result =
        submit(fixture, renderer, oracle, completion);
    expect(result.error == jfg::GraphicsTaskError::output_rejected,
        "independent oracle rejection must surface");
    expect(completion.prepare_calls == 0U && completion.commit_calls == 0U,
        "oracle rejection must precede completion");
}

}  // namespace

int main() {
    test_complete_surface_and_variant();
    test_jfg_vertex_cursor_and_encoded_start();
    test_unknown_command_fails_closed();
    test_malformed_matrix_fails_closed();
    test_invalid_window_map_fails_closed();
    test_missing_end_and_trailing_commands_fail_closed();
    test_counted_list_and_packet_bounds_fail_closed();
    test_unknown_shared_subtypes_fail_closed();
    test_renderer_and_renderer_memory_fail_closed();
    test_oracle_rejection_prevents_completion();
    return EXIT_SUCCESS;
}
