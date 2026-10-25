// The game's image natively: load libcocos2dcpp.so at its addresses, run its static initializers through the
// runtime, check a value they write. splash.exe [path to libcocos2dcpp.so]
#include <cstdint>
#include <cstdio>
#include <cstring>

extern "C" int khux_runtime_init();
extern "C" int khux_image_load(const char *so_path);
extern "C" int khux_image_init(const uint32_t *init_array, int count);
extern "C" const uint32_t *khux_game_init_array(int *count);
extern "C" int khux_sync_engine_data();

int main(int argc, char **argv) {
    const char *so = argc > 1 ? argv[1] : "../recomp/game/libcocos2dcpp.so";
    khux_runtime_init();
    if (khux_image_load(so)) return 1;
    std::printf("engine data: %d objects copied into the image (constants, statics, vtables)\n", khux_sync_engine_data());
    int n = 0;
    const uint32_t *init = khux_game_init_array(&n);
    std::printf("running the game's %d static initializers...\n", n);
    std::fflush(stdout);
    khux_image_init(init, n);
    const uint8_t *black = reinterpret_cast<const uint8_t *>(uintptr_t(0x1007EBC));     // cocos2d::Color4B::BLACK
    std::printf("check: Color4B::BLACK in the image = (%u, %u, %u, %u) - %s\n", black[0], black[1], black[2], black[3],
                black[0] == 0 && black[1] == 0 && black[2] == 0 && black[3] == 255 ? "ok" : "WRONG");
    return 0;
}
