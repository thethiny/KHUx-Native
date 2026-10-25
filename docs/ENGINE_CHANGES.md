# Square Enix's changes to cocos2d-x 3.2

The game's engine is cocos2d-x 3.2 with changes. The native build must reproduce them exactly: the rewritten game
code reads engine objects at the game's offsets and calls their virtual functions at the game's vtable slots.

How they were found (`tools/engine_diff.py`, `tests/engine_sizes.cpp`):
- functions: the binary's engine functions against the symbols of stock 3.2 built from source;
- sizes: `operator new(size)` in each class's `create()` in the binary against `sizeof` in stock 3.2;
- vtables: the binary's `_ZTV` symbols (slots named through the relocations) against clang's
  `-fdump-vtable-layouts` of stock 3.2;
- fields: the binary's getters against clang's `-fdump-record-layouts` of stock 3.2.

## cocos2d::Node (done: 624 bytes, stock 592)

**Fields.** 32 bytes inserted at **0x1F0**, after `_cascadeOpacityEnabled` (0x1ED) and before `_onEnterCallback`
(stock 0x1F0, game 0x210). Every member up to 0x1ED has the stock offset; everything from `_onEnterCallback` on
is 32 bytes later.

```cpp
    bool _cascadeOpacityEnabled;   // 0x1ED (stock)
    Color4F _colorMultiply;        // 0x1F0: setColorEffect's first 4 values (default Color4F::WHITE)
    Color4F _colorAdd;             // 0x200: its last 4 (default Color4F::CLEAR); each value clamped to [-1, 1]
    std::function<void()> _onEnterCallback;   // 0x210 (stock 0x1F0)
```

`Sprite::updateGLProgram` reads them as two `Color4F` (multiply, add): when either is not its default it switches
the sprite to a shader stock 3.2 does not have, `GLProgram::SHADER_NAME_POSITION_TEXTURE_COLOR_EFFECT_NO_MVP`, else
back to `SHADER_NAME_POSITION_TEXTURE_COLOR_NO_MVP`. The effect shader's source is to be taken from the binary.
(The field names above are ours.)

**Virtual functions.** Two inserted (all node classes inherit the shift):

| Function | Declared between | vtable byte (from the vtable pointer) |
|---|---|---|
| `virtual void setColorEffect(float, float, float, float, float, float, float, float)` | `isOpacityModifyRGB` and `init` | 0x244 (`init` moves 0x244 -> 0x248) |
| `virtual void updateGLProgram()` | `updateColor` and `updatePhysicsBodyPosition` | 0x260 (stock 0x25C held `updatePhysicsBodyPosition`) |

`Node::updateGLProgram` is empty; `Sprite::updateGLProgram` overrides it (above). `Node::setColorEffect` (0x896480)
clamps the eight floats into the two colors; the rest of its body is not read yet.

Checked against `Sprite`, `Layer`, `ui::Widget`: their vtables differ from stock by exactly these two slots.

## cocos2d::QuadCommand (done: 0x88 bytes, stock 0x68)

Two `Color4F` appended after `_mv` (0x28-0x67): **0x68** and **0x78** - the multiply / add colors of the node's
color effect, carried to the renderer. `init` takes them as two more arguments
(`init(float, GLuint, GLProgramState*, BlendFunc, V3F_C4B_T2F_Quad*, ssize_t, const Mat4&, const Color4F&,
const Color4F&)`), stores them, and regenerates the material ID when either changed (so quads with different
effects do not batch together).

This is the whole size change of `Sprite`, `AtlasNode` and `ParticleSystemQuad` (each holds a `QuadCommand`; none
gained fields of its own): in the game's `Sprite` constructor every member is stock + 32 (Node) up to
`_quadCommand` (0x2D0) and stock + 64 from `_rect` (0x358) on.

## cocos2d::TTFConfig (done: 36 bytes, stock 32)

Two `bool` appended after `outlineSize` (+0x20, +0x21; `Label::setTTFConfig` copies them as one halfword). They
reach `FontFreeType::create(..., bool distanceField, int outline, bool, bool)` - the game's two extra arguments.

## cocos2d::Label (done: 1232 bytes, stock 1192)

- Node: +32.
- `_fontConfig` (`TTFConfig`, game 0x334): +4 for every member after it.
- Two floats appended: `setIndent` stores at **0x4C8**, `setLineSpacing` at **0x4CC**; both set `_contentDirty`
  (0x301). Stock's 4 bytes of tail padding absorb part of it: 32 + 4 + 8 = 44 bytes more data, 40 more size.

## Other classes (done unless noted)

- **`cocostudio::Skin`** (1288, stock 1192): no fields of its own - every member is stock + 64 (Node + Sprite's
  QuadCommand) and its own `_quadCommand` (game 0x47C) is a QuadCommand, +32.
- **`TextureAtlas`** (60, stock 56): every stock member at its stock offset; 4 bytes appended at **0x38**. None of
  TextureAtlas's own functions use them - who does is still open.
- **`TextFieldTTF`**: members at stock + 40 (Label); 8 bytes appended (game **0x504**, **0x508**, after `_lens` at
  0x500) - with the added `insertTextNewLine` and the keyboard overrides (meaning still to read).
- **`ui::UICCTextField`** (1336, stock 1280): members at stock + 48 (Label + TextFieldTTF); 8 bytes appended (game
  **0x52C**, **0x530**, after `_deleteBackward` 0x52B) - with `setNewLine`.
- **`extension::EditBox`** (928, stock 888): a `Color3B` inserted between `_colText` (0x384) and `_colPlaceHolder`
  (now 0x38A): the editing color (`setEditingFontColor`; the constructor sets it WHITE). Alignment makes it +4 from
  `_maxLength` (0x390) on; 4 more bytes appended (0x398).
- **`Sprite3D`** (+8): `_texture` / `_blend` at stock + 36 - probably `MeshCommand` +4, and 4 more. Not used by the
  game code; last.

Game code calls `ui::TextField` (5 functions), `extension::EditBox` (1), `TextureAtlas` (1) directly; `Sprite3D`,
`MeshCommand`, `TextFieldTTF` / `UICCTextField` only through them.

## All classes (tools/engine_diff.py)

- **Vtables, 466 classes:** 460 are stock + Node's two slots. The other six: `IMEDelegate` gained a virtual
  `insertTextNewLine` (so `TextFieldTTF`, `ui::UICCTextField`, `extension::EditBox` too; `TextFieldTTF` also
  overrides `keyboardWillShow` / `keyboardDidShow` / `keyboardWillHide`), `Application` gained
  `applicationScreenSizeChanged`, `FileUtils` gained `fullPathForFilenameEx` (its other slot differences still to
  check by hand). Not in stock: the Android platform classes, plugin-x, `LWFNode`, `AnimationCurve<3/4>`, and
  `cocos2d::Card` (Square Enix's own).
- **Sizes, 304 classes:** 178 identical, 101 exactly +32 (Node). Own additions: `Sprite` +32 (`PhysicsSprite` and
  `cocostudio::Skin` show it), `cocostudio::Skin` +32 more, `ParticleSystemQuad` +32 (`ParticleSystem` itself has
  none), `AtlasNode` +32 (`LabelAtlas`, `TileMapAtlas`), `Label` +8, `Sprite3D` +8, `extension::EditBox` +8,
  `ui::UICCTextField` +16 over Label, `TextureAtlas` +4. `GLView` differs by platform (Android vs desktop);
  `Animation3D` / `MeshSkin` come out smaller - probably the size reader, to check.

## Applied and verified

`tools/apply_engine_changes.py` applies all of the above (and `Color4F::CLEAR`, which the game has and 3.2 does not)
to the sources; the Android build's extra members are kept on Windows behind `KHUX_ANDROID_LAYOUT` (unused, null).
`tools/build_cocos.sh` runs it. Result of `tools/engine_diff.py` on the modified engine against the game:

- **vtables: 465 of 466 classes identical.** The other is `Application` (platform class, replaced by our host:
  the game's Android `Application` has `applicationScreenSizeChanged` appended).
- **sizes: 301 of 304 classes identical.** The others: `GLView` (platform: Android vs desktop), `Animation3D`,
  `MeshSkin` (the size reader takes the first `operator new` in `create()`, which there allocates the
  `Animation3DCache` / mesh cache singleton - not a difference).

Function bodies marked TODO in the script are not read from the binary yet; layouts and slot order are exact.

## Still to map

- What the appended fields of `TextureAtlas`, `TextFieldTTF`, `UICCTextField`, `EditBox` hold (read their users).
- `Sprite3D` / `MeshCommand` exactly (unused by the game code). `FileUtils`' vtable by hand; `Animation3D` /
  `MeshSkin` sizes (probably the size reader).
- The effect shader's source (`SHADER_NAME_POSITION_TEXTURE_COLOR_EFFECT_NO_MVP`) from the binary.
- The 47 added functions (list: `tools/engine_diff.py functions`), e.g. `Image::initWithBtfData` / `isBtf`,
  `Director::addScheduler` / `removeScheduler` / `setDefaultScheduler`, `TextureCache::setLimit` / `getLimit` /
  `insertTexture`, zip from memory (`unzOpenBuffer`, `*_mem_func`), `Label::setIndent` / `setLineSpacing`,
  `ui::Text::setConfig`, `TextAtlas::setStringBlend`, `FontAtlas::getBmpFontAtlas`, multi-line text fields,
  `FileUtils::fullPathForFilenameEx`, `Application::openURL`, `Device::setKeepScreenOn`,
  `EventDispatcher::removeUnnecessaryEventListeners`, `HttpClient::clearCookies`, `Card`.
- Every other engine class the game uses: size and vtable against stock (the same scripts, more classes).
