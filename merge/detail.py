import json, sys, collections, xxhash, oead
from pathlib import Path
from bcml import util
sys.path.insert(0, "/dev/shm/sw2"); import scan2
W = util.get_hash_table(True); N = util.get_hash_table(False)
root = Path(sys.argv[1]); t = json.load(open(sys.argv[2]))
def unyaz(d):
    d = bytes(d)
    return bytes(oead.yaz0.decompress(d)) if d[:4] == b"Yaz0" else d
def get(name):
    parts = name.split("//"); d = (root / parts[0]).read_bytes()
    for p in parts[1:]:
        buf = unyaz(d); d = bytes(oead.Sarc(buf).get_file(p).data)
    return unyaz(d)
res = collections.Counter(); rows = []
for n in t["wiiu"] + [u[0] for u in t["unknown"]]:
    if "//" in n and any(x in n for x in ("//blyt/", "//timg/", "//anim/")): continue
    d = get(n); leaf = n.split("//")[-1] if "//" in n else util.get_canon_name(n)
    canon = leaf.replace(".s", "."); h = xxhash.xxh64_intdigest(d)
    st = "wiiu-stock" if h in W.get(canon, []) else ("in-wiiu-table-modded" if canon in W else "new")
    nx = "nx-table" if canon in N else "not-in-nx"
    res[(n.rsplit(".", 1)[-1], st, nx)] += 1; rows.append([n, st, nx, len(d)])
for k, v in sorted(res.items()): print(k, v)
for r in rows:
    if not r[0].endswith(("sblwp", "sbfres", "shknm2", "shksc")) or "Shrine" not in r[0]: print(r)
json.dump(rows, open(sys.argv[3], "w"), indent=0)
