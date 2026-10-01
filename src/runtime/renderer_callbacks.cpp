#include "jfg/runtime/renderer_callbacks.hpp"

namespace jfg {

RendererCallbackError RendererCallbackRuntime::register_callbacks(
    RendererCallbacks& callbacks) noexcept {
    if (callbacks_ != nullptr) {
        return RendererCallbackError::already_registered;
    }
    callbacks_ = &callbacks;
    frame_pending_ = false;
    frame_tainted_ = false;
    pending_task_count_ = 0U;
    return RendererCallbackError::none;
}

void RendererCallbackRuntime::unregister_callbacks() noexcept {
    callbacks_ = nullptr;
    frame_pending_ = false;
    frame_tainted_ = false;
    pending_task_count_ = 0U;
}

bool RendererCallbackRuntime::registered() const noexcept {
    return callbacks_ != nullptr;
}

bool RendererCallbackRuntime::frame_pending() const noexcept {
    return frame_pending_;
}

bool RendererCallbackRuntime::frame_tainted() const noexcept {
    return frame_tainted_;
}

std::size_t RendererCallbackRuntime::pending_task_count() const noexcept {
    return pending_task_count_;
}

RendererSubmissionResult RendererCallbackRuntime::submit(
    const GraphicsTaskView& task,
    const std::span<const GraphicsReferencedMemoryRegion> referenced_memory)
    noexcept {
    if (callbacks_ == nullptr) {
        return {RendererCallbackError::not_registered, {}};
    }
    if (frame_pending_) {
        return {RendererCallbackError::frame_pending, {}};
    }

    GraphicsTaskBridge bridge;
    GraphicsTaskResult result = bridge.submit(
        task,
        referenced_memory,
        callbacks_->task_backend(),
        callbacks_->output_oracle(),
        callbacks_->completion_sink());
    if (result.ok()) {
        frame_pending_ = true;
        frame_tainted_ = false;
        pending_task_count_ = 1U;
    }
    return {RendererCallbackError::none, result};
}

RendererSubmissionResult RendererCallbackRuntime::submit_additional(
    const GraphicsTaskView& task,
    const std::span<const GraphicsReferencedMemoryRegion> referenced_memory)
    noexcept {
    if (callbacks_ == nullptr) {
        return {RendererCallbackError::not_registered, {}};
    }
    if (!frame_pending_) {
        return {RendererCallbackError::no_frame_pending, {}};
    }
    if (frame_tainted_) {
        return {RendererCallbackError::frame_tainted, {}};
    }

    GraphicsTaskBridge bridge;
    GraphicsTaskResult result = bridge.submit(
        task,
        referenced_memory,
        callbacks_->task_backend(),
        callbacks_->output_oracle(),
        callbacks_->completion_sink());
    if (result.ok()) {
        ++pending_task_count_;
    }
    else {
        // The renderer may have consumed a prefix before rejection. Never
        // present that partial frame as if it were complete.
        frame_tainted_ = true;
    }
    return {RendererCallbackError::none, result};
}

RendererCallbackError RendererCallbackRuntime::present() noexcept {
    if (callbacks_ == nullptr) {
        return RendererCallbackError::not_registered;
    }
    if (!frame_pending_) {
        return RendererCallbackError::no_frame_pending;
    }
    if (frame_tainted_) {
        return RendererCallbackError::frame_tainted;
    }

    try {
        if (!callbacks_->present()) {
            return RendererCallbackError::presentation_rejected;
        }
    }
    catch (...) {
        return RendererCallbackError::presentation_exception;
    }

    frame_pending_ = false;
    frame_tainted_ = false;
    pending_task_count_ = 0U;
    return RendererCallbackError::none;
}

const char* renderer_callback_error_message(
    const RendererCallbackError error) noexcept {
    switch (error) {
    case RendererCallbackError::none:
        return "no error";
    case RendererCallbackError::already_registered:
        return "renderer callbacks are already registered";
    case RendererCallbackError::not_registered:
        return "renderer callbacks are not registered";
    case RendererCallbackError::frame_pending:
        return "a rendered frame is already pending presentation";
    case RendererCallbackError::frame_tainted:
        return "a pending frame contains a rejected graphics task";
    case RendererCallbackError::no_frame_pending:
        return "no rendered frame is pending presentation";
    case RendererCallbackError::presentation_rejected:
        return "renderer presentation was rejected";
    case RendererCallbackError::presentation_exception:
        return "renderer presentation raised an exception";
    }
    return "unknown renderer callback error";
}

}  // namespace jfg
