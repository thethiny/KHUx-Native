"""Link the whole rewrite natively with the runtime (src/rw_native.cpp), the generated adapters and the engine.

python tools/build_game.py [TEST]     # TEST: a folder under tests/ with main.cpp (default: game)
                                      # -> out/<TEST>/khux.exe (the loader) + khux_game.dll (everything else)

Needs: tools/build_cocos.sh, build_deps.py, build_rewrite.py, gen_adapters.py and gen_vtable_adapters.py first.
"""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'third_party' / 'llvm-mingw-20240619-ucrt-x86_64' / 'bin'
CXX = str(BIN / 'i686-w64-mingw32-clang++.exe')
ENGINE = ROOT / 'out' / 'cocos-i686'
R = ENGINE / 'cocos' / 'CMakeFiles' / 'cocos2d.dir'
RECOMP = next(p for p in (ROOT.parent / 'recomp', ROOT / 'recomp') if (p / 'rewrite' / 'include' / 'rw' / 'lib.hpp').exists())
DEPS = ROOT / 'out' / 'deps' / 'lib'


def run(cmd, what):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ENGINE))
    if r.returncode:
        lines = (r.stdout + r.stderr).splitlines()
        print(f'{what} failed:')
        for i, l in enumerate(lines):
            if 'error' in l:
                ref = next((x for x in lines[i + 1:i + 4] if 'referenced by' in x), '')
                print('  ', l.strip()[:170], ('| ' + ref.strip()[:120]) if ref else '')
        sys.exit(1)


def main():
    test = sys.argv[1] if len(sys.argv) > 1 else 'game'
    out = ROOT / 'out' / test
    out.mkdir(parents=True, exist_ok=True)
    flags = (R / 'flags.make').read_text()
    defs = [d for d in re.search(r'CXX_DEFINES = (.*)', flags).group(1).split() if d not in ('-D_USRDLL', '-DCOCOS2DXWIN32_EXPORTS')]
    cxx = [f for f in re.search(r'CXX_FLAGS = (.*)', flags).group(1).replace(';-std=c++11', '').split() if not f.startswith('-std=')]
    cocos = cxx + defs + ['-std=gnu++17', '-D_LIBCPP_ENABLE_CXX17_REMOVED_FEATURES', f'@{R / "includes_CXX.rsp"}', '-w']
    rw = ['-std=gnu++17', '-O2', '-w', f'-I{RECOMP / "rewrite" / "include"}', f'-I{RECOMP / "rewrite" / "src"}',
          f'-I{RECOMP / "lift"}', f'-I{ROOT / "src"}']
    run([CXX] + rw + ['-c', str(ROOT / 'src' / 'rw_native.cpp'), '-o', str(out / 'rw_native.o')], 'rw_native')
    run([CXX] + cocos + ['-c', str(ROOT / 'src' / 'stubs.cpp'), '-o', str(out / 'stubs.o')], 'stubs')
    run([CXX, '-std=gnu++17', '-O2', '-w', '-c', str(ROOT / 'src' / 'image.cpp'), '-o', str(out / 'image.o')], 'image')
    run([CXX] + rw + ['-c', str(ROOT / 'src' / 'imports_hand.cpp'), '-o', str(out / 'imports_hand.o')], 'imports_hand')
    run([CXX] + cocos + [f'-I{ROOT / "src"}', '-Dmain=khux_program_main', '-c', str(ROOT / 'tests' / test / 'main.cpp'),
         '-o', str(out / 'main.o')], 'main')
    run([CXX, '-std=gnu++17', '-O2', '-w', '-c', str(ROOT / 'src' / 'dll_entry.cpp'), '-o', str(out / 'dll_entry.o')], 'dll_entry')
    # the loader: a fixed low base, no relocations - its image is mapped first and covers the game's data range
    CC = str(BIN / 'i686-w64-mingw32-clang.exe')
    run([CC, '-O2', '-w', str(ROOT / 'src' / 'loader.c'), '-o', str(out / 'khux.exe'), '-static',
         '-Wl,--image-base,0x00D00000', '-Wl,--disable-dynamicbase', '-Wl,--disable-reloc-section'], 'loader')
    objs = sorted((ROOT / 'out' / 'rewrite' / 'obj').glob('*.o'))
    rsp = out / 'objs.rsp'
    rsp.write_text('\n'.join('"' + p.as_posix() + '"' for p in objs))
    gen = ROOT / 'out' / 'gen'
    libs = [ENGINE / 'lib' / f'lib{n}.a' for n in ('cocostudio', 'extensions', 'spine', 'cocos2d', 'chipmunk', 'unzip',
                                                   'tinyxml2', 'xxhash')] + \
           [DEPS / f'lib{n}.a' for n in ('glfw3', 'glew', 'freetype', 'png', 'jpeg', 'tiff', 'webp', 'zlib')]
    run([CXX, '-shared', str(out / 'dll_entry.o'), str(out / 'main.o'), str(out / 'rw_native.o'), str(out / 'stubs.o'), str(out / 'image.o'), str(out / 'imports_hand.o'), f'@{rsp}', str(gen / 'imports.o'), str(gen / 'engine_data.o'), str(gen / 'lib_adapters.o'),
         str(gen / 'vt_adapters.o'), '-o', str(out / 'khux_game.dll'), '-static',
         '-Wl,--image-base,0x50000000', '-Wl,--start-group']
        + [str(p) for p in libs] + ['-Wl,--end-group', '-lopengl32', '-lgdi32', '-luser32', '-lws2_32', '-lwinmm',
        '-lshell32', '-lole32', '-lcomdlg32', '-lversion', '-limm32', '-luuid', '-lpthread'], 'link')
    print('built', out / 'khux.exe', '+', out / 'khux_game.dll')


if __name__ == '__main__':
    main()
