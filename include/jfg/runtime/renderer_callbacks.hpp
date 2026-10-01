#pragma once

#include "jfg/runtime/graphics_task_bridge.hpp"

#include <cstddef>
#include <span>

namespace jfg {

enum class RendererCallbackError {
    none,
    already_registered,
    not_registered,
    frame_pending,
    frame_tainted,
    no_frame_pending,
    presentation_rejected,
    presentation_exception,
};

struct RendererSubmissionResult {
    RendererCallbackError callback_error = RendererCallbackError::none;
    GraphicsTaskResult task;

    [[nodiscard]] bool ok() const noexcept {
        return callback_error == RendererCallbackError::none && task.ok();
    }
};

// Owns the concrete objects for a renderer binding. The output oracle remains
// a distinct object: GraphicsTaskBridge rejects a backend that attempts to
// authorize its own pixels.
class RendererCallbacks {
public:
    virtual ~RendererCallbacks() = default;

    [[nodiscard]] virtual GraphicsTaskBackend& task_backend() noexcept = 0;
    [[nodiscard]] virtual GraphicsOutputOracle& output_oracle() noexcept = 0;
    [[nodiscard]] virtual GraphicsCompletionSink& completion_sink() noexcept = 0;

    // Presentation is invoked only after GraphicsTaskBridge has validated the
    // rendered pixels and committed renderer completion.
    [[nodiscard]] virtual bool present() = 0;
};

// Project-owned callback registration and lifecycle boundary. A successful
// first task creates one pending frame. Additional independently validated
// tasks may be accumulated explicitly before that frame is presented once.
class RendererCallbackRuntime final {
public:
    RendererCallbackRuntime() = default;
    ~RendererCallbackRuntime() = default;
    RendererCallbackRuntime(const RendererCallbackRuntime&) = delete;
    RendererCallbackRuntime& operator=(const RendererCallbackRuntime&) = delete;
    RendererCallbackRuntime(RendererCallbackRuntime&&) = delete;
    RendererCallbackRuntime& operator=(RendererCallbackRuntime&&) = delete;

    [[nodiscard]] RendererCallbackError register_callbacks(
        RendererCallbacks& callbacks) noexcept;
    void unregister_callbacks() noexcept;

    [[nodiscard]] bool registered() const noexcept;
    [[nodiscard]] bool frame_pending() const noexcept;
    [[nodiscard]] bool frame_tainted() const noexcept;
    [[nodiscard]] std::size_t pending_task_count() const noexcept;

    [[nodiscard]] RendererSubmissionResult submit(
        const GraphicsTaskView& task,
        std::span<const GraphicsReferencedMemoryRegion> referenced_memory)
        noexcept;

    [[nodiscard]] RendererSubmissionResult submit_additional(
        const GraphicsTaskView& task,
        std::span<const GraphicsReferencedMemoryRegion> referenced_memory)
        noexcept;

    [[nodiscard]] RendererCallbackError present() noexcept;

private:
    RendererCallbacks* callbacks_ = nullptr;
    bool frame_pending_ = false;
    bool frame_tainted_ = false;
    std::size_t pending_task_count_ = 0U;
};

[[nodiscard]] const char* renderer_callback_error_message(
    RendererCallbackError error) noexcept;

}  // namespace jfg
