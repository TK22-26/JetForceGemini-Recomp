#include "runtime_services.hpp"
#include "process_supervisor.hpp"
namespace jfg::boot::native {
using namespace detail;
#if defined(_WIN32)
bool extract_canonical_ledger(const std::string &output,
                              std::string &ledger_line) {
  static const std::regex pattern(
      R"(\{"kind":"jfg-phase6-native-first-trap","category":"[a-z-]+","guest_target":"0x[0-9a-f]{8}","operation":"[A-Za-z_][A-Za-z0-9_-]*","disposition":"fail-closed-trap","count":1\}\r?\n)");
  std::sregex_iterator found(output.begin(), output.end(), pattern);
  if (found == std::sregex_iterator{} ||
      std::next(found) != std::sregex_iterator{}) {
    return false;
  }
  const std::smatch &match = *found;
  if (match.position() != 0U) {
    return false;
  }
  const std::string trailing = match.suffix().str();
  if (trailing.size() > 4096U ||
      trailing.find("jfg-phase6-native-first-trap") != std::string::npos) {
    return false;
  }
  if (!trailing.empty()) {
    return false;
  }
  ledger_line = match.str();
  if (ledger_line.size() >= 2U && ledger_line[ledger_line.size() - 2U] == '\r')
    ledger_line.erase(ledger_line.size() - 2U, 1U);
  return true;
}

bool extract_canonical_success(const std::string &output,
                               std::string &success_line) {
  static const std::regex pattern(
      R"jfg(\{"kind":"jfg-phase6-native-boot","status":"stable-vi","build_identity":"[A-Za-z0-9_.+-]+","sanitizer":"(?:none|address)","vi_retraces":3,"vi_frames":[1-9][0-9]*,"vi_interrupts":3,"vi_messages_delivered":3,"vi_queue":"0x[89a-f][0-9a-f]{7}","threads_created":[1-9][0-9]*,"rdram_bytes":4194304,"mmio_accesses":[1-9][0-9]*,"unsupported_accesses":0,"mmio_trace":"[rw]:0x[a-f0-9]{8}(?:,[rw]:0x[a-f0-9]{8})*","journal_entries":[1-9][0-9]*,"state_hash":"[0-9a-f]{64}","journal_hash":"[0-9a-f]{64}"\}\r?\n)jfg");
  std::smatch match;
  if (!std::regex_match(output, match, pattern))
    return false;
  success_line = match.str();
  if (success_line.size() >= 2U &&
      success_line[success_line.size() - 2U] == '\r')
    success_line.erase(success_line.size() - 2U, 1U);
  return true;
}

bool extract_canonical_probe(const std::string &output,
                             std::string &probe_line) {
  static const std::regex actor_trace_extension(
      R"jfg(\{"kind":"jfg-phase9-actor-trace","actors":\[.*\]\}\r?\n)jfg");
  static const std::regex king_bear_extension(
      R"jfg(,"hints_state":"0x[0-9a-f]{8}","hints_state_words":"(?:[0-9a-f]{8},){11}[0-9a-f]{8}","king_bear_control_calls":[0-9]+,"king_bear_callback":"0x[0-9a-f]{8}","king_bear_callback_section":[0-9]+,"king_bear_callback_offset":"0x[0-9a-f]{8}","king_bear_actor":"0x[0-9a-f]{8}","king_bear_yaw":"0x[0-9a-f]{4}","king_bear_position_bits":"[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8}","king_bear_state":"0x[0-9a-f]{8}","king_bear_state_words":"[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8}","hinttext_start_calls":[0-9]+,"hinttext_stop_calls":[0-9]+,"hinttext_active_calls":[0-9]+,"hinttext_active_zero_returns":[0-9]+,"hinttext_active_nonzero_returns":[0-9]+,"hinttext_active_last_return":[0-9]+,"hinttext_update_calls":[0-9]+,"hinttext_advance_calls":[0-9]+,"hinttext_accept_calls":[0-9]+,"hinttext_section_base":"0x[0-9a-f]{8}","hinttext_state_words":"(?:[0-9a-f]{8},){15}[0-9a-f]{8}","runlink_module7_words":"[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8}")jfg");
  static const std::regex pattern(
      R"jfg(\{"kind":"jfg-phase8-native-probe","status":"retrace-target","retrace_target":(?:[4-9]|[1-9][0-9]+),"vi_retraces":(?:[4-9]|[1-9][0-9]+),"vi_frames":[1-9][0-9]*,"vi_interrupts":(?:[4-9]|[1-9][0-9]+),"vi_messages_delivered":(?:[4-9]|[1-9][0-9]+),"mmio_accesses":[1-9][0-9]*,"unsupported_accesses":[0-9]+,"dispatches":[0-9]+,"pi_dma":[0-9]+,"overlay_publications":[0-9]+,"overlay_sequence":"[0-9,]*","phase9_route":\{"player_control_calls":[0-9]+,"weapon_update_calls":[0-9]+,"weapon_fire_held_updates":[0-9]+,"weapon_fire_pressed_updates":[0-9]+,"weapon_dummy_fire_calls":[0-9]+,"weapon_fire_calls":[0-9]+,"weapon_shot_calls":[0-9]+,"weapon_hit_calls":[0-9]+,"enemy_kill_calls":[0-9]+,"weapon_stat_shots":[0-9]+,"weapon_stat_hits":[0-9]+,"weapon_stat_kills":[0-9]+,"collision_calls":[0-9]+,"particle_update_calls":[0-9]+,"cutscene_active_calls":[0-9]+,"cutscene_camera_calls":[0-9]+,"level_change_calls":[0-9]+,"death_restart_calls":[0-9]+,"player_hit_check_calls":[0-9]+,"player_actor":"0x[0-9a-f]{8}","player_yaw":"0x[0-9a-f]{4}","player_position_bits":"[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8}","hints_control_calls":[0-9]+,"hints_talk_calls":[0-9]+,"hints_actor":"0x[0-9a-f]{8}","hints_yaw":"0x[0-9a-f]{4}","hints_position_bits":"[0-9a-f]{8},[0-9a-f]{8},[0-9a-f]{8}"\},"controller_events":[0-9]+,"generated_calls":[0-9]+,"mapped_calls":[0-9]+,"queue_create_calls":[0-9]+,"queue_send_calls":[0-9]+,"queue_recv_calls":[0-9]+,"sp_task_load_calls":[0-9]+,"sp_task_start_calls":[0-9]+,"controller_read_start_calls":[0-9]+,"controller_get_data_calls":[0-9]+,"vi_swap_calls":[0-9]+,"graphics_tasks":[0-9]+,"graphics_commands":[0-9]+,"graphics_triangles":[0-9]+,"presented_frames":[0-9]+,"decoded_audio_tasks":[0-9]+,"audio_device_initialized":(?:true|false),"audio_device_started":(?:true|false),"audio_device_frequency":[0-9]+,"audio_device_buffers":[0-9]+,"audio_device_queued_bytes":[0-9]+,"audio_device_consumed_bytes":[0-9]+,"audio_device_consumed_ms":[0-9]+,"audio_device_underruns":[0-9]+,"audio_device_overruns":[0-9]+,"ai_submission_overflows":[0-9]+,"frame_captured":(?:true|false),"input_replay_events":[0-9]+,"controller_samples":[0-9]+,"non_neutral_controller_samples":[0-9]+,"controller_disconnects":[0-9]+,"controller_reconnects":[0-9]+,"game_pressed_observations":[0-9]+,"game_stick_observations":[0-9]+,"last_game_stick_x":-?[0-9]+,"last_game_stick_y":-?[0-9]+,"menu_stick_observations":[0-9]+,"last_menu_stick_x":-?[0-9]+,"last_menu_stick_y":-?[0-9]+,"front_mode":[0-9]+,"flash_path_configured":(?:true|false),"flash_image_loaded":(?:true|false),"flash_image_created":(?:true|false),"flash_persist_count":[0-9]+,"threads_stopped":[0-9]+,"threads_runnable":[0-9]+,"threads_blocked":[0-9]+,"threads_finished":[0-9]+,"hle_counts":"[A-Za-z0-9_=,]+","thread_summary":"[0-9a-f:,]+","controller_read_thread":-?[0-9]+,"si_queue":"0x[0-9a-f]{8}","si_queue_valid":[0-9]+,"si_receive_calls":[0-9]+,"last_si_receive_return":"0x[0-9a-f]{8}","last_si_receive_block":[0-9]+,"last_si_dispatch_trace":"[0-9a-f,]+","journal_events":[0-9]+,"journal_entries":[0-9]+,"journal_overflow":(?:true|false),"state_hash":"[0-9a-f]{64}","journal_hash":"[0-9a-f]{64}"\}\r?\n)jfg");
  const std::string without_actor_trace =
      std::regex_replace(output, actor_trace_extension, "");
  const std::string canonical_output =
      std::regex_replace(without_actor_trace, king_bear_extension, "");
  if (canonical_output == without_actor_trace)
    return false;
  std::smatch match;
  if (!std::regex_match(canonical_output, match, pattern))
    return false;
  probe_line = output;
  if (probe_line.size() >= 2U &&
      probe_line[probe_line.size() - 2U] == '\r')
    probe_line.erase(probe_line.size() - 2U, 1U);
  return true;
}

bool extract_original_os_probe(const std::string& output, unsigned target, std::string& line) {
  char* enabled = nullptr;
  std::size_t size = 0;
  const bool opted_in = _dupenv_s(&enabled, &size, "JFG_PHASE9_GUEST_OS_PROBE") == 0 &&
      enabled && std::strcmp(enabled, "1") == 0;
  std::free(enabled);
  char original_timing[2]{};
  const auto timing_override = GetEnvironmentVariableA("JFG_ORIGINAL_TIMING",original_timing,2U);
  const bool runtime_opted_in = timing_override == 1U ? original_timing[0]=='1' :
      JFG_ORIGINAL_TIMING_GENERATION == 1;
  if (!opted_in && !runtime_opted_in) return false;
  static const std::regex pattern(
      R"jfg(\{"kind":"jfg-phase9-original-os-probe","acceptance":false,"status":"retrace-target","retrace_target":([1-9][0-9]*),"vi_retraces":([1-9][0-9]*),"controller_samples":[0-9]+,"completed_updates":[0-9]+,"cpu_count":[1-9][0-9]*,"instructions":[1-9][0-9]*,"graphics_tasks":[0-9]+,"decoded_audio_tasks":[0-9]+,"unsupported_accesses":0,"runtime_snapshot_complete":false,"state_hash":"[0-9a-f]{64}"\}\r?\n)jfg");
  std::smatch match;
  if (!std::regex_match(output, match, pattern) || match[1].str() != std::to_string(target) ||
      match[2].str() != std::to_string(target)) return false;
  line = output;
  return true;
}

bool extract_canonical_poll_probe(const std::string &output,
                                  const unsigned poll_target,
                                  std::string &probe_line) {
  // Reuse the strict retrace-probe suffix validator. Only the stop reason and
  // early VI counters differ; normalize those after checking their exact
  // order, decimal shape, requested target, and sampled-poll total.
  static const std::regex prefix(
      R"jfg(^\{"kind":"jfg-phase8-native-probe","status":"poll-target","poll_target":([1-9][0-9]*),"vi_retraces":([0-9]+),"vi_frames":([0-9]+),"vi_interrupts":([0-9]+),"vi_messages_delivered":([0-9]+),)jfg");
  static const std::regex samples(R"jfg(,"controller_samples":([0-9]+),)jfg");
  std::smatch prefix_match, sample_match;
  if (!std::regex_search(output, prefix_match, prefix) ||
      prefix_match[1].str() != std::to_string(poll_target) ||
      !std::regex_search(output, sample_match, samples) ||
      sample_match[1].str() != std::to_string(poll_target))
    return false;
  const std::string normalized =
      "{\"kind\":\"jfg-phase8-native-probe\",\"status\":\"retrace-target\","
      "\"retrace_target\":4,\"vi_retraces\":4,\"vi_frames\":4,"
      "\"vi_interrupts\":4,\"vi_messages_delivered\":4," +
      output.substr(prefix_match.length());
  std::string ignored;
  if (!extract_canonical_probe(normalized, ignored))
    return false;
  probe_line = output;
  if (probe_line.size() >= 2U &&
      probe_line[probe_line.size() - 2U] == '\r')
    probe_line.erase(probe_line.size() - 2U, 1U);
  return true;
}

bool extract_canonical_play_exit(const std::string &output,
                                 std::string &play_line) {
  static const std::regex pattern(
      R"jfg(\{"kind":"jfg-phase8-play","status":"window-closed","vi_retraces":[0-9]+,"graphics_tasks":[0-9]+,"presented_frames":[0-9]+,"decoded_audio_tasks":[0-9]+,"audio_device_initialized":(?:true|false),"audio_device_started":(?:true|false),"audio_device_frequency":[0-9]+,"audio_device_buffers":[0-9]+,"audio_device_consumed_bytes":[0-9]+,"audio_device_consumed_ms":[0-9]+,"audio_device_underruns":[0-9]+,"audio_device_overruns":[0-9]+,"frame_captured":(?:true|false),"controller_samples":[0-9]+,"non_neutral_controller_samples":[0-9]+,"non_neutral_controller_writes":[0-9]+,"controller_disconnects":[0-9]+,"controller_reconnects":[0-9]+,"game_pressed_observations":[0-9]+,"last_game_pressed_buttons":"0x[0-9a-f]{4}","game_stick_observations":[0-9]+,"last_game_stick_x":-?[0-9]+,"last_game_stick_y":-?[0-9]+,"menu_stick_observations":[0-9]+,"last_menu_stick_x":-?[0-9]+,"last_menu_stick_y":-?[0-9]+,"front_mode":[0-9]+,"unsupported_accesses":0,"journal_overflow":(?:true|false)\}\r?\n)jfg");
  std::smatch match;
  if (!std::regex_match(output, match, pattern))
    return false;
  play_line = match.str();
  if (play_line.size() >= 2U && play_line[play_line.size() - 2U] == '\r')
    play_line.erase(play_line.size() - 2U, 1U);
  return true;
}

std::wstring quote_argument(std::wstring_view value) {
  std::wstring quoted = L"\"";
  std::size_t slash_count = 0U;
  for (const wchar_t character : value) {
    if (character == L'\\') {
      ++slash_count;
      continue;
    }
    if (character == L'\"') {
      quoted.append(slash_count * 2U + 1U, L'\\');
      quoted += L'\"';
    } else {
      quoted.append(slash_count, L'\\');
      quoted += character;
    }
    slash_count = 0U;
  }
  quoted.append(slash_count * 2U, L'\\');
  quoted += L"\"";
  return quoted;
}

bool read_file(HANDLE file, std::string &output) {
  LARGE_INTEGER size{};
  if (!GetFileSizeEx(file, &size) || size.QuadPart < 0 || size.QuadPart > 65536)
    return false;
  output.resize(static_cast<std::size_t>(size.QuadPart));
  SetFilePointer(file, 0, nullptr, FILE_BEGIN);
  DWORD read = 0U;
  return output.empty() ||
         (ReadFile(file, output.data(), static_cast<DWORD>(output.size()),
                   &read, nullptr) != 0 &&
          read == output.size());
}

bool wide_from_utf8(const char *input, std::wstring &output) {
  if (input == nullptr) {
    return false;
  }
  constexpr int kMaximumWideCharacters = 32768;
  const int size =
      MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, input, -1, nullptr, 0);
  if (size <= 1 || size > kMaximumWideCharacters) {
    return false;
  }
  output.resize(static_cast<std::size_t>(size));
  if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, input, -1,
                          output.data(), size) != size) {
    return false;
  }
  output.pop_back();
  return true;
}

bool parse_token(std::string_view text, std::array<std::uint8_t, 16U> &token) {
  if (text.size() != token.size() * 2U)
    return false;
  for (std::size_t index = 0; index < token.size(); ++index) {
    const auto digit = [](char value) -> int {
      if (value >= '0' && value <= '9')
        return value - '0';
      if (value >= 'a' && value <= 'f')
        return value - 'a' + 10;
      return -1;
    };
    const int high = digit(text[index * 2U]);
    const int low = digit(text[index * 2U + 1U]);
    if (high < 0 || low < 0)
      return false;
    token[index] = static_cast<std::uint8_t>((high << 4) | low);
  }
  return true;
}

bool validate_child_capability(const char *token_text,
                               const char *handle_text) {
  std::array<std::uint8_t, 16U> token{};
  if (token_text == nullptr || handle_text == nullptr ||
      !parse_token(token_text, token))
    return false;
  char *end = nullptr;
  const auto raw = std::strtoull(handle_text, &end, 16);
  if (*handle_text == '\0' || *end != '\0' || raw == 0U)
    return false;
  HANDLE marker = reinterpret_cast<HANDLE>(static_cast<std::uintptr_t>(raw));
  DWORD flags = 0U;
  if (!GetHandleInformation(marker, &flags) ||
      (flags & HANDLE_FLAG_INHERIT) == 0U)
    return false;
  void *view = MapViewOfFile(marker, FILE_MAP_READ, 0, 0, token.size());
  if (view == nullptr)
    return false;
  const bool valid = std::memcmp(view, token.data(), token.size()) == 0;
  UnmapViewOfFile(view);
  return valid;
}

std::wstring token_text(const std::array<std::uint8_t, 16U> &token) {
  constexpr wchar_t digits[] = L"0123456789abcdef";
  std::wstring result(token.size() * 2U, L'0');
  for (std::size_t index = 0; index < token.size(); ++index) {
    result[index * 2U] = digits[token[index] >> 4U];
    result[index * 2U + 1U] = digits[token[index] & 15U];
  }
  return result;
}

bool module_filename(std::wstring &output) {
  std::vector<wchar_t> buffer(260U);
  for (;;) {
    const DWORD size = GetModuleFileNameW(nullptr, buffer.data(),
                                          static_cast<DWORD>(buffer.size()));
    if (size == 0U || size >= buffer.size() - 1U || size > 32767U) {
      if (size == 0U || buffer.size() >= 32768U) {
        return false;
      }
      buffer.resize(buffer.size() * 2U);
      continue;
    }
    output.assign(buffer.data(), size);
    return true;
  }
}

int run_parent(const char *executable_path, const char *rom_path,
               unsigned timeout_ms, const unsigned retrace_target,
               const unsigned poll_target, const bool play_mode) {
  (void)executable_path;
  std::vector<std::uint8_t> validated_rom;
  if (!read_supported_rom(rom_path, validated_rom))
    return 2;
  std::uint32_t entry_target = 0U;
  if (!reset_transfer_target(validated_rom, entry_target))
    return 3;
  wchar_t temp_path[MAX_PATH + 1U]{};
  wchar_t stdout_path[MAX_PATH + 1U]{};
  if (GetTempPathW(MAX_PATH, temp_path) == 0U ||
      GetTempFileNameW(temp_path, L"jfg", 0U, stdout_path) == 0U)
    return 3;
  SECURITY_ATTRIBUTES inheritable{};
  inheritable.nLength = sizeof(inheritable);
  inheritable.bInheritHandle = TRUE;
  HANDLE output =
      CreateFileW(stdout_path, GENERIC_READ | GENERIC_WRITE, 0, &inheritable,
                  CREATE_ALWAYS, FILE_ATTRIBUTE_TEMPORARY, nullptr);
  if (output == INVALID_HANDLE_VALUE) {
    DeleteFileW(stdout_path);
    return 3;
  }
  if (SetHandleInformation(output, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT) ==
      0) {
    CloseHandle(output);
    DeleteFileW(stdout_path);
    return 3;
  }
  int result = 3;
  std::wstring executable;
  std::wstring rom;
  if (!module_filename(executable) || !wide_from_utf8(rom_path, rom)) {
    CloseHandle(output);
    DeleteFileW(stdout_path);
    return result;
  }
  std::wstring command = quote_argument(executable);
  command += L" --_jfg-phase6-child --rom ";
  command += quote_argument(rom);
  if (play_mode) {
    command += L" --play";
  } else if (poll_target != 0U) {
    command += L" --probe-polls ";
    command += std::to_wstring(poll_target);
  } else {
    command += L" --probe-retraces ";
    command += std::to_wstring(retrace_target);
  }
  HANDLE nul =
      CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                  &inheritable, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (nul == INVALID_HANDLE_VALUE) {
    CloseHandle(output);
    DeleteFileW(stdout_path);
    return result;
  }
  if (SetHandleInformation(nul, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT) ==
      0) {
    CloseHandle(nul);
    CloseHandle(output);
    DeleteFileW(stdout_path);
    return result;
  }
  std::array<std::uint8_t, 16U> token{};
  HANDLE marker =
      CreateFileMappingW(INVALID_HANDLE_VALUE, &inheritable, PAGE_READWRITE, 0U,
                         static_cast<DWORD>(token.size()), nullptr);
  void *marker_view = marker == nullptr ? nullptr
                                        : MapViewOfFile(marker, FILE_MAP_WRITE,
                                                        0U, 0U, token.size());
  if (marker == nullptr || marker_view == nullptr ||
      SystemFunction036(token.data(), static_cast<ULONG>(token.size())) ==
          FALSE) {
    if (marker_view != nullptr)
      UnmapViewOfFile(marker_view);
    if (marker != nullptr)
      CloseHandle(marker);
    CloseHandle(nul);
    CloseHandle(output);
    DeleteFileW(stdout_path);
    return result;
  }
  if (SetHandleInformation(marker, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT) ==
      0) {
    CloseHandle(marker);
    CloseHandle(nul);
    CloseHandle(output);
    DeleteFileW(stdout_path);
    return result;
  }
  std::memcpy(marker_view, token.data(), token.size());
  UnmapViewOfFile(marker_view);
  STARTUPINFOW startup{};
  startup.cb = sizeof(startup);
  startup.dwFlags = STARTF_USESTDHANDLES;
  startup.hStdOutput = output;
  startup.hStdError = output;
  startup.hStdInput = nul;
  PROCESS_INFORMATION child{};
  command += L" --_jfg-phase6-token ";
  command += quote_argument(token_text(token));
  command += L" --_jfg-phase6-marker ";
  wchar_t marker_text[2U + sizeof(std::uintptr_t) * 2U + 1U]{};
  std::swprintf(marker_text, std::size(marker_text), L"%llx",
                static_cast<unsigned long long>(
                    reinterpret_cast<std::uintptr_t>(marker)));
  command += marker_text;
  if (CreateProcessW(executable.c_str(), command.data(), nullptr, nullptr, TRUE,
                     CREATE_NO_WINDOW, nullptr, nullptr, &startup,
                     &child) != 0) {
    const DWORD wait =
        WaitForSingleObject(child.hProcess, play_mode ? INFINITE : timeout_ms);
    DWORD exit_code = 0U;
    std::string child_output;
    if (wait == WAIT_TIMEOUT) {
      (void)TerminateProcess(child.hProcess, 4U);
      if (WaitForSingleObject(child.hProcess, INFINITE) == WAIT_OBJECT_0) {
        State state{};
        ledger(state, "watchdog", "wall-clock", entry_target);
        result = 4;
      }
    } else if (wait == WAIT_OBJECT_0 && FlushFileBuffers(output) != 0 &&
               read_file(output, child_output) &&
               GetExitCodeProcess(child.hProcess, &exit_code) != 0 &&
               (exit_code == 0U || exit_code == 4U) &&
               [&child_output, exit_code, retrace_target, poll_target,
                play_mode] {
                 std::string canonical_line;
                 const bool valid =
                     exit_code == 0U
                         ? (play_mode
                                ? extract_canonical_play_exit(
                                      child_output, canonical_line)
                            : poll_target != 0U
                                ? extract_canonical_poll_probe(
                                      child_output, poll_target, canonical_line)
                            : retrace_target == 3U
                                ? extract_canonical_success(child_output,
                                                            canonical_line)
                                : (extract_canonical_probe(child_output, canonical_line) ||
                                   extract_original_os_probe(child_output, retrace_target, canonical_line)))
                         : extract_canonical_ledger(child_output,
                                                    canonical_line);
                  if (!valid) {
                    return false;
                  }
                 child_output = std::move(canonical_line);
                 return true;
               }()) {
      std::fwrite(child_output.data(), 1U, child_output.size(), stdout);
      result = static_cast<int>(exit_code);
    } else {
#if defined(JFG_PHASE8_LIVE_RUNTIME)
      if (!child_output.empty())
        std::fwrite(child_output.data(), 1U, child_output.size(), stderr);
      std::fprintf(stderr, "native boot child rejected: exit=0x%08lx\n",
                   static_cast<unsigned long>(exit_code));
#endif
      if (wait == WAIT_FAILED ||
          GetExitCodeProcess(child.hProcess, &exit_code) == 0) {
        result = 3;
      } else {
        result = static_cast<int>(exit_code == 2U ? 2U : 3U);
      }
    }
    if (GetExitCodeProcess(child.hProcess, &exit_code)) {
      char support_code[32]{};
      std::snprintf(support_code, sizeof(support_code), "native_exit=0x%08lx", static_cast<unsigned long>(exit_code));
      jfg::support_event(support_code);
    }
    CloseHandle(child.hThread);
    CloseHandle(child.hProcess);
  }
  CloseHandle(marker);
  CloseHandle(nul);
  CloseHandle(output);
  DeleteFileW(stdout_path);
  return result;
}
#endif

} // namespace jfg::boot::native
