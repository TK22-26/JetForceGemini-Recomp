#pragma once
// Read-only interpretation of control records in the user's supported US ROM.
// No dialogue text, game code, or ROM tables are embedded here.
#include <array>
#include <cstdint>
#include <map>
#include <set>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

namespace jfg::mod {
enum class Fact { unknown = -1, missing = 0, met = 1 };
inline Fact fact(bool b) { return b ? Fact::met : Fact::missing; }
inline Fact negate(Fact a) {
  return a == Fact::unknown ? a : fact(a == Fact::missing);
}
inline Fact both(Fact a, Fact b) {
  return a == Fact::missing || b == Fact::missing   ? Fact::missing
         : a == Fact::unknown || b == Fact::unknown ? Fact::unknown
                                                    : Fact::met;
}
inline Fact either(Fact a, Fact b) {
  return negate(both(negate(a), negate(b)));
}
inline const char *fact_name(Fact a) {
  return a == Fact::met ? "met" : a == Fact::missing ? "missing" : "unknown";
}
struct NpcFacts {
  bool known = false;
  unsigned character = 0, weapons = 0;
  int currency = 0, race = -1, first_conversation = -1;
  std::array<std::array<std::uint8_t, 4>, 3> items{};
  std::array<std::uint8_t, 144> flags{};
  Fact item(unsigned id, bool any = false) const {
    if (!known || character > 2 || id > 26)
      return Fact::unknown;
    bool owned = false;
    for (unsigned c = 0; c < 3; ++c)
      if (any || c == character)
        owned |= (items[c][id >> 3] & (0x80U >> (id & 7))) != 0;
    return fact(owned);
  }
  Fact flag(unsigned id) const {
    return !known || id >= flags.size() * 8
               ? Fact::unknown
               : fact((flags[id >> 3] & (1U << (id & 7))) != 0);
  }
  Fact rocket() const {
    return known ? fact((weapons & 32) != 0) : Fact::unknown;
  }
  int ship_parts() const {
    if (!known)
      return -1;
    int n = 0;
    for (unsigned i = 32; i <= 43; ++i)
      n += flag(i) == Fact::met;
    return n;
  }
};
inline std::string npc_item_name(int id) {
  switch (id) {
  case 1:
    return "Red key";
  case 16:
    return "Miner magazine";
  case 17:
    return "Mine key";
  case 20:
    return "Pants";
  case 21:
    return "Crowbar";
  case 22:
    return "Night vision goggles";
  case 23:
    return "Gold coin 1";
  case 24:
    return "Gold coin 2";
  case 25:
    return "Gold coin 3";
  default:
    return "Quest item " + std::to_string(id);
  }
}
inline std::string npc_flag_name(int id) {
  switch (id) {
  case 32:
    return "Power cell";
  case 33:
    return "Radar dish";
  case 34:
    return "Fin";
  case 35:
    return "Cargo bay key";
  case 36:
    return "Deflector shield";
  case 43:
    return "Stabilizer";
  case 88:
    return "All Tribals rescued";
  case 89:
    return "Quarry generator activated";
  default:
    return "Shared flag " + std::to_string(id);
  }
}
inline Fact root_predicate(int code, const NpcFacts &f) {
  const bool inverted = (code & 128) != 0;
  const int id = code & 127;
  Fact v = Fact::unknown;
  switch (id) {
  case 0:
    v = Fact::met;
    break;
  case 1:
    v = f.first_conversation < 0 ? Fact::unknown
                                 : fact(f.first_conversation != 0);
    break;
  case 2:
    v = f.item(1);
    break;
  case 3:
    v = f.item(21, true);
    break;
  case 4:
    v = f.rocket();
    break;
  case 5:
    v = f.flag(32);
    break;
  case 6:
    v = f.flag(89);
    break;
  case 7:
    v = f.flag(33);
    break;
  case 8:
    v = f.flag(34);
    break;
  case 9:
    v = f.flag(35);
    break;
  case 10:
    v = !f.known ? Fact::unknown : fact(f.ship_parts() == 0);
    break;
  case 11:
    v = !f.known ? Fact::unknown : fact(f.ship_parts() < 7);
    break;
  case 12:
    v = !f.known ? Fact::unknown : fact(f.ship_parts() >= 7);
    break;
  case 13:
    v = !f.known ? Fact::unknown : fact(f.ship_parts() == 12);
    break;
  case 14:
    v = f.flag(88);
    break;
  case 15:
    v = f.race < 0 ? Fact::unknown : fact(f.race == 0);
    break;
  case 16:
    v = f.race < 0 ? Fact::unknown : fact(f.race == 2);
    break;
  case 17:
    v = f.flag(36);
    break;
  case 18:
    v = f.item(22, true);
    break;
  case 19:
    v = f.flag(43);
    break;
  case 20:
    v = f.item(17, true);
    break;
  }
  return inverted ? negate(v) : v;
}
inline std::string root_description(int code) {
  std::string s;
  switch (code & 127) {
  case 0:
    s = "Always";
    break;
  case 1:
    s = "First-conversation branch";
    break;
  case 2:
    s = "Current character owns Red key";
    break;
  case 3:
    s = "Any character owns " + npc_item_name(21);
    break;
  case 4:
    s = "Current character owns Rocket launcher";
    break;
  case 5:
    s = npc_flag_name(32);
    break;
  case 6:
    s = npc_flag_name(89);
    break;
  case 7:
    s = npc_flag_name(33);
    break;
  case 8:
    s = npc_flag_name(34);
    break;
  case 9:
    s = npc_flag_name(35);
    break;
  case 10:
    s = "No ship parts";
    break;
  case 11:
    s = "Fewer than seven ship parts";
    break;
  case 12:
    s = "At least seven ship parts";
    break;
  case 13:
    s = "All twelve ship parts";
    break;
  case 14:
    s = npc_flag_name(88);
    break;
  case 15:
    s = "Race state zero";
    break;
  case 16:
    s = "Winning race result";
    break;
  case 17:
    s = npc_flag_name(36);
    break;
  case 18:
    s = "Any character owns " + npc_item_name(22);
    break;
  case 19:
    s = npc_flag_name(43);
    break;
  case 20:
    s = "Any character owns " + npc_item_name(17);
    break;
  default:
    s = "Unknown dialogue predicate";
    break;
  }
  return (code & 128) ? "NOT (" + s + ")" : s;
}
inline Fact choice_visible(int id, const NpcFacts &f) {
  switch (id) {
  case -1:
  case 13:
    return Fact::met;
  case 0:
    return negate(f.item(1));
  case 1:
    return negate(either(f.item(16, true), f.item(17, true)));
  case 2:
    return negate(f.item(17, true));
  case 3:
    return negate(f.rocket());
  case 4:
    return negate(f.item(21, true));
  case 5:
    return negate(f.flag(32));
  case 6:
    return negate(f.flag(33));
  case 7:
    return f.flag(33);
  case 8:
    return negate(f.flag(34));
  case 9:
    return f.flag(34);
  case 10:
    return negate(f.flag(35));
  case 11:
    return f.flag(35);
  case 12:
    return negate(f.flag(36));
  case 14:
    return negate(f.item(22, true));
  case 19:
    return f.flag(43);
  case 20:
    return negate(f.flag(43));
  default:
    return Fact::unknown; // Music selection depends on the audio player.
  }
}
inline Fact choice_requirement(int id, const NpcFacts &f) {
  switch (id) {
  case -1:
    return Fact::met;
  case 0:
    return f.item(0);
  case 1:
    return f.item(16);
  case 2:
    return both(f.flag(44), both(f.flag(45), f.flag(46)));
  case 3:
    return f.item(20);
  case 4:
    return f.known ? fact(f.currency >= 5) : Fact::unknown;
  case 5:
    return f.known ? fact(f.currency >= 10) : Fact::unknown;
  case 6:
    return both(f.item(23), both(f.item(24), f.item(25)));
  case 7:
    return f.item(26);
  default:
    return Fact::unknown;
  }
}
inline std::string requirement_description(int id) {
  switch (id) {
  case -1:
    return "No additional payment";
  case 0:
    return "Current character: " + npc_item_name(0);
  case 1:
    return "Trade " + npc_item_name(16) + " (current character)";
  case 2:
    return "All three Floyd components";
  case 3:
    return "Trade " + npc_item_name(20) + " (current character)";
  case 4:
    return "Pay 5 tokens";
  case 5:
    return "Pay 10 tokens";
  case 6:
    return "Trade " + npc_item_name(23) + ", " + npc_item_name(24) + ", " +
           npc_item_name(25);
  case 7:
    return "Trade " + npc_item_name(26) + " (current character)";
  default:
    return "Unknown prerequisite";
  }
}
struct NpcCondition {
  std::string domain, description;
  int id = -1;
  Fact state = Fact::unknown;
};
struct NpcOffer {
  std::string id, kind, reward, status = "unknown", scope = "none";
  int action = -1, item = -1, weapon = -1, flag = -1, destination = -1;
  std::vector<int> consumed_items;
  int cost = 0;
  std::vector<NpcCondition> conditions;
};
inline NpcOffer reward_action(int action, const NpcFacts &f) {
  NpcOffer o;
  o.action = action;
  o.kind = "item";
  o.scope = "current_character";
  Fact owned = Fact::unknown;
  switch (action) {
  case 0:
    o.item = 1;
    break;
  case 1:
    o.item = 16;
    break;
  case 2:
    o.item = 17;
    o.consumed_items = {16};
    o.scope = "any_character";
    break;
  case 3:
  case 4:
    o.kind = "weapon";
    o.weapon = 5;
    o.reward = "Rocket launcher";
    owned = f.rocket();
    if (action == 4)
      o.consumed_items = {23, 24, 25};
    break;
  case 5:
    o.item = 21;
    o.consumed_items = {20};
    o.scope = "any_character";
    break;
  case 6:
  case 7:
    o.kind = "service";
    o.reward = action == 6 ? "Refill health" : "Refill owned weapon ammo";
    o.cost = action == 6 ? 5 : 10;
    break;
  case 8:
  case 9:
  case 10:
  case 11:
  case 12:
  case 18:
    o.kind = "ship_part";
    o.scope = "shared";
    o.flag = action == 18 ? 43 : action + 24;
    o.reward = npc_flag_name(o.flag);
    owned = f.flag(o.flag);
    if (action == 8)
      o.consumed_items = {26};
    break;
  case 13:
    o.item = 22;
    o.scope = "any_character";
    break;
  case 14:
  case 15:
  case 16:
  case 17:
    o.kind = "music";
    o.scope = "none";
    o.reward = "Music selection " + std::to_string(action - 13);
    break;
  default:
    o.kind = "unknown";
    o.reward = "Unknown action";
    o.scope = "none";
    break;
  }
  if (o.item >= 0) {
    o.reward = npc_item_name(o.item);
    owned = f.item(o.item, o.scope == "any_character");
  }
  if (owned == Fact::met)
    o.status = "owned";
  return o;
}
class NpcRewardCatalog {
  struct Row {
    int c1, op, c2, flags, text, auxiliary;
  };
  struct Choice {
    int visible, prerequisite, action;
  };
  std::vector<std::vector<Row>> groups_;
  std::map<int, std::vector<Choice>> choices_;
  static unsigned be16(std::span<const std::uint8_t> b, std::size_t p) {
    if (p > b.size() || b.size() - p < 2)
      throw std::runtime_error("short NPC data");
    return (unsigned(b[p]) << 8) | b[p + 1];
  }
  static int signed16(std::span<const std::uint8_t> b, std::size_t p) {
    const auto v = be16(b, p);
    return v < 32768 ? int(v) : int(v) - 65536;
  }
  static unsigned be32(std::span<const std::uint8_t> b, std::size_t p) {
    return (be16(b, p) << 16) | be16(b, p + 2);
  }
  static std::span<const std::uint8_t> slice(std::span<const std::uint8_t> b,
                                             std::size_t a, std::size_t z) {
    if (a > z || z > b.size())
      throw std::runtime_error("invalid NPC data range");
    return b.subspan(a, z - a);
  }
  void parse_choice(int id, std::span<const std::uint8_t> index,
                    std::span<const std::uint8_t> data, std::set<int> &stack) {
    if (stack.contains(id))
      throw std::runtime_error("NPC choice cycle");
    if (choices_.contains(id))
      return;
    if (id < 0 || id >= 107 || stack.size() >= 16)
      throw std::runtime_error("invalid NPC choice");
    stack.insert(id);
    auto b = slice(data, be32(index, unsigned(id) * 4),
                   be32(index, unsigned(id + 1) * 4));
    const auto count = be16(b, 0);
    if (count == 0 || count > 32 || b.size() < 4 + count * 16)
      throw std::runtime_error("invalid NPC choices");
    std::vector<Choice> rows;
    for (unsigned i = 0; i < count; ++i) {
      const auto p = 4 + i * 16;
      Choice c{signed16(b, p + 4), signed16(b, p + 6), int(be16(b, p + 8))};
      if (c.visible < -1 || c.visible > 20 || c.prerequisite < -1 ||
          c.prerequisite > 7 || (c.action >> 12) > 5 ||
          (c.action < 0x1000 && c.action > 18))
        throw std::runtime_error("unsupported NPC choice semantics");
      rows.push_back(c);
      if ((c.action & 0xF000) == 0x2000)
        parse_choice(c.action & 4095, index, data, stack);
    }
    choices_[id] = std::move(rows);
    stack.erase(id);
  }
  void append_offer(std::vector<NpcOffer> &out, NpcOffer o,
                    const std::string &id,
                    const std::vector<NpcCondition> &conditions) const {
    o.id = id;
    o.conditions = conditions;
    Fact available = Fact::met;
    for (const auto &c : conditions)
      available = both(available, c.state);
    if (o.status != "owned")
      o.status = available == Fact::met       ? "available"
                 : available == Fact::missing ? "blocked"
                                              : "unknown";
    out.push_back(std::move(o));
    if (out.size() > 128)
      throw std::runtime_error("too many NPC offers");
  }
  void walk(int choice, const NpcFacts &f, const std::string &path,
            const std::vector<NpcCondition> &parents,
            std::vector<NpcOffer> &out, unsigned depth = 0) const {
    if (depth >= 16)
      throw std::runtime_error("NPC choice depth");
    const auto &rows = choices_.at(choice);
    for (std::size_t i = 0; i < rows.size(); ++i) {
      const auto &c = rows[i];
      auto conditions = parents;
      const auto id =
          path + "/" + std::to_string(choice) + ":" + std::to_string(i);
      if (c.visible != -1)
        conditions.push_back({"visibility", "Dialogue option visible",
                              c.visible, choice_visible(c.visible, f)});
      if (c.prerequisite != -1)
        conditions.push_back(
            {"prerequisite", requirement_description(c.prerequisite),
             c.prerequisite, choice_requirement(c.prerequisite, f)});
      switch (c.action >> 12) {
      case 0:
        append_offer(out, reward_action(c.action, f), id, conditions);
        break;
      case 2:
        walk(c.action & 4095, f, id, conditions, out, depth + 1);
        break;
      case 3: {
        NpcOffer o;
        o.kind = "transition";
        o.destination = c.action & 4095;
        o.reward = "Scripted scene / level " + std::to_string(o.destination);
        append_offer(out, std::move(o), id, conditions);
        break;
      }
      default:
        break; // Text, cancel and dialogue closure have no reward effect.
      }
    }
  }

public:
  bool ready() const { return groups_.size() == 45; }
  std::size_t group_count() const { return groups_.size(); }
  std::size_t choice_count() const { return choices_.size(); }
  bool load_assets(std::span<const std::uint8_t> selectors,
                   std::span<const std::uint8_t> index,
                   std::span<const std::uint8_t> data) noexcept {
    groups_.clear();
    choices_.clear();
    try {
      if (index.size() != 432 || selectors.size() > 4096 ||
          data.size() > 1048576)
        throw std::runtime_error("unsupported NPC assets");
      for (unsigned i = 0; i < 107; ++i)
        (void)slice(data, be32(index, i * 4), be32(index, (i + 1) * 4));
      std::size_t p = 0;
      std::set<int> stack;
      for (unsigned g = 0; g < 45; ++g) {
        unsigned count = be16(selectors, p);
        p += 2;
        if (count == 0 || count > 32)
          throw std::runtime_error("invalid NPC selector count");
        std::vector<Row> rows;
        for (unsigned i = 0; i < count; ++i, p += 8) {
          auto b = slice(selectors, p, p + 8);
          Row r{b[0], b[1], b[2], b[3], signed16(b, 4), signed16(b, 6)};
          if ((r.c1 & 127) > 20 || (r.c2 & 127) > 20 || r.op > 2 ||
              r.flags > 2 || r.text < 0 || r.text >= 107)
            throw std::runtime_error("unsupported NPC selector");
          if (r.flags == 1)
            parse_choice(r.auxiliary, index, data, stack);
          if (r.flags == 2 && (r.auxiliary < 0 || r.auxiliary > 4095))
            throw std::runtime_error("invalid NPC transition");
          rows.push_back(r);
        }
        groups_.push_back(std::move(rows));
      }
      // Validate expansion once so damaged DAGs cannot explode per-frame work.
      for (unsigned g = 0; g < 45; ++g)
        (void)offers(g, {});
      return true;
    } catch (const std::exception &) {
      groups_.clear();
      choices_.clear();
      return false;
    }
  }
  bool load_rom(std::span<const std::uint8_t> rom) noexcept {
    groups_.clear();
    choices_.clear();
    try {
      if (be32(rom, 0) != 0x80371240U || be32(rom, 0xB1750) != 71)
        return false;
      auto asset = [&](unsigned id) {
        return slice(rom,
                     std::size_t(0xB1880) + be32(rom, 0xB1750 + 4 * (id + 1)),
                     std::size_t(0xB1880) + be32(rom, 0xB1750 + 4 * (id + 2)));
      };
      return load_assets(asset(8), asset(9), asset(10));
    } catch (const std::exception &) {
      return false;
    }
  }
  std::vector<NpcOffer> offers(unsigned dialogue, const NpcFacts &f) const {
    std::vector<NpcOffer> out;
    if (!ready() || dialogue >= groups_.size())
      return out;
    const auto &rows = groups_[dialogue];
    Fact earlier = Fact::missing;
    for (std::size_t i = 0; i < rows.size(); ++i) {
      const auto &r = rows[i];
      const auto a = root_predicate(r.c1, f), b = root_predicate(r.c2, f);
      const auto matches = r.op == 0   ? both(a, b)
                           : r.op == 1 ? either(a, b)
                                       : a;
      const bool fallback = i + 1 == rows.size();
      const auto selected =
          both(negate(earlier), fallback ? Fact::met : matches);
      auto description =
          root_description(r.c1) +
          (r.c2 == 0 ? ""
                     : (r.op == 1 ? " OR " : " AND ") + root_description(r.c2));
      if (fallback)
        description += " (fallback branch)";
      if (i != 0)
        description += "; earlier branches must not match";
      std::vector<NpcCondition> conditions{
          {"dialogue_row", description, int(i), selected}};
      const auto path = std::to_string(dialogue) + ":" + std::to_string(i);
      if (r.flags == 1)
        walk(r.auxiliary, f, path, conditions, out);
      else if (r.flags == 2) {
        NpcOffer o;
        o.kind = "transition";
        o.destination = r.auxiliary;
        o.reward = "Scripted scene / level " + std::to_string(o.destination);
        append_offer(out, std::move(o), path, conditions);
      }
      earlier = either(earlier, matches);
    }
    return out;
  }
};
} // namespace jfg::mod
