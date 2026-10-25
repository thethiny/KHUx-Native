"""Build tests/hello (the first native window) against the engine (build_cocos.sh) and its libraries (build_deps.py).

python tools/build_hello.py     ->  out/hello/hello.exe
"""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'third_party' / 'llvm-mingw-20240619-ucrt-x86_64' / 'bin'
CXX = BIN / 'i686-w64-mingw32-clang++.exe'
ENGINE = ROOT / 'out' / 'cocos-i686'
R = ENGINE / 'cocos' / 'CMakeFiles' / 'cocos2d.dir'
DEPS = ROOT / 'out' / 'deps' / 'lib'
OUT = ROOT / 'out' / 'hello'


def main():
    flags = (R / 'flags.make').read_text()
    defs = re.search(r'CXX_DEFINES = (.*)', flags).group(1).split()
    cxx = re.search(r'CXX_FLAGS = (.*)', flags).group(1).replace(';-std=c++11', '').split()
    defs = [d for d in defs if d not in ('-D_USRDLL', '-DCOCOS2DXWIN32_EXPORTS')]   # an exe, not the engine DLL
    OUT.mkdir(parents=True, exist_ok=True)
    engine_libs = [ENGINE / 'lib' / f'lib{n}.a' for n in ('cocostudio', 'extensions', 'spine', 'cocos2d', 'chipmunk',
                                                          'unzip', 'tinyxml2', 'xxhash')]
    dep_libs = [DEPS / f'lib{n}.a' for n in ('glfw3', 'glew', 'freetype', 'png', 'jpeg', 'tiff', 'webp', 'zlib')]
    sys_libs = ['-lopengl32', '-lgdi32', '-luser32', '-lws2_32', '-lwinmm', '-lshell32', '-lole32', '-lcomdlg32',
                '-lversion', '-limm32', '-luuid']
    cmd = ([str(CXX)] + cxx + defs + [f'@{R / "includes_CXX.rsp"}', str(ROOT / 'tests' / 'hello' / 'main.cpp'),
           '-o', str(OUT / 'hello.exe'), '-static', '-Wl,--start-group']
           + [str(p) for p in engine_libs + dep_libs] + ['-Wl,--end-group'] + sys_libs)
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ENGINE))
    errs = [l for l in (r.stdout + r.stderr).splitlines() if 'error' in l]
    if r.returncode:
        undefined = sorted({m for m in re.findall(r'undefined symbol: (.+)', r.stderr)})
        print(f'link failed: {len(undefined)} undefined symbols')
        for u in undefined[:40]: print('  ', u)
        for e in errs[:10]: print('  ', e[:200])
        sys.exit(1)
    print('built', OUT / 'hello.exe')


if __name__ == '__main__':
    main()
