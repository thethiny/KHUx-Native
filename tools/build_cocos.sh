#!/bin/bash
# Build cocos2d-x 3.2 (the game's engine version) for Windows i686 with clang + libc++ (llvm-mingw).
#
#   bash tools/build_cocos.sh            # download what is missing, patch, configure, build
#
# Downloads into third_party/ (gitignored): llvm-mingw 20240619 (clang 18.1.8), cocos2d-x 3.2 and its dependency
# package v3-deps-5. patches/cocos2d-x-3.2.patch makes the 2014 sources build with a current compiler (no behaviour
# change); tools/apply_engine_changes.py then makes it the game's engine (Square Enix's changes). Output: out/cocos-i686/lib/*.a (cocos2d, cocostudio, extensions, spine, chipmunk, tinyxml2, unzip, xxhash).
# Run from Git Bash on Windows; needs CMake (C:\Program Files\CMake) and Windows tar.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T="$ROOT/third_party"; OUT="$ROOT/out"
TOOLCHAIN=llvm-mingw-20240619-ucrt-x86_64
COCOS=cocos2d-x-cocos2d-x-3.2
DEPS=cocos2d-x-3rd-party-libs-bin-3-deps-5
TAR=/c/Windows/System32/tar.exe
mkdir -p "$T" "$OUT"
cd "$T"

fetch() {  # url file
    [ -f "$2" ] || { echo "downloading $2"; curl -fSL -o "$2" "$1"; }
}
fetch https://github.com/mstorsjo/llvm-mingw/releases/download/20240619/$TOOLCHAIN.zip llvm-mingw.zip
fetch https://github.com/cocos2d/cocos2d-x/archive/refs/tags/cocos2d-x-3.2.zip cocos2d-x-3.2.zip
fetch https://github.com/cocos2d/cocos2d-x-3rd-party-libs-bin/archive/refs/tags/v3-deps-5.zip v3-deps-5.zip
[ -d $TOOLCHAIN ] || $TAR -xf llvm-mingw.zip
if [ ! -d $COCOS ]; then
    $TAR -xf cocos2d-x-3.2.zip
    $TAR -xf v3-deps-5.zip
    cp -rn $DEPS/* $COCOS/external/                     # what cocos2d-x's download-deps.py does
    (cd $COCOS && patch -p1 < "$ROOT/patches/cocos2d-x-3.2.patch")
fi
# Square Enix's changes to the engine (docs/ENGINE_CHANGES.md); a second run changes nothing
python "$ROOT/tools/apply_engine_changes.py"

W() { cygpath -w "$1"; }
E="$(cygpath -m "$T/$COCOS/external")"
INC="-I$E/win32-specific/zlib/include -I$E/win32-specific/gles/include/OGLES -I$E/win32-specific/icon/include"
INC="$INC -I$E/curl/include/win32 -I$E/sqlite3/include"
# KHUX_NATIVE last: the project appends ";-std=..." to these flags, which would break a final -I path
CFLAGS="$INC -DKHUX_ANDROID_LAYOUT=1 -DKHUX_NATIVE=1"
CXXFLAGS="-std=gnu++11 -Wno-c++11-narrowing -Wno-register $INC -DKHUX_ANDROID_LAYOUT=1 -DKHUX_NATIVE=1"
# CMake's MinGW generator refuses Git Bash's sh on PATH: run it from cmd with a clean PATH
cat > "$OUT/cocos_build.bat" <<EOF
@echo off
set PATH=$(W "$T/$TOOLCHAIN/bin");C:\Program Files\CMake\bin;C:\Windows\System32
cmake -S "$(W "$T/$COCOS")" -B "$(W "$OUT/cocos-i686")" -G "MinGW Makefiles" ^
  -DCMAKE_C_COMPILER=i686-w64-mingw32-clang -DCMAKE_CXX_COMPILER=i686-w64-mingw32-clang++ ^
  -DCMAKE_MAKE_PROGRAM=mingw32-make -DDEBUG_MODE=OFF -DBUILD_CppTests=OFF -DBUILD_LuaTests=OFF ^
  -DBUILD_LIBS_LUA=OFF -DBUILD_EDITOR_COCOSBUILDER=OFF -DBUILD_EDITOR_SPINE=ON -DBUILD_EDITOR_COCOSTUDIO=ON ^
  -DBUILD_EXTENSIONS=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_C_FLAGS="$CFLAGS" -DCMAKE_CXX_FLAGS="$CXXFLAGS" || exit /b 1
cmake --build "$(W "$OUT/cocos-i686")" --target cocos2d cocostudio extensions spine -j %NUMBER_OF_PROCESSORS%
EOF
cmd //c "$(W "$OUT/cocos_build.bat")"
ls "$OUT/cocos-i686/lib"
