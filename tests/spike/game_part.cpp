// Two real rewrite functions, their bodies copied verbatim from recomp/rewrite/src/scene/SceneUtilNodes.cpp, built
// natively against the rewrite's own headers. Guest addresses are real pointers here (rw_native.cpp: cpu->mem = 0).
#include "scene/SceneCommon.hpp"

using namespace scene;
using Addr = uint32_t;

namespace {
constexpr uint32_t Text_enableShadow = rwlib::cocos2d::ui::Text::enableShadow;                     // (text, const Color4B&, const Size&, blur)
constexpr uint32_t Text_enableOutline = rwlib::cocos2d::ui::Text::enableOutline;                    // (text, const Color4B&, size)
constexpr uint32_t Label_setAdditionalKerning = rwlib::cocos2d::Label::setAdditionalKerning;
constexpr uint32_t Text_getVirtualRenderer = 0x2D8;                  // Widget vtable slot -> Label*

// ---- verbatim from SceneUtilNodes.cpp ----
// drop shadow: black at 50 %, offset (2, -2), blur 6
void setShadow(Addr text) {
    Frame f;
    uint32_t color = f.alloc(4);
    st8(color, 0); st8(color + 1, 0); st8(color + 2, 0); st8(color + 3, 0x80);
    uint32_t offset = newVec2(f, 2.0f, -2.0f);
    call(Text_enableShadow, {text, color, offset, 6});
}

void setBlackOutline(Addr text) {
    Frame f;
    uint32_t color = f.alloc(4);
    st8(color, 0); st8(color + 1, 0); st8(color + 2, 0); st8(color + 3, 0xFF);
    call(Text_enableOutline, {text, color, 2});
    uint32_t label = vcall(text, Text_getVirtualRenderer, {text});
    call(Label_setAdditionalKerning, {label, fbits(-4.0f)});
}
// ---- end ----
}  // namespace

extern "C" void spike_setShadow(uint32_t text) { setShadow(text); }
extern "C" void spike_setBlackOutline(uint32_t text) { setBlackOutline(text); }

// the addresses this code calls, for rw_native.cpp's adapter table
extern "C" const uint32_t spike_addr_enableShadow = Text_enableShadow;
extern "C" const uint32_t spike_addr_enableOutline = Text_enableOutline;
extern "C" const uint32_t spike_addr_setAdditionalKerning = Label_setAdditionalKerning;
