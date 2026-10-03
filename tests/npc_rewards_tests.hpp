#pragma once
// Synthetic control records: no ROM data or dialogue text in this fixture.
struct NpcFixture {
  std::vector<std::uint8_t> selectors, index, data;
  static void w16(std::vector<std::uint8_t> &b, int v) {
    b.push_back(static_cast<std::uint8_t>(unsigned(v) >> 8));
    b.push_back(static_cast<std::uint8_t>(v));
  }
  static void w32(std::vector<std::uint8_t> &b, unsigned v) {
    w16(b, int(v >> 16));
    w16(b, int(v));
  }
  NpcFixture() {
    for (int g = 0; g < 45; ++g) {
      auto row = [&](int c, int flags, int auxiliary) {
        selectors.insert(selectors.end(), {static_cast<std::uint8_t>(c), 0, 0,
                                           static_cast<std::uint8_t>(flags)});
        w16(selectors, 0);
        w16(selectors, auxiliary);
      };
      if (g == 4 || g == 10) {
        w16(selectors, 2);
        row(130, 1, 0);
        row(2, 0, 0);
      } else if (g == 7) {
        w16(selectors, 2);
        row(131, 1, 1);
        row(3, 0, 0);
      } else if (g == 13) {
        w16(selectors, 1);
        row(0, 1, 3);
      } else if (g == 18) {
        w16(selectors, 2);
        row(14, 1, 4);
        row(0, 0, 0);
      } else {
        w16(selectors, 1);
        row(0, 0, 0);
      }
    }
    for (int i = 0; i < 107; ++i) {
      w32(index, unsigned(data.size()));
      auto choice = [&](int visible, int req, int action) {
        w32(data, 0);
        w16(data, visible);
        w16(data, req);
        w16(data, action);
        w16(data, 0);
        w16(data, 0);
        w16(data, 0);
      };
      w16(data, i == 3 ? 2 : 1);
      w16(data, 0);
      if (i == 0)
        choice(0, -1, 0);
      else if (i == 1)
        choice(-1, 3, 0x2002);
      else if (i == 2)
        choice(4, -1, 5);
      else if (i == 3) {
        choice(-1, 4, 6);
        choice(-1, 5, 7);
      } else if (i == 4)
        choice(20, -1, 18);
      else
        choice(-1, -1, 0x4000);
    }
    w32(index, unsigned(data.size()));
  }
  jfg::mod::NpcRewardCatalog catalog() const {
    jfg::mod::NpcRewardCatalog c;
    check(c.load_assets(selectors, index, data));
    return c;
  }
};
static void npc_reward_tests() {
  using namespace jfg::mod;
  NpcFixture fixture;
  auto c = fixture.catalog();
  check(c.ready() && c.group_count() == 45 && c.choice_count() == 5);
  NpcFacts f;
  f.known = true;
  f.character = 1;
  auto red = c.offers(
      10, f); // Same reward in another dialogue, no room/object hardcode.
  check(red.size() == 1 && red[0].item == 1 && red[0].status == "available");
  f.items[0][0] = 0x40;
  check(c.offers(10, f)[0].status == "available");
  f.items[1][0] = 0x40;
  check(c.offers(10, f)[0].status == "owned");
  auto trade = c.offers(7, f);
  check(trade.size() == 1 && trade[0].status == "blocked" &&
        trade[0].consumed_items == std::vector<int>{20});
  f.items[0][2] = 8;
  check(c.offers(7, f)[0].status ==
        "blocked"); // Payment must be held by active character.
  f.items[1][2] = 8;
  check(c.offers(7, f)[0].status == "available");
  f.items[2][2] = 4;
  check(c.offers(7, f)[0].status ==
        "owned"); // Reward ownership is shared across characters.
  f.currency = 7;
  auto services = c.offers(13, f);
  check(services.size() == 2 && services[0].status == "available" &&
        services[1].status == "blocked");
  f.currency = 10;
  check(c.offers(13, f)[1].status == "available");
  check(c.offers(18, f)[0].status == "blocked");
  f.flags[88 >> 3] |= 1U << (88 & 7);
  check(c.offers(18, f)[0].status == "available");
  f.flags[43 >> 3] |= 1U << (43 & 7);
  check(c.offers(18, f)[0].status == "owned");
  check(c.offers(0, f).empty() && c.offers(45, f).empty());
  f.known = false;
  check(c.offers(10, f)[0].status == "unknown");
  for (int action = 0; action <= 18; ++action)
    check(reward_action(action, f).kind != "unknown");
  check(choice_visible(14, f) == Fact::unknown &&
        choice_requirement(99, f) == Fact::unknown);
  check(root_predicate(200, f) == Fact::unknown);
  auto bad = fixture.data;
  bad[12] = 0x20;
  bad[13] = 0; // Self-recursive choice zero.
  check(!c.load_assets(fixture.selectors, fixture.index, bad) && !c.ready());
  check(!c.load_assets(std::span(fixture.selectors).first(10), fixture.index,
                       fixture.data));
  auto index = fixture.index;
  index[4] = 255;
  check(!c.load_assets(fixture.selectors, index, fixture.data));
  check(!c.load_rom({}) && !c.ready());
}
