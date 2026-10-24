// The memory layouts the rewrite relies on, compared with the original ARM32 build (NDK r10e, libc++).
// Build: i686-w64-mingw32-clang++ -std=c++17 -stdlib=libc++ tests/layout_check.cpp -o out/layout_check.exe
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <functional>
#include <memory>
#include <string>
#include <vector>

static int failures = 0;
static void check(const char *what, long long got, long long want) {
    std::printf("%-58s %6lld  (ARM32: %lld)%s\n", what, got, want, got == want ? "" : "   <-- DIFFERENT");
    if (got != want) failures++;
}

enum Plain { PlainA, PlainB };
struct I64 { int32_t a; int64_t b; };           // 64-bit members are 8-aligned on ARM EABI
struct F64 { int32_t a; double b; };
struct Base {
    virtual ~Base() {}
    virtual int first() { return 1; }
    virtual int second() { return 2; }
};

int main() {
    check("sizeof(void*)", sizeof(void *), 4);
    check("sizeof(long)", sizeof(long), 4);
    check("sizeof(bool)", sizeof(bool), 1);
    // wchar_t is 2 bytes on Windows; only libc++ itself uses it (std::to_wstring), no game code: informational
    std::printf("%-58s %6d  (ARM32: 4, not used by game code)\n", "sizeof(wchar_t)", int(sizeof(wchar_t)));
    check("sizeof(enum)", sizeof(Plain), 4);
    check("offsetof(struct {int32; int64}, b)", offsetof(I64, b), 8);
    check("offsetof(struct {int32; double}, b)", offsetof(F64, b), 8);
    check("sizeof(struct {int32; int64})", sizeof(I64), 16);

    check("sizeof(std::string)", sizeof(std::string), 12);
    std::string s = "abc";
    unsigned char b0;
    std::memcpy(&b0, &s, 1);
    check("short std::string: first byte = length * 2", b0, 6);
    std::string l(40, 'x');
    uint32_t w[3];
    std::memcpy(w, &l, 12);
    check("long std::string: word 0 bit 0 (long flag)", w[0] & 1, 1);
    check("long std::string: word 1 = size", w[1], 40);
    check("long std::string: word 2 = data", w[2] == uint32_t(uintptr_t(l.data())), 1);

    check("sizeof(std::function<void()>) (20 used + 4 padding)", sizeof(std::function<void()>), 24);
    int x = 0;
    std::function<void()> f = [&x] { x++; };
    uint32_t fw[5];
    std::memcpy(fw, &f, sizeof(fw) <= sizeof(f) ? sizeof(fw) : sizeof(f));
    check("std::function: word 4 (__f_) points to its own buffer", fw[4] == uint32_t(uintptr_t(&f)), 1);
    check("sizeof(std::shared_ptr<int>)", sizeof(std::shared_ptr<int>), 8);
    check("sizeof(std::vector<int>)", sizeof(std::vector<int>), 12);

    // Itanium ABI: the virtual destructor takes two slots (complete, deleting), then the functions in order;
    // a pointer to a virtual member function is 1 + its byte offset in the vtable
    int (Base::*mf)() = &Base::second;
    uint32_t mfw[2];
    std::memcpy(mfw, &mf, sizeof(mfw));
    check("vtable byte offset of the 2nd virtual after the dtor", mfw[0] - 1, 12);

    std::printf("\n%s\n", failures ? "LAYOUT DIFFERS" : "all layouts match the ARM32 build");
    return failures;
}
