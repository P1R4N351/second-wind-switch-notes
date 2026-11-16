#!/usr/bin/env python3
"""Count what is still Wii U (big-endian) in the converted Second Wind tree."""
import sys, json, collections
from pathlib import Path
import oead
from bcml import util

root = Path(sys.argv[1])
c = collections.Counter(); left = collections.Counter(); examples = collections.defaultdict(list)

def endian(name, data):
    data = bytes(data)
    if data[:4] == b"Yaz0": data = util.decompress(data)
    m = data[:4]
    if m == b"SARC": return "LE" if data[6:8] == b"\xff\xfe" else "BE"
    if m[:2] == b"BY": return "BE"
    if m[:2] == b"YB": return "LE"
    if m == b"FRES": return "LE" if data[4:8] == b"    " else "BE"      # Switch BFRES: 'FRES    '
    if data[:8] == b"\x57\xe0\xe0\x57\x10\xc0\xc0\x10": return "LE" if data[0x11] == 1 else "BE"   # Havok packfile
    if m in (b"FSTM", b"FWAV", b"FSTP", b"BARS", b"FSAR"): return "BE" if data[4:6] == b"\xfe\xff" else "LE"
    if m == b"AAMP": return "LE"
    return None

def walk(name, data, depth=0):
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    e = endian(name, data)
    if e:
        c[(ext, e)] += 1
        if e == "BE":
            left[ext] += 1
            if len(examples[ext]) < 3: examples[ext].append(name)
    raw = bytes(data)
    if raw[:4] == b"Yaz0":
        try: raw = util.decompress(raw)
        except Exception: return
    if raw[:4] == b"SARC" and depth < 4:
        try:
            for f in oead.Sarc(raw).get_files(): walk(name + "//" + f.name, f.data, depth + 1)
        except Exception as ex: c[("sarc-error", str(ex)[:30])] += 1

files = [f for f in root.rglob("*") if f.is_file() and "logs" not in f.parts]
for f in files: walk(str(f.relative_to(root)), f.read_bytes())
out = {"files": len(files), "still_big_endian_by_ext": dict(left.most_common()), "examples": examples,
       "by_ext_endian": {f"{k[0]}:{k[1]}": v for k, v in sorted(c.items(), key=lambda kv: -kv[1])[:60]}}
print(json.dumps(out, indent=1))
