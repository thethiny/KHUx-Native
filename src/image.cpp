// The game's image (libcocos2dcpp.so), natively (KHUx-Native): its data copied to its original addresses -
// the rewrite reads strings, tables and its own vtables there - its relocations applied (base 0: RELATIVE words are
// already right; symbol words get the symbol's address, imports their stub address), then its own static
// initializers (init_array, all rewritten) run through the runtime, as Android's loader would run them.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unordered_map>
#include <vector>

namespace rw { uint32_t call(uint32_t fn, std::initializer_list<uint32_t> args); }

namespace {
#pragma pack(push, 1)
struct Ehdr { uint8_t ident[16]; uint16_t type, machine; uint32_t version, entry, phoff, shoff, flags;
              uint16_t ehsize, phentsize, phnum, shentsize, shnum, shstrndx; };
struct Phdr { uint32_t type, offset, vaddr, paddr, filesz, memsz, flags, align; };
struct Sym { uint32_t name, value, size; uint8_t info, other; uint16_t shndx; };
#pragma pack(pop)

std::vector<uint8_t> g_file;
uint32_t g_lo, g_hi;
std::unordered_map<std::string, uint32_t> g_import_stub;   // import name -> its stub (PLT) address

uint32_t *word(uint32_t a) { return reinterpret_cast<uint32_t *>(uintptr_t(a)); }
}  // namespace

extern "C" void khux_image_set_import_stub(const char *name, uint32_t stub) { g_import_stub[name] = stub; }

// Copy the image to its addresses and apply its relocations. 0 = ok.
extern "C" int khux_image_load(const char *so_path) {
    FILE *f = std::fopen(so_path, "rb");
    if (!f) { std::fprintf(stderr, "image: cannot open %s\n", so_path); return 1; }
    std::fseek(f, 0, SEEK_END);
    g_file.resize(size_t(std::ftell(f)));
    std::fseek(f, 0, SEEK_SET);
    if (std::fread(g_file.data(), 1, g_file.size(), f) != g_file.size()) { std::fclose(f); return 1; }
    std::fclose(f);
    auto *eh = reinterpret_cast<const Ehdr *>(g_file.data());
    auto *ph = reinterpret_cast<const Phdr *>(g_file.data() + eh->phoff);
    // only the data is read by the rewrite (.rodata on: 0xDEC260 - 0x1010009); the ARM code's addresses are only
    // identifiers. The range belongs to the loader exe (src/loader.c: its own image covers it, so nothing else is
    // mapped there when the process starts).
    g_lo = 0xDE0000;
    g_hi = 0;
    const Phdr *dyn = nullptr;
    for (int i = 0; i < eh->phnum; i++) {
        if (ph[i].type == 1 && ph[i].vaddr + ph[i].memsz > g_hi) g_hi = ph[i].vaddr + ph[i].memsz;
        if (ph[i].type == 2) dyn = &ph[i];
    }
    g_hi = (g_hi + 0xFFFF) & ~0xFFFFu;
    for (uint32_t a = g_lo; a < g_hi; a += 0x1000) {
        MEMORY_BASIC_INFORMATION mi;
        if (!VirtualQuery(reinterpret_cast<void *>(uintptr_t(a)), &mi, sizeof mi) || mi.State != MEM_COMMIT ||
            !(mi.Protect & (PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READWRITE))) {
            std::fprintf(stderr, "image: 0x%08X is not writable memory of the loader (start the game with khux.exe)\n", a);
            return 2;
        }
    }
    for (int i = 0; i < eh->phnum; i++) {
        if (ph[i].type != 1) continue;
        uint32_t a = ph[i].vaddr, off = ph[i].offset, n = ph[i].filesz;
        if (a < g_lo) { uint32_t skip = g_lo - a; if (skip >= n) continue; a += skip; off += skip; n -= skip; }
        std::memcpy(reinterpret_cast<void *>(uintptr_t(a)), g_file.data() + off, n);   // the rest (bss) is zero
    }
    // relocations
    std::unordered_map<int32_t, uint32_t> tag;
    for (uint32_t k = 0; k < dyn->filesz; k += 8) {
        int32_t t; uint32_t v;
        std::memcpy(&t, g_file.data() + dyn->offset + k, 4);
        std::memcpy(&v, g_file.data() + dyn->offset + k + 4, 4);
        if (!tag.count(t)) tag[t] = v;
        if (t == 0) break;
    }
    // the tables live in the first segment (vaddr == file offset there): read them from the file
    auto *syms = reinterpret_cast<const Sym *>(g_file.data() + tag[6]);   // DT_SYMTAB
    auto *strs = reinterpret_cast<const char *>(g_file.data() + tag[5]);   // DT_STRTAB
    auto fword = [&](uint32_t a) { uint32_t v; std::memcpy(&v, g_file.data() + a, 4); return v; };
    int applied = 0, imports = 0, unresolved = 0;
    auto apply = [&](uint32_t rel, uint32_t size) {
        for (uint32_t k = 0; k < size; k += 8) {
            uint32_t o = fword(rel + k), info = fword(rel + k + 4), type = info & 0xFF, si = info >> 8;
            if (o < g_lo || o >= g_hi || type == 23) continue;         // R_ARM_RELATIVE: base 0, already right
            const Sym &s = syms[si];
            uint32_t v;
            if (s.shndx) v = s.value;                                     // defined in the image
            else {
                auto it = g_import_stub.find(strs + s.name);
                v = it != g_import_stub.end() ? it->second : 0;          // calls go to the stub: the runtime resolves it
                imports++;
                if (!v) unresolved++;
            }
            if (type == 2) *word(o) += v;                                // R_ARM_ABS32: addend in place
            else if (type == 21 || type == 22) *word(o) = v;             // GLOB_DAT, JUMP_SLOT
            applied++;
        }
    };
    apply(tag[17], tag[18]);                                             // DT_REL / DT_RELSZ
    apply(tag[23], tag[2]);                                              // DT_JMPREL / DT_PLTRELSZ
    std::printf("image: 0x%08X - 0x%08X mapped, %d relocations applied (%d imports, %d without a stub)\n",
                g_lo, g_hi, applied, imports, unresolved);
    return 0;
}

// Run the image's static initializers (DT_INIT_ARRAY), as the Android loader would. Returns how many ran.
extern "C" int khux_image_init(const uint32_t *init_array, int count) {
    for (int i = 0; i < count; i++) {
        if (std::getenv("KHUX_TRACE_INIT")) { std::printf("init 0x%08X\n", init_array[i]); std::fflush(stdout); }
        rw::call(init_array[i], {});
    }
    return count;
}
