#include "jfg/mod/navigation_mod.hpp"
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>

static void check(bool ok) {
  if (!ok)
    std::abort();
}
int main(int argc, char **argv) {
  using namespace jfg::mod;
  if (argc == 3) {
    std::ifstream in(argv[1], std::ios::binary);
    std::vector<std::uint8_t> bytes{std::istreambuf_iterator<char>(in),
                                    std::istreambuf_iterator<char>()};
    check(bytes.size() == 4194304U);
    Memory m(bytes, false);
    const auto mesh = decode_mesh(m, m.u32(0x800A0D60U));
    const auto list = actors(m);
    const auto doors = exits(m, list);
    for (const auto &item : item_markers(m, list)) std::cout << item.label << "\n";
    std::ofstream out(argv[2]);
    write_mesh(out, mesh, m.u32(0x800FB114U), 1);
    std::cout << "blocks=" << mesh.blocks
              << " vertices=" << mesh.vertices.size()
              << " triangles=" << mesh.triangles.size()
              << " exits=" << doors.size() << '\n';
    check(!mesh.triangles.empty() && !doors.empty() && bool(out));
    return 0;
  }
  bool odd_rejected = false;
  try {
    std::array<std::uint8_t, 3> odd{};
    Memory invalid(odd);
  } catch (const std::runtime_error &) {
    odd_rejected = true;
  }
  check(odd_rejected);
  for (bool swapped : {false, true}) {
    std::vector<std::uint8_t> bytes(4194304U);
    Memory m(bytes, swapped);
    const auto put32 = [&](std::uint32_t a, std::uint32_t v) {
      m.put16(a, static_cast<std::uint16_t>(v >> 16U));
      m.put16(a + 2, static_cast<std::uint16_t>(v));
    };
    const auto put8 = [&](std::uint32_t a, std::uint8_t v) {
      bytes[(a & 0x1FFFFFFFU) ^ (swapped ? 3U : 0U)] = v;
    };
    const auto putfloat = [&](std::uint32_t a, float v) {
      put32(a, std::bit_cast<std::uint32_t>(v));
    };
    const std::uint32_t player = 0x80100000U, control = 0x80101000U,
                        props = 0x80102000U, game = 0x80103000U;
    put32(player + 0x68U, control);
    put32(player + 0x4CU, props);
    put32(0x800FD7D4U, game);
    m.put16(game + 0x15EU, 6U);
    m.put16(props + 6U, 42U);
    NavigationMod mod;
    const auto unchanged = bytes;
    check(!mod.full_health(m, player) && bytes == unchanged);
    mod.enabled = true;
    check(mod.full_health(m, player));
    check(m.u16(props + 6U) == 8704U && m.u16(game + 0x15CU) == 8704U &&
          m.u16(control + 0x5C8U) == 60U);
    check(health_capacity(0) == 1024U && health_capacity(-1) == 0U &&
          health_capacity(25) == 0U);
    put8(control + 1U, 2U);
    m.put16(game + 0x15CU + 2U * 0x76U + 2U, 8U);
    check(mod.full_health(m, player) && m.u16(props + 6U) == 11264U);
    const std::uint32_t enemy = 0x80104000U, ec = 0x80104100U, ep = 0x80104200U,
                        squad = 0x80104300U, sd = 0x80104400U;
    m.put16(enemy + 0x48U, 24U);
    put32(enemy + 0x68U, ec);
    put32(enemy + 0x4CU, ep);
    put32(ec + 0x24U, squad);
    m.put16(squad + 0x48U, 23U);
    put32(squad + 0x68U, sd);
    m.put16(sd + 0x2CU, 0x67U);
    m.put16(ep + 6U, 200U);
    check(mod.clear_enemy(m, enemy) && m.u16(ep + 6U) == 0U &&
          mod.cleared == 1U);
    check(!mod.clear_enemy(m, enemy) && mod.cleared == 1U);
    for (auto type : {0x11C, 0x11D, 0x11E, 0x11F, 0x120, 0x66, 0x70, 0x90, 0x97,
                      0x157, 0xA5}) {
      m.put16(sd + 0x2CU, static_cast<std::uint16_t>(type));
      m.put16(ep + 6U, 200U);
      check(!mod.clear_enemy(m, enemy) && m.u16(ep + 6U) == 200U);
    }
    put32(ec + 0x24U, 0xFFFFFFFFU);
    check(!mod.clear_enemy(m, enemy));
    check(!mod.clear_enemy(m, player));
    put32(ec + 0x24U, squad);
    m.put16(sd + 0x2CU, 0x67U);
    m.put16(ep + 6U, 200U);
    put8(0x800A4FC4U, 1U);
    check(!mod.clear_enemy(m, enemy) && !mod.full_health(m, player) &&
          m.u16(ep + 6U) == 200U);
    put8(0x800A4FC4U, 0U);
    mod.transition();
    check(!mod.clear_enemy(m, enemy) && m.u16(ep + 6U) == 200U);
    check(mod.full_health(m, player));
    for (const auto gate :
         {0x800FD7C4U, 0x801045B8U, 0x800F6DBCU, control + 0x5C0U}) {
      put32(gate, 1U);
      check(!mod.clear_enemy(m, enemy) && !mod.full_health(m, player) &&
            m.u16(ep + 6U) == 200U);
      put32(gate, 0U);
    }
    m.put16(enemy + 0x48U, 12U);
    check(!mod.clear_enemy(m, enemy) && m.u16(ep + 6U) == 200U);
    m.put16(enemy + 0x48U, 24U);
    check(mod.clear_enemy(m, enemy) && mod.cleared == 2U);
    mod.enabled = false;
    m.put16(ep + 6U, 200U);
    check(!mod.clear_enemy(m, enemy) && m.u16(ep + 6U) == 200U);
    mod.enabled = true;
    const std::uint32_t chest = 0x80109000U, chest_control = chest + 0x100U;
    put32(chest + 0x68U, chest_control);
    std::vector<Actor> chest_list{{chest, 98U, {10, 20, 30}}};
    auto items = item_markers(m, chest_list);
    check(items.size() == 1U && items[0].label == "Chest: Shotgun" && !items[0].opened);
    put8(chest_control + 4U, 5U);
    items = item_markers(m, chest_list);
    check(items[0].opened && items[0].kind == "opened");
    put8(chest_control + 5U, 255U);
    items = item_markers(m, chest_list);
    check(items[0].label.find("unidentified") != std::string::npos);
    put32(chest + 0x68U, 0xFFFFFFFFU);
    check(item_markers(m, chest_list).empty());
    const std::uint32_t key_header = chest + 0x200U;
    put32(chest + 0x40U, key_header);
    m.put16(chest + 0x4AU, 0x258U);
    put8(key_header + 4U, 'K'); put8(key_header + 5U, 'e'); put8(key_header + 6U, 'y');
    chest_list[0].behavior = 100U;
    check(item_markers(m, chest_list).size() == 1U && item_markers(m, chest_list)[0].kind == "key");
    m.put16(chest + 0x4AU, 0x500U);
    check(item_markers(m, chest_list).empty());
    const std::uint32_t track = 0x80110000U, block = track + 0x100U,
                        verts = track + 0x200U, faces = track + 0x300U,
                        batches = track + 0x400U, indices = track + 0x500U,
                        planes = track + 0x600U;
    put32(track + 4U, block);
    m.put16(track + 0x1AU, 1U);
    put32(block, verts);
    put32(block + 4U, faces);
    put32(block + 0xCU, batches);
    put32(block + 0x18U, indices);
    put32(block + 0x1CU, planes);
    m.put16(block + 0x24U, 3U);
    m.put16(block + 0x26U, 1U);
    m.put16(block + 0x28U, 1U);
    m.put16(verts + 10U, 100U);
    m.put16(verts + 24U, 100U);
    put8(faces + 1U, 0U);
    put8(faces + 2U, 1U);
    put8(faces + 3U, 2U);
    m.put16(batches + 24U, 1U);
    putfloat(planes + 4U, 1.0F);
    const auto mesh = decode_mesh(m, track);
    check(mesh.vertices.size() == 3U && mesh.triangles.size() == 1U);
    check(mesh.triangles[0].vertices[2] == 2U &&
          mesh.triangles[0].normal.y == 1.0F);
    put8(faces + 3U, 3U);
    bool rejected = false;
    try {
      (void)decode_mesh(m, track);
    } catch (const std::runtime_error &) {
      rejected = true;
    }
    check(rejected);
    put8(faces + 3U, 2U);
    put32(block + 0x1CU, 0xFFFFFFF0U);
    m.put16(indices, 1U);
    rejected = false;
    try {
      (void)decode_mesh(m, track);
    } catch (const std::runtime_error &) {
      rejected = true;
    }
    check(rejected);
    check(!m.valid(0U, 4U) && !m.valid(0x803FFFFFU, 2U) &&
          !m.valid(0xFFFFFFFFU, 4U));
    const std::uint32_t exit = 0x80120000U, xc = exit + 0x100U,
                        xd = exit + 0x200U;
    put32(exit + 0x68U, xc);
    put32(exit + 0x3CU, xd);
    put8(xd + 0xAU, 0x34U);
    put8(xd + 0xBU, 0x12U);
    put32(xc + 0x10U, 30U);
    m.put16(xc + 0x14U, 0xFFFFU);
    const auto doors = exits(m, {{exit, 8U, {1, 2, 3}}});
    check(doors.size() == 1U && doors[0].destination == 0x1234U &&
          doors[0].radius == 30U && doors[0].condition == -1);
    put32(0x800F2CA8U, 1025U);
    rejected = false;
    try {
      (void)actors(m);
    } catch (const std::runtime_error &) {
      rejected = true;
    }
    check(rejected);
  }
  std::cout << "navigation mod tests passed\n";
}
