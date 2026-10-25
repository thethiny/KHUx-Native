// Imports implemented by hand (KHUx-Native): the ones whose native counterpart has a different ABI or layout
// (ARM EABI helpers, bionic's pthread / time structs, variadic logging). Registered by name over every stub of that
// import (khux_for_each_import). Arguments arrive as the ARM words; guest pointers are native pointers.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cerrno>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <mutex>
#include <string>
#include <unordered_map>
#include "rw/rw.hpp"
#include "adapt.hpp"

using khux::Adapter;

namespace {
template <class T> T *P(uint32_t a) { return reinterpret_cast<T *>(uintptr_t(a)); }
std::unordered_map<std::string, Adapter> &hand() { static std::unordered_map<std::string, Adapter> m; return m; }
struct Add { Add(const char *n, Adapter f) { hand()[n] = f; } };
#define IMPORT(name) static uint64_t imp_##name(const uint32_t *a, int n); static Add add_##name(#name, imp_##name); \
    static uint64_t imp_##name(const uint32_t *a, int n)

// ---- printf-style formatting of ARM variadic words (softfp: doubles in 8-aligned word pairs)
std::string format(const char *fmt, const uint32_t *a, int k, int n) {
    std::string out;
    char spec[32], buf[512];
    for (const char *p = fmt; *p; p++) {
        if (*p != '%') { out += *p; continue; }
        if (p[1] == '%') { out += '%'; p++; continue; }
        const char *q = p + 1;
        while (*q && std::strchr("-+ #0123456789.*", *q)) q++;
        bool ll = false;
        while (*q && std::strchr("hlLzjt", *q)) { if (q[0] == 'l' && q[1] == 'l') ll = true; q++; }
        if (!*q) break;
        size_t len = size_t(q - p + 1) < sizeof spec ? size_t(q - p + 1) : sizeof spec - 1;
        std::memcpy(spec, p, len);
        spec[len] = 0;
        char c = *q;
        auto next = [&]() -> uint32_t { return k < n ? a[k++] : 0; };
        if (std::strchr("eEfFgGaA", c)) {
            k = (k + 1) & ~1;
            uint64_t bits = uint64_t(next()) | (uint64_t(next()) << 32);
            double d; std::memcpy(&d, &bits, 8);
            std::snprintf(buf, sizeof buf, spec, d);
        } else if (c == 's') {
            uint32_t s = next();
            std::snprintf(buf, sizeof buf, spec, s ? P<const char>(s) : "(null)");
        } else if (c == 'p') {
            std::snprintf(buf, sizeof buf, "0x%08X", next());
        } else if (ll) {
            k = (k + 1) & ~1;
            uint64_t v = uint64_t(next()) | (uint64_t(next()) << 32);
            std::string s2(spec);
            s2.replace(s2.size() - 1, 1, std::string("ll") + c);
            for (size_t i; (i = s2.find("llll")) != std::string::npos;) s2.erase(i, 2);
            std::snprintf(buf, sizeof buf, s2.c_str(), (long long)v);
        } else {
            std::string s2(spec);
            for (char m : std::string("hlzjtL")) s2.erase(std::remove(s2.begin(), s2.end(), m), s2.end());
            std::snprintf(buf, sizeof buf, s2.c_str(), next());
        }
        out += buf;
        p = q;
    }
    return out;
}
}  // namespace

// ---- ARM EABI helpers (argument order differs from libc)
IMPORT(__aeabi_memcpy) { std::memcpy(P<void>(a[0]), P<void>(a[1]), a[2]); return a[0]; }
IMPORT(__aeabi_memcpy4) { std::memcpy(P<void>(a[0]), P<void>(a[1]), a[2]); return a[0]; }
IMPORT(__aeabi_memcpy8) { std::memcpy(P<void>(a[0]), P<void>(a[1]), a[2]); return a[0]; }
IMPORT(__aeabi_memmove) { std::memmove(P<void>(a[0]), P<void>(a[1]), a[2]); return a[0]; }
IMPORT(__aeabi_memmove4) { std::memmove(P<void>(a[0]), P<void>(a[1]), a[2]); return a[0]; }
IMPORT(__aeabi_memmove8) { std::memmove(P<void>(a[0]), P<void>(a[1]), a[2]); return a[0]; }
IMPORT(__aeabi_memset) { std::memset(P<void>(a[0]), int(a[2]), a[1]); return a[0]; }      // (dest, n, c)
IMPORT(__aeabi_memset4) { std::memset(P<void>(a[0]), int(a[2]), a[1]); return a[0]; }
IMPORT(__aeabi_memset8) { std::memset(P<void>(a[0]), int(a[2]), a[1]); return a[0]; }
IMPORT(__aeabi_memclr) { std::memset(P<void>(a[0]), 0, a[1]); return a[0]; }
IMPORT(__aeabi_memclr4) { std::memset(P<void>(a[0]), 0, a[1]); return a[0]; }
IMPORT(__aeabi_memclr8) { std::memset(P<void>(a[0]), 0, a[1]); return a[0]; }

// ---- C++ runtime / bionic basics
// destructors at exit: not run (the process ends)
IMPORT(__cxa_atexit) { return 0; }
IMPORT(__aeabi_atexit) { return 0; }
IMPORT(__cxa_finalize) { return 0; }
IMPORT(__stack_chk_fail) { std::fprintf(stderr, "game: stack check failed\n"); std::abort(); }
IMPORT(__errno) { return uintptr_t(&errno); }
IMPORT(__assert2) {
    std::fprintf(stderr, "game: assertion failed: %s (%s:%u, %s)\n", P<const char>(a[3]), P<const char>(a[0]), a[1], P<const char>(a[2]));
    std::abort();
}
IMPORT(abort) { std::fprintf(stderr, "game: abort()\n"); std::fflush(stderr); std::abort(); }
IMPORT(__android_log_print) {
    std::string s = format(P<const char>(a[2]), a, 3, n);
    std::printf("[%s] %s\n", a[1] ? P<const char>(a[1]) : "", s.c_str());
    return 0;
}
IMPORT(__android_log_write) { std::printf("[%s] %s\n", a[1] ? P<const char>(a[1]) : "", P<const char>(a[2])); return 0; }

// ---- time (bionic, 32-bit: time_t, timeval and timespec are 32-bit fields)
IMPORT(time) {
    uint32_t t = uint32_t(std::time(nullptr));
    if (a[0]) *P<uint32_t>(a[0]) = t;
    return t;
}
IMPORT(gettimeofday) {
    FILETIME ft;
    GetSystemTimePreciseAsFileTime(&ft);
    uint64_t us = ((uint64_t(ft.dwHighDateTime) << 32 | ft.dwLowDateTime) - 116444736000000000ULL) / 10;
    if (a[0]) { P<uint32_t>(a[0])[0] = uint32_t(us / 1000000); P<uint32_t>(a[0])[1] = uint32_t(us % 1000000); }
    return 0;
}
IMPORT(clock_gettime) {                                   // (clockid, timespec*): realtime 0, monotonic 1
    uint64_t ns;
    if (a[0] == 0) {
        FILETIME ft;
        GetSystemTimePreciseAsFileTime(&ft);
        ns = ((uint64_t(ft.dwHighDateTime) << 32 | ft.dwLowDateTime) - 116444736000000000ULL) * 100;
    } else {
        LARGE_INTEGER f, c;
        QueryPerformanceFrequency(&f);
        QueryPerformanceCounter(&c);
        ns = uint64_t(c.QuadPart / f.QuadPart) * 1000000000ULL + uint64_t(c.QuadPart % f.QuadPart) * 1000000000ULL / uint64_t(f.QuadPart);
    }
    P<uint32_t>(a[1])[0] = uint32_t(ns / 1000000000ULL);
    P<uint32_t>(a[1])[1] = uint32_t(ns % 1000000000ULL);
    return 0;
}

// ---- pthreads over Windows objects. A guest pthread object is a word in guest memory (bionic: mutex, cond, once,
// key are 4 bytes); each is mapped to a native object on first use (a static initializer of 0 is a fresh object).
namespace {
std::mutex g_map_lock;
std::unordered_map<uint32_t, CRITICAL_SECTION *> g_mutex;
std::unordered_map<uint32_t, CONDITION_VARIABLE *> g_cond;
CRITICAL_SECTION *mutex_of(uint32_t m) {
    std::lock_guard<std::mutex> g(g_map_lock);
    auto &cs = g_mutex[m];
    if (!cs) { cs = new CRITICAL_SECTION; InitializeCriticalSection(cs); }
    return cs;
}
CONDITION_VARIABLE *cond_of(uint32_t c) {
    std::lock_guard<std::mutex> g(g_map_lock);
    auto &cv = g_cond[c];
    if (!cv) { cv = new CONDITION_VARIABLE; InitializeConditionVariable(cv); }
    return cv;
}

struct ThreadStart { uint32_t fn, arg; };
DWORD WINAPI thread_main(void *p) {
    ThreadStart st = *static_cast<ThreadStart *>(p);
    delete static_cast<ThreadStart *>(p);
    static thread_local CPU cpu;
    const uint32_t stack_size = 1u << 20;
    uint8_t *stack = static_cast<uint8_t *>(VirtualAlloc(nullptr, stack_size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    std::memset(&cpu, 0, sizeof cpu);
    cpu.r[13] = uint32_t(uintptr_t(stack + stack_size));
    rw::cpu = &cpu;                                         // this thread's guest registers
    return DWORD(rw::call(st.fn, {st.arg}));
}
}  // namespace

IMPORT(pthread_mutex_init) { mutex_of(a[0]); return 0; }
IMPORT(pthread_mutex_destroy) { return 0; }
IMPORT(pthread_mutex_lock) { EnterCriticalSection(mutex_of(a[0])); return 0; }
IMPORT(pthread_mutex_trylock) { return TryEnterCriticalSection(mutex_of(a[0])) ? 0 : EBUSY; }
IMPORT(pthread_mutex_unlock) { LeaveCriticalSection(mutex_of(a[0])); return 0; }
IMPORT(pthread_mutexattr_init) { *P<uint32_t>(a[0]) = 0; return 0; }
IMPORT(pthread_mutexattr_settype) { return 0; }
IMPORT(pthread_mutexattr_destroy) { return 0; }
IMPORT(pthread_cond_init) { cond_of(a[0]); return 0; }
IMPORT(pthread_cond_destroy) { return 0; }
IMPORT(pthread_cond_signal) { WakeConditionVariable(cond_of(a[0])); return 0; }
IMPORT(pthread_cond_broadcast) { WakeAllConditionVariable(cond_of(a[0])); return 0; }
IMPORT(pthread_cond_wait) { SleepConditionVariableCS(cond_of(a[0]), mutex_of(a[1]), INFINITE); return 0; }
IMPORT(pthread_cond_timedwait) {                          // (cond, mutex, abstime realtime)
    FILETIME ft;
    GetSystemTimePreciseAsFileTime(&ft);
    uint64_t now_ms = ((uint64_t(ft.dwHighDateTime) << 32 | ft.dwLowDateTime) - 116444736000000000ULL) / 10000;
    uint64_t at_ms = uint64_t(P<uint32_t>(a[2])[0]) * 1000 + P<uint32_t>(a[2])[1] / 1000000;
    DWORD wait = at_ms > now_ms ? DWORD(at_ms - now_ms) : 0;
    return SleepConditionVariableCS(cond_of(a[0]), mutex_of(a[1]), wait) ? 0 : ETIMEDOUT;
}
IMPORT(pthread_once) {                                    // (once_control*, init): bionic once_control is an int
    static std::mutex m;
    std::lock_guard<std::mutex> g(m);
    if (*P<uint32_t>(a[0]) == 0) { *P<uint32_t>(a[0]) = 1; rw::call(a[1], {}); }
    return 0;
}
IMPORT(pthread_key_create) {                              // (key*, destructor): destructors are not run
    *P<uint32_t>(a[0]) = TlsAlloc();
    return 0;
}
IMPORT(pthread_key_delete) { TlsFree(a[0]); return 0; }
IMPORT(pthread_getspecific) { return uintptr_t(TlsGetValue(a[0])); }
IMPORT(pthread_setspecific) { TlsSetValue(a[0], P<void>(a[1])); return 0; }
IMPORT(pthread_self) { return GetCurrentThreadId(); }
IMPORT(pthread_equal) { return a[0] == a[1]; }
IMPORT(pthread_create) {                                  // (thread*, attr, start, arg)
    DWORD id = 0;
    HANDLE h = CreateThread(nullptr, 0, thread_main, new ThreadStart{a[2], a[3]}, 0, &id);
    if (!h) return EAGAIN;
    CloseHandle(h);
    if (a[0]) *P<uint32_t>(a[0]) = id;
    return 0;
}
IMPORT(pthread_detach) { return 0; }
IMPORT(pthread_attr_init) { std::memset(P<void>(a[0]), 0, 24); return 0; }   // bionic pthread_attr_t: 24 bytes
IMPORT(pthread_attr_destroy) { return 0; }
IMPORT(pthread_attr_setdetachstate) { return 0; }
IMPORT(pthread_attr_setstacksize) { return 0; }
IMPORT(sched_yield) { SwitchToThread(); return 0; }

// Register the hand-written imports on every stub of their names.
extern "C" void khux_for_each_import(void (*f)(uint32_t stub, const char *name, void *ctx), void *ctx);
void khux_register_hand_imports(std::unordered_map<uint32_t, Adapter> &native) {
    khux_for_each_import([](uint32_t stub, const char *name, void *ctx) {
        auto it = hand().find(name);
        if (it != hand().end()) (*static_cast<std::unordered_map<uint32_t, Adapter> *>(ctx))[stub] = it->second;
    }, &native);
}
