// The whole rewrite linked natively: the runtime registers every RW_FUNCTION at startup.
// game.exe: prints how many rewrites registered and checks a few known game functions are present.
#include <cstdio>
#include <cstdint>

extern "C" int khux_runtime_init();
extern "C" int khux_has_rewrite(uint32_t addr);

int main() {
    int n = khux_runtime_init();
    struct { uint32_t addr; const char *name; } known[] = {
        {0x638474, "SceneSplash::create"}, {0x680DA0, "SceneSplash::init"}, {0x637EC0, "SceneTitle::create"},
        {0x45BE94, "SceneUtil::setBlackOutline"}, {0x4DB270, "ChatManager::getUser"}, {0x4FCB30, "MiniMedalScrollView::changeRow"}};
    int ok = 0;
    for (auto &k : known) {
        int has = khux_has_rewrite(k.addr);
        std::printf("  %-32s %s\n", k.name, has ? "registered" : "MISSING");
        ok += has;
    }
    std::printf("%d rewrites registered; %d / %d known functions present\n", n, ok, int(sizeof known / sizeof *known));
    return ok == int(sizeof known / sizeof *known) ? 0 : 1;
}
