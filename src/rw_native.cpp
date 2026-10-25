// The rewrite runtime, native (KHUx-Native): what recomp's host + rw_runtime.cpp provide to the rewritten code,
// without lift.dll or a verifier.
//
//   memory     guest address == host address (cpu->mem = 0, a 32-bit process); the guest stack is a native buffer
//   game code  RW_FUNCTION registrations (rw::add): called by address with the registers and stack set as on ARM
//              (the existing Adapter<&fn>::run reads them), exactly as recomp's host calls a rewrite
//   engine     game -> engine adapters (tools/gen_adapters.py) and engine vtable entries (gen_vtable_adapters.py)
//              by address; anything else is reported and stops the game
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <unordered_map>
#include <vector>
#include "rw/rw.hpp"
#include "adapt.hpp"

// rt.h's verifier state: declared for its inline store helpers, unused natively (logging is off)
extern "C" GTrack *rt_gtrack = nullptr;
extern "C" int rt_log_full_continue = 0;
thread_local uint32_t khux_target;   // the native function a vtable adapter calls (set by the dispatcher)

namespace rw {
thread_local CPU *cpu;
}

namespace khux_rt {
thread_local std::vector<int> t_stack;                     // the game functions this thread is inside (for reports)
std::vector<rw::Entry> &entries() { static std::vector<rw::Entry> e; return e; }
std::unordered_map<uint32_t, int> &game() { static std::unordered_map<uint32_t, int> m; return m; }       // addr & ~1
std::unordered_map<uint32_t, khux::Adapter> &native() { static std::unordered_map<uint32_t, khux::Adapter> m; return m; }
std::unordered_map<uint32_t, uint32_t> &alias() { static std::unordered_map<uint32_t, uint32_t> m; return m; }       // stub -> target

[[noreturn]] void missing(uint32_t fn) {
    std::fprintf(stderr, "rw_native: call to 0x%08X - no rewrite and no adapter for it\n", fn);
    std::fflush(stderr);
    std::abort();
}

// a registered rewrite, called as on ARM: r0-r3, the rest on the stack (8-aligned unless exact), result in r0:r1
uint64_t call_game(int index, std::initializer_list<uint32_t> args, bool exact) {
    CPU *c = rw::cpu;
    uint32_t saved[16];
    std::memcpy(saved, c->r, sizeof saved);
    uint32_t sp = c->r[13];
    int n = int(args.size());
    const uint32_t *a = args.begin();
    if (!exact) {
        if (n > 4) sp -= 4u * uint32_t(n - 4);
        sp &= ~7u;
    }
    for (int k = 4; k < n; k++) *reinterpret_cast<uint32_t *>(uintptr_t(sp + 4u * uint32_t(k - 4))) = a[k];
    c->r[13] = sp;
    for (int k = 0; k < n && k < 4; k++) c->r[k] = a[k];
    t_stack.push_back(index);
    entries()[size_t(index)].run(c);
    t_stack.pop_back();
    uint64_t r = c->r[0] | (uint64_t(c->r[1]) << 32);
    std::memcpy(c->r, saved, sizeof saved);
    return r;
}

uint64_t dispatch(uint32_t fn, std::initializer_list<uint32_t> args, bool exact) {
    auto al = alias().find(fn);                            // an import stub of a function inside the image
    if (al != alias().end()) fn = al->second;
    auto &nat = native();
    auto it = nat.find(fn);
    if (it != nat.end()) {
        khux_target = fn;
        return it->second(args.begin(), int(args.size()));
    }
    auto g = game().find(fn & ~1u);
    if (g != game().end()) return call_game(g->second, args, exact);
    missing(fn);
}
}  // namespace khux_rt

namespace rw {
int add(const Entry &e) {
    int index = int(khux_rt::entries().size());
    khux_rt::entries().push_back(e);
    khux_rt::game().emplace(e.addr & ~1u, index);
    return index;
}
void enter(CPU *c, int index) { khux_rt::entries()[size_t(index)].run(c); }
uint32_t call(uint32_t fn, std::initializer_list<uint32_t> args) { return uint32_t(khux_rt::dispatch(fn, args, false)); }
uint64_t call64(uint32_t fn, std::initializer_list<uint32_t> args) { return khux_rt::dispatch(fn, args, false); }
uint64_t call_exact(uint32_t fn, std::initializer_list<uint32_t> args) { return khux_rt::dispatch(fn, args, true); }
}  // namespace rw

// ---------------------------------------------------------------- startup
extern const khux::AdapterEntry khux_lib_adapters[];
extern const int khux_lib_adapter_count;
void khux_register_vtable_adapters(std::unordered_map<uint32_t, khux::Adapter> &map);
void khux_register_imports(std::unordered_map<uint32_t, khux::Adapter> &native, std::unordered_map<uint32_t, uint32_t> &alias);
void khux_register_hand_imports(std::unordered_map<uint32_t, khux::Adapter> &native);

namespace {
CPU g_main_cpu;
alignas(16) uint8_t g_main_stack[4 << 20];
}

// Set up the main thread's guest state and the adapter tables. Returns the number of registered rewrites.
extern "C" int khux_runtime_init() {
    g_main_cpu.mem = nullptr;                              // guest address == host address
    g_main_cpu.logging = 0;
    g_main_cpu.r[13] = uint32_t(reinterpret_cast<uintptr_t>(g_main_stack + sizeof g_main_stack));
    rw::cpu = &g_main_cpu;
    auto &nat = khux_rt::native();
    for (int i = 0; i < khux_lib_adapter_count; i++) nat[khux_lib_adapters[i].addr] = khux_lib_adapters[i].fn;
    khux_register_vtable_adapters(nat);
    khux_register_imports(nat, khux_rt::alias());
    khux_register_hand_imports(nat);
    std::printf("runtime: %d rewritten functions, %d native adapters\n", int(khux_rt::entries().size()), int(nat.size()));
    return int(khux_rt::entries().size());
}

// Is there a rewrite at this game address? (for tests)
extern "C" int khux_has_rewrite(uint32_t addr) { return khux_rt::game().count(addr & ~1u) ? 1 : 0; }
