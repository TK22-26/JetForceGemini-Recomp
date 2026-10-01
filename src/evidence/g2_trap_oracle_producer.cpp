#include "jfg/evidence/g2_trap_producer.hpp"

#include <array>
#include <map>
#include <set>

namespace {

volatile const char kProbeMarker[] = "jfg_g2_runtime_traps_oracle_probe";
volatile const char kOracleMarker[] = "jfg_g2_runtime_traps_oracle";

using namespace jfg::evidence::trap;

constexpr std::array<std::string_view, 7> kKinds{
    "cpu-break", "cpu-syscall", "switch-bounds", "boot-self-check",
    "dangling-jump-workaround", "checksum", "anti-tamper"};

struct Candidate final {
    std::uint32_t kind;
    std::uint32_t site;
    std::uint32_t reachable;
    std::uint32_t hits;
    std::uint32_t native_material;
    std::uint32_t oracle_material;
    std::array<std::byte, 32> behavior;
    std::array<std::byte, 32> provenance;
};

struct Policy final {
    std::uint32_t kind;
    std::uint32_t mode;
    std::uint32_t owner;
    std::uint32_t estimate;
};

[[nodiscard]] std::string quote(const std::string_view value) {
    return "\"" + std::string(value) + "\"";
}

[[nodiscard]] std::string policy_text(const Candidate& candidate, const Policy& policy) {
    if (candidate.reachable == 0U) {
        return "not-applicable";
    }
    switch (policy.mode) {
    case 1U: return "abort";
    case 2U: return "emulate";
    case 3U: return "defer-to-reviewed-handler";
    default: throw std::runtime_error("oracle policy");
    }
}

[[nodiscard]] std::string owner_text(const std::uint32_t owner) {
    if (owner == 0U || owner > 4U) throw std::runtime_error("oracle owner");
    return "runtime-owner-" + std::to_string(owner);
}

[[nodiscard]] std::string estimate_text(const std::uint32_t estimate) {
    static constexpr std::array<std::string_view, 4> values{
        "small", "medium", "large", "architecture-change"};
    if (estimate == 0U || estimate > values.size()) throw std::runtime_error("oracle estimate");
    return std::string(values[estimate - 1U]);
}

[[nodiscard]] std::string trace_digest(const Candidate& candidate, const std::string_view domain) {
    std::array<std::byte, 96> encoded{};
    std::size_t at = 0U;
    for (const char value : domain) encoded[at++] = static_cast<std::byte>(value);
    for (const std::uint32_t value : {candidate.kind, candidate.site, candidate.reachable,
             candidate.hits, candidate.native_material, candidate.oracle_material}) {
        for (std::size_t byte = 0U; byte < 4U; ++byte) {
            encoded[at++] = static_cast<std::byte>(value >> static_cast<unsigned>(byte * 8U));
        }
    }
    for (const auto value : candidate.behavior) encoded[at++] = value;
    for (const auto value : candidate.provenance) encoded[at++] = value;
    return ::jfg::evidence::hex_digest(std::span(encoded).first(at));
}

}  // namespace

int main(const int argc, const char* const* argv) {
    try {
        if (kProbeMarker[0] != 'j' || kOracleMarker[0] != 'j') return 2;
        const auto identity = parse_identity(argc, argv, "private-oracle-execution");
        const auto bytes = read_case(identity);
        const std::uint32_t candidates = u32(bytes, 12U);
        const std::uint32_t policies = u32(bytes, 16U);
        if (candidates == 0U || candidates > 1024U || policies != 7U ||
            bytes.size() != 20U + candidates * 88U + policies * 16U) {
            throw std::runtime_error("oracle bounds");
        }
        std::vector<Candidate> parsed;
        std::array<std::uint32_t, 7> counts{};
        std::set<std::pair<std::uint32_t, std::uint32_t>> identities;
        for (std::size_t index = 0U; index < candidates; ++index) {
            const std::size_t at = 20U + index * 88U;
            Candidate candidate{u32(bytes, at), u32(bytes, at + 4U), u32(bytes, at + 8U),
                u32(bytes, at + 12U), u32(bytes, at + 16U), u32(bytes, at + 20U), {}, {}};
            std::copy_n(bytes.begin() + static_cast<std::ptrdiff_t>(at + 24U), 32U,
                candidate.behavior.begin());
            std::copy_n(bytes.begin() + static_cast<std::ptrdiff_t>(at + 56U), 32U,
                candidate.provenance.begin());
            if (candidate.kind == 0U || candidate.kind > kKinds.size() || candidate.site == 0U ||
                candidate.reachable > 1U || candidate.hits > 10'000'000U ||
                !identities.insert({candidate.kind, candidate.site}).second ||
                (candidate.reachable == 0U && candidate.hits != 0U) ||
                (candidate.reachable == 1U && candidate.hits == 0U) ||
                std::ranges::all_of(candidate.behavior, [](std::byte value) { return value == std::byte{0}; }) ||
                std::ranges::all_of(candidate.provenance, [](std::byte value) { return value == std::byte{0}; })) throw std::runtime_error("oracle candidate");
            ++counts[candidate.kind - 1U];
            parsed.push_back(candidate);
        }
        std::map<std::uint32_t, Policy> decisions;
        const std::size_t start = 20U + candidates * 88U;
        for (std::size_t index = 0U; index < policies; ++index) {
            const std::size_t at = start + index * 16U;
            const Policy policy{u32(bytes, at), u32(bytes, at + 4U), u32(bytes, at + 8U), u32(bytes, at + 12U)};
            if (policy.kind == 0U || policy.kind > kKinds.size() || !decisions.emplace(policy.kind, policy).second) throw std::runtime_error("oracle decision");
            (void)owner_text(policy.owner); (void)estimate_text(policy.estimate);
        }
        std::sort(parsed.begin(), parsed.end(), [](const Candidate& left, const Candidate& right) {
            return left.kind == right.kind ? left.site < right.site : left.kind < right.kind;
        });
        std::string records; std::string semantic;
        for (const Candidate& candidate : parsed) {
            if (!records.empty()) { records += ','; semantic += ','; }
            const Policy& policy = decisions.at(candidate.kind);
            const bool reachable = candidate.reachable == 1U;
            const std::string site = "site-" + std::to_string(candidate.kind) + "-" + std::to_string(candidate.site);
            const std::string disposition = policy_text(candidate, policy);
            semantic += "{\"disposition\":" + quote(disposition) + ",\"hits\":" + std::to_string(candidate.hits) +
                ",\"kind\":" + quote(kKinds[candidate.kind - 1U]) + ",\"reachability\":" + quote(reachable ? "reachable" : "unreachable") + ",\"site_id\":" + quote(site) + "}";
            records += "{\"disposition\":" + quote(disposition) + ",\"estimate_class\":" + quote(estimate_text(policy.estimate)) +
                ",\"kind\":" + quote(kKinds[candidate.kind - 1U]) + ",\"mitigation_invocation_count\":" + std::to_string(reachable ? 1U : 0U) +
                ",\"native_trace_sha256\":" + (reachable ? quote(trace_digest(candidate, "native")) : "null") +
                ",\"observed_hit_count\":" + std::to_string(candidate.hits) + ",\"oracle_trace_sha256\":" + (reachable ? quote(trace_digest(candidate, "oracle")) : "null") +
                ",\"owner_id\":" + quote(owner_text(policy.owner)) + ",\"reachability\":" + quote(reachable ? "reachable" : "unreachable") +
                ",\"site_id\":" + quote(site) + ",\"static_review_sha256\":" + (reachable ? "null" : quote(trace_digest(candidate, "review"))) + "}";
        }
        std::array<std::size_t, 7> order{0U,1U,2U,3U,4U,5U,6U};
        std::sort(order.begin(), order.end(), [](const std::size_t left, const std::size_t right) { return kKinds[left] < kKinds[right]; });
        std::string count_json;
        for (const std::size_t index : order) { if (!count_json.empty()) count_json += ','; count_json += quote(kKinds[index]) + ":" + std::to_string(counts[index]); }
        const std::string observation = "{\"candidate_counts\":{" + count_json + "},\"case_id\":" + quote(identity.case_id) +
            ",\"kind\":\"jfg-g2-runtime-trap-oracle-observation\",\"records\":[" + records + "],\"schema_version\":1,\"semantic_result_sha256\":" +
            quote(::jfg::evidence::hex_digest(std::as_bytes(std::span(semantic.data(), semantic.size())))) + ",\"subject_sha256\":" + quote(identity.digest) + "}";
        return emit(identity, observation);
    } catch (...) { return 1; }
}
