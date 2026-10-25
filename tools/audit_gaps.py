"""Which functions the game code calls that nothing provides natively yet: no rewrite, no generated adapter, no import
implementation. Static: every function address in the rewrite's game-code sources (rwlib:: names and hex call
targets), import stubs resolved to their targets.

python tools/audit_gaps.py     -> grouped summary; the full list in out/gen/gaps.txt
"""
import collections, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_adapters as G

ROOT, OUT, RECOMP = G.ROOT, G.OUT, G.RECOMP
sys.path.insert(0, str(RECOMP / 'rewrite' / 'tools'))
import libsplit, unit


def main():
    idx = unit.load_index()
    entries = {int(a, 16) for a in idx}
    groups = libsplit.groups()
    a = json.loads((RECOMP / 'out' / 'analysis.json').read_text())
    alias = {int(k, 16): int(v['target'], 16) & ~1 for k, v in a['plt'].items() if v['target']}
    ext_name = {int(k, 16): v['name'] for k, v in a['plt'].items() if not v['target']}
    libvals = {int(v, 16): n for n, v in re.findall(r'inline constexpr uint32_t (\w+) = 0x([0-9A-F]+);',
                                                       (RECOMP / 'rewrite' / 'include' / 'rw' / 'lib.hpp').read_text())}
    src = RECOMP / 'rewrite' / 'src'
    rewritten, called = set(), collections.Counter()
    hexre = re.compile(r'\b0x([0-9A-Fa-f]{6,7})[uU]?\b')
    for f in src.rglob('*.[ch]pp'):
        t = f.read_text(encoding='utf-8', errors='replace')
        for x in re.findall(r'RW_FUNCTION(?:_NOVERIFY)?\(\s*(0x[0-9A-Fa-f]+)', t): rewritten.add(int(x, 16) & ~1)
        regs = [int(x, 16) & ~1 for x in re.findall(r'RW_FUNCTION(?:_NOVERIFY)?\(\s*(0x[0-9A-Fa-f]+)', t)]
        if regs and sum(1 for r in regs if groups.get(r)) * 2 > len(regs): continue   # library rewrite files
        for m in hexre.finditer(t):
            line = t[t.rfind('\n', 0, m.start()) + 1:m.start()]
            if 'RW_FUNCTION' in line or '//' in line: continue
            v = int(m.group(1), 16)
            if v & ~1 in entries or v in alias or v in ext_name: called[v] += 1
        for name in re.findall(r'rwlib::([\w:]+)', t):
            pass
    for v, n in libvals.items(): called[v] += 1                 # every binding is called by game code
    # what exists natively
    native = set()
    for line in (OUT / 'lib_adapters.cpp').read_text(errors='replace').splitlines():
        m = re.match(r'\s*\{0x([0-9A-F]+), ', line)
        if m: native.add(int(m.group(1), 16))
    imp_native = set()
    for line in (OUT / 'imports.cpp').read_text(errors='replace').splitlines():
        m = re.match(r'\s*\{0x([0-9A-F]+), \[\]', line)
        if m: imp_native.add(int(m.group(1), 16))
    hand = set(re.findall(r'IMPORT\((\w+)\)', (ROOT / 'src' / 'imports_hand.cpp').read_text()))
    gaps = collections.defaultdict(list)
    for v in called:
        if v in ext_name:
            if v not in imp_native and ext_name[v] not in hand: gaps['import: ' + ext_name[v]].append(v)
            continue
        t = alias.get(v, v)
        if v in native or t in native or (t & ~1) in rewritten: continue
        name = idx.get(f'{t & ~1:08X}', {}).get('name', '?')
        gaps[groups.get(t & ~1) or 'game'].append((t, name))
    lines, summary = [], []
    for k in sorted(gaps, key=lambda k: -len(gaps[k])):
        if k.startswith('import: '): continue
        summary.append(f'{len(gaps[k]):5}  {k}')
        lines += [f'{k}\t0x{t:X}\t{n}' for t, n in sorted(gaps[k])]
    imports = sorted(k[8:] for k in gaps if k.startswith('import: '))
    summary.append(f'{len(imports):5}  imports not implemented natively')
    lines += [f'import\t{n}' for n in imports]
    (OUT / 'gaps.txt').write_text('\n'.join(lines), encoding='utf-8')
    # every named library function the game code reaches (for gen_adapters.py: not only the rwlib:: bindings)
    rows = []
    for t in sorted({(alias.get(v, v) & ~1) for v in called if v not in ext_name}):
        e = idx.get(f'{t:08X}')
        if e and groups.get(t) and e['name'].startswith('_Z'):
            rows.append(f"0x{t | (1 if e['mode'] == 'thumb' else 0):X}\t{e['name']}")
    (OUT / 'needed.tsv').write_text('\n'.join(rows), encoding='utf-8')
    print('functions the game code calls that nothing provides natively, by library:')
    print('\n'.join(summary))


if __name__ == '__main__':
    main()
