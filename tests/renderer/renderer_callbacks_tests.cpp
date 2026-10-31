#include "jfg/runtime/renderer_callbacks.hpp"

#include <array>
#include <cstddef>
#include <cstdlib>
#include <stdexcept>

namespace {

void require(const bool condition) {
    if (!condition) {
        std::abort();
    }
}

class Backend final : public jfg::GraphicsTaskBackend {
public:
    std::array<std::byte, 64U> pixels{};
    bool accept = true;
    std::size_t executions = 0U;

    [[nodiscard]] jfg::GraphicsBackendCapabilities capabilities() const override {
        return {
            jfg::GraphicsFamily::bounded_custom,
            jfg::GraphicsOutputKind::rendered_pixels,
            jfg::kGraphicsBaseCustomHandlerCount,
            jfg::kGraphicsVariantOverrideCount,
            true,
            true,
        };
    }

    [[nodiscard]] jfg::GraphicsBackendReport execute(
        const jfg::GraphicsTaskView&,
        jfg::GraphicsMemoryBroker& memory) override {
        ++executions;
        (void)memory.read(1U, 0U, 16U);
        return {
            accept,
            accept,
            2U,
            0U,
            {jfg::GraphicsOutputKind::rendered_pixels,
                4U, 4U, 16U, 4U, pixels},
        };
    }
};

class Oracle final : public jfg::GraphicsOutputOracle {
public:
    bool accept = true;
    std::size_t validations = 0U;

    [[nodiscard]] bool validate(const jfg::GraphicsOutputView&) override {
        ++validations;
        return accept;
    }
};

class Completion final : public jfg::GraphicsCompletionSink {
public:
    std::size_t preparations = 0U;
    std::size_t commits = 0U;

    [[nodiscard]] bool prepare_renderer_complete(std::size_t) override {
        ++preparations;
        return true;
    }

    void commit_renderer_complete(std::size_t) noexcept override {
        ++commits;
    }
};

class Callbacks final : public jfg::RendererCallbacks {
public:
    Backend backend;
    Oracle oracle;
    Completion completion;
    bool present_accept = true;
    bool present_throw = false;
    std::size_t presentations = 0U;

    [[nodiscard]] jfg::GraphicsTaskBackend& task_backend() noexcept override {
        return backend;
    }

    [[nodiscard]] jfg::GraphicsOutputOracle& output_oracle() noexcept override {
        return oracle;
    }

    [[nodiscard]] jfg::GraphicsCompletionSink& completion_sink() noexcept override {
        return completion;
    }

    [[nodiscard]] bool present() override {
        ++presentations;
        if (present_throw) {
            throw std::runtime_error("synthetic present failure");
        }
        return present_accept;
    }
};

struct Task {
    std::array<std::byte, 64U> program{};
    std::array<std::byte, 32U> program_data{};
    std::array<std::byte, 16U> commands{};
    std::array<std::byte, 16U> memory{};
    std::array<jfg::GraphicsReferencedMemoryRegion, 1U> regions{
        jfg::GraphicsReferencedMemoryRegion{1U, memory},
    };

    [[nodiscard]] jfg::GraphicsTaskView view() const noexcept {
        return {jfg::GraphicsFamily::bounded_custom,
            program, program_data, commands};
    }
};

}  // namespace

int main() {
    jfg::RendererCallbackRuntime runtime;
    Callbacks callbacks;
    Callbacks second_callbacks;
    const Task task;

    require(!runtime.registered());
    require(runtime.submit(task.view(), task.regions).callback_error ==
        jfg::RendererCallbackError::not_registered);
    require(runtime.present() == jfg::RendererCallbackError::not_registered);

    require(runtime.register_callbacks(callbacks) ==
        jfg::RendererCallbackError::none);
    require(runtime.register_callbacks(second_callbacks) ==
        jfg::RendererCallbackError::already_registered);
    require(runtime.present() ==
        jfg::RendererCallbackError::no_frame_pending);
    require(runtime.submit_additional(task.view(), task.regions).callback_error ==
        jfg::RendererCallbackError::no_frame_pending);

    const jfg::RendererSubmissionResult accepted =
        runtime.submit(task.view(), task.regions);
    require(accepted.ok());
    require(runtime.frame_pending());
    require(!runtime.frame_tainted());
    require(runtime.pending_task_count() == 1U);
    require(callbacks.backend.executions == 1U);
    require(callbacks.oracle.validations == 1U);
    require(callbacks.completion.preparations == 1U);
    require(callbacks.completion.commits == 1U);
    require(runtime.submit(task.view(), task.regions).callback_error ==
        jfg::RendererCallbackError::frame_pending);
    const jfg::RendererSubmissionResult additional =
        runtime.submit_additional(task.view(), task.regions);
    require(additional.ok());
    require(runtime.pending_task_count() == 2U);
    require(callbacks.backend.executions == 2U);
    require(callbacks.oracle.validations == 2U);
    require(callbacks.completion.commits == 2U);

    callbacks.present_accept = false;
    require(runtime.present() ==
        jfg::RendererCallbackError::presentation_rejected);
    require(runtime.frame_pending());
    callbacks.present_accept = true;
    callbacks.present_throw = true;
    require(runtime.present() ==
        jfg::RendererCallbackError::presentation_exception);
    require(runtime.frame_pending());
    callbacks.present_throw = false;
    require(runtime.present() == jfg::RendererCallbackError::none);
    require(!runtime.frame_pending());
    require(runtime.pending_task_count() == 0U);
    require(callbacks.presentations == 3U);
    require(runtime.present() ==
        jfg::RendererCallbackError::no_frame_pending);

    callbacks.oracle.accept = false;
    const jfg::RendererSubmissionResult rejected =
        runtime.submit(task.view(), task.regions);
    require(rejected.callback_error == jfg::RendererCallbackError::none);
    require(rejected.task.error == jfg::GraphicsTaskError::output_rejected);
    require(!runtime.frame_pending());

    callbacks.oracle.accept = true;
    require(runtime.submit(task.view(), task.regions).ok());
    callbacks.oracle.accept = false;
    const jfg::RendererSubmissionResult rejected_additional =
        runtime.submit_additional(task.view(), task.regions);
    require(rejected_additional.task.error ==
        jfg::GraphicsTaskError::output_rejected);
    require(runtime.frame_pending());
    require(runtime.frame_tainted());
    require(runtime.pending_task_count() == 1U);
    require(runtime.present() == jfg::RendererCallbackError::frame_tainted);

    runtime.unregister_callbacks();
    require(!runtime.registered());
    require(!runtime.frame_pending());
    require(!runtime.frame_tainted());
    require(runtime.register_callbacks(second_callbacks) ==
        jfg::RendererCallbackError::none);

    require(renderer_callback_error_message(
        jfg::RendererCallbackError::presentation_exception) != nullptr);
    return 0;
}
