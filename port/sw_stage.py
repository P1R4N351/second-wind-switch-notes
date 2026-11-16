#!/usr/bin/env python3
"""Second Wind for the BotW port: (1) manifest.tsv for the base-game overlay, originals hashed on the Thor from romfs.bin
by index range; (2) a modded DLC volume plan: index entries for stock files kept, replaced ones repointed to bytes
appended after the stock image, added ones appended too. Writes $OUT/manifest.tsv, $OUT/aoc1/append.bin,
$OUT/aoc1/runtime-index.bin and prints the appended size (the device builds the image: stock image + append.bin)."""
import sys, struct, hashlib, subprocess
from pathlib import Path
SERIAL, SRC, OUT = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
SCR = Path(__file__).resolve().parent
def adb(*a, inp=None): return subprocess.run(['adb', '-s', SERIAL, *a], check=True, capture_output=True, input=inp).stdout
def read_index(data):
    magic, count, strings = struct.unpack_from('<8sQQ', data, 0); assert magic == b'TOTKRFS1'
    out = {}
    for i in range(count):
        off, size, name, ln = struct.unpack_from('<QQII', data, 24 + i * 24)
        out[data[strings + name:strings + name + ln - 1].decode()] = (off, size)
    return out
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''): h.update(b)
    return h.hexdigest()
OUT.mkdir(parents=True, exist_ok=True)
# ---- base overlay ----
index = read_index((SCR / 'bgd/runtime-index.bin').read_bytes()); folded = {n.lower(): n for n in index}
mod = SRC / 'romfs'; files = sorted(p for p in mod.rglob('*') if p.is_file())
repl = [p.relative_to(mod).as_posix() for p in files if p.relative_to(mod).as_posix() in index]
IMG = '/sdcard/Android/data/io.github.p1r4n351.botw/files/extracted/botw160/romfs/romfs.bin'
script = ''.join(f'dd if={IMG} iflag=skip_bytes,count_bytes skip={index[n][0]} count={index[n][1]} bs=1048576 2>/dev/null | sha256sum\n' for n in repl)
got = adb('shell', 'sh', inp=script.encode()).decode().split('\n')
orig = {n: got[i].split()[0] for i, n in enumerate(repl)}; assert len(orig) == len(repl) and all(len(v) == 64 for v in orig.values())
lines, same, added, misspelt = [], 0, 0, []
for p in files:
    n = p.relative_to(mod).as_posix(); h = sha(p)
    if n in index:
        if h == orig[n]: same += 1; continue
        lines.append(f'{n}\t{p.stat().st_size}\t{h}\t{orig[n]}')
    elif n.lower() in folded: misspelt.append((n, folded[n.lower()]))
    else: lines.append(f'{n}\t{p.stat().st_size}\t{h}\t-'); added += 1
(OUT / 'manifest.tsv').write_text('\n'.join(lines) + '\n')
print('base: lines', len(lines), 'added', added, 'replaced', len(lines) - added, 'same-as-stock', same, 'misspelt', misspelt[:5], len(misspelt))
# ---- DLC volume 1 ----
aidx = read_index((SCR / 'baoc/1/runtime-index.bin').read_bytes()); afold = {n.lower(): n for n in aidx}
stock_size = 1390370680; amod = SRC / 'aoc1'; (OUT / 'aoc1').mkdir(exist_ok=True)
entries = dict(aidx); pos = stock_size; nrep = nadd = 0; bad = []
with open(OUT / 'aoc1/append.bin', 'wb') as app:
    for p in sorted(q for q in amod.rglob('*') if q.is_file()):
        n = p.relative_to(amod).as_posix(); data = p.read_bytes()
        if n not in aidx and n.lower() in afold: bad.append(n); continue
        nrep += n in aidx; nadd += n not in aidx
        entries[n] = (pos, len(data)); app.write(data); pos += len(data)
names = sorted(entries, key=lambda s: s.encode()); strings = bytearray(); rows = bytearray()
for n in names:
    b = n.encode() + b'\0'; rows.extend(struct.pack('<QQII', entries[n][0], entries[n][1], len(strings), len(b))); strings.extend(b)
idx = struct.pack('<8sQQ', b'TOTKRFS1', len(names), 24 + len(rows)) + rows + strings
(OUT / 'aoc1/runtime-index.bin').write_bytes(idx)
(OUT / 'aoc1/info.txt').write_text(f'IMAGE_SIZE {pos}\nINDEX_SHA256 {hashlib.sha256(idx).hexdigest()}\n')
print('aoc1: files', len(names), 'replaced', nrep, 'added', nadd, 'case-clash', bad, 'image size', pos, 'append', pos - stock_size)
