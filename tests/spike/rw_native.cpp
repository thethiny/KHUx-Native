// The rewrite runtime, native: guest address = host address (cpu->mem = 0), the guest stack is a native buffer,
// and rw::call resolves an address to a typed adapter that calls the real engine function.
//   game addresses (rwlib:: names)  -> adapters registered by address
//   native vtable entries (vcall)   -> adapters registered by the native function's address
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <unordered_map>
extern "C" {
#include "rt.h"
}
#include "cocos2d.h"
#include "ui/CocosGUI.h"
#include "adapt.hpp"

extern "C++" const khux::AdapterEntry khux_lib_adapters[];
extern "C++" const int khux_lib_adapter_count;
void khux_register_vtable_adapters(std::unordered_map<uint32_t, khux::Adapter> &map);
thread_local uint32_t khux_target;   // the address being called (the vtable adapters call it)

USING_NS_CC;

namespace rw {
thread_local CPU *cpu;
}
// rt.h's verifier state: declared for its inline store helpers, unused natively (logging is off)
extern "C" GTrack *rt_gtrack = nullptr;
extern "C" int rt_log_full_continue = 0;

namespace {
using khux::Adapter;
std::unordered_map<uint32_t, Adapter> g_adapters;
CPU g_cpu;
alignas(16) uint8_t g_stack[1 << 20];

float f32(uint32_t u) { float f; std::memcpy(&f, &u, 4); return f; }

uint64_t dispatch(uint32_t fn, std::initializer_list<uint32_t> args) {
    auto it = g_adapters.find(fn);
    if (it == g_adapters.end()) {
        std::fprintf(stderr, "rw_native: no adapter for 0x%08X\n", fn);
        std::abort();
    }
    khux_target = fn;
    return it->second(args.begin(), int(args.size()));
}
}  // namespace

namespace rw {
uint32_t call(uint32_t fn, std::initializer_list<uint32_t> args) { return uint32_t(dispatch(fn, args)); }
uint64_t call64(uint32_t fn, std::initializer_list<uint32_t> args) { return dispatch(fn, args); }
uint64_t call_exact(uint32_t fn, std::initializer_list<uint32_t> args) { return dispatch(fn, args); }
}  // namespace rw

// The game addresses of the engine functions the two test functions call (rw/lib.hpp's values).
extern "C" const uint32_t spike_addr_enableShadow, spike_addr_enableOutline, spike_addr_setAdditionalKerning;

// Itanium ABI: a pointer to a virtual member function holds 1 + its byte offset in the vtable.
template <class F> static uint32_t vtable_offset(F mf) { uint32_t w; std::memcpy(&w, &mf, 4); return w - 1; }

extern "C" int spike_init(void *any_text) {
    g_cpu.mem = nullptr;                                   // guest address == host address
    g_cpu.logging = 0;
    g_cpu.r[13] = uint32_t(reinterpret_cast<uintptr_t>(g_stack + sizeof(g_stack)));
    rw::cpu = &g_cpu;

    // the game -> engine calls: the generated table (tools/gen_adapters.py), one adapter per rwlib:: binding
    for (int i = 0; i < khux_lib_adapter_count; i++) g_adapters[khux_lib_adapters[i].addr] = khux_lib_adapters[i].fn;
    std::printf("adapters: %d generated game -> engine adapters registered\n", khux_lib_adapter_count);
    int found = int(g_adapters.count(spike_addr_enableOutline) + g_adapters.count(spike_addr_enableShadow) +
                    g_adapters.count(spike_addr_setAdditionalKerning));
    std::printf("check: the three engine functions the test code calls are in the generated table: %d / 3\n", found);
    // the game's vcall(text, 0x2D8): our engine's vtable must hold Text::getVirtualRenderer at that offset
    uint32_t off = vtable_offset(&ui::Text::getVirtualRenderer);
    uint32_t vt = *reinterpret_cast<uint32_t *>(any_text);
    uint32_t native_fn = *reinterpret_cast<uint32_t *>(vt + 0x2D8);
    khux_register_vtable_adapters(g_adapters);            // every engine vtable entry (tools/gen_vtable_adapters.py)
    std::printf("adapters: %d in all after the engine's vtable entries\n", int(g_adapters.size()));
    std::printf("check: the native vtable entry at 0x2D8 has a generated adapter: %s\n", g_adapters.count(native_fn) ? "yes" : "NO");
    std::printf("check: ui::Text::getVirtualRenderer is at vtable offset 0x%X in our engine (the game's: 0x2D8) - %s\n",
                off, off == 0x2D8 ? "same" : "DIFFERENT");
    return off == 0x2D8;
}

// CocosDenshion is not built (the game plays its audio through the SQEX engine); cocostudio still references it
#include "audio/include/SimpleAudioEngine.h"
namespace CocosDenshion {
SimpleAudioEngine *SimpleAudioEngine::getInstance() { return nullptr; }
void SimpleAudioEngine::end() {}
}  // namespace CocosDenshion
