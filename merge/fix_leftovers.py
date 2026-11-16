#!/usr/bin/env python3
"""Leftover fixes on the converted Second Wind tree (in place), each logged to fix_leftovers.json:
 - drop the Wii U layout archives (.sblarc) from the partial packs so the stock Switch archive is used (mod change lost)
 - endian-convert Sound/LoopAssetList.blal and Ecosystem/LoadBalancer.sbeco (mod changes kept)
 - replace Wii U stock audio (.bars) and effect (.sesetlist) entries in event packs with the stock Switch entry"""
import sys, json, hashlib, xxhash
from pathlib import Path
import oead
sys.path.insert(0, str(Path(__file__).parent)); import smallconv, scan2
from bcml import util

MOD = Path(sys.argv[1]); GAME = Path(sys.argv[2]); LOG = []
NX = util.get_hash_table(False); WU = util.get_hash_table(True)
def unyaz(d):
    d = bytes(d); return bytes(oead.yaz0.decompress(d)) if d[:4] == b"Yaz0" else d
def sha(d): return hashlib.sha256(bytes(d)).hexdigest()

def rewrite(path, fn):
    raw = path.read_bytes(); yaz = raw[:4] == b"Yaz0"; buf = unyaz(raw); s = oead.Sarc(buf)
    w = oead.SarcWriter.from_sarc(s); w.set_endianness(oead.Endianness.Little)
    if fn(s, w):
        out = bytes(w.write()[1]); path.write_bytes(bytes(oead.yaz0.compress(out)) if yaz else out)

# 1+2: partial packs
for rel in ["01007EF00011E000/romfs/Pack/Bootup.pack", "01007EF00011E000/romfs/Pack/Title.pack", "options/Shrine Overhaul/01007EF00011E000/romfs/Pack/Bootup.pack"]:
    def fn(s, w, rel=rel):
        ch = False
        for f in list(s.get_files()):
            d = unyaz(f.data); kind, plat = scan2.classify(d)
            if f.name.endswith(".sblarc") and plat == "WIIU":
                inner = [x.name for x in oead.Sarc(d).get_files()]
                del w.files[f.name]; ch = True
                LOG.append(dict(action="dropped (stock Switch file will be used; mod change LOST)", file=rel + "//" + f.name, mod_sha256=sha(d), mod_size=len(d),
                                wiiu_entries=len(inner), layouts=[x for x in inner if x.endswith(".bflyt")], textures=[x for x in inner if x.endswith(".bflim")], anims=len([x for x in inner if x.endswith(".bflan")])))
            elif kind == "blal" and plat == "WIIU":
                n = smallconv.blal_be_to_le(d); w.files[f.name] = n; ch = True
                LOG.append(dict(action="endian-converted", file=rel + "//" + f.name, before=sha(d), after=sha(n)))
            elif kind == "beco" and plat == "WIIU":
                n = smallconv.beco_be_to_le(d); w.files[f.name] = bytes(oead.yaz0.compress(n)) if bytes(f.data)[:4] == b"Yaz0" else n; ch = True
                LOG.append(dict(action="endian-converted", file=rel + "//" + f.name, before=sha(d), after=sha(n)))
        return ch
    rewrite(MOD / rel, fn)

# 3: event packs. index stock Switch entries by leaf name
want = {}
ev = MOD / "01007EF00011E000/romfs/Event"
for p in sorted(ev.glob("*.sbeventpack")):
    buf = unyaz(p.read_bytes())
    for f in oead.Sarc(buf).get_files():
        d = unyaz(f.data); kind, plat = scan2.classify(d)
        if plat == "WIIU": want.setdefault(f.name, []).append(p)
stock = {}
for p in sorted((GAME / "Event").glob("*.sbeventpack")):
    buf = unyaz(p.read_bytes())
    for f in oead.Sarc(buf).get_files():
        if f.name in want and f.name not in stock:
            d = unyaz(f.data); canon = f.name.replace(".s", ".")
            if scan2.classify(d)[1] == "NX" and xxhash.xxh64_intdigest(d) in NX.get(canon, []): stock[f.name] = (bytes(f.data), p.name)
for name in want:
    if name not in stock and (GAME / name).exists(): stock[name] = ((GAME / name).read_bytes(), "loose")
for name, packs in want.items():
    for p in packs:
        def fn(s, w, name=name, p=p):
            d = unyaz(s.get_file(name).data); canon = name.replace(".s", ".")
            is_wu_stock = xxhash.xxh64_intdigest(d) in WU.get(canon, [])
            if name in stock and is_wu_stock:
                w.files[name] = stock[name][0]
                LOG.append(dict(action="Wii U stock entry replaced with stock Switch entry (lossless)", file=str(p.relative_to(MOD)) + "//" + name, stock_from=stock[name][1], after=sha(unyaz(stock[name][0]))))
                return True
            LOG.append(dict(action="UNRESOLVED", file=str(p.relative_to(MOD)) + "//" + name, have_stock=name in stock, is_wiiu_stock=is_wu_stock)); return False
        rewrite(p, fn)
json.dump(LOG, open(sys.argv[3], "w"), indent=1)
import collections; print(collections.Counter(l["action"] for l in LOG))
for l in LOG: print(" ", l["action"][:28], "|", l["file"])
