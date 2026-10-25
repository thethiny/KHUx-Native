// The first native window: cocos2d-x 3.2 with Square Enix's changes (the game's engine), a scene, a label and a
// color-effect sprite. tools/build_hello.py builds it. hello.exe [--quit-after SECONDS]
#include <cstdlib>
#include <cstring>
#include "cocos2d.h"

USING_NS_CC;

static float g_quitAfter = 0.0f;

class HelloApp : public Application {
public:
    bool applicationDidFinishLaunching() override {
        auto director = Director::getInstance();
        if (!director->getOpenGLView())
            director->setOpenGLView(GLView::createWithRect("KHUx-Native", Rect(0, 0, 1136, 640)));
        director->setDisplayStats(true);
        director->setAnimationInterval(1.0f / 60.0f);

        auto scene = Scene::create();
        scene->addChild(LayerColor::create(Color4B(24, 28, 52, 255)));
        auto title = Label::createWithSystemFont("KHUx-Native", "Arial", 64);
        title->setPosition(Vec2(568, 400));
        scene->addChild(title);
        auto sub = Label::createWithSystemFont("cocos2d-x 3.2 with Square Enix's changes, built natively for Windows", "Arial", 24);
        sub->setPosition(Vec2(568, 320));
        scene->addChild(sub);

        if (g_quitAfter > 0.0f)
            director->getScheduler()->schedule([](float) { Director::getInstance()->end(); }, this, g_quitAfter, 0, 0.0f,
                                               false, "quit");
        director->runWithScene(scene);
        return true;
    }
    void applicationDidEnterBackground() override { Director::getInstance()->stopAnimation(); }
    void applicationWillEnterForeground() override { Director::getInstance()->startAnimation(); }
};

int main(int argc, char **argv) {
    for (int i = 1; i + 1 < argc; i++)
        if (!std::strcmp(argv[i], "--quit-after")) g_quitAfter = float(std::atof(argv[i + 1]));
    HelloApp app;
    return Application::getInstance()->run();
}
