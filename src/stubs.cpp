// Engine pieces not built yet, stubbed (KHUx-Native).
// CocosDenshion: the game plays its audio through the SQEX engine; cocostudio still references these two.
#include "audio/include/SimpleAudioEngine.h"
namespace CocosDenshion {
SimpleAudioEngine *SimpleAudioEngine::getInstance() { return nullptr; }
void SimpleAudioEngine::end() {}
}  // namespace CocosDenshion
