"""Generate the game -> engine adapters: one per rwlib:: binding (recomp/rewrite/include/rw/lib.hpp) that our engine
build defines, from its mangled signature. -> out/gen/lib_adapters.cpp (khux_lib_adapters[], khux_lib_adapter_count)

python tools/gen_adapters.py [--exclude ns,ns]   # e.g. cocos2d::network,CocosDenshion until curl / websockets are built

Entries that do not compile (protected members, variadic functions, abstract classes, ...) are dropped and listed in
out/gen/lib_adapters_dropped.txt with the compiler's reason; bindings our build does not define (LWF, OpenSSL,
Tremor, ...: libraries not built yet) are listed in out/gen/lib_adapters_missing.txt.
"""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'third_party' / 'llvm-mingw-20240619-ucrt-x86_64' / 'bin'
CXX = str(BIN / 'i686-w64-mingw32-clang++.exe')
ENGINE = ROOT / 'out' / 'cocos-i686'
R = ENGINE / 'cocos' / 'CMakeFiles' / 'cocos2d.dir'
RECOMP = next(p for p in (ROOT.parent / 'recomp', ROOT / 'recomp') if (p / 'rewrite' / 'include' / 'rw' / 'lib.hpp').exists())
OUT = ROOT / 'out' / 'gen'
INCLUDES = ['string', 'vector', 'map', 'unordered_map', 'set', 'list', 'deque', 'functional', 'memory', 'sstream',
            'algorithm', 'mutex', 'thread', 'condition_variable', 'chrono', 'regex', 'locale', 'cocos2d.h', 'ui/CocosGUI.h', 'cocostudio/CocoStudio.h', 'extensions/cocos-ext.h', 'network/HttpClient.h',
            'network/WebSocket.h', 'base/base64.h', 'zlib.h']


def bindings():
    out, seen = [], set()
    for m in re.finditer(r'inline constexpr uint32_t (\w+) = 0x([0-9A-F]+);\s+// (\S+)', (RECOMP / 'rewrite' / 'include' / 'rw' / 'lib.hpp').read_text()):
        out.append((int(m.group(2), 16), m.group(1), m.group(3))); seen.add(int(m.group(2), 16))
    needed = OUT / 'needed.tsv'                            # tools/audit_gaps.py: every named library function reached
    if needed.exists():
        for line in needed.read_text().splitlines():
            a, m = line.split('	')
            if int(a, 16) not in seen: out.append((int(a, 16), m, m)); seen.add(int(a, 16))
    return out


def defined_symbols():
    libs = sorted((ENGINE / 'lib').glob('*.a')) + sorted((ROOT / 'out' / 'deps' / 'lib').glob('*.a'))
    libs += [ROOT / 'third_party' / 'llvm-mingw-20240619-ucrt-x86_64' / 'i686-w64-mingw32' / 'lib' / n for n in ('libc++.a',)]
    out = subprocess.run([str(BIN / 'llvm-nm.exe'), '--defined-only', '-j'] + [str(p) for p in libs], capture_output=True, text=True).stdout
    return {s[1:] if s.startswith('_') else s for s in out.split()}


def demangle(names):
    r = subprocess.run([str(BIN / 'llvm-cxxfilt.exe')], input='\n'.join(names), capture_output=True, text=True)
    return r.stdout.splitlines()


def split_sig(d):
    """'A::B::f(int, X const&) const' -> ('A::B', 'f', 'int, X const&', True); None if it cannot tell."""
    if not d.endswith(')') and not d.endswith(') const'): return None
    const = d.endswith(' const')
    body = d[:-6] if const else d
    depth, i = 0, len(body) - 1
    while i >= 0:
        if body[i] == ')': depth += 1
        elif body[i] == '(':
            depth -= 1
            if depth == 0: break
        i -= 1
    name, params = body[:i], body[i + 1:-1]
    parts = top_split(name)
    if not parts or '<' in parts[-1]: return None           # a function template: not handled
    if ' ' in parts[0]: parts[0] = parts[0].rsplit(' ', 1)[-1]   # a return type before a template's name
    if len(parts) == 1: return '', parts[0], params, const
    return '::'.join(parts[:-1]), parts[-1], params, const


def top_split(name):
    """'a::b<c::d>::e' -> ['a', 'b<c::d>', 'e']: '::' outside template arguments only."""
    out, depth, cur, i = [], 0, '', 0
    while i < len(name):
        c = name[i]
        if c == '<': depth += 1
        elif c == '>': depth -= 1
        if depth == 0 and name.startswith('::', i):
            out.append(cur); cur = ''; i += 2; continue
        cur += c; i += 1
    out.append(cur)
    return out


def entry(addr, mangled, d):
    s = split_sig(d)
    if not s: return None
    scope, leaf, params, const = s
    if '...' in params: return None                          # variadic: by hand
    params = '' if params == 'void' else params
    cls_leaf = top_split(scope)[-1].split('<')[0] if scope else ''   # the class's name without template arguments
    if leaf == cls_leaf:                                     # constructor
        return f'khux::adapt_ctor<{scope}{", " + params if params else ""}>'
    if leaf == '~' + cls_leaf:                               # destructor
        return f'khux::adapt_delete<{scope}>' if 'D0Ev' in mangled else f'khux::adapt_dtor<{scope}>'
    pick = 'pick_c' if const else 'pick'
    is_class = bool(scope) and top_split(scope)[-1][:1].isupper()
    if is_class:   # through a local subclass that re-exports it: protected members are reachable, as from a subclass
        return (f'[](const uint32_t *a, int n) -> uint64_t {{ struct X : {scope} {{ using {scope}::{leaf}; }}; '
                f'return khux::adapt(khux::sel<{params}>::{pick}(&X::{leaf}), a, n); }}')
    target = f'&{scope}::{leaf}' if scope else f'&::{leaf}'
    return f'[](const uint32_t *a, int n) -> uint64_t {{ return khux::adapt(khux::sel<{params}>::{pick}({target}), a, n); }}'


HEADER = '''// Generated by tools/gen_adapters.py - do not edit. The game -> engine adapters, one per rwlib:: binding.
#include "adapt.hpp"
{includes}

namespace khux {{
// the overload with exactly these parameters (P is fixed, not deduced)
template <class... P> struct sel {{
    template <class Rr, class C> static auto pick(Rr (C::*f)(P...)) {{ return f; }}
    template <class Rr> static auto pick(Rr (*f)(P...)) {{ return f; }}
    template <class Rr, class C> static auto pick_c(Rr (C::*f)(P...) const) {{ return f; }}
}};
}}

using namespace cocos2d;
'''


def compile_flags():
    flags = (R / 'flags.make').read_text()
    defs = [d for d in re.search(r'CXX_DEFINES = (.*)', flags).group(1).split() if d not in ('-D_USRDLL', '-DCOCOS2DXWIN32_EXPORTS')]
    cxx = [f for f in re.search(r'CXX_FLAGS = (.*)', flags).group(1).replace(';-std=c++11', '').split() if not f.startswith('-std=')]
    C = ROOT / 'third_party' / 'cocos2d-x-cocos2d-x-3.2'
    return cxx + defs + ['-std=gnu++17', '-D_LIBCPP_ENABLE_CXX17_REMOVED_FEATURES', '-w', f'@{R / "includes_CXX.rsp"}',
                         f'-I{C / "cocos" / "editor-support"}', f'-I{C / "cocos" / "ui"}', f'-I{C}', f'-I{ROOT / "src"}']


def excluded():
    if '--exclude' not in sys.argv: return ()
    return tuple(x + '::' for x in sys.argv[sys.argv.index('--exclude') + 1].split(','))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    have = defined_symbols()
    b = bindings()
    ex = excluded()
    # a C++ function needs no symbol in our libraries when it is a template or inline: the adapter's call generates
    # it (std::string members, cocos2d::Vector<T>, Vec2's inline constructors, ...). Compiling decides; C functions
    # must be defined in what we link.
    cxx_ok = lambda m: m.startswith('_Z') and not m.startswith(('_ZN3LWF', '_ZN7cocos2d6plugin'))
    ours = [(a, n, m) for a, n, m in b if m in have or cxx_ok(m)]
    missing = [(a, n, m) for a, n, m in b if not (m in have or cxx_ok(m))]
    dem = dict(zip([m for _, _, m in ours], demangle([m for _, _, m in ours])))
    rows, skipped = [], []
    for a, n, m in ours:
        if dem[m].startswith(ex) if ex else False:
            skipped.append((n, dem[m], 'excluded')); continue
        e = entry(a, m, dem[m])
        (rows.append((a, n, m, e)) if e else skipped.append((n, dem[m], 'not generated (variadic / template / unreadable)')))
    dropped = []
    flags = compile_flags()
    for it in range(30):
        head = HEADER.format(includes='\n'.join(f'#include "{h}"' for h in INCLUDES))
        lines = head.splitlines()
        first = len(lines) + 2
        body = ['', 'extern const khux::AdapterEntry khux_lib_adapters[] = {']
        body += [f'    {{0x{a:X}, {e}, "{n}"}},' for a, n, m, e in rows]
        body += ['};', f'extern const int khux_lib_adapter_count = {len(rows)};', '']
        src = OUT / 'lib_adapters.cpp'
        src.write_text('\n'.join(lines + body), encoding='utf-8')
        r = subprocess.run([CXX] + flags + ['-c', str(src), '-o', str(OUT / 'lib_adapters.o'), '-ferror-limit=0'],
                           capture_output=True, text=True, cwd=str(ENGINE))
        if r.returncode == 0: break
        bad = {}
        # an error is reported where it happens (often in adapt.hpp); the entry is the first line of this file
        # named after it (the error itself or an "in instantiation ... requested here" note)
        why = None
        for line in r.stderr.splitlines():
            m = re.search(r': error: (.*)', line)
            if m:
                why = m.group(1)
                if 'lib_adapters.cpp' not in line: continue
            m = re.search(r'lib_adapters\.cpp:(\d+):\d+: (?:error|note)', line)
            if m and why:
                k = int(m.group(1)) - first - 1
                if 0 <= k < len(rows): bad.setdefault(k, why); why = None
        if not bad: sys.exit('compile failed outside the entries:\n' + r.stderr[-3000:])
        dropped += [(rows[k][1], dem[rows[k][2]], why) for k, why in bad.items()]
        rows = [row for k, row in enumerate(rows) if k not in bad]
    (OUT / 'lib_adapters_dropped.txt').write_text('\n'.join(f'{n}\t{d}\t{w}' for n, d, w in dropped + skipped), encoding='utf-8')
    (OUT / 'lib_adapters_missing.txt').write_text('\n'.join(f'{n}\t{m}' for a, n, m in missing), encoding='utf-8')
    print(f'{len(b)} bindings: {len(rows)} adapters generated and compiled, {len(dropped)} dropped (compile), '
          f'{len(skipped)} not generated, {len(missing)} not in our build yet')


if __name__ == '__main__':
    main()
