# Libraries in the original game (v1.0.1)

What `libcocos2dcpp.so` (v1.0.1, armeabi-v7a) was built from, read from the binary itself: version strings,
version functions, which APIs are present, and the ELF notes. The native build uses the same versions so that
struct layouts, vtables and behaviour match the code the rewrite was checked against.

## Toolchain

| Part | Version | Evidence |
|---|---|---|
| Android NDK | **r10e** | `.comment`: `GCC: (GNU) 4.9 20140827 (prerelease)` and `clang version 3.6`, the pair NDK r10e shipped |
| Linker | gold 1.11 | `.note.gnu.gold-version` |
| C++ library | **NDK llvm-libc++** (the r10e snapshot) | build paths `/tmp/ndk-user/tmp/build-libc++/ndk/sources/cxx-stl/llvm-libc++/...` |
| ABI | ARM EABI, Itanium C++ ABI | `.ARM.attributes` (`ARM v7`, `aeabi`) |

Older `GCC: (GNU) 4.4.3`, `4.6.x-google` and `4.8` tags come from prebuilt third-party archives linked in.

Layouts the rewrite depends on (libc++ on 32-bit): `std::string` 12 bytes, `std::function` 24 bytes (16-byte buffer, `__f_` at +16 pointing
to it, 4 bytes of padding), `std::shared_ptr` 8 bytes.

## Engine

| Library | Version | Evidence |
|---|---|---|
| **cocos2d-x** | **3.2** | `cocos2d::cocos2dVersion()` returns `"cocos2d-x 3.2"`. Everything new in 3.2 is present (`Animate3D`, `experimental::TMXTiledMap`, `GLProgramState`, `Animation3D`), nothing new in 3.3 is (`Camera`, which 3.3's `Director` uses every frame) |
| cocostudio (armature) | `armatureVersion()` = `"1.1.0.0"` | the cocostudio shipped in cocos2d-x 3.2 |
| CocosGUI (`cocos2d::ui`) | `CocosGUIVersion()` = `"CocosGUI v1.0.0.0"` | the ui module of cocos2d-x 3.2 |
| **LWF** (GREE) | runtime accepting data format **0x13 / 0x12 / 0x11** | `LWF::Data::Load` checks the `LWF` magic, then those three version bytes |

Not in the binary: cocos2d-x 3.3+ classes (`Camera`, `ui::Scale9Sprite`, `CSLoader`, `ClippingRectangleNode`).
The game project was named `hole` (build paths `/Users/hojo/Documents/Projects/hole_en_release/...`).

## Third-party libraries

The game did not use cocos2d-x 3.2's stock dependency package (v3-deps-5 has libpng 1.6.2, the game
1.6.16): the C libraries below are newer. That is expected: cocos2d-x projects take these from the separate, updatable
`cocos2d-x-3rd-party-libs` repository (its build paths, `/Users/guanghui/Github/cocos2d-x-3rd-party-libs-src/...`,
are in the strings).

| Library | Version | Evidence |
|---|---|---|
| OpenSSL | **1.0.1l** (15 Jan 2015) | `"... part of OpenSSL 1.0.1l 15 Jan 2015"` |
| libpng | **1.6.16** | `"libpng version 1.6.16 - December 22, 2014"` |
| zlib | **1.2.8** | `"deflate 1.2.8 ..."`, `"inflate 1.2.8 ..."` |
| libtiff | **4.0.3** | `"LIBTIFF, Version 4.0.3"` |
| libjpeg (IJG) | **9** (2013) | `"Copyright (C) 2013, Thomas G. Lane, Guido Vollbeding"` |
| libwebp | **0.2.1** | `WebPGetDecoderVersion()` / `WebPGetEncoderVersion()` return 513 (0x000201) |
| libwebsockets | **1.3** (commit 762deb8) | `lws_get_library_version()` = `"1.3 762deb8"` |
| FreeType | **2.5.5** | `FT_New_Library` stores the version as 2, 5, 5 |
| tinyxml2 | **1.0.9** | the copy in cocos2d-x 3.2's deps package (v3-deps-5), compiled into the game; its API matches the methods present |
| chipmunk | **6.2.1** | bundled as source in cocos2d-x 3.2 (`external/chipmunk`, `CP_VERSION` 6.2.1); 6.2 API present |
| Ogg Vorbis | **Tremor** (integer decoder) on **libogg 1.3.x** | `ov_read(vf, buffer, length, bitstream)` - 4 arguments (libvorbis has 7); libogg's `ogg_stream_flush_fill` (new in 1.3.0) and `ogg_stream_iovecin` |
| LZMA SDK | `LzmaDec` (exact release: byte check) | decoder only (`LzmaDec_*`, `LzmaDecode`); its API has not changed across SDK releases |
| rapidjson | **0.11** (cocos2d-x 3.2's copy) | `ParseStream<0, GenericStringStream>` with two template arguments and `AddMember(const char*, int, Allocator&)` - the API before 1.0 |
| curl | linked, 4 functions left | the rest was stripped |

## The engine is a modified cocos2d-x 3.2

`tools/engine_diff.py` and `tests/engine_sizes.cpp` compare the game's engine with stock 3.2 built from source.

- **47 functions have no counterpart anywhere in cocos2d-x 3.2** (plugin-x and the LWF renderer aside). Among them:
  `Image::initWithBtfData` / `isBtf` (the game's BTF texture format), `Node::setColorEffect`,
  `Node::updateGLProgram`, `Sprite::updateGLProgram`, `Director::addScheduler` / `removeScheduler` /
  `setDefaultScheduler`, `TextureCache::setLimit` / `getLimit` / `insertTexture`, zip archives read from memory
  (`unzOpenBuffer`, `*_mem_func`), `Label::setIndent` / `setLineSpacing`, `ui::Text::setConfig`,
  `TextAtlas::setStringBlend`, `FontAtlas::getBmpFontAtlas`, multi-line text fields (`insertTextNewLine`,
  `setNewLine`), `FileUtils::fullPathForFilenameEx`, `HttpClient::clearCookies`, `Application::openURL`,
  `Device::setKeepScreenOn`, `EventDispatcher::removeUnnecessaryEventListeners`, `Card`. Some may be backports from
  cocos2d-x 3.3+; most are Square Enix's own.
- **`cocos2d::Node` is 32 bytes larger** in the game (624 bytes vs 592), so every node class is: `Layer`, `Scene`,
  the `ui::` widgets, `cocostudio::Armature`, ... (+32). `Label` +40, `ParticleSystemQuad` +64. Classes that are not
  nodes match (`CallFunc`, `SpriteFrame`, `EventListenerTouchOneByOne`).

So the native build needs its own cocos2d-x 3.2: stock 3.2 plus these fields at their offsets plus the added
functions (all of them are in the binary, decompiled and lifted).

## Counted as game code

The Square Enix sound engine (`SQEX::*`, `SdSoundSystem_*`, `akb*`) is part of the game, not a library: it stays
our rewrite. It decodes Ogg Vorbis through the Tremor / libogg above.

## Next checks

The rows marked "byte check" can be pinned by compiling the candidate upstream version for ARM with the NDK r10e
toolchain and comparing function bodies with the original.

## Layout check of the native toolchain

`tests/layout_check.cpp` (clang 18 / llvm-mingw, i686, libc++, `-static`): every layout above matches the ARM32
build - type sizes, 8-aligned 64-bit fields, `std::string` (long and short forms), `std::function`,
`shared_ptr`, `vector`, the Itanium vtable order. Only `wchar_t` differs (2 bytes on Windows); no game code uses it.
