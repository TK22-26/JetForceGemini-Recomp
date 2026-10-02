#pragma once

// Optional host-side tooling for the supported US ROM. No game assets are
// embedded.
#include <array>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <ostream>
#include <span>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace jfg::mod {
class Memory {
  std::span<std::uint8_t> bytes_;
  bool swapped_;

public:
  explicit Memory(std::span<std::uint8_t> bytes, bool native_words = true)
      : bytes_(bytes), swapped_(native_words) {
    if (native_words && bytes.size() % 4U != 0U)
      throw std::runtime_error("native mod memory must contain complete words");
  }
  bool valid(std::uint32_t a, std::uint64_t n) const noexcept {
    const auto segment = a & 0xE0000000U;
    const auto offset = a & 0x1FFFFFFFU;
    return (segment == 0x80000000U || segment == 0xA0000000U) &&
           offset <= bytes_.size() && n <= bytes_.size() - offset;
  }
  void require(std::uint32_t a, std::uint64_t n) const {
    if (!valid(a, n))
      throw std::runtime_error("invalid mod memory range");
  }
  std::uint8_t u8(std::uint32_t a) const {
    require(a, 1);
    return bytes_[(a & 0x1FFFFFFFU) ^ (swapped_ ? 3U : 0U)];
  }
  std::uint16_t u16(std::uint32_t a) const {
    require(a, 2);
    return static_cast<std::uint16_t>((u8(a) << 8U) | u8(a + 1U));
  }
  std::int16_t s16(std::uint32_t a) const {
    return std::bit_cast<std::int16_t>(u16(a));
  }
  std::uint32_t u32(std::uint32_t a) const {
    require(a, 4);
    return (static_cast<std::uint32_t>(u16(a)) << 16U) | u16(a + 2U);
  }
  float f32(std::uint32_t a) const {
    const auto value = std::bit_cast<float>(u32(a));
    if (!std::isfinite(value))
      throw std::runtime_error("nonfinite mod coordinate");
    return value;
  }
  void put16(std::uint32_t a, std::uint16_t v) {
    require(a, 2);
    bytes_[(a & 0x1FFFFFFFU) ^ (swapped_ ? 3U : 0U)] =
        static_cast<std::uint8_t>(v >> 8U);
    bytes_[((a + 1U) & 0x1FFFFFFFU) ^ (swapped_ ? 3U : 0U)] =
        static_cast<std::uint8_t>(v);
  }
};

struct Vec3 {
  float x{}, y{}, z{};
};
inline Vec3 position(const Memory &m, std::uint32_t actor) {
  m.require(actor, 0x18);
  return {m.f32(actor + 12), m.f32(actor + 16), m.f32(actor + 20)};
}
inline void json_vec(std::ostream &out, Vec3 p) {
  out << '[' << p.x << ',' << p.y << ',' << p.z << ']';
}

// Identifiers observed in the game's tribal classification, not name matching.
inline bool tribal(std::uint16_t type) noexcept {
  return (type >= 0x11CU && type < 0x121U) || type == 0x66U || type == 0x70U ||
         type == 0x90U || type == 0x97U || type == 0x157U || type == 0xA5U;
}
inline std::uint16_t health_capacity(std::int16_t upgrades) noexcept {
  return upgrades >= 0 && upgrades <= 24
             ? static_cast<std::uint16_t>(
                   (5U * static_cast<unsigned>(upgrades) + 4U) * 256U)
             : 0U;
}

struct Actor {
  std::uint32_t address{};
  std::uint16_t behavior{};
  Vec3 position{};
};
struct Exit {
  std::uint32_t address{};
  Vec3 position{}, normal{};
  float plane_d{};
  std::uint32_t radius{};
  std::uint16_t destination{};
  std::int16_t condition{}, directional{};
};
struct Triangle {
  std::array<std::uint32_t, 3> vertices{};
  std::uint32_t flags{}, block{};
  Vec3 normal{};
};
struct Mesh {
  std::vector<Vec3> vertices;
  std::vector<Triangle> triangles;
  std::uint32_t blocks{};
};

inline std::vector<Actor> actors(const Memory &m) {
  const auto table = m.u32(0x800F2CA4U), count = m.u32(0x800F2CA8U);
  if (count > 1024U)
    throw std::runtime_error("invalid mod actor count");
  if (count == 0U)
    return {};
  m.require(table, static_cast<std::uint64_t>(count) * 4U);
  std::vector<Actor> result;
  for (std::uint32_t i = 0; i < count; ++i) {
    const auto a = m.u32(table + i * 4U);
    if (!m.valid(a, 0xA4U))
      continue;
    try {
      result.push_back({a, m.u16(a + 0x48U), position(m, a)});
    } catch (const std::runtime_error
                 &) { /* Incomplete objects are not actionable. */
    }
  }
  return result;
}

inline std::vector<Exit> exits(const Memory &m,
                               const std::vector<Actor> &list) {
  std::vector<Exit> result;
  for (const auto &a : list) {
    if (a.behavior != 8U)
      continue;
    const auto control = m.u32(a.address + 0x68U),
               definition = m.u32(a.address + 0x3CU);
    if (!m.valid(control, 0x18U) || !m.valid(definition, 0x1CU))
      continue;
    try {
      result.push_back(
          {a.address,
           a.position,
           {m.f32(control), m.f32(control + 4), m.f32(control + 8)},
           m.f32(control + 12),
           m.u32(control + 0x10U),
           static_cast<std::uint16_t>(m.u8(definition + 0xAU) |
                                      (m.u8(definition + 0xBU) << 8U)),
           m.s16(control + 0x14U),
           m.s16(control + 0x16U)});
    } catch (const std::runtime_error &) {
    }
  }
  return result;
}

struct NpcMarker {
  std::uint32_t address{};
  Vec3 position{};
  std::uint16_t object_id{}, behavior{};
  int squad_type = -1;
  const char *kind = "npc";
  const char *label = "NPC";
};
// Descriptive labels verified against the supported ROM's object headers.
// These are character categories, not inferred quest/reward completion.
inline const char *npc_label(std::uint16_t object) noexcept {
  switch (object) {
  case 350:
  case 550:
  case 551:
    return "NPC: Guide";
  case 476:
    return "NPC: King";
  case 486:
    return "NPC: Wise character";
  case 487:
    return "NPC: Limpet";
  case 488:
  case 489:
  case 490:
    return "NPC: Old mole";
  case 612:
    return "NPC: Sidekick";
  case 772:
    return "NPC: DJ";
  default:
    return "NPC";
  }
}
inline const char *tribal_label(std::uint16_t type) noexcept {
  switch (type) {
  case 0x66:
    return "Tribal: Chief";
  case 0x70:
    return "Tribal: Lantern";
  case 0x90:
    return "Tribal: Pickaxe";
  case 0x97:
    return "Tribal: Barrow";
  case 0xA5:
    return "Tribal: Spade";
  case 0x157:
    return "Tribal: Hammer";
  case 0x11E:
  case 0x11F:
    return "Tribal: Child";
  case 0x120:
    return "Tribal: Baby";
  default:
    return "Tribal";
  }
}
inline std::vector<NpcMarker> npc_markers(const Memory &m,
                                          const std::vector<Actor> &list) {
  std::vector<NpcMarker> result;
  for (const auto &a : list) {
    if (a.behavior != 90U && a.behavior != 24U)
      continue;
    try {
      m.require(a.address, 0xA4U);
      const auto control = m.u32(a.address + 0x68U);
      const auto properties = m.u32(a.address + 0x4CU);
      if (!m.valid(properties, 8U))
        continue;
      NpcMarker npc{a.address,  a.position, m.u16(a.address + 0x4AU),
                    a.behavior, -1,         "npc",
                    "NPC"};
      if (a.behavior == 90U) {
        // Shared dialogue controller (mrhints), not scenery name matching.
        if (!m.valid(control, 0x38U) || m.s16(properties + 6U) == 0)
          continue;
        npc.label = npc_label(npc.object_id);
      } else {
        if (!m.valid(control, 0x28U) || m.s16(properties + 6U) <= 0)
          continue;
        const auto squad = m.u32(control + 0x24U);
        if (!m.valid(squad, 0xA4U) || m.u16(squad + 0x48U) != 23U)
          continue;
        const auto data = m.u32(squad + 0x68U);
        if (!m.valid(data, 0x2EU))
          continue;
        const auto type = m.u16(data + 0x2CU);
        if (!tribal(type))
          continue;
        npc.squad_type = type;
        npc.kind = "tribal";
        npc.label = tribal_label(type);
      }
      result.push_back(npc);
    } catch (const std::runtime_error &) {
      // Loading or removed actors are not valid interaction targets.
    }
  }
  return result;
}
inline void write_npcs(std::ostream &out, const std::vector<NpcMarker> &list) {
  out << '[';
  bool first = true;
  for (const auto &npc : list) {
    if (!first)
      out << ',';
    first = false;
    out << "{\"address\":" << npc.address << ",\"position\":";
    json_vec(out, npc.position);
    // Labels are host-owned literals; no unescaped ROM text enters JSON.
    out << ",\"kind\":\"" << npc.kind << "\",\"label\":\"" << npc.label
        << "\",\"object_id\":" << npc.object_id
        << ",\"behavior\":" << npc.behavior
        << ",\"squad_type\":" << npc.squad_type << '}';
  }
  out << ']';
}

struct ItemMarker {
  std::uint32_t address{};
  Vec3 position{};
  std::string kind, label;
  int content_code = -1;
  bool opened = false;
};
// Weapon indices used by the inventory and weapon-pickup controller.
inline const char *weapon_name(unsigned index) {
  constexpr std::array<const char *, 15> names = {
      "Pistol",       "Homing missiles", "Machine gun",     "Shotgun",
      "Shrink ray",   "Rocket launcher", "Flamethrower",    "Grenades",
      "Shurikens",    "Fish food",       "Proximity mines", "Timed mines",
      "Remote mines", "Flares",          "Cluster bombs"};
  return index < names.size() ? names[index] : "Unknown weapon";
}
inline std::vector<ItemMarker> item_markers(const Memory &m,
                                            const std::vector<Actor> &list) {
  std::vector<ItemMarker> result;
  for (const auto &a : list) {
    try {
      ItemMarker item{a.address, a.position, "", "", -1, false};
      const auto object = m.u16(a.address + 0x4AU);
      if (a.behavior == 98U) {
        const auto control = m.u32(a.address + 0x68U);
        if (!m.valid(control, 6U))
          continue;
        item.content_code = m.u8(control + 5U);
        item.opened = m.u8(control + 4U) == 5U;
        // Chest reward switch, including duplicate entries, verified against
        // the supported ROM's jump table. -1 denotes a special collectable
        // whose player-facing name has not yet been verified.
        constexpr std::array<int, 21> weapons = {3,  1,  2,  2,  9,  8,  -1,
                                                 -1, 14, 13, 14, 12, 11, 10,
                                                 7,  6,  4,  -1, -1, -1, 5};
        const int weapon =
            item.content_code < static_cast<int>(weapons.size())
                ? weapons[static_cast<unsigned>(item.content_code)]
                : -1;
        item.kind = item.opened ? "opened" : weapon >= 0 ? "weapon" : "chest";
        item.label = "Chest: ";
        item.label += weapon >= 0
                          ? weapon_name(static_cast<unsigned>(weapon))
                          : "item " + std::to_string(item.content_code) +
                                " (unidentified)";
        if (item.opened)
          item.label += " (opened)";
      } else if (a.behavior == 61U) {
        item.kind = "health";
        item.label = "Health";
      } else if (a.behavior == 66U) {
        item.kind = "ammo";
        item.label = "Ammo / capacity";
      } else {
        // The original pickup initializer matches these object IDs against
        // weaponPowerUpObjects before storing its inventory index at +0x88.
        bool weapon_object = object == 0x88U;
        for (unsigned n = 0; n < 15U; ++n)
          weapon_object =
              weapon_object ||
              (object != 0U && object == m.u16(0x800A0CB0U + n * 2U));
        if (weapon_object) {
          const auto index = m.u16(a.address + 0x88U);
          if (index >= 15U)
            continue;
          item.kind = "weapon";
          item.label = weapon_name(index);
          item.content_code = index;
        } else {
          const auto header = m.u32(a.address + 0x40U);
          if (!m.valid(header, 20U))
            continue;
          std::string name;
          for (unsigned n = 4; n < 20U; ++n) {
            const auto c = m.u8(header + n);
            if (c == 0U)
              break;
            if (c < 32U || c > 126U) {
              name.clear();
              break;
            }
            name += static_cast<char>(c);
          }
          std::string lower = name;
          for (char &c : lower)
            if (c >= 'A' && c <= 'Z')
              c = static_cast<char>(c + ('a' - 'A'));
          // A key-like name alone could be a switch. Require the object-ID
          // family used by keyInit as well; retain the raw variant.
          if (object >= 0x258U && object <= 0x25FU &&
              lower.find("key") != std::string::npos) {
            item.kind = "key";
            item.label = "Key";
            item.content_code = static_cast<int>(object - 0x258U);
          } else
            continue;
        }
      }
      result.push_back(std::move(item));
    } catch (const std::runtime_error &) {
      // Incomplete objects may disappear between updates; never guess.
    }
  }
  return result;
}

inline Mesh decode_mesh(const Memory &m, std::uint32_t track) {
  m.require(track, 0x20U);
  const auto blocks = m.u32(track + 4U);
  const auto count = m.u16(track + 0x1AU);
  if (count == 0U || count > 512U)
    throw std::runtime_error("invalid mod mesh block count");
  m.require(blocks, static_cast<std::uint64_t>(count) * 0x48U);
  Mesh result;
  result.blocks = count;
  for (std::uint32_t b = 0; b < count; ++b) {
    const auto block = blocks + b * 0x48U;
    const auto vertices = m.u32(block), faces = m.u32(block + 4U),
               batches = m.u32(block + 0xCU);
    const auto planes = m.u32(block + 0x1CU),
               plane_indices = m.u32(block + 0x18U);
    const auto nv = m.u16(block + 0x24U), nf = m.u16(block + 0x26U),
               nb = m.u16(block + 0x28U);
    if (nv > 16384U || nf > 16384U || nb > 4096U ||
        result.vertices.size() + nv > 131072U ||
        result.triangles.size() + nf > 262144U)
      throw std::runtime_error("mod mesh too large");
    if (nv == 0U || nf == 0U)
      continue;
    m.require(vertices, static_cast<std::uint64_t>(nv) * 10U);
    m.require(faces, static_cast<std::uint64_t>(nf) * 16U);
    m.require(batches, static_cast<std::uint64_t>(nb + 1U) * 16U);
    m.require(plane_indices, static_cast<std::uint64_t>(nf) * 8U);
    const auto base = static_cast<std::uint32_t>(result.vertices.size());
    for (std::uint32_t i = 0; i < nv; ++i) {
      const auto v = vertices + i * 10U;
      result.vertices.push_back({static_cast<float>(m.s16(v)),
                                 static_cast<float>(m.s16(v + 2)),
                                 static_cast<float>(m.s16(v + 4))});
    }
    for (std::uint32_t batch = 0; batch < nb; ++batch) {
      const auto at = batches + batch * 16U;
      const auto vertex_base = m.u16(at + 6U), first = m.u16(at + 8U),
                 end = m.u16(at + 24U);
      if (first > end || end > nf)
        throw std::runtime_error("invalid mod mesh batch");
      for (std::uint32_t i = first; i < end; ++i) {
        Triangle tri;
        tri.flags = m.u32(at + 12U);
        tri.block = b;
        for (std::uint32_t j = 0; j < 3U; ++j) {
          const auto index = static_cast<std::uint32_t>(vertex_base) +
                             m.u8(faces + i * 16U + 1U + j);
          if (index >= nv)
            throw std::runtime_error("invalid mod triangle index");
          tri.vertices[j] = base + index;
        }
        const auto plane_offset =
            static_cast<std::uint32_t>(m.u16(plane_indices + i * 8U)) * 16U;
        m.require(planes, static_cast<std::uint64_t>(plane_offset) + 16U);
        const auto plane = planes + plane_offset;
        m.require(plane, 16U);
        tri.normal = {m.f32(plane), m.f32(plane + 4U), m.f32(plane + 8U)};
        result.triangles.push_back(tri);
      }
    }
  }
  return result;
}

inline void write_mesh(std::ostream &out, const Mesh &mesh, std::uint32_t level,
                       std::uint64_t generation) {
  out << "{\"schema\":1,\"level\":" << level << ",\"generation\":" << generation
      << ",\"blocks\":" << mesh.blocks << ",\"vertices\":[";
  bool first = true;
  for (const auto &v : mesh.vertices) {
    if (!first)
      out << ',';
    first = false;
    json_vec(out, v);
  }
  out << "],\"triangles\":[";
  first = true;
  for (const auto &t : mesh.triangles) {
    if (!first)
      out << ',';
    first = false;
    out << "{\"v\":[" << t.vertices[0] << ',' << t.vertices[1] << ','
        << t.vertices[2] << "],\"flags\":" << t.flags
        << ",\"block\":" << t.block << ",\"normal\":";
    json_vec(out, t.normal);
    out << '}';
  }
  out << "]}\n";
}

// Normal single-player gameplay, without scripted camera or input control.
inline bool gameplay_active(const Memory &m, std::uint32_t player) {
  if (!m.valid(player, 0xA4U))
    return false;
  const auto control = m.u32(player + 0x68U);
  if (!m.valid(control, 0x5C4U) || m.u32(control + 0x5C0U) != 0U)
    return false;
  return m.u8(0x800A4FC4U) == 0U && m.u32(0x800FD7C4U) == 0U &&
         m.u32(0x801045B8U) == 0U && m.u32(0x800F6DBCU) == 0U;
}

class NavigationMod {
public:
  bool enabled = false;
  std::uint32_t player = 0, last_track = 0, last_level = UINT32_MAX;
  std::uint64_t updates = 0, generation = 1, cleared = 0, health_restores = 0,
                invalid = 0;
  std::uint32_t first_clear_level = UINT32_MAX;
  std::uint64_t first_clear_update = 0;
  void transition() noexcept {
    player = 0;
    last_track = 0;
    last_level = UINT32_MAX;
    ++generation;
  }
  bool full_health(Memory &m, std::uint32_t actor) noexcept {
    if (!enabled)
      return false;
    try {
      if (!gameplay_active(m, actor) || !m.valid(actor, 0xA4U))
        return false;
      const auto control = m.u32(actor + 0x68U),
                 properties = m.u32(actor + 0x4CU);
      m.require(control, 0x5CAU);
      m.require(properties, 8U);
      const auto character =
          static_cast<std::uint32_t>(m.u8(control + 1U) & 3U);
      const auto game = m.u32(0x800FD7D4U);
      m.require(game, 0x334U);
      const auto saved = game + 0x15CU + character * 0x76U;
      const auto maximum = health_capacity(m.s16(saved + 2U));
      if (maximum == 0U)
        return false;
      if (m.u16(properties + 6U) != maximum)
        ++health_restores;
      m.put16(properties + 6U, maximum);
      m.put16(saved, maximum);
      // Keep the game's invulnerability timer alive without creating a shield
      // object.
      m.put16(control + 0x5C8U, 60U);
      player = actor;
      return true;
    } catch (const std::runtime_error &) {
      ++invalid;
      return false;
    }
  }
  bool clear_enemy(Memory &m, std::uint32_t actor) noexcept {
    if (!enabled || player == 0U || actor == player)
      return false;
    try {
      if (!gameplay_active(m, player) || !m.valid(actor, 0xA4U))
        return false;
      // Only the normal squad-member behavior; animated cutscene actors differ.
      if (m.u16(actor + 0x48U) != 24U)
        return false;
      const auto control = m.u32(actor + 0x68U),
                 properties = m.u32(actor + 0x4CU);
      if (!m.valid(control, 0xA8U) || !m.valid(properties, 12U))
        return false;
      const auto squad = m.u32(control + 0x24U);
      if (!m.valid(squad, 0xA4U) || m.u16(squad + 0x48U) != 23U)
        return false;
      const auto data = m.u32(squad + 0x68U);
      if (!m.valid(data, 0x34U))
        return false;
      const auto type = m.u16(data + 0x2CU);
      if (tribal(type) || m.s16(properties + 6U) <= 0)
        return false;
      // Leave the object in the game so its original death logic updates squad
      // gates.
      m.put16(properties + 6U, 0U);
      if (cleared == 0U) {
        first_clear_level = m.u32(0x800FB114U);
        first_clear_update = updates;
      }
      ++cleared;
      return true;
    } catch (const std::runtime_error &) {
      ++invalid;
      return false;
    }
  }
  void write_state(std::ostream &out, const Memory &m,
                   const std::vector<Actor> &list, std::uint32_t level,
                   bool mesh_ready) const {
    out << "{\"schema\":1,\"level\":" << level
        << ",\"generation\":" << generation << ",\"timestamp_ms\":"
        << std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::system_clock::now().time_since_epoch())
               .count()
        << ",\"update\":" << updates
        << ",\"mesh_ready\":" << (mesh_ready ? "true" : "false")
        << ",\"clearing_active\":"
        << (player != 0U && gameplay_active(m, player) ? "true" : "false")
        << ",\"first_clear_level\":" << first_clear_level
        << ",\"first_clear_update\":" << first_clear_update
        << ",\"enemies_cleared\":" << cleared
        << ",\"health_restores\":" << health_restores
        << ",\"invalid_reads\":" << invalid << ",\"player\":";
    bool found = false;
    for (const auto &a : list)
      if (a.address == player) {
        out << "{\"address\":" << player << ",\"position\":";
        json_vec(out, a.position);
        out << ",\"yaw\":" << m.s16(player)
            << ",\"health\":" << m.s16(m.u32(player + 0x4CU) + 6U) << '}';
        found = true;
        break;
      }
    if (!found)
      out << "null";
    out << ",\"exits\":[";
    bool first = true;
    for (const auto &e : exits(m, list)) {
      if (!first)
        out << ',';
      first = false;
      out << "{\"address\":" << e.address << ",\"position\":";
      json_vec(out, e.position);
      out << ",\"normal\":";
      json_vec(out, e.normal);
      out << ",\"plane_d\":" << e.plane_d << ",\"radius\":" << e.radius
          << ",\"destination_code\":" << e.destination
          << ",\"condition_code\":" << e.condition
          << ",\"directional\":" << e.directional << '}';
    }

    out << "],\"markers\":[";
    first = true;
    for (const auto &item : item_markers(m, list)) {
      if (!first)
        out << ',';
      first = false;
      out << "{\"address\":" << item.address << ",\"position\":";
      json_vec(out, item.position);
      // Labels contain only host-owned ASCII literals and numeric IDs.
      out << ",\"kind\":\"" << item.kind << "\",\"label\":\"" << item.label
          << "\",\"content_code\":" << item.content_code
          << ",\"opened\":" << (item.opened ? "true" : "false") << '}';
    }
    out << "],\"npcs\":";
    write_npcs(out, npc_markers(m, list));
    out << ",\"actors\":[";
    first = true;
    for (const auto &a : list) {
      if (!first)
        out << ',';
      first = false;
      out << "{\"address\":" << a.address << ",\"behavior\":" << a.behavior
          << ",\"position\":";
      json_vec(out, a.position);
      out << '}';
    }
    out << "]}\n";
  }
};
} // namespace jfg::mod
