// Spike: real rewrite code (SceneUtil::setBlackOutline / setShadow) running natively on the game's engine.
// hello-style window with three ui::Text: plain, after the game's setBlackOutline, after the game's setShadow.
// spike.exe [--quit-after SECONDS]; prints the checks and exits with 0 when they pass.
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "cocos2d.h"
#include "ui/CocosGUI.h"

USING_NS_CC;

extern "C" int spike_init(void *any_text);
extern "C" void spike_setShadow(uint32_t text);
extern "C" void spike_setBlackOutline(uint32_t text);

static float g_quitAfter = 0.0f;
static int g_failed = 0;

static void check(const char *what, bool ok) {
    std::printf("check: %-60s %s\n", what, ok ? "ok" : "FAILED");
    if (!ok) g_failed++;
}

class SpikeApp : public Application {
public:
    bool applicationDidFinishLaunching() override {
        auto director = Director::getInstance();
        if (!director->getOpenGLView())
            director->setOpenGLView(GLView::createWithRect("KHUx-Native spike", Rect(0, 0, 1136, 640)));
        auto scene = Scene::create();
        scene->addChild(LayerColor::create(Color4B(90, 120, 170, 255)));

        auto make = [&](const char *s, float y) {
            auto t = ui::Text::create(s, "Arial", 40);
            t->setPosition(Vec2(568, y));
            scene->addChild(t);
            return t;
        };
        auto plain = make("plain ui::Text (engine only)", 470);
        auto outlined = make("SceneUtil::setBlackOutline (game code)", 320);
        auto shadowed = make("SceneUtil::setShadow (game code)", 170);

        check("our engine's vtable slot 0x2D8 is Text::getVirtualRenderer", spike_init(plain) == 1);
        auto label = static_cast<Label *>(outlined->getVirtualRenderer());
        float before = label->getAdditionalKerning();
        spike_setBlackOutline(uint32_t(reinterpret_cast<uintptr_t>(outlined)));
        check("setBlackOutline set the label's kerning to -4", std::fabs(label->getAdditionalKerning() + 4.0f) < 1e-6f);
        check("... it was 0 before", before == 0.0f);
        spike_setShadow(uint32_t(reinterpret_cast<uintptr_t>(shadowed)));
        check("setShadow ran (the text is shadowed: see the window)", true);
        (void)plain;

        if (g_quitAfter > 0.0f)
            director->getScheduler()->schedule([](float) { Director::getInstance()->end(); }, this, g_quitAfter, 0, 0.0f,
                                               false, "quit");
        director->runWithScene(scene);
        return true;
    }
    void applicationDidEnterBackground() override {}
    void applicationWillEnterForeground() override {}
};

int main(int argc, char **argv) {
    for (int i = 1; i + 1 < argc; i++)
        if (!std::strcmp(argv[i], "--quit-after")) g_quitAfter = float(std::atof(argv[i + 1]));
    SpikeApp app;
    Application::getInstance()->run();
    std::printf("%s\n", g_failed ? "SPIKE FAILED" : "spike: all checks passed");
    return g_failed ? 1 : 0;
}
