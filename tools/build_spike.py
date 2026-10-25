"""Build tests/spike: two real rewrite functions running natively on the game's engine -> out/spike/spike.exe.
The game part is compiled against the rewrite's headers (the recomp checkout next to this repo: it has rw/lib.hpp)."""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'third_party' / 'llvm-mingw-20240619-ucrt-x86_64' / 'bin'
CXX = str(BIN / 'i686-w64-mingw32-clang++.exe')
ENGINE = ROOT / 'out' / 'cocos-i686'
R = ENGINE / 'cocos' / 'CMakeFiles' / 'cocos2d.dir'
RECOMP = next(p for p in (ROOT.parent / 'recomp', ROOT / 'recomp') if (p / 'rewrite' / 'include' / 'rw' / 'lib.hpp').exists())
DEPS = ROOT / 'out' / 'deps' / 'lib'
OUT = ROOT / 'out' / 'spike'
S = ROOT / 'tests' / 'spike'


def run(cmd, what):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ENGINE))
    if r.returncode:
        print(f'{what} failed:'); print('\n'.join(l for l in (r.stdout + r.stderr).splitlines() if 'error' in l)[:3000]); sys.exit(1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    flags = (R / 'flags.make').read_text()
    defs = [d for d in re.search(r'CXX_DEFINES = (.*)', flags).group(1).split() if d not in ('-D_USRDLL', '-DCOCOS2DXWIN32_EXPORTS')]
    cxx = re.search(r'CXX_FLAGS = (.*)', flags).group(1).replace(';-std=c++11', '').split()
    rw_inc = [f'-I{RECOMP / "rewrite" / "include"}', f'-I{RECOMP / "rewrite" / "src"}', f'-I{RECOMP / "lift"}']
    run([CXX, '-std=gnu++17', '-O2', '-w', '-c', str(S / 'game_part.cpp'), '-o', str(OUT / 'game_part.o')] + rw_inc, 'game_part')
    run([CXX] + [f for f in cxx if not f.startswith('-std=')] + defs + ['-std=gnu++17', '-D_LIBCPP_ENABLE_CXX17_REMOVED_FEATURES',
         f'@{R / "includes_CXX.rsp"}', f'-I{RECOMP / "lift"}', f'-I{ROOT / "src"}', '-w', '-c', str(S / 'rw_native.cpp'),
         '-o', str(OUT / 'rw_native.o')], 'rw_native')
    run([CXX] + cxx + defs + [f'@{R / "includes_CXX.rsp"}', '-w', '-c', str(S / 'main.cpp'), '-o', str(OUT / 'main.o')], 'main')
    libs = [ENGINE / 'lib' / f'lib{n}.a' for n in ('cocostudio', 'extensions', 'spine', 'cocos2d', 'chipmunk', 'unzip',
                                                   'tinyxml2', 'xxhash')] + \
           [DEPS / f'lib{n}.a' for n in ('glfw3', 'glew', 'freetype', 'png', 'jpeg', 'tiff', 'webp', 'zlib')]
    gen = ROOT / 'out' / 'gen' / 'lib_adapters.o'   # tools/gen_adapters.py
    run([CXX, str(OUT / 'main.o'), str(OUT / 'rw_native.o'), str(OUT / 'game_part.o'), str(gen), str(gen.parent / 'vt_adapters.o'), '-o', str(OUT / 'spike.exe'),
         '-static', '-Wl,--start-group'] + [str(p) for p in libs] + ['-Wl,--end-group', '-lopengl32', '-lgdi32', '-luser32',
         '-lws2_32', '-lwinmm', '-lshell32', '-lole32', '-lcomdlg32', '-lversion', '-limm32', '-luuid'], 'link')
    print('built', OUT / 'spike.exe')


if __name__ == '__main__':
    main()
