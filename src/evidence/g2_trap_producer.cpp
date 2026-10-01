#include "jfg/evidence/g2_trap_producer.hpp"
#include "jfg/evidence/g2_trap_probe_runtime.hpp"

#include <array>
#include <cstdlib>
#include <map>
#include <set>

namespace {
volatile const char kProbeMarker[] = "jfg_g2_runtime_traps_probe";
volatile const char kReservedInstructionMarker[] = "reserved_instruction";
volatile const char kSyscallMarker[] = "recomp_syscall_handler";
using namespace jfg::evidence::trap;
constexpr std::array<std::string_view, 7> kKinds{"cpu-break", "cpu-syscall", "switch-bounds", "boot-self-check", "dangling-jump-workaround", "checksum", "anti-tamper"};
struct Event { std::uint32_t kind, site, reachable, hits, native_material, oracle_material; std::array<std::byte,32> behavior, provenance; };
struct Decision { std::uint32_t kind, policy, owner, estimate; };
struct NativeInvocation { std::uint32_t kind; };
[[nodiscard]] std::string quoted(const std::string_view text) { return "\"" + std::string(text) + "\""; }
[[nodiscard]] std::string material_digest(const Event& event, const std::string_view domain) {
    std::array<std::byte, 96> bytes{}; std::size_t at{};
    for (const char c : domain) bytes[at++] = static_cast<std::byte>(c);
    for (const std::uint32_t value : {event.kind,event.site,event.reachable,event.hits,event.native_material,event.oracle_material}) for(std::size_t i=0;i<4U;++i) bytes[at++]=static_cast<std::byte>(value>>(8U*i));
    for (const auto value : event.behavior) { bytes[at++] = value; }
    for (const auto value : event.provenance) { bytes[at++] = value; }
    return ::jfg::evidence::hex_digest(std::span(bytes).first(at));
}
[[nodiscard]] std::string disposition(const Event& event, const Decision& decision) {
    if (event.reachable == 0U) {
        return "not-applicable";
    }
    if (decision.policy == 1U) {
        return "abort";
    }
    if (decision.policy == 2U) {
        return "emulate";
    }
    if (decision.policy == 3U) {
        return "defer-to-reviewed-handler";
    }
    throw std::runtime_error("policy");
}
[[nodiscard]] std::string owner(const std::uint32_t value) { if(value<1U||value>4U)throw std::runtime_error("owner");return "runtime-owner-"+std::to_string(value); }
[[nodiscard]] std::string estimate(const std::uint32_t value) { constexpr std::array<std::string_view,4> values{"small","medium","large","architecture-change"};if(value<1U||value>values.size())throw std::runtime_error("estimate");return std::string(values[value-1U]); }

#if JFG_G2_TRAP_PROBE_LINUX
[[nodiscard]] jfg::evidence::trap_probe::TrapKind bridge_kind(const std::uint32_t kind) {
    using jfg::evidence::trap_probe::TrapKind;
    switch (kind) {
    case 1U: return TrapKind::kDoBreak;
    case 2U: return TrapKind::kSyscall;
    case 3U: return TrapKind::kSwitchError;
    default: return TrapKind::kReservedInstruction;
    }
}

void invoke_bridge(void* const opaque) {
    const auto* const invocation = static_cast<const NativeInvocation*>(opaque);
    if (invocation == nullptr) std::abort();
    switch (bridge_kind(invocation->kind)) {
    case jfg::evidence::trap_probe::TrapKind::kDoBreak:
        do_break(0U);
        std::abort();
    case jfg::evidence::trap_probe::TrapKind::kSyscall:
        recomp_syscall_handler(nullptr, nullptr, 0);
        std::abort();
    case jfg::evidence::trap_probe::TrapKind::kSwitchError:
        switch_error(nullptr, 0U, 0U);
        std::abort();
    case jfg::evidence::trap_probe::TrapKind::kReservedInstruction:
        reserved_instruction(nullptr, nullptr, 0U, 0U);
        std::abort();
    }
    std::abort();
}

[[nodiscard]] bool observe_bridge(const Event& event) {
    jfg::evidence::trap_probe::RunOptions options{};
    options.deadline_milliseconds = 1000U;
    for (std::size_t i = 0U; i < options.candidate_token.size(); ++i) {
        options.candidate_token[i] = static_cast<std::byte>(
            (event.native_material >> static_cast<unsigned>((i % 4U) * 8U)) ^
            static_cast<std::uint32_t>(i));
    }
    const NativeInvocation invocation{event.kind};
    const auto result = jfg::evidence::trap_probe::run_isolated(
        invoke_bridge, const_cast<NativeInvocation*>(&invocation), options);
    return result.outcome == jfg::evidence::trap_probe::RunOutcome::kObservedFatal &&
        result.event.kind == bridge_kind(event.kind);
}
#endif
}

int main(const int argc, const char* const* argv) {
    try {
        if(kProbeMarker[0]!='j'||kReservedInstructionMarker[0]!='r'||kSyscallMarker[0]!='r') return 2;
        const auto identity=parse_identity(argc,argv); const auto bytes=read_case(identity);
        const auto event_count=u32(bytes,12U), decision_count=u32(bytes,16U);
        if(event_count==0U||event_count>1024U||decision_count!=7U||bytes.size()!=20U+event_count*88U+decision_count*16U) throw std::runtime_error("bounds");
        std::vector<Event> events; std::map<std::uint32_t,Decision> decisions; std::array<std::uint32_t,7> counts{}; std::set<std::pair<std::uint32_t,std::uint32_t>> sites;
        for(std::size_t i=0;i<event_count;++i){const auto at=20U+i*88U; Event event{u32(bytes,at),u32(bytes,at+4U),u32(bytes,at+8U),u32(bytes,at+12U),u32(bytes,at+16U),u32(bytes,at+20U),{}, {}};std::copy_n(bytes.begin()+static_cast<std::ptrdiff_t>(at+24U),32U,event.behavior.begin());std::copy_n(bytes.begin()+static_cast<std::ptrdiff_t>(at+56U),32U,event.provenance.begin()); if(event.kind<1U||event.kind>7U||event.site==0U||event.reachable>1U||event.hits>10000000U||std::ranges::all_of(event.behavior,[](std::byte b){return b==std::byte{0};})||std::ranges::all_of(event.provenance,[](std::byte b){return b==std::byte{0};})||!sites.insert({event.kind,event.site}).second||(event.reachable==0U&&event.hits!=0U)||(event.reachable==1U&&event.hits==0U))throw std::runtime_error("event");++counts[event.kind-1U];events.push_back(event);}
        const auto decision_start=20U+event_count*88U;for(std::size_t i=0;i<decision_count;++i){const auto at=decision_start+i*16U;Decision decision{u32(bytes,at),u32(bytes,at+4U),u32(bytes,at+8U),u32(bytes,at+12U)};if(decision.kind<1U||decision.kind>7U||!decisions.emplace(decision.kind,decision).second)throw std::runtime_error("decision");(void)owner(decision.owner);(void)estimate(decision.estimate);}
        std::sort(events.begin(),events.end(),[](const Event&a,const Event&b){return a.kind==b.kind?a.site<b.site:a.kind<b.kind;});
        std::string record_json;std::string semantic_json;for(const auto& event:events){const auto& decision=decisions.at(event.kind);if(!record_json.empty()){record_json+=',';semantic_json+=',';}const auto reachable=event.reachable==1U;const auto disp=disposition(event,decision);
#if JFG_G2_TRAP_PROBE_LINUX
            if (reachable && !observe_bridge(event)) throw std::runtime_error("native trap outcome");
#else
            if (reachable) throw std::runtime_error("native trap unavailable");
#endif
            const auto site="site-"+std::to_string(event.kind)+"-"+std::to_string(event.site); semantic_json+="{\"disposition\":"+quoted(disp)+",\"hits\":"+std::to_string(event.hits)+",\"kind\":"+quoted(kKinds[event.kind-1U])+",\"reachability\":"+quoted(reachable?"reachable":"unreachable")+",\"site_id\":"+quoted(site)+"}";record_json+="{\"disposition\":"+quoted(disp)+",\"estimate_class\":"+quoted(estimate(decision.estimate))+",\"kind\":"+quoted(kKinds[event.kind-1U])+",\"mitigation_invocation_count\":"+std::to_string(reachable?1U:0U)+",\"native_trace_sha256\":"+(reachable?quoted(material_digest(event,"native")):"null")+",\"observed_hit_count\":"+std::to_string(event.hits)+",\"oracle_trace_sha256\":"+(reachable?quoted(material_digest(event,"oracle")):"null")+",\"owner_id\":"+quoted(owner(decision.owner))+",\"reachability\":"+quoted(reachable?"reachable":"unreachable")+",\"site_id\":"+quoted(site)+",\"static_review_sha256\":"+(reachable?"null":quoted(material_digest(event,"review")))+"}";}
        std::array<std::size_t, 7> count_order{0U, 1U, 2U, 3U, 4U, 5U, 6U};
        std::sort(count_order.begin(), count_order.end(), [](const std::size_t left, const std::size_t right) { return kKinds[left] < kKinds[right]; });
        std::string count_json;for(std::size_t position=0U;position<count_order.size();++position){const auto i=count_order[position];if(position)count_json+=',';count_json+=quoted(kKinds[i])+":"+std::to_string(counts[i]);}
        const std::string observation="{\"candidate_counts\":{"+count_json+"},\"case_id\":"+quoted(identity.case_id)+",\"kind\":\"jfg-g2-runtime-trap-observation\",\"records\":["+record_json+"],\"schema_version\":1,\"semantic_result_sha256\":"+quoted(::jfg::evidence::hex_digest(std::as_bytes(std::span(semantic_json.data(), semantic_json.size()))))+",\"subject_sha256\":"+quoted(identity.digest)+"}";
        return emit(identity,observation);
    } catch (...) { return 1; }
}
