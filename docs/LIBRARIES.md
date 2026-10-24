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

Layouts the rewrite depends on (libc++ on 32-bit): `std::string` 12 bytes, `std::function` 20 bytes (16-byte
buffer, then `__f_`), `std::shared_ptr` 8 bytes.

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

The newer versions below are expected: cocos2d-x projects take these from the separate, updatable
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
| FreeType | 2.5.x (to confirm) | no version string; the version lives in `FT_Library` at run time. cocos2d-x 3.2's externals carried FreeType 2.5 |
| tinyxml2 | (to confirm) | classes present (`tinyxml2::XMLElement`, ...), no version string |
| chipmunk | (to confirm) | sources under `cocos2d/external/chipmunk`; cocos2d-x 3.2 carried chipmunk 6.2 |
| Ogg Vorbis | (to confirm) | ~180 functions, no version string |
| LZMA SDK | (to confirm) | `LzmaDec_*` decoder only |
| rapidjson | the copy in cocos2d-x 3.2's externals | template code only, no version string |
| curl | linked, 4 functions left | the rest was stripped |

## Not open source

The Square Enix sound engine (`SQEX::*`, `SdSoundSystem_*`, `akb*`) has no upstream: it stays our rewrite.

## Next checks

The "(to confirm)" rows can be pinned by compiling the candidate upstream version for ARM with the NDK r10e
toolchain and comparing function bodies with the original.
