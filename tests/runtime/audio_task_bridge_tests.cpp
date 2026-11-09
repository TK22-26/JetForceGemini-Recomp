#include "jfg/runtime/audio_task_bridge.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdlib>
#include <cstdio>
#include <source_location>
#include <span>
#include <stdexcept>
#include <vector>

namespace {

template <typename T>
concept ExposesRawOutput = requires(T value) { value.output; };

template <typename T>
concept ExposesRawReferencedRegions = requires(T value) {
    value.referenced_regions;
};

static_assert(!ExposesRawOutput<jfg::AudioBackendTaskView>);
static_assert(!ExposesRawReferencedRegions<jfg::AudioBackendTaskView>);

[[noreturn]] void fail(const std::source_location location) {
    std::fprintf(
        stderr,
        "audio bridge synthetic assertion failed at line %u\n",
        location.line());
    std::abort();
}

void require(
    const bool condition,
    const std::source_location location = std::source_location::current()) {
    if (!condition) {
        fail(location);
    }
}

constexpr std::byte byte(const unsigned int value) {
    return static_cast<std::byte>(value);
}

enum class BackendMode {
    complete,
    reject,
    incomplete_parse,
    unsupported_command,
    wrong_variant,
    invalid_region,
    out_of_bounds_read,
    partial_regions,
    partial_output,
    overlapping_output,
    false_report,
    short_parse,
    long_parse,
    throw_execute,
};

class SyntheticBackend final : public jfg::AudioTaskBackend {
public:
    jfg::AudioBackendCapabilities advertised{
        jfg::kAudioProgramVariantCount,
        true,
        true,
        true,
        true,
    };
    BackendMode mode = BackendMode::complete;
    bool throw_capabilities = false;
    std::size_t execution_count = 0U;

    [[nodiscard]] jfg::AudioBackendCapabilities capabilities() const override {
        if (throw_capabilities) {
            throw std::runtime_error("synthetic capability failure");
        }
        return advertised;
    }

    [[nodiscard]] jfg::AudioBackendReport execute(
        const jfg::AudioBackendTaskView& task,
        jfg::AudioMemoryAccess& memory) override {
        ++execution_count;
        if (mode == BackendMode::throw_execute) {
            throw std::runtime_error("synthetic execution failure");
        }

        jfg::AudioBackendReport report{};
        report.accepted = mode != BackendMode::reject;
        report.parse_complete = mode != BackendMode::incomplete_parse;
        report.selected_variant = mode == BackendMode::wrong_variant
            ? jfg::AudioProgramVariant::unknown
            : task.variant;
        report.parsed_command_count = mode == BackendMode::short_parse
            ? 1U
            : mode == BackendMode::long_parse ? 3U : 2U;
        report.unsupported_command_count =
            mode == BackendMode::unsupported_command ? 1U : 0U;

        std::array<std::byte, 4U> left{};
        std::array<std::byte, 4U> right{};
        if (mode == BackendMode::invalid_region) {
            static_cast<void>(memory.read(7U, 0U, left));
            return report;
        }
        if (mode == BackendMode::out_of_bounds_read) {
            static_cast<void>(memory.read(0U, 2U, left));
            return report;
        }

        require(memory.read(0U, 0U, left));
        report.input_read_operation_count = 1U;
        report.input_bytes_read = left.size();
        if (mode != BackendMode::partial_regions) {
            require(memory.read(1U, 0U, right));
            report.input_read_operation_count = 2U;
            report.input_bytes_read += right.size();
        }

        std::array<std::byte, 8U> rendered{};
        for (std::size_t index = 0U; index < left.size(); ++index) {
            rendered[index] = left[index];
            rendered[index + left.size()] = right[index];
        }
        if (task.variant == jfg::AudioProgramVariant::secondary) {
            std::reverse(rendered.begin(), rendered.end());
        }

        if (mode == BackendMode::partial_output) {
            require(memory.write_output(0U, std::span(rendered).first<4U>()));
            report.output_write_operation_count = 1U;
            report.output_bytes_written = 4U;
        }
        else {
            require(memory.write_output(0U, std::span(rendered).first<4U>()));
            report.output_write_operation_count = 1U;
            report.output_bytes_written = 4U;
            if (mode == BackendMode::overlapping_output) {
                static_cast<void>(
                    memory.write_output(2U, std::span(rendered).last<4U>()));
            }
            else {
                require(
                    memory.write_output(4U, std::span(rendered).last<4U>()));
                report.output_write_operation_count = 2U;
                report.output_bytes_written = rendered.size();
            }
        }

        if (mode == BackendMode::false_report) {
            ++report.input_bytes_read;
        }
        return report;
    }
};

class ExactOutputValidator final : public jfg::AudioOutputValidator {
public:
    std::array<std::byte, 8U> expected{};
    bool reject = false;
    bool throw_validate = false;
    std::size_t validation_count = 0U;

    [[nodiscard]] bool validate(
        const std::span<const std::byte> output) override {
        ++validation_count;
        if (throw_validate) {
            throw std::runtime_error("synthetic output validation failure");
        }
        return !reject && std::ranges::equal(output, expected);
    }
};

struct SyntheticTask {
    std::array<std::byte, 64U> active_program{};
    std::array<std::byte, 32U> program_data{};
    std::array<std::byte, 16U> command_stream{};
    std::array<std::byte, 4U> region_a{
        byte(1U), byte(2U), byte(3U), byte(4U)};
    std::array<std::byte, 4U> region_b{
        byte(5U), byte(6U), byte(7U), byte(8U)};
    std::array<jfg::AudioReferencedRegion, 2U> regions{
        jfg::AudioReferencedRegion{region_a},
        jfg::AudioReferencedRegion{region_b},
    };
    std::array<std::byte, 8U> output{};

    SyntheticTask() {
        reset_output();
    }

    void reset_output() {
        output.fill(byte(0xCCU));
    }

    [[nodiscard]] jfg::AudioTaskView view(
        const jfg::AudioProgramVariant variant =
            jfg::AudioProgramVariant::primary) noexcept {
        return {
            variant,
            active_program,
            program_data,
            command_stream,
            regions,
            output,
        };
    }
};

[[nodiscard]] std::array<std::byte, 8U> expected_primary() {
    return {
        byte(1U), byte(2U), byte(3U), byte(4U),
        byte(5U), byte(6U), byte(7U), byte(8U),
    };
}

[[nodiscard]] std::array<std::byte, 8U> expected_secondary() {
    auto expected = expected_primary();
    std::reverse(expected.begin(), expected.end());
    return expected;
}

class BrokeredRspProgram final : public jfg::AudioRspProgram {
public:
    jfg::AudioRspExitReason exit_reason = jfg::AudioRspExitReason::broke;
    jfg::AudioProgramVariant observed_variant_override =
        jfg::AudioProgramVariant::unknown;
    std::size_t* destruction_count = nullptr;
    jfg::AudioRuntimeTaskWorker* destructor_worker = nullptr;
    jfg::AudioWorkerInstallation destructor_installation;
    jfg::AudioWorkerError* destructor_uninstall_error = nullptr;
    bool throw_execute = false;
    std::size_t execution_count = 0U;

    ~BrokeredRspProgram() override {
        if (destruction_count != nullptr) {
            ++*destruction_count;
        }
        if (destructor_worker != nullptr && destructor_uninstall_error != nullptr) {
            *destructor_uninstall_error =
                destructor_worker->uninstall(destructor_installation);
        }
    }

    [[nodiscard]] jfg::AudioRspProgramReport execute(
        const jfg::AudioBackendTaskView& task,
        jfg::AudioMemoryAccess& memory) override {
        ++execution_count;
        if (throw_execute) {
            throw std::runtime_error("synthetic installed program failure");
        }
        jfg::AudioRspProgramReport report{};
        report.exit_reason = exit_reason;
        report.selected_variant = observed_variant_override ==
                jfg::AudioProgramVariant::unknown
            ? task.variant
            : observed_variant_override;
        if (exit_reason != jfg::AudioRspExitReason::broke) {
            return report;
        }

        const std::array<std::byte, 8U> produced =
            report.selected_variant == jfg::AudioProgramVariant::secondary
            ? expected_secondary()
            : expected_primary();

        std::array<std::byte, 4U> observed{};
        require(memory.read(0U, 0U, observed));
        require(memory.read(1U, 0U, observed));
        require(memory.write_output(0U, std::span(produced).first<4U>()));
        require(memory.write_output(4U, std::span(produced).last<4U>()));

        report.parse_complete = true;
        report.parsed_command_count =
            task.command_stream.size() / jfg::kAudioCommandAlignmentBytes;
        report.input_read_operation_count = 2U;
        report.input_bytes_read = 8U;
        report.output_write_operation_count = 2U;
        report.output_bytes_written = produced.size();
        return report;
    }
};

class MutableRspProgram final : public jfg::AudioRspProgram {
public:
    std::array<std::byte, 4U> replacement{
        byte(9U), byte(10U), byte(11U), byte(12U)};
    bool write_succeeded = false;

    [[nodiscard]] jfg::AudioRspProgramReport execute(
        const jfg::AudioBackendTaskView& task,
        jfg::AudioMemoryAccess& memory) override {
        jfg::AudioRspProgramReport report{};
        report.exit_reason = jfg::AudioRspExitReason::broke;
        report.selected_variant = task.variant;
        report.parse_complete = true;
        report.parsed_command_count =
            task.command_stream.size() / jfg::kAudioCommandAlignmentBytes;

        write_succeeded = memory.write_region(0U, 0U, replacement);
        if (!write_succeeded) {
            return report;
        }
        report.region_write_operation_count = 1U;
        report.region_bytes_written = replacement.size();

        std::array<std::byte, 4U> staged{};
        std::array<std::byte, 4U> stable{};
        require(memory.read(0U, 0U, staged));
        require(memory.read(1U, 0U, stable));
        report.input_read_operation_count = 2U;
        report.input_bytes_read = staged.size() + stable.size();
        require(memory.write_output(0U, staged));
        require(memory.write_output(4U, stable));
        report.output_write_operation_count = 2U;
        report.output_bytes_written = staged.size() + stable.size();
        return report;
    }
};

class RecordingCompletionSink final : public jfg::AudioTaskCompletionSink {
public:
    std::span<const std::byte> output;
    std::array<std::byte, 8U> expected{};
    bool accept = true;
    bool throw_prepare = false;
    bool output_visible = false;
    std::size_t prepare_count = 0U;
    std::size_t commit_count = 0U;

    RecordingCompletionSink(
        const std::span<const std::byte> observed_output,
        const std::array<std::byte, 8U>& expected_output) noexcept
        : output(observed_output), expected(expected_output) {}

    [[nodiscard]] bool prepare_sp_complete(
        const jfg::AudioTaskResult& result) override {
        ++prepare_count;
        if (throw_prepare) {
            throw std::runtime_error("synthetic completion preparation failure");
        }
        output_visible = result.ok() && std::ranges::equal(output, expected);
        return accept;
    }

    void commit_sp_complete(
        const jfg::AudioTaskResult&) noexcept override {
        ++commit_count;
    }
};

class ReentrantCompletionSink final : public jfg::AudioTaskCompletionSink {
public:
    jfg::AudioRuntimeTaskWorker* worker = nullptr;
    jfg::AudioWorkerInstallation installation;
    const jfg::AudioTaskView* task = nullptr;
    jfg::AudioOutputValidator* validator = nullptr;
    std::span<const std::byte> output;
    std::array<std::byte, 8U> expected{};
    jfg::AudioWorkerError uninstall_error = jfg::AudioWorkerError::none;
    jfg::AudioWorkerError nested_submit_error = jfg::AudioWorkerError::none;
    bool output_visible = false;
    std::size_t prepare_count = 0U;
    std::size_t commit_count = 0U;

    [[nodiscard]] bool prepare_sp_complete(
        const jfg::AudioTaskResult& result) override {
        ++prepare_count;
        output_visible = result.ok() && std::ranges::equal(output, expected);
        uninstall_error = worker->uninstall(installation);
        nested_submit_error = worker->submit(
            installation,
            *task,
            *validator,
            *this).error;
        return output_visible;
    }

    void commit_sp_complete(
        const jfg::AudioTaskResult&) noexcept override {
        ++commit_count;
    }
};

void require_unchanged(const SyntheticTask& task) {
    require(std::all_of(
        task.output.begin(),
        task.output.end(),
        [](const std::byte value) { return value == byte(0xCCU); }));
}

void require_failure(
    const jfg::AudioTaskResult& result,
    const jfg::AudioTaskError expected,
    const SyntheticTask& task) {
    require(!result.ok());
    require(!result.referenced_memory_closed);
    require(!result.output_validated);
    require(!result.completion_authorized);
    if (result.error != expected) {
        std::fprintf(
            stderr,
            "unexpected audio error %d expected %d\n",
            static_cast<int>(result.error),
            static_cast<int>(expected));
    }
    require(result.error == expected);
    require_unchanged(task);
}

void test_both_variants() {
    const jfg::AudioTaskBridge bridge;
    for (const auto variant : {
             jfg::AudioProgramVariant::primary,
             jfg::AudioProgramVariant::secondary,
         }) {
        SyntheticTask task;
        SyntheticBackend backend;
        ExactOutputValidator validator;
        validator.expected = variant == jfg::AudioProgramVariant::primary
            ? expected_primary()
            : expected_secondary();

        const auto result = bridge.submit(task.view(variant), backend, validator);
        require(result.ok());
        require(result.selected_variant == variant);
        require(result.parsed_command_count == 2U);
        require(result.input_bytes_read == 8U);
        require(result.output_bytes_written == 8U);
        require(result.referenced_memory_closed);
        require(result.output_validated);
        require(result.completion_authorized);
        require(backend.execution_count == 1U);
        require(validator.validation_count == 1U);
        require(task.output == validator.expected);
    }
}

void test_rsp_adapter_uses_one_internal_dispatch_wrapper() {
    const jfg::AudioTaskBridge bridge;
    BrokeredRspProgram program;
    jfg::AudioRspTaskAdapter adapter(&program);
    const auto capabilities = adapter.capabilities();
    require(capabilities.program_variant_count == 2U);
    require(capabilities.primary_variant_supported);
    require(capabilities.secondary_variant_supported);
    require(capabilities.referenced_memory_broker_only);
    require(capabilities.unknown_commands_fail_closed);

    for (const auto variant : {
             jfg::AudioProgramVariant::primary,
             jfg::AudioProgramVariant::secondary,
         }) {
        SyntheticTask task;
        ExactOutputValidator validator;
        validator.expected = variant == jfg::AudioProgramVariant::primary
            ? expected_primary()
            : expected_secondary();
        const auto result = bridge.submit(task.view(variant), adapter, validator);
        require(result.ok());
        require(task.output == validator.expected);
    }
    require(program.execution_count == 2U);

    {
        SyntheticTask task;
        jfg::AudioRspTaskAdapter incomplete(nullptr);
        ExactOutputValidator validator;
        require_failure(
            bridge.submit(task.view(), incomplete, validator),
            jfg::AudioTaskError::incomplete_backend_capabilities,
            task);
    }
    {
        SyntheticTask task;
        program.exit_reason = jfg::AudioRspExitReason::unsupported;
        ExactOutputValidator validator;
        require_failure(
            bridge.submit(task.view(), adapter, validator),
            jfg::AudioTaskError::backend_rejected,
            task);
    }
    {
        SyntheticTask task;
        program.exit_reason = jfg::AudioRspExitReason::broke;
        program.observed_variant_override =
            jfg::AudioProgramVariant::secondary;
        ExactOutputValidator validator;
        require_failure(
            bridge.submit(task.view(), adapter, validator),
            jfg::AudioTaskError::selected_variant_mismatch,
            task);
    }
}

void test_scheduler_completion_follows_validated_output() {
    const jfg::AudioTaskSchedulerGate scheduler;
    BrokeredRspProgram program;
    jfg::AudioRspTaskAdapter adapter(&program);

    {
        SyntheticTask task;
        ExactOutputValidator validator;
        validator.expected = expected_primary();
        RecordingCompletionSink sink{
            task.output,
            expected_primary(),
        };
        const auto result = scheduler.submit(
            task.view(), adapter, validator, sink);
        require(result.ok());
        require(result.completion_emitted);
        require(sink.prepare_count == 1U);
        require(sink.commit_count == 1U);
        require(sink.output_visible);
    }
    {
        SyntheticTask task;
        ExactOutputValidator validator;
        validator.expected = expected_primary();
        validator.reject = true;
        RecordingCompletionSink sink{
            task.output,
            expected_primary(),
        };
        const auto result = scheduler.submit(
            task.view(), adapter, validator, sink);
        require(!result.ok());
        require(!result.completion_emitted);
        require(sink.prepare_count == 0U);
        require(sink.commit_count == 0U);
        require_unchanged(task);
    }
    {
        SyntheticTask task;
        ExactOutputValidator validator;
        validator.expected = expected_primary();
        RecordingCompletionSink sink{
            task.output,
            expected_primary(),
        };
        sink.accept = false;
        const auto result = scheduler.submit(
            task.view(), adapter, validator, sink);
        require(result.task.ok());
        require(!result.ok());
        require(!result.completion_emitted);
        require(sink.prepare_count == 1U);
        require(sink.commit_count == 0U);
        require(sink.output_visible);
    }
    {
        SyntheticTask task;
        ExactOutputValidator validator;
        validator.expected = expected_primary();
        RecordingCompletionSink sink{
            task.output,
            expected_primary(),
        };
        sink.throw_prepare = true;
        const auto result = scheduler.submit(
            task.view(), adapter, validator, sink);
        require(result.task.ok());
        require(!result.ok());
        require(!result.completion_emitted);
        require(sink.prepare_count == 1U);
        require(sink.commit_count == 0U);
    }
}

void test_mutable_work_regions_are_transactional() {
    const jfg::AudioTaskBridge bridge;
    for (const bool reject_output : {false, true}) {
        SyntheticTask task;
        const auto original = task.region_a;
        std::array<std::byte, 4U> committed = original;
        task.regions[0] = jfg::AudioReferencedRegion{
            task.region_a,
            committed,
        };

        MutableRspProgram program;
        jfg::AudioRspTaskAdapter adapter(&program);
        ExactOutputValidator validator;
        validator.expected = {
            byte(9U), byte(10U), byte(11U), byte(12U),
            byte(5U), byte(6U), byte(7U), byte(8U),
        };
        validator.reject = reject_output;

        const auto result = bridge.submit(task.view(), adapter, validator);
        require(program.write_succeeded);
        if (reject_output) {
            require_failure(
                result,
                jfg::AudioTaskError::output_validation_failed,
                task);
            require(committed == original);
        }
        else {
            require(result.ok());
            require(result.referenced_bytes_written == 4U);
            require(committed == program.replacement);
            require(task.output == validator.expected);
        }
    }

    SyntheticTask read_only;
    MutableRspProgram program;
    jfg::AudioRspTaskAdapter adapter(&program);
    ExactOutputValidator validator;
    require_failure(
        bridge.submit(read_only.view(), adapter, validator),
        jfg::AudioTaskError::memory_access_violation,
        read_only);
    require(!program.write_succeeded);
}

void test_runtime_worker_installation_and_busy_identity() {
    jfg::AudioRuntimeTaskWorker worker;
    jfg::AudioRuntimeTaskWorker other_worker;
    SyntheticTask task;
    ExactOutputValidator validator;
    validator.expected = expected_primary();
    RecordingCompletionSink sink{task.output, expected_primary()};

    const auto absent = worker.submit(
        {}, task.view(), validator, sink);
    require(absent.error == jfg::AudioWorkerError::not_installed);
    require(validator.validation_count == 0U);
    require(sink.prepare_count == 0U);
    require(sink.commit_count == 0U);
    require(worker.uninstall({}) == jfg::AudioWorkerError::not_installed);
    require(worker.install(nullptr).error ==
        jfg::AudioWorkerError::invalid_program);

    std::size_t first_destruction_count = 0U;
    auto first_program = std::make_unique<BrokeredRspProgram>();
    BrokeredRspProgram* const first_observer = first_program.get();
    first_observer->destruction_count = &first_destruction_count;
    const auto first_install = worker.install(std::move(first_program));
    require(first_install.ok());
    jfg::AudioWorkerError destructor_uninstall_error =
        jfg::AudioWorkerError::none;
    first_observer->destructor_worker = &worker;
    first_observer->destructor_installation = first_install.installation;
    first_observer->destructor_uninstall_error = &destructor_uninstall_error;

    std::size_t rejected_destruction_count = 0U;
    auto rejected_program = std::make_unique<BrokeredRspProgram>();
    rejected_program->destruction_count = &rejected_destruction_count;
    const auto double_install = worker.install(std::move(rejected_program));
    require(double_install.error == jfg::AudioWorkerError::already_installed);
    require(rejected_destruction_count == 1U);
    require(first_destruction_count == 0U);

    auto other_program = std::make_unique<BrokeredRspProgram>();
    const auto other_install = other_worker.install(std::move(other_program));
    require(other_install.ok());

    const std::size_t execution_before_stale = first_observer->execution_count;
    require(worker.submit(
                {}, task.view(), validator, sink).error ==
        jfg::AudioWorkerError::stale_installation);
    require(worker.submit(
                other_install.installation,
                task.view(),
                validator,
                sink).error == jfg::AudioWorkerError::stale_installation);
    require(first_observer->execution_count == execution_before_stale);

    task.reset_output();
    const auto first_dispatch = worker.submit(
        first_install.installation,
        task.view(),
        validator,
        sink);
    require(first_dispatch.ok());
    require(sink.output_visible);
    require(sink.prepare_count == 1U);
    require(sink.commit_count == 1U);

    task.reset_output();
    const auto reentrant_view = task.view();
    ReentrantCompletionSink reentrant;
    reentrant.worker = &worker;
    reentrant.installation = first_install.installation;
    reentrant.task = &reentrant_view;
    reentrant.validator = &validator;
    reentrant.output = task.output;
    reentrant.expected = expected_primary();
    const auto reentrant_dispatch = worker.submit(
        first_install.installation,
        reentrant_view,
        validator,
        reentrant);
    require(reentrant_dispatch.ok());
    require(reentrant.output_visible);
    require(reentrant.uninstall_error == jfg::AudioWorkerError::busy);
    require(reentrant.nested_submit_error == jfg::AudioWorkerError::busy);
    require(reentrant.prepare_count == 1U);
    require(reentrant.commit_count == 1U);

    task.reset_output();
    first_observer->throw_execute = true;
    RecordingCompletionSink throwing_sink{task.output, expected_primary()};
    const auto throwing_dispatch = worker.submit(
        first_install.installation,
        task.view(),
        validator,
        throwing_sink);
    require(throwing_dispatch.error == jfg::AudioWorkerError::none);
    require(throwing_dispatch.scheduled.task.error ==
        jfg::AudioTaskError::backend_exception);
    require(throwing_sink.prepare_count == 0U);
    require(throwing_sink.commit_count == 0U);
    first_observer->throw_execute = false;

    task.reset_output();
    ExactOutputValidator throwing_validator;
    throwing_validator.expected = expected_primary();
    throwing_validator.throw_validate = true;
    RecordingCompletionSink validator_sink{task.output, expected_primary()};
    const auto validator_dispatch = worker.submit(
        first_install.installation,
        task.view(),
        throwing_validator,
        validator_sink);
    require(validator_dispatch.scheduled.task.error ==
        jfg::AudioTaskError::backend_exception);
    require(validator_sink.prepare_count == 0U);
    require(validator_sink.commit_count == 0U);

    task.reset_output();
    RecordingCompletionSink rejected_sink{task.output, expected_primary()};
    rejected_sink.accept = false;
    const std::size_t execution_before_rejection =
        first_observer->execution_count;
    const auto rejected_dispatch = worker.submit(
        first_install.installation,
        task.view(),
        validator,
        rejected_sink);
    require(rejected_dispatch.error == jfg::AudioWorkerError::none);
    require(rejected_dispatch.scheduled.task.ok());
    require(!rejected_dispatch.ok());
    require(rejected_sink.prepare_count == 1U);
    require(rejected_sink.commit_count == 0U);
    require(first_observer->execution_count == execution_before_rejection + 1U);

    require(worker.uninstall(other_install.installation) ==
        jfg::AudioWorkerError::stale_installation);
    require(first_destruction_count == 0U);
    require(worker.uninstall(first_install.installation) ==
        jfg::AudioWorkerError::none);
    require(first_destruction_count == 1U);
    require(destructor_uninstall_error == jfg::AudioWorkerError::not_installed);
    require(worker.uninstall(first_install.installation) ==
        jfg::AudioWorkerError::not_installed);

    std::size_t second_destruction_count = 0U;
    auto second_program = std::make_unique<BrokeredRspProgram>();
    second_program->destruction_count = &second_destruction_count;
    const auto second_install = worker.install(std::move(second_program));
    require(second_install.ok());
    require(second_install.installation != first_install.installation);
    require(worker.submit(
                first_install.installation,
                task.view(),
                validator,
                sink).error == jfg::AudioWorkerError::stale_installation);
    require(worker.uninstall(second_install.installation) ==
        jfg::AudioWorkerError::none);
    require(second_destruction_count == 1U);
    require(other_worker.uninstall(other_install.installation) ==
        jfg::AudioWorkerError::none);

    require(jfg::audio_worker_error_message(
                jfg::AudioWorkerError::stale_installation)[0] != '\0');
}

void test_task_bounds() {
    const jfg::AudioTaskBridge bridge;
    SyntheticTask task;
    SyntheticBackend backend;
    ExactOutputValidator validator;

    auto invalid = task.view(jfg::AudioProgramVariant::unknown);
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::unsupported_variant,
        task);
    require(backend.execution_count == 0U);

    invalid = task.view();
    invalid.active_program = {};
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::empty_active_program,
        task);

    std::array<std::byte, 5U> misaligned_program{};
    invalid = task.view();
    invalid.active_program = misaligned_program;
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::active_program_misaligned,
        task);

    const std::vector<std::byte> oversized_program(
        jfg::kMaximumAudioActiveProgramBytes + 4U);
    invalid = task.view();
    invalid.active_program = oversized_program;
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::active_program_too_large,
        task);

    invalid = task.view();
    invalid.program_data = {};
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::empty_program_data,
        task);

    const std::vector<std::byte> oversized_data(
        jfg::kMaximumAudioProgramDataBytes + 1U);
    invalid = task.view();
    invalid.program_data = oversized_data;
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::program_data_too_large,
        task);

    invalid = task.view();
    invalid.command_stream = {};
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::empty_command_stream,
        task);

    std::array<std::byte, 9U> misaligned_commands{};
    invalid = task.view();
    invalid.command_stream = misaligned_commands;
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::command_stream_misaligned,
        task);

    const std::vector<std::byte> oversized_commands(
        jfg::kMaximumAudioCommandStreamBytes +
        jfg::kAudioCommandAlignmentBytes);
    invalid = task.view();
    invalid.command_stream = oversized_commands;
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::command_stream_too_large,
        task);

    invalid = task.view();
    invalid.output = {};
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::empty_output,
        task);

    std::array<std::byte, 6U> misaligned_output{};
    invalid = task.view();
    invalid.output = misaligned_output;
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::output_misaligned,
        task);

    std::vector<std::byte> oversized_output(
        jfg::kMaximumAudioOutputBytes + jfg::kAudioOutputFrameBytes);
    invalid = task.view();
    invalid.output = std::span<std::byte>(
        oversized_output.data(),
        oversized_output.size());
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::output_too_large,
        task);
}

void test_referenced_memory_bounds() {
    const jfg::AudioTaskBridge bridge;
    SyntheticTask task;
    SyntheticBackend backend;
    ExactOutputValidator validator;

    auto invalid = task.view();
    invalid.referenced_regions = {};
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::missing_referenced_memory,
        task);

    std::array<jfg::AudioReferencedRegion,
        jfg::kMaximumAudioReferencedRegionCount + 1U> too_many{};
    for (auto& region : too_many) {
        region.bytes = task.region_a;
    }
    invalid = task.view();
    invalid.referenced_regions = too_many;
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::too_many_referenced_regions,
        task);

    auto empty_regions = task.regions;
    empty_regions[0].bytes = {};
    invalid = task.view();
    invalid.referenced_regions = empty_regions;
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::empty_referenced_region,
        task);

    const std::vector<std::byte> oversized(
        jfg::kMaximumAudioReferencedRegionBytes + 1U);
    const std::array<jfg::AudioReferencedRegion, 1U> oversized_region{
        jfg::AudioReferencedRegion{oversized},
    };
    invalid = task.view();
    invalid.referenced_regions = oversized_region;
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::referenced_region_too_large,
        task);

    const std::vector<std::byte> maximum_a(
        jfg::kMaximumAudioReferencedRegionBytes);
    const std::vector<std::byte> maximum_b(
        jfg::kMaximumAudioReferencedRegionBytes);
    const std::array<jfg::AudioReferencedRegion, 3U> excessive_total{
        jfg::AudioReferencedRegion{maximum_a},
        jfg::AudioReferencedRegion{maximum_b},
        jfg::AudioReferencedRegion{task.region_a},
    };
    invalid = task.view();
    invalid.referenced_regions = excessive_total;
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::referenced_memory_too_large,
        task);

    const std::array<jfg::AudioReferencedRegion, 2U> duplicate_regions{
        jfg::AudioReferencedRegion{task.region_a},
        jfg::AudioReferencedRegion{task.region_a},
    };
    invalid = task.view();
    invalid.referenced_regions = duplicate_regions;
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::overlapping_memory_regions,
        task);

    const std::array<jfg::AudioReferencedRegion, 1U> output_region_alias{
        jfg::AudioReferencedRegion{task.output},
    };
    invalid = task.view();
    invalid.referenced_regions = output_region_alias;
    require_failure(
        bridge.submit(invalid, backend, validator),
        jfg::AudioTaskError::overlapping_memory_regions,
        task);

    const std::array<std::span<const std::byte>, 3U> top_level_aliases{
        std::span<const std::byte>(task.active_program).first<4U>(),
        std::span<const std::byte>(task.program_data).first<4U>(),
        std::span<const std::byte>(task.command_stream).first<8U>(),
    };
    for (const std::span<const std::byte> top_level : top_level_aliases) {
        const std::array<jfg::AudioReferencedRegion, 2U> top_level_alias{
            jfg::AudioReferencedRegion{top_level},
            jfg::AudioReferencedRegion{task.region_b},
        };
        invalid = task.view();
        invalid.referenced_regions = top_level_alias;
        require_failure(
            bridge.submit(invalid, backend, validator),
            jfg::AudioTaskError::overlapping_memory_regions,
            task);
    }

    const std::array<std::span<std::byte>, 3U> output_aliases{
        std::span<std::byte>(task.active_program).first<8U>(),
        std::span<std::byte>(task.program_data).first<8U>(),
        std::span<std::byte>(task.command_stream).first<8U>(),
    };
    for (const std::span<std::byte> output_alias : output_aliases) {
        invalid = task.view();
        invalid.output = output_alias;
        require_failure(
            bridge.submit(invalid, backend, validator),
            jfg::AudioTaskError::overlapping_memory_regions,
            task);
    }
}

void test_capabilities() {
    const jfg::AudioTaskBridge bridge;
    for (const int mutation : {0, 1, 2, 3, 4}) {
        SyntheticTask task;
        SyntheticBackend backend;
        ExactOutputValidator validator;
        switch (mutation) {
        case 0:
            backend.advertised.program_variant_count = 1U;
            break;
        case 1:
            backend.advertised.primary_variant_supported = false;
            break;
        case 2:
            backend.advertised.secondary_variant_supported = false;
            break;
        case 3:
            backend.advertised.referenced_memory_broker_only = false;
            break;
        default:
            backend.advertised.unknown_commands_fail_closed = false;
            break;
        }
        require_failure(
            bridge.submit(task.view(), backend, validator),
            jfg::AudioTaskError::incomplete_backend_capabilities,
            task);
        require(backend.execution_count == 0U);
    }
}

void test_backend_failures() {
    const jfg::AudioTaskBridge bridge;
    const std::array<std::pair<BackendMode, jfg::AudioTaskError>, 12U> cases{
        std::pair{BackendMode::reject, jfg::AudioTaskError::backend_rejected},
        std::pair{BackendMode::incomplete_parse, jfg::AudioTaskError::parse_incomplete},
        std::pair{BackendMode::unsupported_command, jfg::AudioTaskError::unsupported_commands},
        std::pair{BackendMode::wrong_variant, jfg::AudioTaskError::selected_variant_mismatch},
        std::pair{BackendMode::invalid_region, jfg::AudioTaskError::memory_access_violation},
        std::pair{BackendMode::out_of_bounds_read, jfg::AudioTaskError::memory_access_violation},
        std::pair{BackendMode::partial_regions, jfg::AudioTaskError::referenced_memory_incomplete},
        std::pair{BackendMode::partial_output, jfg::AudioTaskError::output_incomplete},
        std::pair{BackendMode::overlapping_output, jfg::AudioTaskError::memory_access_violation},
        std::pair{BackendMode::false_report, jfg::AudioTaskError::invalid_backend_report},
        std::pair{BackendMode::short_parse, jfg::AudioTaskError::invalid_backend_report},
        std::pair{BackendMode::long_parse, jfg::AudioTaskError::invalid_backend_report},
    };

    for (const auto& [mode, expected] : cases) {
        SyntheticTask task;
        SyntheticBackend backend;
        backend.mode = mode;
        ExactOutputValidator validator;
        validator.expected = expected_primary();
        require_failure(
            bridge.submit(task.view(), backend, validator), expected, task);
        require(validator.validation_count == 0U);
    }
}

void test_output_validation_is_transactional() {
    const jfg::AudioTaskBridge bridge;
    for (const bool throws : {false, true}) {
        SyntheticTask task;
        SyntheticBackend backend;
        ExactOutputValidator validator;
        validator.expected = expected_primary();
        validator.reject = !throws;
        validator.throw_validate = throws;
        const auto expected = throws
            ? jfg::AudioTaskError::backend_exception
            : jfg::AudioTaskError::output_validation_failed;
        require_failure(
            bridge.submit(task.view(), backend, validator), expected, task);
        require(validator.validation_count == 1U);
    }
}

void test_exceptions_fail_closed() {
    const jfg::AudioTaskBridge bridge;
    for (const bool capability_throw : {true, false}) {
        SyntheticTask task;
        SyntheticBackend backend;
        backend.throw_capabilities = capability_throw;
        backend.mode = capability_throw
            ? BackendMode::complete
            : BackendMode::throw_execute;
        ExactOutputValidator validator;
        require_failure(
            bridge.submit(task.view(), backend, validator),
            jfg::AudioTaskError::backend_exception,
            task);
        require(backend.execution_count == (capability_throw ? 0U : 1U));
    }
}

}  // namespace

int main() {
    test_both_variants();
    test_rsp_adapter_uses_one_internal_dispatch_wrapper();
    test_scheduler_completion_follows_validated_output();
    test_mutable_work_regions_are_transactional();
    test_runtime_worker_installation_and_busy_identity();
    test_task_bounds();
    test_referenced_memory_bounds();
    test_capabilities();
    test_backend_failures();
    test_output_validation_is_transactional();
    test_exceptions_fail_closed();
    require(jfg::audio_task_error_message(
                jfg::AudioTaskError::memory_access_violation)[0] != '\0');
    return EXIT_SUCCESS;
}
