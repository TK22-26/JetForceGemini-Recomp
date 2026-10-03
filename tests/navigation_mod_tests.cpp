#include "jfg/mod/navigation_mod.hpp"
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <source_location>
#include <sstream>

static void
check(bool ok,
      const std::source_location where = std::source_location::current()) {
  if (!ok) {
    std::cerr << "Navigation check failed at " << where.file_name() << ':'
              << where.line() << '\n';
    std::abort();
  }
}
#include "npc_rewards_tests.hpp"
#include "navigation_pilot_tests.hpp"
#include "navigation_collision_tests.hpp"
int main(int argc, char **argv) {
  navigation_collision_tests();
  npc_reward_tests();
  navigation_pilot_tests();
  const auto npc_catalog = NpcFixture().catalog();
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
    for (const auto &item : item_markers(m, list))
      std::cout << item.label << "\n";
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
    put8(0x800A329CU, 1U); put8(0x800FD7BDU, 1U);
    check(transition_confirmation(m));
    put8(0x800FD7BDU, 0U); check(!transition_confirmation(m));
    put8(0x800A329CU, 0U);
    mod.manual_inputs = 7;
    mod.transition();
    check(mod.manual_inputs == 7);
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
    check(items.size() == 1U && items[0].label == "Chest: Shotgun" &&
          !items[0].opened);
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
    put8(key_header + 4U, 'K');
    put8(key_header + 5U, 'e');
    put8(key_header + 6U, 'y');
    chest_list[0].behavior = 100U;
    check(item_markers(m, chest_list).size() == 1U &&
          item_markers(m, chest_list)[0].kind == "key");
    m.put16(chest + 0x4AU, 0x500U);
    check(item_markers(m, chest_list).empty());

    // NPC markers never mutate memory and never classify enemies as friendlies.
    const std::uint32_t guide = 0x80130000U, gc = guide + 0x100U,
                        gp = guide + 0x200U;
    put32(guide + 0x68U, gc);
    put32(guide + 0x4CU, gp);
    m.put16(guide + 0x4AU, 350U);
    m.put16(gp + 6U, 256U);
    std::vector<Actor> characters{{guide, 90U, {20, 30, 40}},
                                  {enemy, 24U, {100, 200, 300}}};
    m.put16(ep + 6U, 1024U);
    m.put16(sd + 0x2CU, 0x11CU);
    auto before_npcs = bytes;
    auto npcs = npc_markers(m, characters);
    check(npcs.size() == 2U && std::string(npcs[0].label) == "NPC: Guide" &&
          std::string(npcs[1].kind) == "tribal" &&
          npcs[1].squad_type == 0x11C && npcs[1].position.x == 100.0F &&
          bytes == before_npcs);
    for (auto type : {0x11C, 0x11D, 0x11E, 0x11F, 0x120, 0x66, 0x70, 0x90, 0x97,
                      0x157, 0xA5}) {
      m.put16(sd + 0x2CU, static_cast<std::uint16_t>(type));
      check(npc_markers(m, characters).size() == 2U);
    }
    m.put16(sd + 0x2CU, 45U);
    check(npc_markers(m, characters).size() == 1U); // Ordinary hostile.
    m.put16(sd + 0x2CU, 0x11CU);
    m.put16(ep + 6U, 0U);
    check(npc_markers(m, characters).size() == 1U); // Dead Tribal.
    m.put16(ep + 6U, 1024U);
    put32(ec + 0x24U, 0xFFFFFFFFU);
    check(npc_markers(m, characters).size() == 1U);
    put32(ec + 0x24U, squad);
    characters[0].behavior = 51U;
    characters[1].behavior = 54U;
    check(npc_markers(m, characters).empty()); // Cutscene/scenery.
    characters[0].behavior = 90U;
    put32(guide + 0x68U, 0xFFFFFFFFU);
    check(npc_markers(m, characters).empty());
    put32(guide + 0x68U, gc);
    for (auto object :
         {350, 476, 486, 487, 488, 489, 490, 550, 551, 612, 772, 999}) {
      m.put16(guide + 0x4AU, static_cast<std::uint16_t>(object));
      check(npc_markers(m, characters).size() == 1U);
    }
    std::ostringstream npc_json;
    write_npcs(npc_json, npc_markers(m, characters));
    check(npc_json.str().find("\"kind\":\"npc\"") != std::string::npos);
    m.put16(gp + 6U, 0U);
    check(npc_markers(m, characters).empty());

    // The block named ForestCrate has no verified contents and is not an item.
    const char *block_name = "ForestCrate";
    for (unsigned n = 0; n < 16U; ++n)
      put8(key_header + 4U + n,
           n < 11U ? static_cast<std::uint8_t>(block_name[n]) : 0U);
    m.put16(chest + 0x4AU, 135U);
    chest_list[0].behavior = 54U;
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
    // Inventory and dialogue completion are separate, character-scoped facts.
    put8(control + 1U, 1U);
    const auto saved1 = game + 0x15CU + 0x76U;
    put8(saved1 + 0x66U, 0U);
    put8(game + 8U, 8U);
    m.put16(saved1 + 0xAU, 4U);
    m.put16(guide + 0x4AU, 350U);
    m.put16(gp + 6U, 256U);
    put8(gc + 0x31U, 4U);
    put8(gc + 0x32U, 4U);
    std::vector<Actor> progression_list{{player, 1U, {1, 2, 3}},
                                        {guide, 90U, {20, 30, 40}}};
    const auto before_progression = bytes;
    auto inv = inventory(m, player);
    check(inv.known && inv.character == 1U && !inv.red_key &&
          inv.magnus_spoken && inv.weapons == 4U);
    auto nodes =
        interactions(m, progression_list, 157U, inv, &npc_catalog, player);
    check(nodes.size() == 1U && nodes[0].reward_item == 1 &&
          nodes[0].status == "available" && nodes[0].spoken == 1);
    check(bytes == before_progression);
    put8(saved1 + 0x66U, 0x40U);
    nodes = interactions(m, progression_list, 157U, inventory(m, player),
                         &npc_catalog, player);
    check(nodes[0].status == "owned");
    put8(control + 1U, 0U);
    check(!inventory(m, player)
               .red_key); // Other character's inventory is untouched.
    put8(control + 1U, 3U);
    check(!inventory(m, player).known);
    put8(control + 1U, 1U);
    put32(0x800FD7D4U, 0xffffffffU);
    check(!inventory(m, player).known);
    nodes = interactions(m, progression_list, 157U, inventory(m, player),
                         &npc_catalog, player);
    check(nodes[0].status == "unknown" && nodes[0].spoken == -1);
    put32(0x800FD7D4U, game);
    put8(0x800A4FC4U, 1U);
    check(!inventory(m, player).known);
    put8(0x800A4FC4U, 0U);
    check(interactions(m, progression_list, 35U, inv, &npc_catalog, player)[0]
              .reward_item == 1);
    check(interactions(m, progression_list, 35U, inv)[0].status == "unknown");
    put8(gc + 0x32U, 5U);
    check(interactions(m, progression_list, 157U, inv, &npc_catalog, player)[0]
              .reward_item == 1);
    put8(gc + 0x32U, 4U);
    std::ostringstream progression_json;
    write_progression(progression_json, m, {{guide, 90U, {20, 30, 40}}}, player,
                      157U);
    check(progression_json.str().find("\"red_key\":null") !=
          std::string::npos); // Removed player cannot expose stale inventory.

    const std::uint32_t target = 0x80230000U, tc = target + 0x100U,
                        tp = target + 0x200U, door = target + 0x300U,
                        dc = target + 0x400U;
    put32(target + 0x68U, tc);
    put32(target + 0x4CU, tp);
    m.put16(target + 0x48U, 111U);
    put32(door + 0x68U, dc);
    m.put16(door + 0x48U, 7U);
    put8(tc + 8U, 2U);
    put8(dc + 0x44U, 2U);
    put8(dc + 0x43U, 3U);
    m.put16(dc + 0x3EU, 8U);
    m.put16(tp + 6U, 2048U);
    m.put16(tc + 6U, 3072U);
    m.put16(tc, 124U);
    std::vector<Actor> target_list{{target, 111U, {3260, 404, -2755}},
                                   {door, 7U, {3324, 310, -2897}}};
    nodes = interactions(m, target_list, 157U, inv);
    check(nodes.size() == 2U && nodes[0].linked_actor == door &&
          nodes[0].door_id == 2);
    check(nodes[0].required_weapon == -1 && nodes[0].reset_ticks == 124 &&
          nodes[0].target_health == 2048);
    check(nodes[0].status == "needs_shooting" &&
          nodes[1].status == "key_missing" && nodes[1].required_item == 1);
    put8(tc + 0xAU, 1U);
    inv.red_key = true;
    nodes = interactions(m, target_list, 157U, inv);
    check(nodes[0].status == "activated" && nodes[1].status == "key_owned");
    m.put16(dc + 0x3EU, 0U);
    check(interactions(m, target_list, 157U, inv)[1].status ==
          "key_lock_cleared");
    put8(dc + 0x44U, 3U);
    check(interactions(m, target_list, 157U, inv)[0].linked_actor == 0U);
    put32(door + 0x68U, 0xffffffffU);
    check(interactions(m, target_list, 157U, inv).size() == 1U);
    put32(chest + 0x68U, chest_control);
    m.put16(chest + 0x48U, 98U);
    put8(chest_control + 5U, 2U);
    put8(chest_control + 4U, 0U);
    nodes = interactions(m, {{chest, 98U, {10, 20, 30}}}, 237U, inv);
    check(nodes[0].reward_weapon == 2 && nodes[0].status == "unopened");
    put8(chest_control + 4U, 5U);
    check(interactions(m, {{chest, 98U, {10, 20, 30}}}, 237U, inv)[0].status ==
          "opened");

    put32(0x800F2CA8U, 1025U);
    rejected = false;
    try {
      (void)actors(m);
    } catch (const std::runtime_error &) {
      rejected = true;
    }
    check(rejected);
  }
  {
    NavigationConfirmation confirm;
    auto send = [&](const char *text, bool prompt=true, bool manual=false, bool replay=false) {
      std::istringstream command(text);return confirm.command(command,prompt,manual,replay,27,13,7,1000);
    };
    check(send("JFGCONFIRM1 27 13 1 1000 7"));
    check(!send("JFGCONFIRM1 27 13 1 1000 7"));
    check(!send("JFGCONFIRM1 27 13 2 1000 7",false));
    check(!send("JFGCONFIRM1 27 13 2 1000 7"));
    check(!send("JFGCONFIRM1 27 13 3 1000 7",true,true));
    check(!send("JFGCONFIRM1 27 13 4 1000 7",true,false,true));
    check(!send("JFGCONFIRM1 28 13 5 1000 7"));
    check(!send("JFGCONFIRM1 27 12 5 1000 7"));
    check(!send("JFGCONFIRM1 27 13 5 -1 7"));
    check(!send("JFGCONFIRM1 27 13 5 1001 7"));
    check(!send("JFGCONFIRM1 27 13 5 1000 6"));
    check(!send("JFGCONFIRM1 27 13 5 1000 7 extra"));
    check(confirm.count==1);
  }
  std::cout << "navigation mod tests passed\n";
}
