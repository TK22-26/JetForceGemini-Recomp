#include "jfg/runtime/graphics_task_bridge.hpp"

#include <array>
#include <cstddef>
#include <cstdlib>
#include <stdexcept>
#include <type_traits>
#include <vector>

namespace {

[[noreturn]] void fail() {
    std::abort();
}

void require(const bool condition) {
    if (!condition) {
        fail();
    }
}

class SyntheticBackend : public jfg::GraphicsTaskBackend {
public:
    jfg::GraphicsBackendCapabilities advertised{
        jfg::GraphicsFamily::bounded_custom,
        jfg::GraphicsOutputKind::rendered_pixels,
        jfg::kGraphicsBaseCustomHandlerCount,
        jfg::kGraphicsVariantOverrideCount,
        true,
        true,
    };
    std::array<std::byte, 64U> output_bytes{};
    jfg::GraphicsBackendReport report{
        true,
        true,
        2U,
        0U,
        {jfg::GraphicsOutputKind::rendered_pixels,
            4U, 4U, 16U, 4U, output_bytes},
    };
    bool throw_from_capabilities = false;
    bool throw_from_execute = false;
    std::uint32_t memory_region_id = 7U;
    std::size_t memory_offset = 0U;
    std::size_t memory_length = 4U;
    std::size_t memory_read_count = 1U;
    std::size_t execution_count = 0U;
    std::size_t observed_access_count = 0U;
    std::size_t observed_access_bytes = 0U;
    bool observed_memory_closed = false;
    std::vector<int>* order = nullptr;

    [[nodiscard]] jfg::GraphicsBackendCapabilities capabilities() const override {
        if (throw_from_capabilities) {
            throw std::runtime_error("synthetic capability failure");
        }
        return advertised;
    }

    [[nodiscard]] jfg::GraphicsBackendReport execute(
        const jfg::GraphicsTaskView&,
        jfg::GraphicsMemoryBroker& memory) override {
        ++execution_count;
        if (order != nullptr) {
            order->push_back(1);
        }
        if (throw_from_execute) {
            throw std::runtime_error("synthetic execution failure");
        }
        for (std::size_t index = 0U; index < memory_read_count; ++index) {
            (void)memory.read(memory_region_id, memory_offset, memory_length);
        }
        observed_access_count = memory.access_count();
        observed_access_bytes = memory.accessed_bytes();
        observed_memory_closed = memory.closed();
        return report;
    }
};

class SyntheticOutputOracle final : public jfg::GraphicsOutputOracle {
public:
    bool accepted = true;
    bool throw_from_validate = false;
    std::size_t validation_count = 0U;
    std::vector<int>* order = nullptr;

    [[nodiscard]] bool validate(
        const jfg::GraphicsOutputView&) override {
        ++validation_count;
        if (order != nullptr) {
            order->push_back(2);
        }
        if (throw_from_validate) {
            throw std::runtime_error("synthetic oracle failure");
        }
        return accepted;
    }
};

class DualBackendOracle final :
    public SyntheticBackend,
    public jfg::GraphicsOutputOracle {
public:
    std::size_t validation_count = 0U;

    [[nodiscard]] bool validate(
        const jfg::GraphicsOutputView&) override {
        ++validation_count;
        return true;
    }
};

class SyntheticCompletionSink final : public jfg::GraphicsCompletionSink {
public:
    bool accepted = true;
    bool throw_from_prepare = false;
    std::size_t prepare_count = 0U;
    std::size_t commit_count = 0U;
    std::size_t last_parsed_command_count = 0U;
    std::vector<int>* order = nullptr;

    [[nodiscard]] bool prepare_renderer_complete(
        const std::size_t parsed_command_count) override {
        ++prepare_count;
        last_parsed_command_count = parsed_command_count;
        if (order != nullptr) {
            order->push_back(3);
        }
        if (throw_from_prepare) {
            throw std::runtime_error("synthetic completion preparation failure");
        }
        return accepted;
    }

    void commit_renderer_complete(
        const std::size_t parsed_command_count) noexcept override {
        ++commit_count;
        last_parsed_command_count = parsed_command_count;
        if (order != nullptr) {
            order->push_back(4);
        }
    }
};

struct SyntheticTask {
    std::array<std::byte, 64U> active_program{};
    std::array<std::byte, 32U> program_data{};
    std::array<std::byte, 16U> command_stream{};
    std::array<std::byte, 32U> referenced_bytes{};
    std::array<jfg::GraphicsReferencedMemoryRegion, 1U> referenced_regions{
        jfg::GraphicsReferencedMemoryRegion{7U, referenced_bytes},
    };

    [[nodiscard]] jfg::GraphicsTaskView view() const noexcept {
        return {
            jfg::GraphicsFamily::bounded_custom,
            active_program,
            program_data,
            command_stream,
        };
    }
};

[[nodiscard]] jfg::GraphicsTaskResult submit(
    const jfg::GraphicsTaskBridge& bridge,
    const SyntheticTask& task,
    SyntheticBackend& backend,
    const jfg::GraphicsTaskView& view) {
    SyntheticOutputOracle oracle;
    SyntheticCompletionSink completion;
    return bridge.submit(
        view,
        task.referenced_regions,
        backend,
        oracle,
        completion);
}

[[nodiscard]] jfg::GraphicsTaskResult submit(
    const jfg::GraphicsTaskBridge& bridge,
    const SyntheticTask& task,
    SyntheticBackend& backend) {
    return submit(bridge, task, backend, task.view());
}

void require_failure(
    const jfg::GraphicsTaskResult& result,
    const jfg::GraphicsTaskError expected) {
    require(!result.ok());
    require(!result.completion_authorized);
    require(result.parsed_command_count == 0U);
    require(result.error == expected);
}

}  // namespace

int main() {
    static_assert(
        !std::is_copy_constructible_v<jfg::GraphicsMemoryBroker>);
    static_assert(
        !std::is_copy_assignable_v<jfg::GraphicsMemoryBroker>);
    static_assert(
        !std::is_move_constructible_v<jfg::GraphicsMemoryBroker>);
    static_assert(
        !std::is_move_assignable_v<jfg::GraphicsMemoryBroker>);

    const jfg::GraphicsTaskBridge bridge;
    const SyntheticTask task;

    {
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        const auto result = bridge.submit(
            task.view(),
            task.referenced_regions,
            backend,
            oracle,
            completion);
        require(result.ok());
        require(result.completion_authorized);
        require(result.parsed_command_count == 2U);
        require(backend.execution_count == 1U);
        require(backend.observed_access_count == 1U);
        require(backend.observed_access_bytes == 4U);
        require(backend.observed_memory_closed);
        require(oracle.validation_count == 1U);
        require(completion.prepare_count == 1U);
        require(completion.commit_count == 1U);
        require(completion.last_parsed_command_count == 2U);
    }

    {
        SyntheticBackend backend;
        auto invalid = task.view();
        invalid.active_program = {};
        require_failure(
            submit(bridge, task, backend, invalid),
            jfg::GraphicsTaskError::empty_active_program);
        require(backend.execution_count == 0U);
    }

    {
        SyntheticBackend backend;
        std::array<std::byte, jfg::kMaximumGraphicsActiveProgramBytes + 1U>
            oversized{};
        auto invalid = task.view();
        invalid.active_program = oversized;
        require_failure(
            submit(bridge, task, backend, invalid),
            jfg::GraphicsTaskError::active_program_too_large);
    }

    {
        SyntheticBackend backend;
        std::array<std::byte, 5U> misaligned{};
        auto invalid = task.view();
        invalid.active_program = misaligned;
        require_failure(
            submit(bridge, task, backend, invalid),
            jfg::GraphicsTaskError::active_program_misaligned);
    }

    {
        SyntheticBackend backend;
        auto invalid = task.view();
        invalid.program_data = {};
        require_failure(
            submit(bridge, task, backend, invalid),
            jfg::GraphicsTaskError::empty_program_data);
    }

    {
        SyntheticBackend backend;
        std::array<std::byte, jfg::kMaximumGraphicsProgramDataBytes + 1U>
            oversized{};
        auto invalid = task.view();
        invalid.program_data = oversized;
        require_failure(
            submit(bridge, task, backend, invalid),
            jfg::GraphicsTaskError::program_data_too_large);
    }

    {
        SyntheticBackend backend;
        auto invalid = task.view();
        invalid.command_stream = {};
        require_failure(
            submit(bridge, task, backend, invalid),
            jfg::GraphicsTaskError::empty_command_stream);
    }

    {
        SyntheticBackend backend;
        const std::vector<std::byte> oversized(
            jfg::kMaximumGraphicsCommandStreamBytes +
            jfg::kGraphicsCommandAlignmentBytes);
        auto invalid = task.view();
        invalid.command_stream = oversized;
        require_failure(
            submit(bridge, task, backend, invalid),
            jfg::GraphicsTaskError::command_stream_too_large);
    }

    {
        SyntheticBackend backend;
        std::array<std::byte, 9U> misaligned{};
        auto invalid = task.view();
        invalid.command_stream = misaligned;
        require_failure(
            submit(bridge, task, backend, invalid),
            jfg::GraphicsTaskError::command_stream_misaligned);
    }

    {
        SyntheticBackend backend;
        auto invalid = task.view();
        invalid.family = jfg::GraphicsFamily::unknown;
        backend.advertised.family = jfg::GraphicsFamily::unknown;
        require_failure(
            submit(bridge, task, backend, invalid),
            jfg::GraphicsTaskError::unsupported_family);
        require(backend.execution_count == 0U);
    }

    {
        SyntheticBackend backend;
        backend.advertised.family = jfg::GraphicsFamily::unknown;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::unsupported_family);
        require(backend.execution_count == 0U);
    }

    {
        SyntheticBackend backend;
        backend.advertised.base_custom_handler_count =
            jfg::kGraphicsBaseCustomHandlerCount - 1U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::incomplete_handler_surface);
        require(backend.execution_count == 0U);
    }

    {
        SyntheticBackend backend;
        backend.advertised.variant_override_count =
            jfg::kGraphicsVariantOverrideCount - 1U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::incomplete_handler_surface);
        require(backend.execution_count == 0U);
    }

    {
        SyntheticBackend backend;
        backend.advertised.shared_base_delegate = false;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::incomplete_handler_surface);
        require(backend.execution_count == 0U);
    }

    {
        SyntheticBackend backend;
        backend.advertised.unknown_commands_fail_closed = false;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::incomplete_handler_surface);
    }

    {
        SyntheticBackend backend;
        backend.advertised.output_kind = jfg::GraphicsOutputKind::unknown;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::incomplete_handler_surface);
        require(backend.execution_count == 0U);
    }

    {
        SyntheticBackend backend;
        backend.report.accepted = false;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::backend_rejected);
    }

    {
        SyntheticBackend backend;
        backend.report.parse_complete = false;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::parse_incomplete);
    }

    {
        SyntheticBackend backend;
        backend.report.unsupported_command_count = 1U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::unsupported_commands);
    }

    {
        SyntheticBackend backend;
        backend.report.unsupported_command_count = 3U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::invalid_backend_report);
    }

    {
        SyntheticBackend backend;
        backend.report.output.kind =
            jfg::GraphicsOutputKind::semantic_submission;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::invalid_backend_report);
    }

    {
        SyntheticBackend backend;
        backend.memory_offset = task.referenced_bytes.size();
        backend.memory_length = 1U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::referenced_memory_open);
        require(!backend.observed_memory_closed);
    }

    {
        SyntheticBackend backend;
        backend.report.output.bytes = {};
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::output_not_observed);
    }

    {
        SyntheticBackend backend;
        backend.report.parsed_command_count = 0U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::invalid_backend_report);
    }

    {
        SyntheticBackend backend;
        backend.report.parsed_command_count = 1U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::invalid_backend_report);
    }

    {
        SyntheticBackend backend;
        backend.report.parsed_command_count =
            jfg::kMaximumGraphicsParsedCommandCount + 1U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::invalid_backend_report);
    }

    {
        SyntheticBackend backend;
        backend.throw_from_capabilities = true;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::backend_exception);
        require(backend.execution_count == 0U);
    }

    {
        SyntheticBackend backend;
        backend.throw_from_execute = true;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::backend_exception);
        require(backend.execution_count == 1U);
    }

    {
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        require_failure(
            bridge.submit(task.view(), {}, backend, oracle, completion),
            jfg::GraphicsTaskError::empty_referenced_memory);
        require(backend.execution_count == 0U);
        require(oracle.validation_count == 0U);
        require(completion.prepare_count == 0U);
        require(completion.commit_count == 0U);
    }

    {
        DualBackendOracle backend_and_oracle;
        SyntheticCompletionSink completion;
        require_failure(
            bridge.submit(
                task.view(),
                task.referenced_regions,
                backend_and_oracle,
                backend_and_oracle,
                completion),
            jfg::GraphicsTaskError::output_oracle_not_independent);
        require(backend_and_oracle.execution_count == 0U);
        require(backend_and_oracle.validation_count == 0U);
        require(completion.prepare_count == 0U);
        require(completion.commit_count == 0U);
    }

    {
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        const std::vector<jfg::GraphicsReferencedMemoryRegion> too_many(
            jfg::kMaximumGraphicsReferencedRegionCount + 1U,
            {1U, task.referenced_bytes});
        require_failure(
            bridge.submit(
                task.view(), too_many, backend, oracle, completion),
            jfg::GraphicsTaskError::too_many_referenced_regions);
        require(backend.execution_count == 0U);
        require(oracle.validation_count == 0U);
        require(completion.prepare_count == 0U);
        require(completion.commit_count == 0U);
    }

    {
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        const std::array<jfg::GraphicsReferencedMemoryRegion, 1U> invalid{
            jfg::GraphicsReferencedMemoryRegion{1U, {}},
        };
        require_failure(
            bridge.submit(
                task.view(), invalid, backend, oracle, completion),
            jfg::GraphicsTaskError::invalid_referenced_region);
        require(backend.execution_count == 0U);
    }

    {
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        const std::array<jfg::GraphicsReferencedMemoryRegion, 2U> duplicate{
            jfg::GraphicsReferencedMemoryRegion{1U, task.referenced_bytes},
            jfg::GraphicsReferencedMemoryRegion{1U, task.referenced_bytes},
        };
        require_failure(
            bridge.submit(
                task.view(), duplicate, backend, oracle, completion),
            jfg::GraphicsTaskError::invalid_referenced_region);
        require(backend.execution_count == 0U);
    }

    {
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        const std::vector<std::byte> oversized(
            jfg::kMaximumGraphicsReferencedMemoryBytes + 1U);
        const std::array<jfg::GraphicsReferencedMemoryRegion, 1U> regions{
            jfg::GraphicsReferencedMemoryRegion{1U, oversized},
        };
        require_failure(
            bridge.submit(
                task.view(), regions, backend, oracle, completion),
            jfg::GraphicsTaskError::referenced_memory_too_large);
        require(backend.execution_count == 0U);
    }

    {
        SyntheticBackend backend;
        backend.memory_region_id = 8U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::referenced_memory_open);
        require(backend.observed_access_count == 0U);
        require(!backend.observed_memory_closed);
    }

    {
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        std::array<std::byte, 8U> second_region_bytes{};
        const std::array<jfg::GraphicsReferencedMemoryRegion, 2U> regions{
            jfg::GraphicsReferencedMemoryRegion{7U, task.referenced_bytes},
            jfg::GraphicsReferencedMemoryRegion{8U, second_region_bytes},
        };
        require_failure(
            bridge.submit(task.view(), regions, backend, oracle, completion),
            jfg::GraphicsTaskError::referenced_memory_open);
        require(backend.observed_access_count == 1U);
        require(!backend.observed_memory_closed);
        require(oracle.validation_count == 0U);
        require(completion.prepare_count == 0U);
        require(completion.commit_count == 0U);
    }

    {
        SyntheticBackend backend;
        backend.memory_length = 0U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::referenced_memory_open);
    }

    {
        SyntheticBackend backend;
        backend.memory_length = 1U;
        backend.memory_read_count =
            jfg::kMaximumGraphicsMemoryAccessCount + 1U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::referenced_memory_open);
        require(
            backend.observed_access_count ==
            jfg::kMaximumGraphicsMemoryAccessCount);
        require(!backend.observed_memory_closed);
    }

    {
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        const std::vector<std::byte> maximum_region(
            jfg::kMaximumGraphicsReferencedMemoryBytes);
        const std::array<jfg::GraphicsReferencedMemoryRegion, 1U> regions{
            jfg::GraphicsReferencedMemoryRegion{1U, maximum_region},
        };
        backend.memory_region_id = 1U;
        backend.memory_length = maximum_region.size();
        backend.memory_read_count =
            (jfg::kMaximumGraphicsMemoryAccessBytes /
             jfg::kMaximumGraphicsReferencedMemoryBytes) +
            1U;
        require_failure(
            bridge.submit(
                task.view(), regions, backend, oracle, completion),
            jfg::GraphicsTaskError::referenced_memory_open);
        require(
            backend.observed_access_bytes ==
            jfg::kMaximumGraphicsMemoryAccessBytes);
        require(!backend.observed_memory_closed);
    }

    {
        SyntheticBackend backend;
        backend.report.output.width = 0U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::invalid_output);
    }

    {
        SyntheticBackend backend;
        backend.report.output.row_pitch_bytes = 15U;
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::invalid_output);
    }

    {
        SyntheticBackend backend;
        backend.report.output.bytes =
            std::span<const std::byte>(backend.output_bytes).first(63U);
        require_failure(
            submit(bridge, task, backend),
            jfg::GraphicsTaskError::invalid_output);
    }

    {
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        oracle.accepted = false;
        require_failure(
            bridge.submit(
                task.view(),
                task.referenced_regions,
                backend,
                oracle,
                completion),
            jfg::GraphicsTaskError::output_rejected);
        require(oracle.validation_count == 1U);
        require(completion.prepare_count == 0U);
        require(completion.commit_count == 0U);
    }

    {
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        oracle.throw_from_validate = true;
        require_failure(
            bridge.submit(
                task.view(),
                task.referenced_regions,
                backend,
                oracle,
                completion),
            jfg::GraphicsTaskError::output_oracle_exception);
        require(completion.prepare_count == 0U);
        require(completion.commit_count == 0U);
    }

    {
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        completion.accepted = false;
        require_failure(
            bridge.submit(
                task.view(),
                task.referenced_regions,
                backend,
                oracle,
                completion),
            jfg::GraphicsTaskError::completion_rejected);
        require(oracle.validation_count == 1U);
        require(completion.prepare_count == 1U);
        require(completion.commit_count == 0U);
    }

    {
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        completion.throw_from_prepare = true;
        require_failure(
            bridge.submit(
                task.view(),
                task.referenced_regions,
                backend,
                oracle,
                completion),
            jfg::GraphicsTaskError::completion_exception);
        require(oracle.validation_count == 1U);
        require(completion.prepare_count == 1U);
        require(completion.commit_count == 0U);
    }

    {
        std::vector<int> order;
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        backend.order = &order;
        oracle.order = &order;
        completion.order = &order;
        const auto result = bridge.submit(
            task.view(),
            task.referenced_regions,
            backend,
            oracle,
            completion);
        require(result.ok());
        require((order == std::vector<int>{1, 2, 3, 4}));
    }

    {
        std::vector<int> order;
        SyntheticBackend backend;
        SyntheticOutputOracle oracle;
        SyntheticCompletionSink completion;
        backend.order = &order;
        oracle.order = &order;
        completion.order = &order;
        oracle.accepted = false;
        require_failure(
            bridge.submit(
                task.view(),
                task.referenced_regions,
                backend,
                oracle,
                completion),
            jfg::GraphicsTaskError::output_rejected);
        require((order == std::vector<int>{1, 2}));
        require(completion.prepare_count == 0U);
        require(completion.commit_count == 0U);
    }

    require(jfg::graphics_task_error_message(
                jfg::GraphicsTaskError::unsupported_commands)[0] != '\0');
    return EXIT_SUCCESS;
}
