#include "jfg/runtime/bounded_custom_graphics.hpp"

#include <algorithm>
#include <array>
#include <limits>

namespace jfg {
namespace {

constexpr std::uint32_t kAddressMask =
    kBoundedGraphicsAddressSpaceBytes - 1U;
constexpr std::uint8_t kOpDmaMatrix = 0x01U;
constexpr std::uint8_t kOpDmaTextureOffset = 0x02U;
constexpr std::uint8_t kOpMoveMemory = 0x03U;
constexpr std::uint8_t kOpDmaVertex = 0x04U;
constexpr std::uint8_t kOpDmaTriangles = 0x05U;
constexpr std::uint8_t kOpDisplayList = 0x06U;
constexpr std::uint8_t kOpDmaDisplayList = 0x07U;
constexpr std::uint8_t kOpEndDisplayList = 0xB8U;
constexpr std::uint8_t kOpMoveWord = 0xBCU;
constexpr std::uint8_t kOpDmaOffsets = 0xBFU;
constexpr std::uint8_t kMoveWordBillboard = 0x02U;
constexpr std::uint8_t kMoveWordSegment = 0x06U;
constexpr std::uint8_t kMoveWordModelMatrix = 0x0AU;
constexpr std::uint8_t kMoveMemoryForceMatrix = 0x9EU;
constexpr std::uint8_t kTextureRectangle = 0xE4U;
constexpr std::uint8_t kTextureRectangleFlip = 0xE5U;

[[nodiscard]] std::uint32_t read_be32(
    const std::span<const std::byte> bytes,
    const std::size_t offset) noexcept {
    return
        (std::to_integer<std::uint32_t>(bytes[offset]) << 24U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 1U]) << 16U) |
        (std::to_integer<std::uint32_t>(bytes[offset + 2U]) << 8U) |
        std::to_integer<std::uint32_t>(bytes[offset + 3U]);
}

void write_be32(
    std::vector<std::byte>& bytes,
    const std::size_t offset,
    const std::uint32_t value) noexcept {
    bytes[offset] = static_cast<std::byte>(value >> 24U);
    bytes[offset + 1U] = static_cast<std::byte>(value >> 16U);
    bytes[offset + 2U] = static_cast<std::byte>(value >> 8U);
    bytes[offset + 3U] = static_cast<std::byte>(value);
}

void write_be64(
    std::vector<std::byte>& bytes,
    const std::size_t offset,
    const std::uint64_t value) noexcept {
    for (std::size_t index = 0U; index < 8U; ++index) {
        bytes[offset + index] = static_cast<std::byte>(
            value >> ((7U - index) * 8U));
    }
}

[[nodiscard]] bool fixed_base_opcode(const std::uint8_t opcode) noexcept {
    switch (opcode) {
    case 0x00U:
    case kOpMoveMemory:
    case 0x09U:
    case 0xB2U:
    case 0xB3U:
    case 0xB4U:
    case 0xB5U:
    case 0xB6U:
    case 0xB7U:
    case 0xB9U:
    case 0xBAU:
    case 0xBBU:
    case kOpMoveWord:
    case 0xBDU:
    case 0xBEU:
    case 0xC0U:
    case 0xE4U:
    case 0xE5U:
    case 0xE6U:
    case 0xE7U:
    case 0xE8U:
    case 0xE9U:
    case 0xEAU:
    case 0xEBU:
    case 0xECU:
    case 0xEDU:
    case 0xEEU:
    case 0xEFU:
    case 0xF0U:
    case 0xF2U:
    case 0xF3U:
    case 0xF4U:
    case 0xF5U:
    case 0xF6U:
    case 0xF7U:
    case 0xF8U:
    case 0xF9U:
    case 0xFAU:
    case 0xFBU:
    case 0xFCU:
    case 0xFDU:
    case 0xFEU:
    case 0xFFU:
        return true;
    default:
        return false;
    }
}

[[nodiscard]] bool known_move_memory_subtype(
    const std::uint8_t subtype) noexcept {
    return subtype == 0x80U || subtype == 0x82U || subtype == 0x84U ||
        (subtype >= 0x86U && subtype <= 0x96U &&
            (subtype & 1U) == 0U) ||
        subtype == 0x98U || subtype == 0x9AU || subtype == 0x9CU ||
        subtype == kMoveMemoryForceMatrix;
}

[[nodiscard]] bool known_base_move_word_subtype(
    const std::uint8_t subtype) noexcept {
    return subtype == 0x00U || subtype == 0x04U ||
        subtype == kMoveWordSegment || subtype == 0x08U ||
        subtype == 0x0CU || subtype == 0x0EU;
}

struct ParserFrame {
    bool root = false;
    bool counted = false;
    std::size_t cursor = 0U;
    std::size_t remaining = 0U;
};

struct ParserState {
    std::array<std::uint32_t, 16U> segments{};
    std::uint32_t matrix_offset = 0U;
    std::uint32_t vertex_offset = 0U;
    std::uint32_t texture_offset = 0U;
    std::size_t vertex_cursor = 0U;
    bool billboard = false;
    std::uint32_t model_matrix_index = 0U;
};

class RendererAbortGuard final {
public:
    explicit RendererAbortGuard(
        BoundedCustomGraphicsRenderer& renderer) noexcept
        : renderer_(renderer) {}

    RendererAbortGuard(const RendererAbortGuard&) = delete;
    RendererAbortGuard& operator=(const RendererAbortGuard&) = delete;

    ~RendererAbortGuard() {
        if (active_) {
            renderer_.abort();
        }
    }

    void release() noexcept {
        active_ = false;
    }

private:
    BoundedCustomGraphicsRenderer& renderer_;
    bool active_ = true;
};

[[nodiscard]] bool resolve_segmented(
    const ParserState& state,
    const std::uint32_t value,
    std::uint32_t& result) noexcept {
    const std::size_t segment = (value >> 24U) & 0x0FU;
    const std::uint32_t offset = value & kAddressMask;
    const std::uint32_t base = state.segments[segment];
    if (base > kAddressMask || offset > kAddressMask - base) {
        return false;
    }
    result = base + offset;
    return true;
}

[[nodiscard]] bool add_address(
    const std::uint32_t left,
    const std::uint32_t right,
    std::uint32_t& result) noexcept {
    if (left > kAddressMask || right > kAddressMask - left) {
        return false;
    }
    result = left + right;
    return true;
}

[[nodiscard]] GraphicsBackendReport rejected_report(
    const std::size_t parsed,
    const bool unsupported = false) noexcept {
    if (unsupported) {
        return {true, true, parsed, 1U, {}};
    }
    return {false, false, parsed, 0U, {}};
}

}  // namespace

BoundedGraphicsMemoryReader::BoundedGraphicsMemoryReader(
    GraphicsMemoryBroker& broker,
    const std::span<const BoundedGraphicsMemoryWindow> windows) noexcept
    : broker_(broker), windows_(windows) {}

std::span<const std::byte> BoundedGraphicsMemoryReader::read(
    const std::uint32_t target_address,
    const std::size_t length) noexcept {
    if (failed_ || length == 0U ||
        target_address >= kBoundedGraphicsAddressSpaceBytes ||
        length > kBoundedGraphicsAddressSpaceBytes - target_address) {
        poison_broker();
        return {};
    }
    for (const BoundedGraphicsMemoryWindow& window : windows_) {
        if (target_address < window.target_base) {
            continue;
        }
        const std::size_t offset = target_address - window.target_base;
        if (offset <= window.byte_count &&
            length <= window.byte_count - offset) {
            const std::span<const std::byte> result =
                broker_.read(window.region_id, offset, length);
            if (result.size() != length) {
                failed_ = true;
                return {};
            }
            return result;
        }
    }
    poison_broker();
    return {};
}

bool BoundedGraphicsMemoryReader::failed() const noexcept {
    return failed_;
}

void BoundedGraphicsMemoryReader::poison_broker() noexcept {
    if (!failed_ && !windows_.empty()) {
        const BoundedGraphicsMemoryWindow& first = windows_.front();
        static_cast<void>(broker_.read(
            first.region_id,
            first.byte_count,
            1U));
    }
    failed_ = true;
}

bool BoundedGraphicsSemanticRenderer::begin() {
    output_.clear();
    submitted_command_count_ = 0U;
    active_ = true;
    failed_ = false;
    return true;
}

bool BoundedGraphicsSemanticRenderer::submit(
    const BoundedGraphicsRendererEvent& event,
    const std::span<const std::byte> payload,
    BoundedGraphicsMemoryReader&) {
    if (!active_ || failed_ || event.command_count == 0U ||
        event.command_count > event.commands.size()) {
        failed_ = true;
        return false;
    }
    const std::size_t payload_record_count =
        payload.size() / kBoundedGraphicsSemanticRecordBytes +
        ((payload.size() % kBoundedGraphicsSemanticRecordBytes) != 0U ? 1U : 0U);
    if (event.command_count >
            (kMaximumGraphicsOutputBytes - output_.size()) /
                kBoundedGraphicsSemanticRecordBytes ||
        payload_record_count >
            (kMaximumGraphicsOutputBytes - output_.size() -
                event.command_count * kBoundedGraphicsSemanticRecordBytes) /
                kBoundedGraphicsSemanticRecordBytes) {
        failed_ = true;
        return false;
    }

    for (std::size_t index = 0U; index < event.command_count; ++index) {
        const std::size_t base = output_.size();
        output_.resize(base + kBoundedGraphicsSemanticRecordBytes);
        output_[base] = static_cast<std::byte>(event.kind);
        output_[base + 1U] = static_cast<std::byte>(
            event.commands[index].word0 >> 24U);
        output_[base + 2U] = static_cast<std::byte>(index);
        output_[base + 3U] = static_cast<std::byte>(event.command_count);
        write_be32(output_, base + 4U, event.argument0);
        write_be32(output_, base + 8U, event.argument1);
        write_be32(output_, base + 12U, event.argument2);
        write_be64(output_, base + 16U,
            index == 0U ? payload.size() : 0U);
        write_be32(output_, base + 24U, event.commands[index].word0);
        write_be32(output_, base + 28U, event.commands[index].word1);
    }
    const std::size_t payload_base = output_.size();
    output_.resize(
        payload_base + payload_record_count *
            kBoundedGraphicsSemanticRecordBytes);
    std::copy(payload.begin(), payload.end(), output_.begin() +
        static_cast<std::ptrdiff_t>(payload_base));
    std::fill(
        output_.begin() + static_cast<std::ptrdiff_t>(
            payload_base + payload.size()),
        output_.end(),
        std::byte{0});
    submitted_command_count_ += event.command_count;
    return true;
}

GraphicsOutputView BoundedGraphicsSemanticRenderer::finish(
    const std::size_t parsed_command_count) {
    if (!active_ || failed_ || parsed_command_count == 0U ||
        submitted_command_count_ != parsed_command_count || output_.empty() ||
        output_.size() % kBoundedGraphicsSemanticRecordBytes != 0U) {
        failed_ = true;
        return {};
    }
    active_ = false;
    return {
        GraphicsOutputKind::semantic_submission,
        kBoundedGraphicsSemanticRecordBytes,
        output_.size() / kBoundedGraphicsSemanticRecordBytes,
        kBoundedGraphicsSemanticRecordBytes,
        1U,
        output_,
    };
}

void BoundedGraphicsSemanticRenderer::abort() noexcept {
    output_.clear();
    submitted_command_count_ = 0U;
    active_ = false;
    failed_ = true;
}

BoundedCustomGraphicsBackend::BoundedCustomGraphicsBackend(
    const std::span<const BoundedGraphicsMemoryWindow> windows,
    const std::uint32_t command_stream_target_address,
    BoundedCustomGraphicsRenderer& renderer) noexcept
    : command_stream_target_address_(command_stream_target_address),
      renderer_(renderer) {
    if (command_stream_target_address_ >=
        kBoundedGraphicsAddressSpaceBytes) {
        return;
    }
    if (windows.empty() || windows.size() > windows_.size()) {
        return;
    }
    for (std::size_t index = 0U; index < windows.size(); ++index) {
        const BoundedGraphicsMemoryWindow& window = windows[index];
        if (window.byte_count == 0U ||
            window.target_base >= kBoundedGraphicsAddressSpaceBytes ||
            window.byte_count >
                kBoundedGraphicsAddressSpaceBytes - window.target_base) {
            return;
        }
        for (std::size_t earlier = 0U; earlier < index; ++earlier) {
            const BoundedGraphicsMemoryWindow& other = windows[earlier];
            const std::size_t window_end =
                static_cast<std::size_t>(window.target_base) +
                window.byte_count;
            const std::size_t other_end =
                static_cast<std::size_t>(other.target_base) +
                other.byte_count;
            if (window.region_id == other.region_id ||
                (window.target_base < other_end &&
                    other.target_base < window_end)) {
                return;
            }
        }
        windows_[index] = window;
    }
    window_count_ = windows.size();
    windows_valid_ = true;
}

GraphicsBackendCapabilities BoundedCustomGraphicsBackend::capabilities()
    const {
    return {
        GraphicsFamily::bounded_custom,
        GraphicsOutputKind::semantic_submission,
        kGraphicsBaseCustomHandlerCount,
        kGraphicsVariantOverrideCount,
        true,
        true,
    };
}

GraphicsBackendReport BoundedCustomGraphicsBackend::execute(
    const GraphicsTaskView& task,
    GraphicsMemoryBroker& memory) {
    RendererAbortGuard renderer_guard(renderer_);
    if (!windows_valid_ || !renderer_.begin()) {
        return rejected_report(0U);
    }

    BoundedGraphicsMemoryReader reader(
        memory,
        std::span<const BoundedGraphicsMemoryWindow>(
            windows_.data(), window_count_));
    ParserState state;
    std::array<ParserFrame, kBoundedGraphicsDisplayListStackDepth> stack{};
    std::size_t depth = 1U;
    stack[0] = {true, false, command_stream_target_address_, 0U};
    std::size_t parsed = 0U;
    std::size_t verified_prefix_bytes = 0U;

    auto fail = [&](const bool unsupported = false) {
        return rejected_report(parsed, unsupported);
    };
    auto fetch = [&](ParserFrame& frame, BoundedGraphicsCommand& command) {
        if (frame.counted && frame.remaining == 0U) {
            return false;
        }
        const std::span<const std::byte> bytes = reader.read(
            static_cast<std::uint32_t>(frame.cursor),
            kGraphicsCommandAlignmentBytes);
        if (bytes.size() != kGraphicsCommandAlignmentBytes) {
            return false;
        }
        if (frame.root && verified_prefix_bytes < task.command_stream.size()) {
            const std::span<const std::byte> expected =
                task.command_stream.subspan(
                    verified_prefix_bytes,
                    kGraphicsCommandAlignmentBytes);
            if (!std::equal(bytes.begin(), bytes.end(), expected.begin())) {
                return false;
            }
            verified_prefix_bytes += kGraphicsCommandAlignmentBytes;
        }
        command.word0 = read_be32(bytes, 0U);
        command.word1 = read_be32(bytes, 4U);
        frame.cursor += kGraphicsCommandAlignmentBytes;
        if (frame.counted) {
            --frame.remaining;
        }
        ++parsed;
        return parsed <= kMaximumGraphicsParsedCommandCount;
    };
    auto submit = [&](const BoundedGraphicsRendererEvent& event,
                      const std::span<const std::byte> payload = {}) {
        return renderer_.submit(event, payload, reader) && !reader.failed();
    };
    auto one_command_event = [](
        const BoundedGraphicsEventKind kind,
        const BoundedGraphicsCommand command,
        const std::uint32_t argument0 = 0U,
        const std::uint32_t argument1 = 0U,
        const std::uint32_t argument2 = 0U) {
        BoundedGraphicsRendererEvent event;
        event.kind = kind;
        event.commands[0] = command;
        event.command_count = 1U;
        event.argument0 = argument0;
        event.argument1 = argument1;
        event.argument2 = argument2;
        return event;
    };

    bool top_level_ended = false;
    while (depth != 0U) {
        while (depth != 0U && stack[depth - 1U].counted &&
            stack[depth - 1U].remaining == 0U) {
            if (stack[depth - 1U].root) {
                top_level_ended = true;
                --depth;
                break;
            }
            --depth;
        }
        if (depth == 0U) {
            break;
        }

        ParserFrame& frame = stack[depth - 1U];
        BoundedGraphicsCommand command;
        if (!fetch(frame, command)) {
            return fail();
        }
        const std::uint8_t opcode =
            static_cast<std::uint8_t>(command.word0 >> 24U);

        if (opcode == kOpEndDisplayList) {
            if (!submit(one_command_event(
                    BoundedGraphicsEventKind::end_display_list, command))) {
                return fail();
            }
            const bool was_root = frame.root;
            if (frame.counted && frame.remaining != 0U) {
                return fail();
            }
            --depth;
            if (was_root) {
                top_level_ended = true;
                break;
            }
            continue;
        }

        if (opcode == kOpDisplayList) {
            const std::uint32_t mode = (command.word0 >> 16U) & 0xFFU;
            std::uint32_t target = 0U;
            if (mode > 1U || !resolve_segmented(state, command.word1, target) ||
                reader.read(target, kGraphicsCommandAlignmentBytes).size() !=
                    kGraphicsCommandAlignmentBytes) {
                return fail();
            }
            if (!submit(one_command_event(
                    BoundedGraphicsEventKind::display_list,
                    command, target, mode))) {
                return fail();
            }
            if (mode == 0U) {
                if (depth >= stack.size()) {
                    return fail();
                }
                stack[depth++] = {false, false, target, 0U};
            }
            else {
                const bool root = frame.root;
                const bool counted = frame.counted;
                const std::size_t remaining = frame.remaining;
                frame = {root, counted, target, remaining};
            }
            continue;
        }

        if (opcode == kOpDmaDisplayList) {
            const std::uint32_t count = (command.word0 >> 16U) & 0xFFU;
            const std::uint32_t encoded_bytes = command.word0 & 0xFFFFU;
            std::uint32_t target = 0U;
            if (count == 0U || encoded_bytes != count * 8U ||
                depth >= stack.size() ||
                !resolve_segmented(state, command.word1, target) ||
                reader.read(target, encoded_bytes).size() != encoded_bytes) {
                return fail();
            }
            if (!submit(one_command_event(
                    BoundedGraphicsEventKind::dma_display_list,
                    command, count, target, encoded_bytes))) {
                return fail();
            }
            stack[depth++] = {false, true, target, count};
            continue;
        }

        if (opcode == kOpDmaMatrix) {
            const std::uint32_t encoded_bytes = command.word0 & 0xFFFFU;
            const std::uint32_t index = (command.word0 >> 16U) & 0x0FU;
            const std::uint32_t multiply = (command.word0 >> 23U) & 1U;
            std::uint32_t segmented = 0U;
            std::uint32_t target = 0U;
            if (encoded_bytes != 64U ||
                index >= kBoundedGraphicsMatrixCapacity ||
                !resolve_segmented(state, command.word1, segmented)) {
                return fail();
            }
            target = (state.matrix_offset + segmented) &
                (kAddressMask & ~0x07U);
            const std::span<const std::byte> payload = reader.read(target, 64U);
            if (payload.size() != 64U ||
                !submit(one_command_event(
                    BoundedGraphicsEventKind::dma_matrix,
                    command, index, multiply, target), payload)) {
                return fail();
            }
            state.model_matrix_index = index;
            continue;
        }

        if (opcode == kOpDmaTextureOffset) {
            std::uint32_t target = 0U;
            if (!resolve_segmented(state, command.word1, target) ||
                !submit(one_command_event(
                    BoundedGraphicsEventKind::dma_texture_offset,
                    command, target))) {
                return fail();
            }
            state.texture_offset = target;
            continue;
        }

        if (opcode == kOpDmaVertex) {
            const std::size_t count =
                (command.word0 >> 19U) & 0x1FU;
            const std::size_t requested_start =
                (command.word0 >> 9U) & 0x1FU;
            const std::uint32_t source_offset =
                (command.word0 >> 16U) & 0x06U;
            const bool append = (command.word0 & 0x00010000U) != 0U;
            if (append) {
                if (state.billboard) {
                    state.vertex_cursor = 1U;
                }
            }
            else {
                state.vertex_cursor = 0U;
            }
            if (requested_start >
                kBoundedGraphicsVertexCapacity - state.vertex_cursor) {
                return fail();
            }
            const std::size_t first =
                state.vertex_cursor + requested_start;
            if (count == 0U ||
                first > kBoundedGraphicsVertexCapacity - count) {
                return fail();
            }
            std::uint32_t segmented = 0U;
            std::uint32_t target = 0U;
            if (!resolve_segmented(state, command.word1, segmented)) {
                return fail();
            }
            target = (state.vertex_offset + segmented) &
                (kAddressMask & ~0x07U);
            if (!add_address(target, source_offset, target)) {
                return fail();
            }
            const std::size_t byte_count = count * 10U;
            const std::span<const std::byte> payload =
                reader.read(target, byte_count);
            if (payload.size() != byte_count ||
                !submit(one_command_event(
                    BoundedGraphicsEventKind::dma_vertex,
                    command,
                    static_cast<std::uint32_t>(first),
                    static_cast<std::uint32_t>(count),
                    target), payload)) {
                return fail();
            }
            state.vertex_cursor += count;
            continue;
        }

        if (opcode == kOpDmaTriangles) {
            const std::size_t count = ((command.word0 >> 20U) & 0x0FU) + 1U;
            const std::uint32_t texture = (command.word0 >> 16U) & 0x0FU;
            std::uint32_t target = 0U;
            if (!resolve_segmented(state, command.word1, target)) {
                return fail();
            }
            const std::size_t byte_count = count * 16U;
            const std::span<const std::byte> payload =
                reader.read(target, byte_count);
            if (payload.size() != byte_count ||
                !submit(one_command_event(
                    BoundedGraphicsEventKind::dma_triangles,
                    command,
                    static_cast<std::uint32_t>(count),
                    texture,
                    target), payload)) {
                return fail();
            }
            state.vertex_cursor = 0U;
            continue;
        }

        if (opcode == kOpDmaOffsets) {
            const std::uint32_t matrix_offset = command.word0 & 0x00FFFFFFU;
            const std::uint32_t vertex_offset = command.word1 & 0x00FFFFFFU;
            if (matrix_offset > kAddressMask || vertex_offset > kAddressMask ||
                !submit(one_command_event(
                    BoundedGraphicsEventKind::dma_offsets,
                    command, matrix_offset, vertex_offset))) {
                return fail();
            }
            state.matrix_offset = matrix_offset;
            state.vertex_offset = vertex_offset;
            continue;
        }

        if (opcode == kOpMoveWord) {
            const std::uint8_t subtype =
                static_cast<std::uint8_t>(command.word0);
            if (subtype == kMoveWordBillboard) {
                if ((command.word1 & ~1U) != 0U) {
                    return fail();
                }
                state.billboard = (command.word1 & 1U) != 0U;
                if (!submit(one_command_event(
                    BoundedGraphicsEventKind::billboard,
                    command, state.billboard ? 1U : 0U))) {
                    return fail();
                }
                continue;
            }
            if (subtype == kMoveWordModelMatrix) {
                state.model_matrix_index = (command.word1 >> 6U) & 0x03U;
                if (!submit(one_command_event(
                    BoundedGraphicsEventKind::model_matrix_select,
                    command, state.model_matrix_index))) {
                    return fail();
                }
                continue;
            }
            if (subtype == kMoveWordSegment) {
                const std::size_t segment = (command.word0 >> 10U) & 0x0FU;
                const std::uint32_t base = command.word1 & 0x00FFFFFFU;
                if (base > kAddressMask) {
                    return fail();
                }
                state.segments[segment] = base;
            }
            if (!known_base_move_word_subtype(subtype)) {
                return fail(true);
            }
        }

        if (!fixed_base_opcode(opcode)) {
            return fail(true);
        }
        if (opcode == kOpMoveMemory && !known_move_memory_subtype(
                static_cast<std::uint8_t>(command.word0 >> 16U))) {
            return fail(true);
        }
        BoundedGraphicsRendererEvent event;
        event.kind = BoundedGraphicsEventKind::base_command;
        event.commands[0] = command;
        event.command_count = 1U;
        std::size_t packet_count = 1U;
        if (opcode == kTextureRectangle ||
            opcode == kTextureRectangleFlip) {
            packet_count = 2U;
        }
        else if (opcode == kOpMoveMemory &&
            static_cast<std::uint8_t>(command.word0 >> 16U) ==
                kMoveMemoryForceMatrix) {
            packet_count = 4U;
        }
        for (std::size_t index = 1U; index < packet_count; ++index) {
            if (!fetch(frame, event.commands[index])) {
                return fail();
            }
            event.command_count = index + 1U;
        }
        if ((opcode == kTextureRectangle ||
                opcode == kTextureRectangleFlip) &&
            static_cast<std::uint8_t>(
                event.commands[1].word0 >> 24U) == 0xB4U) {
            if (!fetch(frame, event.commands[2]) ||
                static_cast<std::uint8_t>(
                    event.commands[2].word0 >> 24U) != 0xB3U) {
                return fail();
            }
            event.command_count = 3U;
        }
        if (!submit(event)) {
            return fail();
        }
    }

    if (!top_level_ended || depth != 0U || reader.failed() ||
        verified_prefix_bytes != task.command_stream.size()) {
        return fail();
    }
    const GraphicsOutputView output = renderer_.finish(parsed);
    if (output.bytes.empty()) {
        return rejected_report(parsed);
    }
    renderer_guard.release();
    return {true, true, parsed, 0U, output};
}

}  // namespace jfg
