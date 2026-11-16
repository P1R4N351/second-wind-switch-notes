#!/usr/bin/env python3
"""Index the merged BotW RomFS image that sits on the Thor, reading only its tables over adb, with the project's own
index_romfs(); write runtime-index.bin and romfs-config.txt the way scripts/prepare_romfs_backend.py does."""
import sys, json, struct, hashlib, subprocess
from pathlib import Path
SERIAL, OUT = sys.argv[1], Path(sys.argv[2])
SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCR / 'ba/games/totk/scripts'))
from extract_romfs import index_romfs   # noqa
IMAGE = '/data/local/tmp/botw/romfs.bin'

def adb(*a):
    return subprocess.run(['adb', '-s', SERIAL, *a], check=True, capture_output=True).stdout

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

p = RemotePath(IMAGE)
files = index_romfs(p)
pins = json.loads((SCR / 'cmp/mac/games/botw/assets/expected-v1.6.0.json').read_text())['romfs']
assert p.f.size == pins['size'], (p.f.size, pins['size'])
strings = bytearray(); rows = bytearray()
for item in files:
    name = item['path'].encode() + b'\0'; rows.extend(struct.pack('<QQII', item['offset'], item['size'], len(strings), len(name))); strings.extend(name)
index = struct.pack('<8sQQ', b'TOTKRFS1', len(files), 24 + len(rows)) + rows + strings
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'runtime-index.bin').write_bytes(index)
(OUT / 'romfs-config.txt').write_text(f'ROMFS_IMAGE_SIZE {pins["size"]}\nROMFS_IMAGE_SHA256 {pins["sha256"]}\nROMFS_INDEX_SHA256 {hashlib.sha256(index).hexdigest()}\n')
print(json.dumps({'files': len(files), 'expected_files': pins.get('files'), 'index_bytes': len(index), 'first': files[0]['path'], 'last': files[-1]['path']}))
