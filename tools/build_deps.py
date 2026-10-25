"""Build the C libraries cocos2d-x needs, from upstream, for Windows i686 (clang + llvm-mingw).

python tools/build_deps.py [name ...]     # all, or the named ones

Versions: the game's where it had them (docs/LIBRARIES.md: zlib 1.2.8, libpng 1.6.16, libjpeg 9, FreeType 2.5.5,
libtiff 4.0.3, libwebp 0.2.1); GLFW 3.0.4 and GLEW 1.10.0 as cocos2d-x 3.2 shipped them (the game used Android's
own window and GL). Sources go to third_party/deps-src/, libraries and headers to out/deps/{lib,include}/.
"""
import concurrent.futures, os, shutil, subprocess, sys, tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'third_party' / 'deps-src'
OUT = ROOT / 'out' / 'deps'
BIN = ROOT / 'third_party' / 'llvm-mingw-20240619-ucrt-x86_64' / 'bin'
CC = str(BIN / 'i686-w64-mingw32-clang.exe')
AR = str(BIN / 'llvm-ar.exe')

FT_MODULES = ['base/ftbase.c', 'base/ftinit.c', 'base/ftsystem.c', 'base/ftdebug.c', 'base/ftbbox.c', 'base/ftbitmap.c',
              'base/ftglyph.c', 'base/ftstroke.c', 'base/ftsynth.c', 'base/fttype1.c', 'base/ftmm.c', 'base/ftlcdfil.c',
              'autofit/autofit.c', 'truetype/truetype.c', 'sfnt/sfnt.c', 'smooth/smooth.c', 'raster/raster.c',
              'psnames/psnames.c', 'psaux/psaux.c', 'cff/cff.c', 'cid/type1cid.c', 'type1/type1.c',
              'pshinter/pshinter.c', 'pfr/pfr.c', 'type42/type42.c', 'winfonts/winfnt.c', 'pcf/pcf.c', 'bdf/bdf.c',
              'gzip/ftgzip.c', 'lzw/ftlzw.c']
JPEG = ('jaricom jcapimin jcapistd jcarith jccoefct jccolor jcdctmgr jchuff jcinit jcmainct jcmarker jcmaster jcomapi '
        'jcparam jcprepct jcsample jctrans jdapimin jdapistd jdarith jdatadst jdatasrc jdcoefct jdcolor jddctmgr jdhuff '
        'jdinput jdmainct jdmarker jdmaster jdmerge jdpostct jdsample jdtrans jerror jfdctflt jfdctfst jfdctint jidctflt '
        'jidctfst jidctint jquant1 jquant2 jutils jmemmgr jmemnobs').split()

def tiff_prep(d):
    """libtiff's MSVC config headers, with MSVC's __int64 spelled long long (clang rejects it there)."""
    for a, b in (('tif_config.vc.h', 'tif_config.h'), ('tiffconf.vc.h', 'tiffconf.h')):
        t = (d / 'libtiff' / a).read_text(errors='replace')
        (d / 'libtiff' / b).write_text(t.replace('unsigned __int64', 'unsigned long long').replace('signed __int64', 'long long'))


LIBS = {
    'zlib': dict(url='https://github.com/madler/zlib/archive/refs/tags/v1.2.8.tar.gz', dir='zlib-1.2.8',
                 srcs=lambda d: [p for p in d.glob('*.c') if p.stem not in ('example', 'minigzip')],
                 inc=['.'], headers=['zlib.h', 'zconf.h']),
    'png': dict(url='https://github.com/pnggroup/libpng/archive/refs/tags/v1.6.16.tar.gz', dir='libpng-1.6.16',
                prep=lambda d: shutil.copy(d / 'scripts' / 'pnglibconf.h.prebuilt', d / 'pnglibconf.h'),
                srcs=lambda d: [p for p in d.glob('png*.c') if p.stem not in ('pngtest',)],
                inc=['.', '../zlib-1.2.8'], headers=['png.h', 'pngconf.h', 'pnglibconf.h']),
    'jpeg': dict(url='https://www.ijg.org/files/jpegsrc.v9.tar.gz', dir='jpeg-9',
                 prep=lambda d: shutil.copy(d / 'jconfig.vc', d / 'jconfig.h'),
                 srcs=lambda d: [d / f'{n}.c' for n in JPEG],
                 inc=['.'], headers=['jpeglib.h', 'jconfig.h', 'jmorecfg.h', 'jerror.h']),
    'freetype': dict(url='https://download.savannah.gnu.org/releases/freetype/freetype-old/freetype-2.5.5.tar.gz',
                     dir='freetype-2.5.5', srcs=lambda d: [d / 'src' / m for m in FT_MODULES],
                     inc=['include'], defs=['FT2_BUILD_LIBRARY'], headers=['include/*']),   # 2.5.5: headers directly in include/
    'tiff': dict(url='https://download.osgeo.org/libtiff/old/tiff-4.0.3.tar.gz', dir='tiff-4.0.3',
                 prep=lambda d: tiff_prep(d),
                 srcs=lambda d: [p for p in (d / 'libtiff').glob('tif_*.c')
                                 if p.stem not in ('tif_unix', 'tif_vms', 'tif_wince', 'tif_acorn', 'tif_apple',
                                                   'tif_atari', 'tif_msdos', 'tif_win3')],
                 inc=['libtiff'], headers=['libtiff/tiff.h', 'libtiff/tiffio.h', 'libtiff/tiffvers.h',
                                           'libtiff/tiffconf.h']),
    'webp': dict(url='https://github.com/webmproject/libwebp/archive/refs/tags/v0.2.1.tar.gz', dir='libwebp-0.2.1',
                 srcs=lambda d: [p for sub in ('dec', 'dsp', 'utils', 'enc') for p in (d / 'src' / sub).glob('*.c')],
                 inc=['src'], headers=['src/webp']),
    'glew': dict(url='https://downloads.sourceforge.net/project/glew/glew/1.10.0/glew-1.10.0.tgz', dir='glew-1.10.0',
                 srcs=lambda d: [d / 'src' / 'glew.c'], inc=['include'],
                 # cocos2d-x 3.2's own glew.h (GLEW 1.7/1.8) declares glewInit etc. without __stdcall
                 defs=['GLEW_STATIC', 'GLEWAPIENTRY='],
                 headers=['include/GL']),
}


def fetch(name, spec):
    d = SRC / spec['dir']
    if d.exists(): return d
    SRC.mkdir(parents=True, exist_ok=True)
    tgz = SRC / f'{name}.tar.gz'
    if not tgz.exists():
        print(f'downloading {name}', flush=True)
        # curl, not urllib: it uses Windows' certificate store (Python 3.9's is out of date for some mirrors)
        subprocess.run(['curl', '-fsSL', '--retry', '3', '-o', str(tgz), spec['url']], check=True)
    with tarfile.open(tgz) as t: t.extractall(SRC)
    if 'prep' in spec: spec['prep'](d)
    return d


def build(name, spec):
    d = fetch(name, spec)
    obj = OUT / 'obj' / name
    obj.mkdir(parents=True, exist_ok=True)
    flags = ['-O2', '-w'] + [f'-I{d / i}' for i in spec['inc']] + [f'-D{x}' for x in spec.get('defs', [])]
    srcs = spec['srcs'](d)
    def cc(s):
        o = obj / ('_'.join(s.relative_to(d).with_suffix('').parts) + '.o')   # dec/frame.c and enc/frame.c differ
        r = subprocess.run([CC, '-c', str(s), '-o', str(o)] + flags, capture_output=True, text=True)
        return o, r.returncode, r.stderr
    with concurrent.futures.ThreadPoolExecutor(os.cpu_count()) as ex:
        res = list(ex.map(cc, srcs))
    bad = [(o, e) for o, rc, e in res if rc]
    if bad:
        for o, e in bad[:3]: print(f'  {name}: {o.name}: {e.strip().splitlines()[-1] if e.strip() else "?"}')
        return False
    (OUT / 'lib').mkdir(parents=True, exist_ok=True)
    lib = OUT / 'lib' / f'lib{name}.a'
    if lib.exists(): lib.unlink()
    subprocess.run([AR, 'rcs', str(lib)] + [str(o) for o, _, _ in res], check=True)
    for h in spec['headers']:
        if h.endswith('/*'):                                 # a folder's contents
            for c in (d / h[:-2]).iterdir():
                dst = OUT / 'include' / c.name
                if c.is_dir(): shutil.copytree(c, dst, dirs_exist_ok=True)
                else: dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy(c, dst)
            continue
        src = d / h
        dst = OUT / 'include' / src.name
        if src.is_dir(): shutil.copytree(src, dst, dirs_exist_ok=True)
        else: dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy(src, dst)
    print(f'{name}: {len(srcs)} sources -> {lib.name}', flush=True)
    return True


def build_glfw():
    url, dname = 'https://github.com/glfw/glfw/archive/refs/tags/3.0.4.tar.gz', 'glfw-3.0.4'
    d = fetch('glfw', dict(url=url, dir=dname))
    b = OUT / 'glfw-build'
    bat = OUT / 'glfw.bat'
    bat.write_text('@echo off\n'
                   f'set PATH={BIN};C:\\Program Files\\CMake\\bin;C:\\Windows\\System32\n'
                   f'cmake -S "{d}" -B "{b}" -G "MinGW Makefiles" -DCMAKE_C_COMPILER=i686-w64-mingw32-clang '
                   '-DCMAKE_MAKE_PROGRAM=mingw32-make -DCMAKE_BUILD_TYPE=Release -DGLFW_BUILD_EXAMPLES=OFF '
                   '-DGLFW_BUILD_TESTS=OFF -DGLFW_BUILD_DOCS=OFF -DCMAKE_POLICY_VERSION_MINIMUM=3.5 >nul || exit /b 1\n'
                   f'cmake --build "{b}" -j %NUMBER_OF_PROCESSORS% >nul || exit /b 1\n')
    r = subprocess.run(['cmd', '/c', str(bat)], capture_output=True, text=True)
    lib = next(b.rglob('libglfw3.a'), None)
    if r.returncode or not lib:
        print('  glfw:', (r.stdout + r.stderr)[-600:]); return False
    (OUT / 'lib').mkdir(parents=True, exist_ok=True)
    shutil.copy(lib, OUT / 'lib' / 'libglfw3.a')
    shutil.copytree(d / 'include' / 'GLFW', OUT / 'include' / 'GLFW', dirs_exist_ok=True)
    print('glfw: -> libglfw3.a', flush=True)
    return True


def main():
    want = sys.argv[1:] or list(LIBS) + ['glfw']
    ok = True
    for n in want:
        ok &= build_glfw() if n == 'glfw' else build(n, LIBS[n])
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
