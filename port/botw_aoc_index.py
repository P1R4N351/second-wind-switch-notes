#!/usr/bin/env python3
"""Index the BotW DLC RomFS images on the Thor (tables read over adb) and write, per volume, runtime-index.bin, plus
aoc-config.txt as aoc_romfs.c reads it. Image hashes are computed on the device."""
import sys, struct, hashlib, subprocess
from pathlib import Path
SERIAL, OUT = sys.argv[1], Path(sys.argv[2])
SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCR / 'ba/games/totk/scripts'))
from extract_romfs import index_romfs   # noqa
def adb(*a): return subprocess.run(['adb', '-s', SERIAL, *a], check=True, capture_output=True).stdout
class AdbFile:
    def __init__(self, path): self.path, self.pos = path, 0; self.size = int(adb('shell', f'stat -c %s {path}').strip())
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def seek(self, off, whence=0): self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
    def tell(self): return self.pos
    def read(self, n=-1):
        if n < 0: n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0: return b''
        data = adb('exec-out', f'dd if={self.path} iflag=skip_bytes,count_bytes skip={self.pos} count={n} bs=1048576 2>/dev/null')
        assert len(data) == n, (len(data), n); self.pos += n; return data
class RemotePath:
    def __init__(self, path): self.f = AdbFile(path)
    def open(self, mode='rb'): return self.f
    def stat(self):
        class S: pass
        s = S(); s.st_size = self.f.size; return s
cfg = ['AOC_PRESENT_MASK 3']
for i in (1, 2):
    image = f'/data/local/tmp/botw/aoc{i}.romfs.bin'
    p = RemotePath(image); files = sorted(index_romfs(p), key=lambda f: f['path'].encode())
    strings = bytearray(); rows = bytearray()
    for item in files:
        name = item['path'].encode() + b'\0'; rows.extend(struct.pack('<QQII', item['offset'], item['size'], len(strings), len(name))); strings.extend(name)
    index = struct.pack('<8sQQ', b'TOTKRFS1', len(files), 24 + len(rows)) + rows + strings
    d = OUT / str(i); d.mkdir(parents=True, exist_ok=True); (d / 'runtime-index.bin').write_bytes(index)
    sha = adb('shell', f'sha256sum {image}').split()[0].decode()
    cfg += [f'AOC{i}_IMAGE_SIZE {p.f.size}', f'AOC{i}_IMAGE_SHA256 {sha}', f'AOC{i}_INDEX_SHA256 {hashlib.sha256(index).hexdigest()}']
    print(i, len(files), p.f.size, files[0]['path'], files[-1]['path'])
(OUT / 'aoc-config.txt').write_text('\n'.join(cfg) + '\n')
