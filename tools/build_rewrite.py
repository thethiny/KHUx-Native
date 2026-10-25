"""Compile the rewrite's game code (recomp/rewrite/src) natively for i686 -> out/rewrite/obj/*.o

python tools/build_rewrite.py [--report N]

Compiles every source in parallel (incremental: only sources newer than their object, or whose headers changed) and
prints the errors grouped by message (the first N groups; default 25), so causes can be fixed in bulk.
"""
import collections, concurrent.futures, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'third_party' / 'llvm-mingw-20240619-ucrt-x86_64' / 'bin'
CXX = str(BIN / 'i686-w64-mingw32-clang++.exe')
RECOMP = next(p for p in (ROOT.parent / 'recomp', ROOT / 'recomp') if (p / 'rewrite' / 'include' / 'rw' / 'lib.hpp').exists())
SRC = RECOMP / 'rewrite' / 'src'
OUT = ROOT / 'out' / 'rewrite'
FLAGS = ['-std=gnu++17', '-O1', '-w', '-ferror-limit=50', f'-I{RECOMP / "rewrite" / "include"}', f'-I{SRC}',
         f'-I{RECOMP / "lift"}', f'-I{ROOT / "src"}', '-DKHUX_NATIVE=1']


def main():
    n_report = int(sys.argv[sys.argv.index('--report') + 1]) if '--report' in sys.argv else 25
    (OUT / 'obj').mkdir(parents=True, exist_ok=True)
    srcs = sorted(SRC.rglob('*.cpp'))
    headers = list((RECOMP / 'rewrite' / 'include').rglob('*.hpp')) + list(SRC.rglob('*.hpp')) + list(SRC.rglob('*.inc'))
    newest = max(p.stat().st_mtime for p in headers)
    def obj(s): return OUT / 'obj' / ('_'.join(s.relative_to(SRC).with_suffix('').parts) + '.o')
    todo = [s for s in srcs if not obj(s).exists() or obj(s).stat().st_mtime < max(s.stat().st_mtime, newest)]
    def cc(s):
        r = subprocess.run([CXX, '-c', str(s), '-o', str(obj(s))] + FLAGS, capture_output=True, text=True)
        return s, r.returncode, r.stderr
    with concurrent.futures.ThreadPoolExecutor(os.cpu_count()) as ex:
        res = list(ex.map(cc, todo))
    failed = [(s, e) for s, rc, e in res if rc]
    groups, example = collections.Counter(), {}
    for s, e in failed:
        for m in re.finditer(r'(\S+?):(\d+):\d+: error: (.*)', e):
            msg = re.sub(r"'[^']*'", "'X'", m.group(3))
            groups[msg] += 1
            example.setdefault(msg, f'{Path(m.group(1)).name}:{m.group(2)}: {m.group(3)}')
    print(f'{len(srcs)} sources, {len(todo)} compiled now, {len(failed)} failed; {sum(groups.values())} errors in '
          f'{len(groups)} kinds')
    for msg, n in groups.most_common(n_report):
        print(f'{n:6}  {example[msg][:200]}')
    (OUT / 'failed.txt').write_text('\n'.join(str(s.relative_to(SRC)) for s, _ in failed), encoding='utf-8')


if __name__ == '__main__':
    main()
