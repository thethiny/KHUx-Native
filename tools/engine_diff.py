"""Is the game's engine stock cocos2d-x 3.2? Compares the original binary with our build of the 3.2 sources.

python tools/engine_diff.py functions    # engine functions in the binary that stock 3.2 does not define

Binary side: the recomp function index (every function of v1.0.1's libcocos2dcpp.so with its mangled name).
Stock side: the symbols our i686 build defines (out/cocos-i686/lib/*.a, via llvm-nm). Itanium mangling is the same
on both targets (i686 adds a leading underscore). A function the game has and stock 3.2 lacks is a modification
(added or re-signatured) - or a template instance over a game type, listed apart. Functions only stock 3.2 has are
expected: the game's link dropped what it did not use.
"""
import collections, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# the function index is generated output (recomp/out/): the main recomp checkout next to this repo has it
RECOMP = next(p for p in (ROOT.parent / 'recomp', ROOT / 'recomp') if (p / 'out').exists())
LIBS = ROOT / 'out' / 'cocos-i686' / 'lib'
NM = ROOT / 'third_party' / 'llvm-mingw-20240619-ucrt-x86_64' / 'bin' / 'llvm-nm.exe'
ENGINE = re.compile(r'^_ZNK?(?:7cocos2d|10cocostudio|5spine)|^_Z\d*(?:cc|cp)|^cp[A-Z]|^_spine|^spine')


def binary_functions():
    sys.path.insert(0, str(RECOMP / 'rewrite' / 'tools'))
    import unit
    return {e['name'] for e in unit.load_index().values() if ENGINE.search(e['name'])}


def stock_functions():
    out = subprocess.run([str(NM), '--defined-only', '-j'] + [str(p) for p in sorted(LIBS.glob('*.a'))],
                         capture_output=True, text=True).stdout
    return {s[1:] if s.startswith('_') else s for s in out.split()}


def game_types():
    """Class names the game itself defines (from the binary's names outside the engine namespaces)."""
    sys.path.insert(0, str(RECOMP / 'rewrite' / 'tools'))
    import unit
    names = set()
    for e in unit.load_index().values():
        m = re.match(r'_ZNK?(\d+)', e['name'])
        if m:
            n = int(m.group(1)); s = e['name'][m.end():m.end() + n]
            if s not in ('cocos2d', 'cocostudio', 'spine', 'std'): names.add(s)
    return names


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else 'functions'
    if what == 'functions':
        b, s = binary_functions(), stock_functions()
        missing = sorted(b - s)
        game = game_types()
        over_game = [m for m in missing if any(f'{len(t)}{t}' in m for t in game if len(t) > 3)]
        rest = [m for m in missing if m not in over_game]
        print(f'engine functions in the binary: {len(b)}; defined by stock 3.2: {len(b & s)}')
        print(f'not in stock 3.2: {len(missing)} ({len(over_game)} template instances over game types)')
        for m in rest: print('  ', m)


if __name__ == '__main__':
    main()


def qualified(m):
    """'cocos2d::TextureCache::setLimit' from a nested mangled name (None if it cannot tell)."""
    m2 = re.match(r'_ZNK?(.*)', m)
    if not m2: return None
    s, parts = m2.group(1), []
    while s and s[0].isdigit():
        n = re.match(r'\d+', s).group(0); s = s[len(n):]
        parts.append(s[:int(n)]); s = s[int(n):]
    if s[:2] in ('C1', 'C2'): parts.append(parts[-1])
    elif s[:2] in ('D0', 'D1', 'D2'): parts.append('~' + parts[-1])
    return '::'.join(parts) if len(parts) > 1 else None


def classify(rest, src):
    """Split functions missing from the build: defined somewhere in the 3.2 source (platform / signature) or not."""
    text = {}
    for f in list(src.rglob('*.cpp')) + list(src.rglob('*.h')) + list(src.rglob('*.mm')):
        text[f] = f.read_text(encoding='utf-8', errors='replace')
    in_src, added = collections.defaultdict(list), []
    for m in rest:
        q = qualified(m)
        if not q: continue
        cls, meth = q.split('::')[-2], q.split('::')[-1]
        pat = re.compile(re.escape(cls) + r'\s*::\s*' + re.escape(meth) + r'\s*\(')
        hits = [f for f, t in text.items() if pat.search(t)]
        if hits: in_src['/'.join(hits[0].relative_to(src).parts[:2])].append(m)
        else: added.append((q, m))
    return in_src, added


def elf_vtables(classes):
    """{class mangled name: [slot symbol, ...]} for _ZTV<class> in the original binary (dynamic symbols + relocs)."""
    import struct
    d = open(RECOMP / 'game' / 'libcocos2dcpp.so', 'rb').read()
    phoff, phnum = struct.unpack_from('<I', d, 0x1C)[0], struct.unpack_from('<H', d, 0x2C)[0]
    segs, dyn = [], None
    for i in range(phnum):
        t, off, va, pa, fs, ms = struct.unpack_from('<6I', d, phoff + 32 * i)
        if t == 1: segs.append((va, off, fs))
        if t == 2: dyn = (off, fs)
    def fo(a):
        for va, off, fs in segs:
            if va <= a < va + fs: return off + a - va
    tags = {}
    for k in range(0, dyn[1], 8):
        t, v = struct.unpack_from('<2I', d, dyn[0] + k); tags.setdefault(t, v)
    symtab, strtab = fo(tags[6]), fo(tags[5])
    nsym = (strtab - symtab) // 16 if strtab > symtab else 40000
    def sym(i):
        nm, val, size = struct.unpack_from('<3I', d, symtab + 16 * i)
        e = d.index(b'\0', strtab + nm); return d[strtab + nm:e].decode(errors='replace'), val, size
    syms = [sym(i) for i in range(nsym)]
    byaddr = {}
    sys.path.insert(0, str(RECOMP / 'rewrite' / 'tools'))
    import unit
    for a, e in unit.load_index().items(): byaddr[int(a, 16)] = e['name']
    rel = {}
    for k in range(0, tags[18], 8):
        o, info = struct.unpack_from('<2I', d, fo(tags[17]) + k)
        rel[o] = (info & 0xFF, syms[info >> 8][0] if info >> 8 else None)
    out = {}
    for name, val, size in syms:
        if not name.startswith('_ZTV'): continue
        cls = name[4:]
        if cls not in classes: continue
        slots = []
        for o in range(val + 8, val + size, 4):             # after offset-to-top and the typeinfo
            ty, s = rel.get(o, (None, None))
            if s: slots.append(s)
            else:
                raw = struct.unpack_from('<I', d, fo(o))[0]
                slots.append(byaddr.get(raw & ~1, f'0x{raw:X}'))
        out[cls] = slots
    return out


def clang_vtable(dump, cls):
    """Method names of the slots of `cls` (e.g. cocos2d::Node) in a clang -fdump-vtable-layouts output."""
    lines = Path(dump).read_text(errors='replace').splitlines()
    try: i = next(k for k, l in enumerate(lines) if l.startswith(f"Vtable for '{cls}'"))
    except StopIteration: return None
    out = []
    for l in lines[i + 1:]:
        if not l.strip(): break
        m = re.match(r'\s*\d+ \| (.*)', l)
        if not m: continue
        sig = m.group(1)
        if sig.startswith('offset_to_top') or sig.endswith('RTTI') or sig.startswith('vcall_offset') or sig.startswith('vbase_offset'): continue
        n = re.search(r'::(~?\w+|operator[^\s(]+)\(', sig)
        out.append(n.group(1) if n else sig)
    return out


def method(mangled):
    q = qualified(mangled)
    return q.split('::')[-1] if q else mangled


def compare_vtable(bin_slots, stock):
    import difflib
    b = [method(s) for s in bin_slots]
    sm = difflib.SequenceMatcher(a=stock, b=b, autojunk=False)
    diffs = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != 'equal': diffs.append((op, i1, stock[i1:i2], j1, b[j1:j2]))
    return diffs


def stock_vtable_dumps():
    """clang -fdump-vtable-layouts of every engine C++ source (compile_commands.json), cached in out/vt/all.txt."""
    import json, concurrent.futures
    cache = ROOT / 'out' / 'vt' / 'all.txt'
    if cache.exists(): return cache.read_text(errors='replace')
    cmds = [c for c in json.loads((ROOT / 'out' / 'cocos-i686' / 'compile_commands.json').read_text())
            if c['file'].endswith('.cpp')]
    def run(c):
        cmd = re.sub(r' -o \S+', ' -o NUL', c['command']) + ' -Xclang -fdump-vtable-layouts'
        return subprocess.run(cmd, cwd=c['directory'], capture_output=True, text=True, errors='replace').stdout
    with concurrent.futures.ThreadPoolExecutor(12) as ex:
        out = ''.join(ex.map(run, cmds))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(out, encoding='utf-8')
    return out


def stock_vtables(dump):
    """{class name: [slot method names]} from a vtable-layout dump (first layout seen per class)."""
    out, cur, slots = {}, None, []
    for l in dump.splitlines():
        m = re.match(r"Vtable for '(.+)' \(\d+ entries\)\.", l)
        if m:
            cur, slots = m.group(1), []
            continue
        if cur is None: continue
        if not l.strip():
            out.setdefault(cur, slots); cur = None; continue
        m = re.match(r'\s*\d+ \| (.*)', l)
        if not m: continue
        sig = m.group(1)
        if sig.startswith(('offset_to_top', 'vcall_offset', 'vbase_offset')) or sig.endswith('RTTI'): continue
        n = re.search(r'::(~?\w+|operator[^\s(]+)\(', sig)
        slots.append(n.group(1) if n else sig)
    return out


def demangle_class(m):
    """'cocos2d::ui::Widget' from 'N7cocos2d2ui6WidgetE' (nested names only)."""
    if not m.startswith('N'): 
        n = re.match(r'(\d+)', m); return m[len(n.group(1)):len(n.group(1)) + int(n.group(1))] if n else None
    s, parts = m[1:], []
    while s and s[0].isdigit():
        n = re.match(r'\d+', s).group(0); s = s[len(n):]; parts.append(s[:int(n)]); s = s[int(n):]
    return '::'.join(parts) if s == 'E' else None


class _EnginePrefix:
    def __contains__(self, cls):
        return bool(re.match(r'N(?:7cocos2d|10cocostudio|5spine)', cls))


def bin_slot_names(slots):
    """Method names of binary vtable slots; offset-to-top values and typeinfo of secondary vtables dropped,
    thunks (_ZThn624_...) named by their target."""
    out = []
    for s in slots:
        if s.startswith('_ZTI') or re.fullmatch(r'0x[0-9A-F]+', s): continue
        s = re.sub(r'^_ZTc[hv]n?\d+_[hv]n?\d+_', '_Z', s)   # covariant-return thunks
        s = re.sub(r'^_ZTh[nv]\d+_', '_Z', s)
        s = re.sub(r'^_ZTv0_n\d+_', '_Z', s)
        out.append(method(s))
    return out


def all_vtables():
    import difflib
    st = stock_vtables(stock_vtable_dumps())
    bv = elf_vtables(_EnginePrefix())
    node_ins = {'setColorEffect', 'updateGLProgram'}
    clean, changed, missing = [], [], []
    for m, slots in sorted(bv.items()):
        cls = demangle_class(m)
        if cls not in st: missing.append(cls or m); continue
        b, s = bin_slot_names(slots), [x for x in st[cls]]
        # the game's linker merged identical functions (a subclass destructor slot holds the base's) and pure
        # virtuals are __cxa_pure_virtual (sub_C99C2C): compare destructors as one name, pure slots as the stock name
        norm = lambda n: '~' if n.startswith('~') else n
        b = [s[k] if k < len(s) and x == 'sub_C99C2C' else x for k, x in enumerate(b)]
        s, b = [norm(x) for x in s], [norm(x) for x in b]
        ops = [o for o in difflib.SequenceMatcher(a=s, b=b, autojunk=False).get_opcodes() if o[0] != 'equal']
        extra = [o for o in ops if not (o[0] == 'insert' and set(b[o[3]:o[4]]) <= node_ins)]
        (changed if extra else clean).append((cls, extra, s, b))
    return clean, changed, missing


def binary_sizes():
    """{class: size} from operator new(size) in each X::create(...) of the decompile."""
    import glob
    src = ROOT.parent / 'Input' / '1.0.1' / 'libcocos2dcpp_decompile' / 'decompile'
    sizes = {}
    for f in sorted(glob.glob(str(src / '*.c'))):
        t = open(f, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'\n[^\n(]*?\b((?:cocos2d|cocostudio|spine)(?:::\w+)+)::create\([^)]*\)\s*\n\{', t):
            cls = m.group(1)
            if cls in sizes: continue
            body = t[m.end():m.end() + 1500]
            body = body[:body.find('\n}\n')] if '\n}\n' in body else body
            n = re.search(r'operator new\((0x[0-9A-F]+|\d+)u?\)', body)
            if n: sizes[cls] = int(n.group(1), 0)
    return sizes


def all_sizes():
    b = binary_sizes()
    known = set(stock_vtables(stock_vtable_dumps()))
    classes = sorted(c for c in b if c in known)
    T = ROOT / 'third_party' / 'llvm-mingw-20240619-ucrt-x86_64' / 'bin' / 'i686-w64-mingw32-clang++.exe'
    R = ROOT / 'out' / 'cocos-i686' / 'cocos' / 'CMakeFiles' / 'cocos2d.dir'
    flags = (R / 'flags.make').read_text()
    defs = re.search(r'CXX_DEFINES = (.*)', flags).group(1).split()
    cxx = re.search(r'CXX_FLAGS = (.*)', flags).group(1).replace(';-std=c++11', '').split()
    C = ROOT / 'third_party' / 'cocos2d-x-cocos2d-x-3.2' / 'cocos'
    it = 0
    while True:
        it += 1; src = ROOT / 'out' / f'all_sizes_{it}.cpp'   # a fresh file each pass (a just-written one can stay locked)   # drop classes that do not compile here (platform-only headers), then build
        lines = ['#include <cstdio>', '#include "cocos2d.h"', '#include "ui/CocosGUI.h"', '#include "cocostudio/CocoStudio.h"',
                 '#include "extensions/cocos-ext.h"', 'int main() {']
        lines += [f'    std::printf("%s %u\\n", "{c}", unsigned(sizeof({c})));' for c in classes] + ['}']
        src.write_text('\n'.join(lines))
        r = subprocess.run([str(T)] + cxx + defs + [f'@{R / "includes_CXX.rsp"}', f'-I{C / "editor-support"}', f'-I{C / "ui"}',
                            f'-I{C.parent}', '-static', str(src), '-o', str(ROOT / 'out' / f'all_sizes_{it}.exe')],
                           capture_output=True, text=True, cwd=str(R.parent.parent))
        bad = {int(x) for x in re.findall(r'all_sizes_\d+\.cpp:(\d+):\d+: error', r.stderr)}
        if r.returncode == 0: break
        if not bad: raise SystemExit(r.stderr[-2000:])
        classes = [c for k, c in enumerate(classes) if k + 7 not in bad]
    out = subprocess.run([str(ROOT / 'out' / f'all_sizes_{it}.exe')], capture_output=True, text=True).stdout
    stock = {l.split()[0]: int(l.split()[1]) for l in out.splitlines() if l.strip()}
    return {c: (stock[c], b[c]) for c in stock}


def stock_layouts():
    """{class: {field: offset}} (direct members) from clang -fdump-record-layouts of the size program."""
    cache = ROOT / 'out' / 'vt' / 'layouts.txt'
    if not cache.exists():
        T = ROOT / 'third_party' / 'llvm-mingw-20240619-ucrt-x86_64' / 'bin' / 'i686-w64-mingw32-clang++.exe'
        R = ROOT / 'out' / 'cocos-i686' / 'cocos' / 'CMakeFiles' / 'cocos2d.dir'
        flags = (R / 'flags.make').read_text()
        defs = re.search(r'CXX_DEFINES = (.*)', flags).group(1).split()
        cxx = re.search(r'CXX_FLAGS = (.*)', flags).group(1).replace(';-std=c++11', '').split()
        C = ROOT / 'third_party' / 'cocos2d-x-cocos2d-x-3.2' / 'cocos'
        src = max((ROOT / 'out').glob('all_sizes_*.cpp'), key=lambda p: p.stat().st_mtime)
        r = subprocess.run([str(T)] + cxx + defs + [f'@{R / "includes_CXX.rsp"}', f'-I{C / "editor-support"}', f'-I{C / "ui"}',
                           f'-I{C.parent}', '-fsyntax-only', '-Xclang', '-fdump-record-layouts', str(src)],
                           capture_output=True, text=True, errors='replace', cwd=str(R.parent.parent))
        cache.write_text(r.stdout, encoding='utf-8')
    out, cur = {}, None
    for l in cache.read_text(errors='replace').splitlines():
        m = re.match(r'\s*0 \| (?:class|struct) (\S+)$', l)
        if m: cur = m.group(1); out.setdefault(cur, {}); continue
        if cur is None: continue
        m = re.match(r'\s*(\d+)(?::[\d-]+)? \|   (?! )(.*?) (_\w+)$', l)
        if m: out[cur].setdefault(m.group(3), int(m.group(1)))
        elif not l.strip(): cur = None
    return out


def game_getter_offsets(cls):
    """{field guessed from the getter name: offset} from the decompile's one-line getters of `cls`."""
    import glob
    src = ROOT.parent / 'Input' / '1.0.1' / 'libcocos2dcpp_decompile' / 'decompile'
    if not hasattr(game_getter_offsets, 'text'):
        game_getter_offsets.text = ''.join(open(f, encoding='utf-8', errors='replace').read() for f in sorted(glob.glob(str(src / '*.c'))))
    t = game_getter_offsets.text
    out = {}
    for m in re.finditer(r'\n[^\n]*\b' + re.escape(cls) + r'::(get|is)(\w+)\((?:const )?' + re.escape(cls) +
                         r' \*this\)\s*\n\{\s*\n\s*return (.{0,80});\s*\n\}', t):
        name, expr = m.group(2), m.group(3)
        o = re.fullmatch(r'\*\(\((_DWORD|_BYTE|unsigned __int8|float|int|_WORD|unsigned __int16) \*\)this \+ (\d+)\)', expr) \
            or re.fullmatch(r'\(char \*\)this \+ (\d+)', expr)
        if not o: continue
        if o.lastindex == 2:
            unit = {'_BYTE': 1, 'unsigned __int8': 1, '_WORD': 2, 'unsigned __int16': 2}.get(o.group(1), 4)
            off = int(o.group(2)) * unit
        else: off = int(o.group(1))
        field = '_' + name[0].lower() + name[1:]
        out[field] = off
    return out


def field_shifts(cls, layouts):
    """[(stock offset, game offset, field)] for the getters of `cls` that name a stock field."""
    st = layouts.get(cls, {})
    rows = [(st[f], o, f) for f, o in game_getter_offsets(cls).items() if f in st]
    return sorted(rows)
