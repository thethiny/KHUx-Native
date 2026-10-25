/* khux.exe - the loader (KHUx-Native). Its own image, linked at a fixed base, covers the address range where the
 * game's data lives (0xDE0000 - 0x1020000): Windows maps an exe before anything else, so nothing (stack, heaps,
 * system tables) can be placed there. Everything else is in khux_game.dll, loaded high; it copies the game's data
 * into this range (src/image.cpp). */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

#define GUEST_LO 0x00DE0000u
#define GUEST_HI 0x01020000u

/* zero-filled, writable: the bulk of this exe's image */
__attribute__((used)) static unsigned char guest_range[0x400000];

typedef int (*KhuxMain)(int argc, char **argv);

int main(int argc, char **argv) {
    unsigned lo = (unsigned)(UINT_PTR)guest_range, hi = lo + (unsigned)sizeof guest_range;
    if (lo > GUEST_LO || hi < GUEST_HI) {
        fprintf(stderr, "khux.exe: its reserved range 0x%08X - 0x%08X does not cover 0x%08X - 0x%08X (relink)\n",
                lo, hi, GUEST_LO, GUEST_HI);
        return 3;
    }
    HMODULE dll = LoadLibraryA("khux_game.dll");
    if (!dll) {
        fprintf(stderr, "khux.exe: cannot load khux_game.dll (error %lu)\n", GetLastError());
        return 4;
    }
    KhuxMain entry = (KhuxMain)(void *)GetProcAddress(dll, "khux_main");
    if (!entry) {
        fprintf(stderr, "khux.exe: khux_game.dll has no khux_main\n");
        return 5;
    }
    return entry(argc, argv);
}
