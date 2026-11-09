#include "jfg/boot/original_os_probe.hpp"
#include "runtime_services.hpp"
namespace jfg::boot::native::detail {
void hash_u32(jfg::testkernel::Sha256 &hasher, const std::uint32_t value) {
  const std::array<std::uint8_t, 4U> bytes = {
      static_cast<std::uint8_t>(value >> 24U),
      static_cast<std::uint8_t>(value >> 16U),
      static_cast<std::uint8_t>(value >> 8U),
      static_cast<std::uint8_t>(value)};
  hasher.update_bytes(bytes.data(), bytes.size());
}

void hash_u64(jfg::testkernel::Sha256 &hasher, const std::uint64_t value) {
  hash_u32(hasher, static_cast<std::uint32_t>(value >> 32U));
  hash_u32(hasher, static_cast<std::uint32_t>(value));
}

std::string journal_hash(const State &state) {
  jfg::testkernel::Sha256 hasher;
  static constexpr std::string_view domain = "jfg-phase6-native-journal-v1";
  hasher.update_bytes(domain.data(), domain.size());
  hash_u64(hasher, state.journal.count);
  for (std::size_t index = 0U; index < state.journal.count; ++index) {
    const NativeEvent &event = state.journal.entries[index];
    hash_u32(hasher, static_cast<std::uint32_t>(event.kind));
    hash_u32(hasher, event.a);
    hash_u32(hasher, event.b);
    hash_u32(hasher, event.c);
  }
  return jfg::testkernel::hex_digest(hasher.finish());
}

std::string mmio_trace_text(const State &state) {
  std::string trace;
  for (std::size_t index = 0U; index < state.journal.count; ++index) {
    const NativeEvent &event = state.journal.entries[index];
    if (event.kind != NativeEventKind::kMmioRead &&
        event.kind != NativeEventKind::kMmioWrite)
      continue;
    if (!trace.empty())
      trace.push_back(',');
    char entry[13U]{};
    (void)std::snprintf(entry, sizeof(entry), "%c:0x%08x",
                        event.kind == NativeEventKind::kMmioWrite ? 'w' : 'r',
                        event.a);
    trace += entry;
  }
  return trace;
}

std::string state_hash(const State &state) {
  jfg::testkernel::Sha256 hasher;
  static constexpr std::string_view domain = "jfg-phase6-native-state-v1";
  hasher.update_bytes(domain.data(), domain.size());
  hasher.update_bytes(state.rdram, kRdramSize);
  hash_u32(hasher, state.root_priority);
  hash_u32(hasher, state.interrupt_mask);
  hash_u32(hasher, state.vi_mode);
  hash_u32(hasher, state.vi_queue);
  hash_u32(hasher, state.vi_message);
  hash_u32(hasher, state.vi_retrace_interval);
  hash_u32(hasher, state.vi_current_framebuffer);
  hash_u32(hasher, state.vi_next_framebuffer);
  hash_u32(hasher, state.vi_special_features);
  hash_u32(hasher, state.vi_blacked ? 1U : 0U);
  hash_u64(hasher, state.vi_frames);
  hash_u64(hasher, state.vi_interrupts);
  hash_u64(hasher, state.vi_messages_delivered);
  hash_u64(hasher, state.vi_retraces);
  hash_u64(hasher, state.scheduler == nullptr
                       ? 0U
                       : state.scheduler->dispatch_count());
  hash_u64(hasher, state.thread_order.size());
  for (const auto &[guest, id] : state.thread_order) {
    hash_u32(hasher, guest);
    hash_u32(hasher, static_cast<std::uint32_t>(id));
    const auto snapshot = state.scheduler->snapshot_of(id);
    hash_u32(hasher, snapshot.has_value() ? snapshot->priority : 0U);
    hash_u32(hasher, snapshot.has_value()
                         ? static_cast<std::uint32_t>(snapshot->state)
                         : 0U);
    hash_u32(hasher, snapshot.has_value() ? snapshot->blocked_queue : 0U);
  }
  return jfg::testkernel::hex_digest(hasher.finish());
}

void ledger(State &state, std::string_view category, std::string_view operation,
            std::uint32_t guest_target) {
  if (!state.ledgered) {
    state.ledgered = true;
    jfg::support_event("failure=" + std::string(category) + "/" + std::string(operation));
    std::fprintf(stdout,
                 "{\"kind\":\"jfg-phase6-native-first-trap\",\"category\":\"%.*"
                 "s\",\"guest_target\":\"0x%08x\",\"operation\":\"%.*s\","
                 "\"disposition\":\"fail-closed-trap\",\"count\":1}\n",
                 static_cast<int>(category.size()), category.data(),
                 guest_target, static_cast<int>(operation.size()),
                 operation.data());
    std::fflush(stdout);
  }
}

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
LONG WINAPI child_exception_filter(EXCEPTION_POINTERS *exception);

// Explicit private diagnostics only: abort otherwise bypasses the unhandled
// exception filter and loses the guest state at a fail-closed switch trap.
void private_abort_capture(int signal_number) {
  (void)signal_number;
  // Explicit private capture only: retain the aborting host call chain before
  // the exception filter exits. No addresses are written during ordinary Play.
  if(const auto* state=g_active_child_state;state && !state->rdram_capture_path.empty()) {
    FILE* stack=nullptr;
    (void)fopen_s(&stack,(state->rdram_capture_path+".abort-stack.txt").c_str(),"wb");
    if(stack) {
      void* frames[64]{};
      const auto count=CaptureStackBackTrace(0,64,frames,nullptr);
      for(unsigned i=0;i<count;++i) {
        HMODULE module=nullptr;char name[MAX_PATH]{};
        (void)GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|
            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCSTR>(frames[i]),&module);
        if(module)(void)GetModuleFileNameA(module,name,MAX_PATH);
        const char* basename=std::strrchr(name,'\\');
        std::fprintf(stack,"%u %s %llx\n",i,basename?basename+1:name,
            static_cast<unsigned long long>(reinterpret_cast<std::uintptr_t>(frames[i])-
            reinterpret_cast<std::uintptr_t>(module)));
      }
      std::fclose(stack);
    }
  }
  CONTEXT private_abort_context{};
  RtlCaptureContext(&private_abort_context);
  EXCEPTION_RECORD private_abort_record{};
  private_abort_record.ExceptionCode=0xe04a4647U;
  private_abort_record.ExceptionAddress=
      reinterpret_cast<void*>(private_abort_context.Rip);
  EXCEPTION_POINTERS private_abort_pointers{&private_abort_record,&private_abort_context};
  (void)child_exception_filter(&private_abort_pointers);
}

constexpr std::array<std::uint32_t,10> kPrivatePageWatchWords{
    (game_data("diagnostic.currentModel")&0x1FFFFFFFU),((game_data("diagnostic.modelScratch")&0x1FFFFFFFU)+0U),((game_data("diagnostic.modelScratch")&0x1FFFFFFFU)+4U),((game_data("diagnostic.modelScratch")&0x1FFFFFFFU)+8U),((game_data("diagnostic.modelScratch")&0x1FFFFFFFU)+12U),
    ((game_data("diagnostic.modelScratch")&0x1FFFFFFFU)+16U),((game_data("diagnostic.modelScratch")&0x1FFFFFFFU)+20U),((game_data("diagnostic.modelScratch")&0x1FFFFFFFU)+24U),((game_data("diagnostic.modelScratch")&0x1FFFFFFFU)+28U),((game_data("diagnostic.modelScratch")&0x1FFFFFFFU)+32U)};
struct PrivatePageWriteStep {
  void* page = nullptr;
  std::uintptr_t instruction = 0U;
  std::array<std::uint32_t,10> before{};
};
thread_local PrivatePageWriteStep private_page_write_step{};
bool arm_private_memory_pages(State& state) {
  const auto base=reinterpret_cast<std::uintptr_t>(state.rdram);
  constexpr std::array<std::uintptr_t,4> offsets{(game_data("diagnostic.modelScratch")&0x1FFFF000U),(game_data("diagnostic.currentModel")&0x1FFFF000U),((game_data("diagnostic.modelScratch")&0x1FFFF000U)+0x20000000U),((game_data("diagnostic.currentModel")&0x1FFFF000U)+0x20000000U)};
  for (const auto offset:offsets) {
    MEMORY_BASIC_INFORMATION info{};
    if (VirtualQuery(reinterpret_cast<void*>(base+offset),&info,sizeof(info))==0U ||
        info.State!=MEM_COMMIT || info.Protect!=PAGE_READWRITE)return false;
  }
  std::size_t protected_pages=0U;
  for (const auto offset:offsets) {
    DWORD previous=0U;
    if (!VirtualProtect(reinterpret_cast<void*>(base+offset),4096U,PAGE_READONLY,&previous)) {
      for (std::size_t restore=0U;restore<protected_pages;++restore)
        (void)VirtualProtect(reinterpret_cast<void*>(base+offsets[restore]),4096U,PAGE_READWRITE,&previous);
      return false;
    }
    ++protected_pages;
  }
  state.private_model_pages_ready=true;
  FILE* page_watch_receipt=nullptr;
  (void)fopen_s(&page_watch_receipt,(state.rdram_capture_path+".watch-setup.txt").c_str(),"ab");
  if (page_watch_receipt!=nullptr) {
    std::fprintf(page_watch_receipt,"page-watch cached-and-uncached pages=4 words=10 vi=%llu\n",
                 static_cast<unsigned long long>(state.vi_retraces));
    std::fclose(page_watch_receipt);
  }
  return true;
}
LONG CALLBACK private_page_write_observer(EXCEPTION_POINTERS* exception) {
  auto* const state=g_active_child_state;
  if (state==nullptr || !state->private_model_page_watch || exception==nullptr ||
      exception->ExceptionRecord==nullptr || exception->ContextRecord==nullptr)
    return EXCEPTION_CONTINUE_SEARCH;
  auto& record=*exception->ExceptionRecord;
  auto& host=*exception->ContextRecord;
  auto& pending=private_page_write_step;
  if (record.ExceptionCode==EXCEPTION_SINGLE_STEP && pending.page!=nullptr) {
    DWORD previous=0U;
    if (!VirtualProtect(pending.page,4096U,PAGE_READONLY,&previous))
      fail_closed_dispatch(*state,"private-memory-watch","page-reprotect",state->guest_last_pc);
    pending.page=nullptr;
    host.EFlags&=~0x100U;
    for (std::size_t watch_index=0U;watch_index<kPrivatePageWatchWords.size();++watch_index) {
      std::uint32_t current=0U;
      std::memcpy(&current,state->rdram+kPrivatePageWatchWords[watch_index],4U);
      const auto before=pending.before[watch_index];
      const bool invalid=watch_index==0U
          ? before>=0x80000000U && before<0x80400000U && current!=0U &&
            (current<0x80000000U || current>=0x80400000U)
          : current!=before;
      if (invalid) {
        state->private_model_pointer=before;
        state->private_model_write_offset=kPrivatePageWatchWords[watch_index];
        state->private_memory_writer_pc=pending.instruction;
        state->private_model_write_trap=true;
        return child_exception_filter(exception);
      }
    }
    return EXCEPTION_CONTINUE_EXECUTION;
  }
  if (record.ExceptionCode!=EXCEPTION_ACCESS_VIOLATION ||
      record.NumberParameters<2U || record.ExceptionInformation[0]!=1U)
    return EXCEPTION_CONTINUE_SEARCH;
  const auto address=record.ExceptionInformation[1];
  const auto base=reinterpret_cast<std::uintptr_t>(state->rdram);
  if (address<base)return EXCEPTION_CONTINUE_SEARCH;
  const auto mapped_offset=address-base;
  if (!(mapped_offset<kRdramSize ||
        (mapped_offset>=0x20000000U && mapped_offset<0x20000000U+kRdramSize)))
    return EXCEPTION_CONTINUE_SEARCH;
  const auto physical_page=(mapped_offset&0x1fffffffU)&~std::uintptr_t{4095U};
  if (physical_page!=(game_data("diagnostic.modelScratch")&0x1FFFF000U) && physical_page!=(game_data("diagnostic.currentModel")&0x1FFFF000U))
    return EXCEPTION_CONTINUE_SEARCH;
  if (pending.page!=nullptr || (host.EFlags&0x100U)!=0U)
    fail_closed_dispatch(*state,"private-memory-watch","page-step-overlap",state->guest_last_pc);
  for (std::size_t watch_index=0U;watch_index<kPrivatePageWatchWords.size();++watch_index)
    std::memcpy(&pending.before[watch_index],state->rdram+kPrivatePageWatchWords[watch_index],4U);
  pending.page=reinterpret_cast<void*>(address&~std::uintptr_t{4095U});
  pending.instruction=host.Rip;
  DWORD previous=0U;
  if (!VirtualProtect(pending.page,4096U,PAGE_READWRITE,&previous))
    fail_closed_dispatch(*state,"private-memory-watch","page-write-enable",state->guest_last_pc);
  host.EFlags|=0x100U;
  return EXCEPTION_CONTINUE_EXECUTION;
}

thread_local volatile bool private_model_watch_armed = false;
constexpr std::array<std::uint32_t,4> kPrivateMemoryWatchOffsets{(game_data("diagnostic.currentModel")&0x1FFFFFFFU),((game_data("diagnostic.modelScratch")&0x1FFFFFFFU)+0U),((game_data("diagnostic.modelScratch")&0x1FFFFFFFU)+12U),((game_data("diagnostic.modelScratch")&0x1FFFFFFFU)+32U)};
thread_local std::array<std::uint32_t,4> private_model_watch_previous{};
bool arm_private_model_write_watch(State& state) {
  const DWORD requesting_thread=GetCurrentThreadId();
  const auto watched_address=reinterpret_cast<DWORD64>(state.rdram+(game_data("diagnostic.currentModel")&0x1FFFFFFFU));
  bool configured=false;
  DWORD watch_error=0U;
  DWORD64 original_dr0=0U,original_dr7=0U;
  std::thread private_watch_helper([&] {
    HANDLE requesting_handle=OpenThread(
        THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT|THREAD_SET_CONTEXT,FALSE,requesting_thread);
    if (requesting_handle==nullptr) { watch_error=GetLastError();return; }
    CONTEXT debug_context{};
    debug_context.ContextFlags=CONTEXT_DEBUG_REGISTERS;
    if (SuspendThread(requesting_handle)!=DWORD(-1)) {
      if (GetThreadContext(requesting_handle,&debug_context)) {
        original_dr0=debug_context.Dr0;original_dr7=debug_context.Dr7;
        if ((debug_context.Dr7&255U)==0U) {
          debug_context.Dr0=watched_address;
          debug_context.Dr1=reinterpret_cast<DWORD64>(state.rdram+kPrivateMemoryWatchOffsets[1]);
          debug_context.Dr2=reinterpret_cast<DWORD64>(state.rdram+kPrivateMemoryWatchOffsets[2]);
          debug_context.Dr3=reinterpret_cast<DWORD64>(state.rdram+kPrivateMemoryWatchOffsets[3]);
          debug_context.Dr6=0U;
          debug_context.Dr7=(debug_context.Dr7&~DWORD64{0xffff00ffU})|0xdddd0055U;
          configured=SetThreadContext(requesting_handle,&debug_context)!=FALSE;
          if (!configured) watch_error=GetLastError();
        } else watch_error=ERROR_BUSY;
      } else watch_error=GetLastError();
      // Do not perform allocation, logging, or other host work while this
      // requesting thread is suspended. Only the kernel context operations run.
      if (ResumeThread(requesting_handle)==DWORD(-1)) std::_Exit(4);
    } else watch_error=GetLastError();
    CloseHandle(requesting_handle);
  });
  private_watch_helper.join();
  FILE* private_watch_setup_log=nullptr;
  (void)fopen_s(&private_watch_setup_log,(state.rdram_capture_path+".watch-setup.txt").c_str(),"ab");
  if (private_watch_setup_log!=nullptr) {
    std::fprintf(private_watch_setup_log,
        "thread=%lu original_dr0=%llx original_dr7=%llx configured=%u error=%lu watched=%llx\n",
        requesting_thread,original_dr0,original_dr7,configured?1U:0U,watch_error,watched_address);
    std::fclose(private_watch_setup_log);
  }
  if (configured) {
    for (std::size_t watch_index=0;watch_index<kPrivateMemoryWatchOffsets.size();++watch_index)
      std::memcpy(&private_model_watch_previous[watch_index],
                  state.rdram+kPrivateMemoryWatchOffsets[watch_index],4U);
    private_model_watch_armed=true;
  }
  return configured;
}
LONG CALLBACK private_model_write_observer(EXCEPTION_POINTERS* exception) {
  auto* const state=g_active_child_state;
  if (state==nullptr || !state->private_model_hardware_watch ||
      exception==nullptr || exception->ExceptionRecord==nullptr ||
      exception->ContextRecord==nullptr) return EXCEPTION_CONTINUE_SEARCH;
  auto& host=*exception->ContextRecord;
  const auto code=exception->ExceptionRecord->ExceptionCode;
  if (code!=EXCEPTION_SINGLE_STEP || !private_model_watch_armed ||
      (host.Dr6&15U)==0U) return EXCEPTION_CONTINUE_SEARCH;
  const std::array<DWORD64,4> watched_addresses{host.Dr0,host.Dr1,host.Dr2,host.Dr3};
  for (std::size_t watch_index=0;watch_index<kPrivateMemoryWatchOffsets.size();++watch_index) {
    const DWORD64 watch_bit=DWORD64{1}<<watch_index;
    if ((host.Dr6&watch_bit)==0U)continue;
    const auto offset=kPrivateMemoryWatchOffsets[watch_index];
    if (watched_addresses[watch_index]!=reinterpret_cast<DWORD64>(state->rdram+offset))
      return EXCEPTION_CONTINUE_SEARCH;
    std::uint32_t current=0U;
    std::memcpy(&current,state->rdram+offset,4U);
    const auto previous=private_model_watch_previous[watch_index];
    private_model_watch_previous[watch_index]=current;
    host.ContextFlags|=CONTEXT_DEBUG_REGISTERS;host.Dr6&=~watch_bit;
    const bool invalid=watch_index==0U
        ? previous>=0x80000000U && previous<0x80400000U &&
          current!=0U && (current<0x80000000U || current>=0x80400000U)
        : current!=previous;
    if (invalid) {
      state->private_model_pointer=previous;
      state->private_model_write_offset=offset;
      state->private_model_write_trap=true;
      return child_exception_filter(exception);
    }
  }
  return EXCEPTION_CONTINUE_EXECUTION;
}
LONG WINAPI child_exception_filter(EXCEPTION_POINTERS *exception) {
  jfg::support_crash(exception);
  State *const state = g_active_child_state;
  if (state != nullptr) {
    if (state->native_clock_sample_output.is_open())
      state->native_clock_sample_output.flush();
    const std::uint32_t target =
        state->recent_dispatch_position == 0U
            ? 0U
            : state->recent_dispatches[(state->recent_dispatch_position - 1U) %
                                       state->recent_dispatches.size()];
    const DWORD code =
        exception != nullptr && exception->ExceptionRecord != nullptr
            ? exception->ExceptionRecord->ExceptionCode
            : 0U;
    char support_exception[40]{};
    std::snprintf(support_exception, sizeof(support_exception), "native_exception=0x%08lx", static_cast<unsigned long>(code));
    jfg::support_event(support_exception);
    // Private, explicit RAM-capture sessions also retain the otherwise lost
    // native-fault context. Ordinary Play neither captures RAM nor logs host
    // addresses. This observes the failed execution; it never resumes it.
    if (!state->rdram_capture_path.empty()) {
      FILE* private_fault_capture_stream = nullptr;
      (void)fopen_s(&private_fault_capture_stream,
                   (state->rdram_capture_path+".fault.txt").c_str(),"wb");
      FILE* const private_fault_output = private_fault_capture_stream != nullptr
                                            ? private_fault_capture_stream : stderr;

      if (state->private_model_write_trap) {
        std::uint32_t after=0U;
        std::memcpy(&after,state->rdram+state->private_model_write_offset,4U);
        std::fprintf(private_fault_output,"private-memory-write method=%s address=%08x old=%08x new=%08x writer_pc=%llx\n",
                     state->private_model_page_watch ? "pages" : "hardware",
                     0x80000000U+state->private_model_write_offset,state->private_model_pointer,after,
                     static_cast<unsigned long long>(state->private_memory_writer_pc));
      }
      hle::GuestMemory memory({state->rdram, kRdramSize},
                             hle::GuestMemory::Layout::native_word_big_endian);
      std::uint32_t running_thread = 0U;
      const bool thread_read = memory.read_u32(game_data("os.current_thread"), running_thread);
      const auto* record = exception != nullptr ? exception->ExceptionRecord : nullptr;
      const auto access_kind = record != nullptr && record->NumberParameters >= 2U
                                   ? record->ExceptionInformation[0] : 0U;
      const auto access_address = record != nullptr && record->NumberParameters >= 2U
                                      ? record->ExceptionInformation[1] : 0U;
      std::fprintf(private_fault_output,
          "private-native-fault vi=%llu poll=%llu epc=%08x last_pc=%08x last_word=%08x "
          "running_thread=%08x thread_read=%u access_kind=%llu access_address=%llx rdram=%llx\n",
          static_cast<unsigned long long>(state->vi_retraces),
          static_cast<unsigned long long>(state->controller_samples),
          state->guest_epc, state->guest_last_pc, state->guest_last_word,
          running_thread, thread_read ? 1U : 0U,
          static_cast<unsigned long long>(access_kind),
          static_cast<unsigned long long>(access_address),
          static_cast<unsigned long long>(reinterpret_cast<std::uintptr_t>(state->rdram)));
#if defined(_M_X64) || defined(__x86_64__)
      if (exception != nullptr && exception->ContextRecord != nullptr) {
        const auto& host = *exception->ContextRecord;
        std::fprintf(private_fault_output,
            "private-native-registers rax=%llx rbx=%llx rcx=%llx rdx=%llx rsi=%llx rdi=%llx "
            "rbp=%llx rsp=%llx r8=%llx r9=%llx r10=%llx r11=%llx r12=%llx r13=%llx "
            "r14=%llx r15=%llx rip=%llx\n",
            host.Rax, host.Rbx, host.Rcx, host.Rdx, host.Rsi, host.Rdi, host.Rbp, host.Rsp,
            host.R8, host.R9, host.R10, host.R11, host.R12, host.R13, host.R14, host.R15, host.Rip);
      }
#endif
      if (state->private_fault_cpu != nullptr) {
        const auto& cpu = *state->private_fault_cpu;
        const std::array<std::uint64_t,32> registers{
            0, cpu.r1, cpu.r2, cpu.r3, cpu.r4, cpu.r5, cpu.r6, cpu.r7,
            cpu.r8, cpu.r9, cpu.r10, cpu.r11, cpu.r12, cpu.r13, cpu.r14, cpu.r15,
            cpu.r16, cpu.r17, cpu.r18, cpu.r19, cpu.r20, cpu.r21, cpu.r22, cpu.r23,
            cpu.r24, cpu.r25, cpu.r26, cpu.r27, cpu.r28, cpu.r29, cpu.r30, cpu.r31};
        std::fprintf(private_fault_output, "private-last-observed-cpu status=%08x fcr31=%08x",
                     cpu.status_reg, cpu.fcr31);
        for (std::size_t index=0; index<registers.size(); ++index)
          std::fprintf(private_fault_output, " r%zu=%016llx", index,
                       static_cast<unsigned long long>(registers[index]));
        std::fputc('\n', private_fault_output);
      }
      const bool captured = write_private_rdram_capture(*state);
      std::fprintf(private_fault_output, "private-native-rdram-captured=%u\n", captured ? 1U : 0U);
      std::fflush(private_fault_output);
      if (private_fault_capture_stream != nullptr) std::fclose(private_fault_capture_stream);
    }
    if (state->private_model_write_trap) {
      ledger(*state,"private-memory-watch","hardware-model-pointer",state->guest_last_pc);
      std::_Exit(4);
    }
    if (state->active_bzero_address != 0U) {
      std::array<char, 64U> operation{};
      (void)std::snprintf(operation.data(), operation.size(),
                          "bzero-%08x-%08x", state->active_bzero_address,
                          state->active_bzero_length);
      ledger(*state, "native-crash", operation.data(), target);
    } else {
      std::array<char, 64U> operation{};
      const auto module = reinterpret_cast<std::uintptr_t>(
          GetModuleHandleW(nullptr));
      const auto instruction =
          exception != nullptr && exception->ExceptionRecord != nullptr
              ? reinterpret_cast<std::uintptr_t>(
                    exception->ExceptionRecord->ExceptionAddress)
              : 0U;
      (void)std::snprintf(operation.data(), operation.size(),
                          code == EXCEPTION_ACCESS_VIOLATION
                              ? "access-rva-%08llx"
                              : "exception-rva-%08llx",
                          static_cast<unsigned long long>(instruction - module));
      ledger(*state, "native-crash", operation.data(), target);
    }
  }
  std::_Exit(4);
}
#endif

[[noreturn]] void fail_closed_dispatch(State &state, std::string_view category,
                                       std::string_view operation,
                                       std::uint32_t guest_target) {
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (state.input_record.is_open())
    state.input_record.flush();
  if (state.native_clock_sample_output.is_open())
    state.native_clock_sample_output.flush();
  if (state.timing_trace.is_open())
    state.timing_trace.flush();
  state.gameplay_trace.flush();
  if (!state.rdram_capture_path.empty())
    (void)write_private_rdram_capture(state);
#endif
  stop_pc_rumble(state);
  ledger(state, category, operation, guest_target);
  std::_Exit(4);
}

[[noreturn]] void stable_vi_gate(State &state) {
  if (state.journal.overflow || state.mmio_trace == nullptr ||
      state.mmio_trace->unsupported_accesses != 0U ||
      state.vi_interrupts < state.vi_retraces ||
      state.vi_messages_delivered < state.vi_retraces) {
    fail_closed_dispatch(state, "native", "invalid-stable-gate", 0U);
  }
  const std::string state_digest = state_hash(state);
  const std::string journal_digest = journal_hash(state);
  const std::string mmio_trace = mmio_trace_text(state);
  std::fprintf(stdout,
               "{\"kind\":\"jfg-phase6-native-boot\",\"status\":\"stable-vi\","
               "\"build_identity\":\"%s\",\"sanitizer\":\"%s\","
               "\"vi_retraces\":%llu,\"vi_frames\":%llu,"
               "\"vi_interrupts\":%llu,\"vi_messages_delivered\":%llu,"
               "\"vi_queue\":\"0x%08x\","
               "\"threads_created\":%zu,\"rdram_bytes\":%zu,"
               "\"mmio_accesses\":%llu,\"unsupported_accesses\":%llu,"
               "\"mmio_trace\":\"%s\","
               "\"journal_entries\":%zu,\"state_hash\":\"%s\","
               "\"journal_hash\":\"%s\"}\n",
               JFG_PHASE6_BUILD_IDENTITY, JFG_PHASE6_SANITIZER_ID,
               static_cast<unsigned long long>(state.vi_retraces),
               static_cast<unsigned long long>(state.vi_frames),
               static_cast<unsigned long long>(state.vi_interrupts),
               static_cast<unsigned long long>(state.vi_messages_delivered),
               state.vi_queue,
               state.threads.size(), kRdramSize,
               static_cast<unsigned long long>(state.mmio_trace->accesses),
               static_cast<unsigned long long>(
                   state.mmio_trace->unsupported_accesses),
               mmio_trace.c_str(), state.journal.count, state_digest.c_str(),
               journal_digest.c_str());
  std::fflush(stdout);
  jfg::frame_diagnostic_state().finish();
  jfg::finish_interpolation_trace(); jfg::finish_blur_source_audit();
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  state.host_audio.finish_capture();
  state.timing_trace.finish();
  state.input_record.finish();
  state.gameplay_trace.finish();
#endif
  state.guest_clock_trace.finish();
  state.snapshot_writer.finish();
  state.movement_trace.finish();
  state.jump_trace.finish();
  stop_pc_rumble(state);
  std::_Exit(0);
}

#if defined(JFG_PHASE8_LIVE_RUNTIME)
[[noreturn]] void probe_target_gate(State &state) {
#if defined(_WIN32)
  if (state.diagnostic_clock_release_vi != 0U && !state.diagnostic_clock_released)
    fail_closed_dispatch(state,"native-clock-tape","prefix-release-not-reached",0U);
  if (state.native_clock_samples.active()) {
    if (!state.native_clock_samples.finish())
      fail_closed_dispatch(state,"native-clock-tape","incomplete-or-invalid-transcript",0U);
    state.gameplay_trace.event("native-clock-tape",{state.native_clock_samples.samples(),
        state.cpu_count,state.observed_guest_instructions,state.native_clock_samples.replaying()});
  }
#endif
  if (state.mmio_trace == nullptr)
    fail_closed_dispatch(state, "probe", "missing-mmio-trace", 0U);
  if (state.guest_os_probe) {
    const bool target_reached = state.poll_target != 0U
        ? state.controller_samples == state.poll_target
        : state.vi_retraces == state.retrace_target;
    if (!target_reached || state.mmio_trace->unsupported_accesses != 0 || state.mmio_trace->device_error)
      fail_closed_dispatch(state, "guest-probe", "invalid-target", 0U);
    // Explicitly separate this diagnostic from legacy HLE scheduler evidence.
    // In particular, do not invent HLE thread snapshots for original OS threads.

    if (!service_host_audio(state,false) || !write_private_rdram_capture(state))
      fail_closed_dispatch(state,"guest-capture","final-state",0U);
    if (state.presented_frames != 0U && !write_live_frame_capture(state))
      fail_closed_dispatch(state,"guest-capture","final-image",0U);
    if (state.timing_trace) state.timing_trace << "fast-hook\t"
        << state.execution_fast_hits << '\t' << state.observed_guest_instructions << '\n';
    if (state.timing_trace) state.timing_trace << "original-os-health\t" << state.vi_frames << '\t'
        << state.vi_retraces << '\t' << state.presented_frames << '\t'
        << state.audio_device_underruns << '\t' << state.audio_device_overruns << '\t'
        << state.mmio_trace->unsupported_accesses << '\t' << state.observed_guest_instructions << '\n';
    state.retrace_hash_trace.flush(); state.update_hash_trace.flush();
    state.poll_hash_trace.flush(); state.guest_clock_trace.flush();
    state.timing_trace.flush();
    state.gameplay_trace.flush();
    const jfg::boot::OriginalOsProbe observation{state.retrace_target,state.poll_target,
        state.vi_retraces,state.controller_samples,state.completed_game_updates,state.cpu_count,
        state.observed_guest_instructions,state.graphics_tasks,state.decoded_audio_tasks,state_hash(state)};
    const auto record=jfg::boot::original_os_probe_json(observation);
    if(record.empty())fail_closed_dispatch(state,"guest-probe","invalid-observation",0U);
    std::fputs(record.c_str(),stdout);
    std::fflush(stdout); jfg::frame_diagnostic_state().finish(); jfg::finish_interpolation_trace(); jfg::finish_blur_source_audit(); state.host_audio.finish_capture(); state.timing_trace.finish(); state.guest_clock_trace.finish(); state.input_record.finish(); state.gameplay_trace.finish(); state.snapshot_writer.finish(); state.movement_trace.finish(); state.jump_trace.finish(); stop_pc_rumble(state); std::_Exit(0);
  }
  const auto &event_counts = state.journal.observed_counts;
  std::string overlay_sequence;
  for (std::size_t index = 0U; index < state.journal.count; ++index) {
    const NativeEvent &event = state.journal.entries[index];
    if (event.kind != NativeEventKind::kOverlayPublished)
      continue;
    if (!overlay_sequence.empty())
      overlay_sequence.push_back(',');
    overlay_sequence += std::to_string(event.a);
  }
  std::string hle_counts;
  for (std::size_t index = 0U; index < kMappingCount; ++index) {
    if (state.mapped_call_counts[index] == 0U)
      continue;
    if (!hle_counts.empty())
      hle_counts.push_back(',');
    hle_counts += kMappings[index].name;
    hle_counts.push_back('=');
    hle_counts += std::to_string(state.mapped_call_counts[index]);
  }
  std::array<std::size_t, 4U> thread_states{};
  std::string thread_summary;
  if (state.scheduler != nullptr) {
    for (std::size_t thread_index = 0U;
         thread_index < state.thread_order.size(); ++thread_index) {
      const auto &[guest, id] = state.thread_order[thread_index];
      (void)guest;
      const auto snapshot = state.scheduler->snapshot_of(id);
      if (snapshot.has_value()) {
        const auto index = static_cast<std::size_t>(snapshot->state);
        if (index < thread_states.size())
          ++thread_states[index];
        if (!thread_summary.empty())
          thread_summary.push_back(',');
        thread_summary += std::to_string(id);
        thread_summary.push_back(':');
        thread_summary += std::to_string(snapshot->priority);
        thread_summary.push_back(':');
        thread_summary +=
            std::to_string(static_cast<std::uint32_t>(snapshot->state));
        thread_summary.push_back(':');
        char queue[11U]{};
        (void)std::snprintf(queue, sizeof(queue), "%08x",
                            snapshot->blocked_queue);
        thread_summary += queue;
        thread_summary.push_back(':');
        char entry[11U]{};
        (void)std::snprintf(
            entry, sizeof(entry), "%08x",
            thread_index < state.thread_entries.size()
                ? state.thread_entries[thread_index]
                : 0U);
        thread_summary += entry;
      }
    }
  }
  std::uint32_t si_queue = 0U, si_queue_valid = 0U;
  const auto si = state.events.find(5U);
  if (si != state.events.end()) {
    si_queue = si->second.first;
    hle::GuestMemory memory({state.rdram, kRdramSize},
                            hle::GuestMemory::Layout::native_word_big_endian);
    (void)memory.read_u32(si_queue + hle::kMqOffValidCount, si_queue_valid);
  }
  std::string si_dispatch_trace;
  for (const std::uint32_t dispatch_target : state.last_si_dispatch_trace) {
    if (!si_dispatch_trace.empty())
      si_dispatch_trace.push_back(',');
    char entry[11U]{};
    (void)std::snprintf(entry, sizeof(entry), "%08x", dispatch_target);
    si_dispatch_trace += entry;
  }
#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
  if (!service_host_audio(state, false))
    fail_closed_dispatch(state, "audio", "host-device-final", 0U);
  if (!persist_controller_pak(state))
    fail_closed_dispatch(state, "save", "controller-pak-persist", 0U);
  if (!write_live_frame_capture(state))
    fail_closed_dispatch(state, "renderer", "frame-capture", 0U);
  if (!write_private_rdram_capture(state))
    fail_closed_dispatch(state, "runtime", "rdram-capture", 0U);
#endif
  const std::string state_digest = state_hash(state);
  const std::string journal_digest = journal_hash(state);
  const unsigned front_mode = state.rdram[(game_data("globals.frontendMode")&0x1FFFFFFFU) ^ 3U];
  hle::GuestMemory probe_memory(
      {state.rdram, kRdramSize},
      hle::GuestMemory::Layout::native_word_big_endian);
  std::uint32_t player_position_x = 0U;
  std::uint32_t player_position_y = 0U;
  std::uint32_t player_position_z = 0U;
  std::uint16_t player_yaw = 0U;
  if (state.phase9_player_actor != 0U) {
    std::uint32_t rotation_pair = 0U;
    if (probe_memory.read_u32(state.phase9_player_actor, rotation_pair))
      player_yaw = static_cast<std::uint16_t>(rotation_pair >> 16U);
    (void)probe_memory.read_u32(state.phase9_player_actor + 0x0CU,
                                player_position_x);
    (void)probe_memory.read_u32(state.phase9_player_actor + 0x10U,
                                player_position_y);
    (void)probe_memory.read_u32(state.phase9_player_actor + 0x14U,
                                player_position_z);
  }
  std::uint32_t hints_position_x = 0U;
  std::uint32_t hints_position_y = 0U;
  std::uint32_t hints_position_z = 0U;
  std::uint32_t hints_state = 0U;
  std::array<std::uint32_t, 12U> hints_state_words{};
  std::uint16_t hints_yaw = 0U;
  if (state.phase9_hints_actor != 0U) {
    std::uint32_t rotation_pair = 0U;
    if (probe_memory.read_u32(state.phase9_hints_actor, rotation_pair))
      hints_yaw = static_cast<std::uint16_t>(rotation_pair >> 16U);
    (void)probe_memory.read_u32(state.phase9_hints_actor + 0x0CU,
                                hints_position_x);
    (void)probe_memory.read_u32(state.phase9_hints_actor + 0x10U,
                                hints_position_y);
    (void)probe_memory.read_u32(state.phase9_hints_actor + 0x14U,
                                hints_position_z);
    if (probe_memory.read_u32(state.phase9_hints_actor + 0x68U,
                              hints_state) && hints_state != 0U) {
      for (std::size_t word = 0U; word < hints_state_words.size(); ++word)
        (void)probe_memory.read_u32(
            hints_state + static_cast<std::uint32_t>(word * 4U),
            hints_state_words[word]);
    }
  }
  std::uint32_t king_bear_actor = 0U;
  std::uint32_t object_list = 0U;
  std::uint32_t object_count = 0U;
  if (probe_memory.read_u32(game_data("globals.objectList"), object_list) &&
      probe_memory.read_u32(game_data("globals.objectCount"), object_count) &&
      object_list != 0U && object_count <= 1024U) {
    for (std::uint32_t index = 0U; index < object_count; ++index) {
      std::uint32_t actor = 0U;
      std::uint32_t header = 0U;
      std::uint32_t name_word_0 = 0U;
      std::uint32_t name_word_1 = 0U;
      if (!probe_memory.read_u32(object_list + index * 4U, actor) ||
          actor == 0U ||
          !probe_memory.read_u32(actor + game_member("layout.actor.header"), header) || header == 0U ||
          !probe_memory.read_u32(header + 4U, name_word_0) ||
          !probe_memory.read_u32(header + 8U, name_word_1))
        continue;
      if (name_word_0 == 0x4B696E67U && name_word_1 == 0x42656172U) {
        king_bear_actor = actor;
        break;
      }
    }
  }
  std::uint32_t king_bear_position_x = 0U;
  std::uint32_t king_bear_position_y = 0U;
  std::uint32_t king_bear_position_z = 0U;
  std::uint32_t king_bear_state = 0U;
  std::uint32_t king_bear_state_word_0 = 0U;
  std::uint32_t king_bear_sound_handle = 0U;
  std::uint32_t king_bear_state_word_30 = 0U;
  std::uint32_t king_bear_state_word_34 = 0U;
  std::uint16_t king_bear_yaw = 0U;
  if (king_bear_actor != 0U) {
    std::uint32_t rotation_pair = 0U;
    if (probe_memory.read_u32(king_bear_actor, rotation_pair))
      king_bear_yaw = static_cast<std::uint16_t>(rotation_pair >> 16U);
    (void)probe_memory.read_u32(king_bear_actor + 0x0CU,
                                king_bear_position_x);
    (void)probe_memory.read_u32(king_bear_actor + 0x10U,
                                king_bear_position_y);
    (void)probe_memory.read_u32(king_bear_actor + 0x14U,
                                king_bear_position_z);
    if (probe_memory.read_u32(king_bear_actor + 0x68U, king_bear_state) &&
        king_bear_state != 0U) {
      (void)probe_memory.read_u32(king_bear_state, king_bear_state_word_0);
      (void)probe_memory.read_u32(king_bear_state + 0x2CU,
                                  king_bear_sound_handle);
      (void)probe_memory.read_u32(king_bear_state + 0x30U,
                                  king_bear_state_word_30);
      (void)probe_memory.read_u32(king_bear_state + 0x34U,
                                  king_bear_state_word_34);
    }
  }
  std::uint32_t king_bear_callback_section = UINT32_MAX;
  std::uint32_t king_bear_callback_offset = 0U;
  if (state.phase9_king_bear_callback == game_overlay_token("overlay.mrhints.control")) {
    king_bear_callback_section = game_module(OriginalModule::mr_hints);
    king_bear_callback_offset = 0x2E8U;
  } else if (state.phase9_king_bear_callback != 0U) {
    RunlinkAddressResolution resolution{};
    if (resolve_runlink_text_address(
            probe_memory, kRunlinkModuleTablePointer,
            kRunlinkOverlaySlotCount, state.phase9_king_bear_callback,
            resolution) == RunlinkAddressResult::resolved) {
      for (std::uint32_t section = 0U;
           section < jfg_generated_section_count(); ++section) {
        JfgGeneratedSectionMetadata metadata{};
        if (jfg_generated_section_metadata(section, &metadata) != 0 &&
            metadata.is_overlay == 1U &&
            metadata.rom_start == resolution.identity.rom_start &&
            metadata.text_size == resolution.identity.text_size &&
            metadata.data_size == resolution.identity.data_size &&
            metadata.bss_size == resolution.identity.bss_size) {
          king_bear_callback_section = section;
          king_bear_callback_offset = resolution.text_offset;
          break;
        }
      }
    }
  }
  std::array<std::uint32_t, 8U> runlink_module7_words{};
  constexpr std::array<std::uint32_t, 16U> kHintTextStateOffsets{
      0x2A20U, 0x2A24U, 0x2A28U, 0x2A2CU,
      0x2A38U, 0x2A3CU, 0x2A40U, 0x2A44U,
      0x2A4CU, 0x2A58U, 0x2A5CU, 0x2A70U,
      0x2C30U, 0x2C34U, 0x2C3CU, 0x2C40U};
  const std::uint32_t hinttext_section_base =
      section_addresses != nullptr
          ? static_cast<std::uint32_t>(section_addresses[game_module(OriginalModule::hint_text)])
          : 0U;
  std::array<std::uint32_t, kHintTextStateOffsets.size()>
      hinttext_state_words{};
  if (hinttext_section_base != 0U) {
    const std::uint64_t sign_extended_base = static_cast<std::uint64_t>(
        static_cast<std::int64_t>(
            static_cast<std::int32_t>(hinttext_section_base)));
    for (std::size_t word = 0U; word < hinttext_state_words.size(); ++word) {
      const std::uint64_t host_offset = sign_extended_base +
          kHintTextStateOffsets[word] - UINT64_C(0xFFFFFFFF80000000);
      if (host_offset <= kGuestAddressSpan - sizeof(std::uint32_t))
        std::memcpy(&hinttext_state_words[word], state.rdram + host_offset,
                    sizeof(std::uint32_t));
    }
  }
  std::uint32_t runlink_module_table = 0U;
  if (probe_memory.read_u32(kRunlinkModuleTablePointer,
                            runlink_module_table) &&
      runlink_module_table != 0U) {
    const std::uint32_t record = runlink_module_table +
        7U * kRunlinkModuleRecordSize;
    for (std::size_t word = 0U; word < runlink_module7_words.size(); ++word)
      (void)probe_memory.read_u32(
          record + static_cast<std::uint32_t>(word * sizeof(std::uint32_t)),
          runlink_module7_words[word]);
  }
  std::uint64_t weapon_stat_shots = 0U;
  std::uint64_t weapon_stat_hits = 0U;
  std::uint64_t weapon_stat_kills = 0U;
  std::uint32_t player_data = 0U;
  if (probe_memory.read_u32(game_data("globals.selectedPlayer"), player_data) && player_data != 0U) {
    for (std::uint32_t weapon = 0U; weapon < 16U; ++weapon) {
      std::uint32_t shots = 0U;
      std::uint32_t hits = 0U;
      std::uint32_t kills = 0U;
      const std::uint32_t slot = weapon * sizeof(std::uint32_t);
      if (probe_memory.read_u32(player_data + 0x474U + slot, shots))
        weapon_stat_shots += shots;
      if (probe_memory.read_u32(player_data + 0x4B4U + slot, hits))
        weapon_stat_hits += hits;
      if (probe_memory.read_u32(player_data + 0x434U + slot, kills))
        weapon_stat_kills += kills;
    }
  }
  bool emit_actor_trace = false;
#if defined(_WIN32)
  char *actor_trace = nullptr;
  std::size_t actor_trace_size = 0U;
  if (_dupenv_s(&actor_trace, &actor_trace_size, "JFG_PHASE9_ACTOR_TRACE") ==
          0 &&
      actor_trace != nullptr && std::strcmp(actor_trace, "1") == 0)
    emit_actor_trace = true;
  std::free(actor_trace);
#else
  if (const char *actor_trace = std::getenv("JFG_PHASE9_ACTOR_TRACE");
      actor_trace != nullptr && std::strcmp(actor_trace, "1") == 0)
    emit_actor_trace = true;
#endif
  if (emit_actor_trace) {
    std::uint32_t actor_list = 0U;
    std::uint32_t actor_count = 0U;
    if (probe_memory.read_u32(game_data("globals.objectList"), actor_list) &&
        probe_memory.read_u32(game_data("globals.objectCount"), actor_count) &&
        actor_count <= 256U) {
      std::fprintf(stdout, "{\"kind\":\"jfg-phase9-actor-trace\","
                           "\"actors\":[");
      bool first_actor = true;
      for (std::uint32_t index = 0U; index < actor_count; ++index) {
        std::uint32_t actor = 0U;
        std::uint32_t header = 0U;
        std::uint32_t name0 = 0U;
        std::uint32_t name1 = 0U;
        std::uint32_t x = 0U;
        std::uint32_t y = 0U;
        std::uint32_t z = 0U;
        if (!probe_memory.read_u32(actor_list + index * 4U, actor) ||
            actor == 0U || !probe_memory.read_u32(actor + game_member("layout.actor.header"), header) ||
            header == 0U || !probe_memory.read_u32(header + 4U, name0) ||
            !probe_memory.read_u32(header + 8U, name1) ||
            !probe_memory.read_u32(actor + game_member("layout.actor.x"), x) ||
            !probe_memory.read_u32(actor + game_member("layout.actor.y"), y) ||
            !probe_memory.read_u32(actor + game_member("layout.actor.z"), z))
          continue;
        if (!first_actor)
          std::fputc(',', stdout);
        first_actor = false;
        std::fprintf(stdout,
                     "{\"index\":%u,\"actor\":\"0x%08x\","
                     "\"name_words\":\"%08x,%08x\","
                     "\"position_words\":\"%08x,%08x,%08x\"}",
                     index, actor, name0, name1, x, y, z);
      }
      std::fputs("]}\n", stdout);
    }
  }
  // Host wall-clock totals are diagnostics, not simulation state. They live
  // in the timing side channel so the canonical probe record below is
  // byte-identical across deterministic runs.
  if (state.timing_trace) {
    state.timing_trace << "totals\t" << state.vi_retraces << '\t'
                       << state.audio_task_microseconds << '\t'
                       << state.graphics_prepare_microseconds << '\t'
                       << state.graphics_submit_microseconds << '\t'
                       << state.graphics_present_microseconds << '\n';
  }
  std::fprintf(
      stdout,
      "{\"kind\":\"jfg-phase8-native-probe\",\"status\":\"%s\","
      "\"%s\":%u,\"vi_retraces\":%llu,\"vi_frames\":%llu,"
      "\"vi_interrupts\":%llu,\"vi_messages_delivered\":%llu,"
      "\"mmio_accesses\":%llu,\"unsupported_accesses\":%llu,"
      "\"dispatches\":%zu,\"pi_dma\":%llu,"
      "\"overlay_publications\":%llu,"
      "\"overlay_sequence\":\"%s\","
      "\"phase9_route\":{\"player_control_calls\":%llu,"
      "\"weapon_update_calls\":%llu,\"weapon_fire_held_updates\":%llu,"
      "\"weapon_fire_pressed_updates\":%llu,"
      "\"weapon_dummy_fire_calls\":%llu,\"weapon_fire_calls\":%llu,"
      "\"weapon_shot_calls\":%llu,"
      "\"weapon_hit_calls\":%llu,\"enemy_kill_calls\":%llu,"
      "\"weapon_stat_shots\":%llu,\"weapon_stat_hits\":%llu,"
      "\"weapon_stat_kills\":%llu,"
      "\"collision_calls\":%llu,\"particle_update_calls\":%llu,"
      "\"cutscene_active_calls\":%llu,\"cutscene_camera_calls\":%llu,"
      "\"level_change_calls\":%llu,\"death_restart_calls\":%llu,"
      "\"player_hit_check_calls\":%llu,"
      "\"player_actor\":\"0x%08x\","
      "\"player_yaw\":\"0x%04x\","
      "\"player_position_bits\":\"%08x,%08x,%08x\","
      "\"hints_control_calls\":%llu,\"hints_talk_calls\":%llu,"
      "\"hints_actor\":\"0x%08x\",\"hints_yaw\":\"0x%04x\","
      "\"hints_position_bits\":\"%08x,%08x,%08x\","
      "\"hints_state\":\"0x%08x\","
      "\"hints_state_words\":"
      "\"%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x,"
      "%08x,%08x,%08x,%08x\","
      "\"king_bear_control_calls\":%llu,"
      "\"king_bear_callback\":\"0x%08x\","
      "\"king_bear_callback_section\":%u,"
      "\"king_bear_callback_offset\":\"0x%08x\","
      "\"king_bear_actor\":\"0x%08x\","
      "\"king_bear_yaw\":\"0x%04x\","
      "\"king_bear_position_bits\":\"%08x,%08x,%08x\","
      "\"king_bear_state\":\"0x%08x\","
      "\"king_bear_state_words\":\"%08x,%08x,%08x,%08x\","
      "\"hinttext_start_calls\":%llu,\"hinttext_stop_calls\":%llu,"
      "\"hinttext_active_calls\":%llu,"
      "\"hinttext_active_zero_returns\":%llu,"
      "\"hinttext_active_nonzero_returns\":%llu,"
      "\"hinttext_active_last_return\":%u,"
      "\"hinttext_update_calls\":%llu,"
      "\"hinttext_advance_calls\":%llu,"
      "\"hinttext_accept_calls\":%llu,"
      "\"hinttext_section_base\":\"0x%08x\","
      "\"hinttext_state_words\":"
      "\"%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x,"
      "%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x\","
      "\"runlink_module7_words\":"
      "\"%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x\"},"
      "\"controller_events\":%llu,"
      "\"generated_calls\":%llu,\"mapped_calls\":%llu,"
      "\"queue_create_calls\":%llu,\"queue_send_calls\":%llu,"
      "\"queue_recv_calls\":%llu,\"sp_task_load_calls\":%llu,"
      "\"sp_task_start_calls\":%llu,"
      "\"controller_read_start_calls\":%llu,"
      "\"controller_get_data_calls\":%llu,\"vi_swap_calls\":%llu,"
      "\"graphics_tasks\":%llu,\"graphics_commands\":%llu,"
      "\"graphics_triangles\":%llu,\"presented_frames\":%llu,"
      "\"decoded_audio_tasks\":%llu,"
      "\"audio_device_initialized\":%s,\"audio_device_started\":%s,"
      "\"audio_device_frequency\":%u,\"audio_device_buffers\":%llu,"
      "\"audio_device_queued_bytes\":%llu,"
      "\"audio_device_consumed_bytes\":%llu,"
      "\"audio_device_consumed_ms\":%llu,"
      "\"audio_device_underruns\":%llu,\"audio_device_overruns\":%llu,"
      "\"ai_submission_overflows\":%llu,\"frame_captured\":%s,"
      "\"input_replay_events\":%zu,\"controller_samples\":%llu,"
      "\"non_neutral_controller_samples\":%llu,"
      "\"controller_disconnects\":%llu,\"controller_reconnects\":%llu,"
      "\"game_pressed_observations\":%llu,"
      "\"game_stick_observations\":%llu,"
      "\"last_game_stick_x\":%d,\"last_game_stick_y\":%d,"
      "\"menu_stick_observations\":%llu,"
      "\"last_menu_stick_x\":%d,\"last_menu_stick_y\":%d,"
      "\"front_mode\":%u,"
      "\"flash_path_configured\":%s,\"flash_image_loaded\":%s,"
      "\"flash_image_created\":%s,\"flash_persist_count\":%llu,"
      "\"threads_stopped\":%zu,\"threads_runnable\":%zu,"
      "\"threads_blocked\":%zu,\"threads_finished\":%zu,"
      "\"hle_counts\":\"%s\","
      "\"thread_summary\":\"%s\",\"controller_read_thread\":%d,"
      "\"si_queue\":\"0x%08x\",\"si_queue_valid\":%u,"
      "\"si_receive_calls\":%llu,\"last_si_receive_return\":\"0x%08x\","
      "\"last_si_receive_block\":%u,"
      "\"last_si_dispatch_trace\":\"%s\","
      "\"journal_events\":%llu,\"journal_entries\":%zu,"
      "\"journal_overflow\":%s,"
      "\"state_hash\":\"%s\",\"journal_hash\":\"%s\"}\n",
      state.poll_target != 0U ? "poll-target" : "retrace-target",
      state.poll_target != 0U ? "poll_target" : "retrace_target",
      state.poll_target != 0U ? state.poll_target : state.retrace_target,
      static_cast<unsigned long long>(state.vi_retraces),
      static_cast<unsigned long long>(state.vi_frames),
      static_cast<unsigned long long>(state.vi_interrupts),
      static_cast<unsigned long long>(state.vi_messages_delivered),
      static_cast<unsigned long long>(state.mmio_trace->accesses),
      static_cast<unsigned long long>(state.mmio_trace->unsupported_accesses),
      static_cast<std::size_t>(state.dispatch_calls),
      static_cast<unsigned long long>(
          event_counts[static_cast<std::size_t>(NativeEventKind::kPiDma)]),
      static_cast<unsigned long long>(event_counts[static_cast<std::size_t>(
          NativeEventKind::kOverlayPublished)]),
      overlay_sequence.c_str(),
      static_cast<unsigned long long>(state.phase9_player_control_calls),
      static_cast<unsigned long long>(state.phase9_weapon_update_calls),
      static_cast<unsigned long long>(state.phase9_weapon_fire_held_updates),
      static_cast<unsigned long long>(state.phase9_weapon_fire_pressed_updates),
      static_cast<unsigned long long>(state.phase9_weapon_dummy_fire_calls),
      static_cast<unsigned long long>(state.phase9_weapon_fire_calls),
      static_cast<unsigned long long>(state.phase9_weapon_shot_calls),
      static_cast<unsigned long long>(state.phase9_weapon_hit_calls),
      static_cast<unsigned long long>(state.phase9_enemy_kill_calls),
      static_cast<unsigned long long>(weapon_stat_shots),
      static_cast<unsigned long long>(weapon_stat_hits),
      static_cast<unsigned long long>(weapon_stat_kills),
      static_cast<unsigned long long>(state.phase9_collision_calls),
      static_cast<unsigned long long>(state.phase9_particle_update_calls),
      static_cast<unsigned long long>(state.phase9_cutscene_active_calls),
      static_cast<unsigned long long>(state.phase9_cutscene_camera_calls),
      static_cast<unsigned long long>(state.phase9_level_change_calls),
      static_cast<unsigned long long>(state.phase9_death_restart_calls),
      static_cast<unsigned long long>(state.phase9_player_hit_check_calls),
      state.phase9_player_actor, static_cast<unsigned>(player_yaw),
      player_position_x, player_position_y, player_position_z,
      static_cast<unsigned long long>(state.phase9_hints_control_calls),
      static_cast<unsigned long long>(state.phase9_hints_talk_calls),
      state.phase9_hints_actor, static_cast<unsigned>(hints_yaw),
      hints_position_x, hints_position_y, hints_position_z,
      hints_state, hints_state_words[0], hints_state_words[1],
      hints_state_words[2], hints_state_words[3], hints_state_words[4],
      hints_state_words[5], hints_state_words[6], hints_state_words[7],
      hints_state_words[8], hints_state_words[9], hints_state_words[10],
      hints_state_words[11],
      static_cast<unsigned long long>(state.phase9_king_bear_control_calls),
      state.phase9_king_bear_callback, king_bear_callback_section,
      king_bear_callback_offset,
      king_bear_actor, static_cast<unsigned>(king_bear_yaw),
      king_bear_position_x, king_bear_position_y, king_bear_position_z,
      king_bear_state, king_bear_state_word_0, king_bear_sound_handle,
      king_bear_state_word_30, king_bear_state_word_34,
      static_cast<unsigned long long>(state.phase9_hinttext_start_calls),
      static_cast<unsigned long long>(state.phase9_hinttext_stop_calls),
      static_cast<unsigned long long>(state.phase9_hinttext_active_calls),
      static_cast<unsigned long long>(
          state.phase9_hinttext_active_zero_returns),
      static_cast<unsigned long long>(
          state.phase9_hinttext_active_nonzero_returns),
      state.phase9_hinttext_active_last_return,
      static_cast<unsigned long long>(state.phase9_hinttext_update_calls),
      static_cast<unsigned long long>(state.phase9_hinttext_advance_calls),
      static_cast<unsigned long long>(state.phase9_hinttext_accept_calls),
      hinttext_section_base,
      hinttext_state_words[0], hinttext_state_words[1],
      hinttext_state_words[2], hinttext_state_words[3],
      hinttext_state_words[4], hinttext_state_words[5],
      hinttext_state_words[6], hinttext_state_words[7],
      hinttext_state_words[8], hinttext_state_words[9],
      hinttext_state_words[10], hinttext_state_words[11],
      hinttext_state_words[12], hinttext_state_words[13],
      hinttext_state_words[14], hinttext_state_words[15],
      runlink_module7_words[0], runlink_module7_words[1],
      runlink_module7_words[2], runlink_module7_words[3],
      runlink_module7_words[4], runlink_module7_words[5],
      runlink_module7_words[6], runlink_module7_words[7],
      static_cast<unsigned long long>(event_counts[static_cast<std::size_t>(
          NativeEventKind::kController)]),
      static_cast<unsigned long long>(state.generated_calls),
      static_cast<unsigned long long>(state.mapped_calls),
      static_cast<unsigned long long>(state.queue_create_calls),
      static_cast<unsigned long long>(state.queue_send_calls),
      static_cast<unsigned long long>(state.queue_recv_calls),
      static_cast<unsigned long long>(state.sp_task_load_calls),
      static_cast<unsigned long long>(state.sp_task_start_calls),
      static_cast<unsigned long long>(state.controller_read_start_calls),
      static_cast<unsigned long long>(state.controller_get_data_calls),
      static_cast<unsigned long long>(state.vi_swap_calls),
      static_cast<unsigned long long>(state.graphics_tasks),
      static_cast<unsigned long long>(state.graphics_commands),
      static_cast<unsigned long long>(state.graphics_triangles),
      static_cast<unsigned long long>(state.presented_frames),
      static_cast<unsigned long long>(state.decoded_audio_tasks),
      state.audio_device_initialized ? "true" : "false",
      state.audio_device_started ? "true" : "false",
      state.audio_device_frequency,
      static_cast<unsigned long long>(state.audio_device_buffers),
      static_cast<unsigned long long>(state.audio_device_queued_bytes),
      static_cast<unsigned long long>(state.audio_device_consumed_bytes),
      static_cast<unsigned long long>(state.audio_device_consumed_ms),
      static_cast<unsigned long long>(state.audio_device_underruns),
      static_cast<unsigned long long>(state.audio_device_overruns),
      static_cast<unsigned long long>(
          state.mmio_trace == nullptr
              ? 0U
              : state.mmio_trace->ai_submission_overflows),
      state.frame_captured ? "true" : "false",
      state.input_replay_event_count,
      static_cast<unsigned long long>(state.controller_samples),
      static_cast<unsigned long long>(state.non_neutral_controller_samples),
      static_cast<unsigned long long>(state.controller_disconnects),
      static_cast<unsigned long long>(state.controller_reconnects),
      static_cast<unsigned long long>(state.game_pressed_observations),
      static_cast<unsigned long long>(state.game_stick_observations),
      static_cast<int>(state.last_game_stick_x),
      static_cast<int>(state.last_game_stick_y),
      static_cast<unsigned long long>(state.menu_stick_observations),
      static_cast<int>(state.last_menu_stick_x),
      static_cast<int>(state.last_menu_stick_y),
      front_mode,
      state.flash_path.empty() ? "false" : "true",
      state.flash_image_loaded ? "true" : "false",
      state.flash_image_created ? "true" : "false",
      static_cast<unsigned long long>(state.flash_persist_count),
      thread_states[static_cast<std::size_t>(ThreadState::kStopped)],
      thread_states[static_cast<std::size_t>(ThreadState::kRunnable)],
      thread_states[static_cast<std::size_t>(ThreadState::kBlocked)],
      thread_states[static_cast<std::size_t>(ThreadState::kFinished)],
      hle_counts.c_str(),
      thread_summary.c_str(), state.controller_read_thread, si_queue,
      si_queue_valid,
      static_cast<unsigned long long>(state.si_receive_calls),
      state.last_si_receive_return, state.last_si_receive_block,
      si_dispatch_trace.c_str(),
      static_cast<unsigned long long>(state.journal.observed_total),
      state.journal.count, state.journal.overflow ? "true" : "false",
      state_digest.c_str(), journal_digest.c_str());
  std::fflush(stdout);
  jfg::frame_diagnostic_state().finish();
  jfg::finish_interpolation_trace(); jfg::finish_blur_source_audit();
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  state.host_audio.finish_capture();
  state.timing_trace.finish();
  state.input_record.finish();
  state.gameplay_trace.finish();
#endif
  state.guest_clock_trace.finish();
  state.snapshot_writer.finish();
  state.movement_trace.finish();
  state.jump_trace.finish();
  stop_pc_rumble(state);
  std::_Exit(0);
}
#endif

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)
[[noreturn]] void play_exit(State &state) {
  jfg::support_event("native=closed");
  if (state.mmio_trace == nullptr ||
      state.mmio_trace->unsupported_accesses != 0U) {
    fail_closed_dispatch(state, "play", "invalid-clean-exit", 0U);
  }
  if (!service_host_audio(state, false))
    fail_closed_dispatch(state, "audio", "host-device-final", 0U);
  if (!persist_controller_pak(state))
    fail_closed_dispatch(state, "save", "controller-pak-persist", 0U);
  if (!write_live_frame_capture(state))
    fail_closed_dispatch(state, "renderer", "frame-capture", 0U);
  if (!write_private_rdram_capture(state))
    fail_closed_dispatch(state, "runtime", "rdram-capture", 0U);
  // Retain final counters even if the detailed trace capped and the launcher
  // filtered the long stdout record.
  if (state.timing_trace.is_open())
    state.timing_trace << "play-health\t" << state.vi_frames << '\t'
                       << state.vi_retraces << "\t0\t"
                       << state.audio_device_underruns << '\t'
                       << state.audio_device_overruns << '\t'
                       << state.timing_game_updates << '\t'
                       << state.controller_samples << '\n';
  const unsigned front_mode = state.rdram[(game_data("globals.frontendMode")&0x1FFFFFFFU) ^ 3U];
  std::fprintf(
      stdout,
      "{\"kind\":\"jfg-phase8-play\",\"status\":\"window-closed\","
      "\"vi_retraces\":%llu,\"graphics_tasks\":%llu,"
      "\"presented_frames\":%llu,\"decoded_audio_tasks\":%llu,"
      "\"audio_device_initialized\":%s,\"audio_device_started\":%s,"
      "\"audio_device_frequency\":%u,\"audio_device_buffers\":%llu,"
      "\"audio_device_consumed_bytes\":%llu,"
      "\"audio_device_consumed_ms\":%llu,"
      "\"audio_device_underruns\":%llu,\"audio_device_overruns\":%llu,"
      "\"frame_captured\":%s,"
      "\"controller_samples\":%llu,"
      "\"non_neutral_controller_samples\":%llu,"
      "\"non_neutral_controller_writes\":%llu,"
      "\"controller_disconnects\":%llu,\"controller_reconnects\":%llu,"
      "\"game_pressed_observations\":%llu,"
      "\"last_game_pressed_buttons\":\"0x%04x\","
      "\"game_stick_observations\":%llu,"
      "\"last_game_stick_x\":%d,\"last_game_stick_y\":%d,"
      "\"menu_stick_observations\":%llu,"
      "\"last_menu_stick_x\":%d,\"last_menu_stick_y\":%d,"
      "\"front_mode\":%u,"
      "\"unsupported_accesses\":0,\"journal_overflow\":%s}\n",
      static_cast<unsigned long long>(state.vi_retraces),
      static_cast<unsigned long long>(state.graphics_tasks),
      static_cast<unsigned long long>(state.presented_frames),
      static_cast<unsigned long long>(state.decoded_audio_tasks),
      state.audio_device_initialized ? "true" : "false",
      state.audio_device_started ? "true" : "false",
      state.audio_device_frequency,
      static_cast<unsigned long long>(state.audio_device_buffers),
      static_cast<unsigned long long>(state.audio_device_consumed_bytes),
      static_cast<unsigned long long>(state.audio_device_consumed_ms),
      static_cast<unsigned long long>(state.audio_device_underruns),
      static_cast<unsigned long long>(state.audio_device_overruns),
      state.frame_captured ? "true" : "false",
      static_cast<unsigned long long>(state.controller_samples),
      static_cast<unsigned long long>(state.non_neutral_controller_samples),
      static_cast<unsigned long long>(state.non_neutral_controller_writes),
      static_cast<unsigned long long>(state.controller_disconnects),
      static_cast<unsigned long long>(state.controller_reconnects),
      static_cast<unsigned long long>(state.game_pressed_observations),
      state.last_game_pressed_buttons,
      static_cast<unsigned long long>(state.game_stick_observations),
      static_cast<int>(state.last_game_stick_x),
      static_cast<int>(state.last_game_stick_y),
      static_cast<unsigned long long>(state.menu_stick_observations),
      static_cast<int>(state.last_menu_stick_x),
      static_cast<int>(state.last_menu_stick_y),
      front_mode,
      state.journal.overflow ? "true" : "false");
  std::fflush(stdout);
  jfg::frame_diagnostic_state().finish();
  jfg::finish_interpolation_trace(); jfg::finish_blur_source_audit();
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  state.host_audio.finish_capture();
  state.timing_trace.finish();
  state.input_record.finish();
  state.gameplay_trace.finish();
#endif
  state.guest_clock_trace.finish();
  state.snapshot_writer.finish();
  state.movement_trace.finish();
  state.jump_trace.finish();
  stop_pc_rumble(state);
  std::_Exit(0);
}
#endif

[[noreturn]] void retrace_gate(State &state) {
  if (state.poll_target != 0U)
    fail_closed_dispatch(state, "probe", "poll-not-reached", 0U);
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  if (state.guest_os_probe)probe_target_gate(state);
#endif
  if (state.retrace_target == 3U)
    stable_vi_gate(state);
#if defined(JFG_PHASE8_LIVE_RUNTIME)
  probe_target_gate(state);
#else
  fail_closed_dispatch(state, "native", "unexpected-retrace-target", 0U);
#endif
}

#if defined(_WIN32) && defined(JFG_PHASE8_LIVE_RUNTIME)

#endif
} // namespace jfg::boot::native::detail
