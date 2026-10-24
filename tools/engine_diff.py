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
