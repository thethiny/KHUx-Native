// sizeof of the engine classes in stock cocos2d-x 3.2, to compare with the game's (operator new in each create()).
// Built by tools/engine_diff.py sizes with the engine build's own defines and include paths.
#include <cstdio>
#include "cocos2d.h"
#include "ui/CocosGUI.h"
#include "cocostudio/CocoStudio.h"

#define SIZE(T) std::printf("%-40s %u\n", #T, unsigned(sizeof(T)))

int main() {
    SIZE(cocos2d::Node);
    SIZE(cocos2d::Layer);
    SIZE(cocos2d::LayerColor);
    SIZE(cocos2d::Scene);
    SIZE(cocos2d::Sprite);
    SIZE(cocos2d::Label);
    SIZE(cocos2d::ui::Widget);
    SIZE(cocos2d::ui::Layout);
    SIZE(cocos2d::ui::Button);
    SIZE(cocos2d::ui::Text);
    SIZE(cocos2d::ui::ImageView);
    SIZE(cocos2d::ui::ScrollView);
    SIZE(cocos2d::ui::ListView);
    SIZE(cocos2d::ui::LoadingBar);
    SIZE(cocostudio::Armature);
    SIZE(cocos2d::ParticleSystemQuad);
    SIZE(cocos2d::DrawNode);
    SIZE(cocos2d::ClippingNode);
    SIZE(cocos2d::ProgressTimer);
    SIZE(cocos2d::CallFunc);
    SIZE(cocos2d::SpriteFrame);
    SIZE(cocos2d::EventListenerTouchOneByOne);
    SIZE(cocos2d::RenderTexture);
    SIZE(cocos2d::MenuItemSprite);
    return 0;
}
