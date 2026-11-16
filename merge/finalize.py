#!/usr/bin/env python3
"""Build /dev/shm/swfinal from the BCML export, then verify it.
usage: finalize.py <export dir> <final dir> <summary.json> [--fix-rstb]
 A  select: every exported file that differs from stock 1.6.0 (or is absent from it) is hard-linked into final/{romfs,aoc1}
 R  RSTB: recompute the size of every delivered / pack-nested resource with BCML's own calculator and compare with the table
 V  platform scan (scan2) with a stock-identical exemption, SARC/BYML/AAMP parse, Yaz0 decompress
 T  files.tsv"""
import sys, os, json, hashlib, collections, binascii, io, random
from pathlib import Path
from multiprocessing import Pool
import oead, xxhash
sys.path.insert(0, str(Path(__file__).parent)); import scan2
from bcml import util
from bcml.mergers import rstable
from rstb.util import read_rstb

EXPORT, FINAL, SUMMARY = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]); FIX = "--fix-rstb" in sys.argv
GAME, DLC = Path("/dev/shm/swgame"), Path("/dev/shm/swdlc")
VOLS = {"romfs": (EXPORT / "01007EF00011E000/romfs", GAME, ""), "aoc1": (EXPORT / "01007EF00011F001/romfs", DLC, "Aoc/0010/")}
RSTB_REL = "System/Resource/ResourceSizeTable.product.srsizetable"
ACTIVE_LANG_MSG = "Message/Msg_USen.product.sarc"

def unyaz(d):
    d = bytes(d); return bytes(oead.yaz0.decompress(d)) if d[:4] == b"Yaz0" else d
def sha(d): return hashlib.sha256(d).hexdigest()

def select(args):
    vol, rel = args; src, stockdir, prefix = VOLS[vol]; p = src / rel; data = p.read_bytes()
    canon = prefix + rel.replace(".s", "."); NX = util.get_hash_table(False); st = stockdir / rel
    row = dict(vol=vol, path=rel, size=len(data), sha256=sha(data), stock_sha256="-")
    if st.exists():
        sd = st.read_bytes(); row["stock_sha256"] = sha(sd)
        if sd == data: row["decision"] = "drop: byte-identical to pulled stock file"
        elif len(data) and unyaz(sd) == unyaz(data): row["decision"] = "drop: same content as pulled stock file after decompression"
        else: row["decision"] = "keep: modified"
    elif canon in NX:
        row["decision"] = "drop: content hash equals stock 1.6.0 (BCML hash table; stock file not pulled)" if len(data) and xxhash.xxh64_intdigest(unyaz(data)) in NX[canon] else "keep: modified (stock not pulled)"
    else: row["decision"] = "keep: added"
    return row

def is_modded(canon, data, is_aoc):
    if not util.is_file_modded(canon, data, True): return False
    if is_aoc and not util.is_file_modded("Aoc/0010/" + canon, data, True): return False
    return True

def walk(sarc, is_aoc, where, out):
    for f in sarc.get_files():
        canon = f.name.replace(".s", "."); ext = Path(canon).suffix
        if ext in rstable.EXCLUDE_EXTS or canon in rstable.EXCLUDE_NAMES: continue
        data = unyaz(f.data); modded = is_modded(canon, data, is_aoc); size = None
        if modded:
            size = rstable.calculate_size(canon, data, guess=True)
            if is_aoc and ext == ".bfres" and "Dungeon" in f.name: size += 1000
        out.append((["Aoc/0010/" + canon, canon] if is_aoc else [canon], size, modded, where + "//" + f.name))
        if modded and (ext in util.SARC_EXTS - rstable.SARC_EXCLUDES):
            try: sub = oead.Sarc(data)
            except Exception: continue
            walk(sub, is_aoc, where + "//" + f.name, out)

def resources(args):
    vol, rel = args; p = FINAL / vol / rel; out = []
    if p.stat().st_size == 0: return out
    prefix = "Aoc/0010/" if vol == "aoc1" else ""; canon = prefix + rel.replace(".s", ".")
    if p.suffix not in rstable.EXCLUDE_EXTS and canon not in rstable.EXCLUDE_NAMES:
        names = [canon] + ([rel.replace(".s", ".")] if vol == "aoc1" and rel.startswith("Map/MainField/") else [])
        out.append((names, rstable.calculate_size(p, guess=True), True, vol + "/" + rel))
    if p.suffix in util.SARC_EXTS - rstable.SARC_EXCLUDES:
        buf = unyaz(p.read_bytes())
        try: s = oead.Sarc(buf)
        except Exception: return out
        walk(s, vol == "aoc1", vol + "/" + rel, out)
    return out

def scan_one(args):
    vol, rel = args
    out = dict(counts=collections.Counter(), wiiu=[], unknown=[], errors=[], sarc_ok=0, byml_ok=0, aamp_ok=0)
    scan2.walk(vol + "/" + rel, (FINAL / vol / rel).read_bytes(), out)
    # exemption: a flagged leaf that is byte-identical to the same entry of the pulled stock container is stock Switch data
    keep_w, keep_u, exempt = [], [], 0
    def stock_leaf(name):
        parts = name.split("//"); v, r = parts[0].split("/", 1); st = VOLS[v][1] / r
        if not st.exists(): return None
        d = st.read_bytes()
        for part in parts[1:]:
            buf = unyaz(d)
            try: d = bytes(oead.Sarc(buf).get_file(part).data)
            except Exception: return None
        return unyaz(d)
    def mine(name):
        parts = name.split("//"); d = (FINAL / parts[0]).read_bytes()
        for part in parts[1:]:
            buf = unyaz(d); d = bytes(oead.Sarc(buf).get_file(part).data)
        return unyaz(d)
    for n in out["wiiu"]:
        s = stock_leaf(n)
        if s is not None and s == mine(n): exempt += 1
        else: keep_w.append(n)
    for u in out["unknown"]:
        s = stock_leaf(u[0])
        if s is not None and s == mine(u[0]): exempt += 1
        else: keep_u.append(u)
    out["wiiu"], out["unknown"], out["exempt"] = keep_w, keep_u, exempt
    return out

if __name__ == "__main__":
    scan2.PARSE = True
    summary = {}
    # ---------- A
    FINAL.mkdir(parents=True, exist_ok=True)
    for v in VOLS: assert not (FINAL / v).exists(), "final volume dirs must not exist yet"
    todo = [(v, str(f.relative_to(VOLS[v][0]))) for v in VOLS for f in sorted(VOLS[v][0].rglob("*")) if f.is_file()]
    with Pool(4, maxtasksperchild=200) as pool: rows = pool.map(select, todo, chunksize=16)
    kept = [r for r in rows if r["decision"].startswith("keep")]; dropped = [r for r in rows if not r["decision"].startswith("keep")]
    for r in kept:
        dst = FINAL / r["vol"] / r["path"]; dst.parent.mkdir(parents=True, exist_ok=True); os.link(VOLS[r["vol"]][0] / r["path"], dst)
    listed = {v: set(Path(__file__).with_name(f"stock_{v}_names.txt").read_text().split("\n")) for v in VOLS}
    xc = collections.Counter(("in stock listing" if r["path"] in listed[r["vol"]] else "not in stock listing") + " | " + r["decision"].split(":")[0] + ": " + r["decision"].split(":")[1].split("(")[0].strip() for r in rows)
    summary["stock_listing_crosscheck"] = xc
    assert not any(k.startswith("not in stock listing | keep: modified") or k.startswith("in stock listing | keep: added") for k in xc), xc
    summary["select"] = dict(exported=len(rows), kept=len(kept), dropped=len(dropped), by_decision=collections.Counter(r["vol"] + " | " + r["decision"] for r in rows),
                             dropped_files=[[r["vol"], r["path"], r["decision"]] for r in dropped])
    print("A:", json.dumps(summary["select"]["by_decision"], indent=1), flush=True)
    files = [(r["vol"], r["path"]) for r in kept]
    # ---------- R
    stock = read_rstb(str(GAME / RSTB_REL), False); tpath = FINAL / "romfs" / RSTB_REL; table = read_rstb(str(tpath), False)
    with Pool(4, maxtasksperchild=100) as pool: res = [x for l in pool.imap_unordered(resources, files, chunksize=8) for x in l]
    agg = {}
    for names, size, modded, where in res:
        for i, n in enumerate(names):
            a = agg.setdefault(n, dict(sizes=[], unmodded=0, primary=False, where=where))
            if modded: a["sizes"].append(size)
            else: a["unmodded"] += 1
            a["primary"] |= (i == 0)
    def expect(n, a):
        """returns ('absent', None) | ('value', v) | ('stock', None)"""
        if not a["sizes"]: return ("stock", None)
        s = max(a["sizes"])
        if n == ACTIVE_LANG_MSG: return ("absent", None)          # BCML drops the active language's message archive entry
        if s == 0: return ("absent", None) if a["primary"] or stock.is_in_table(n) else ("stock", None)
        if stock.is_in_table(n) and stock.get_size(n) >= s: return ("value", stock.get_size(n))
        return ("value", s)
    def check(tbl):
        bad = collections.defaultdict(list)
        for n, a in agg.items():
            kind, v = expect(n, a); have = tbl.get_size(n) if tbl.is_in_table(n) else None
            if kind == "stock": v = stock.get_size(n) if stock.is_in_table(n) else None
            if kind == "absent": v = None
            if have == v: continue
            if have is None: cat = "missing entry" + ("" if a["primary"] else " (secondary name)")
            elif v is None: cat = "entry present but BCML rule says remove (size not computable)" if a["sizes"] else "entry added for unmodified resource"
            elif have < v: cat = "entry smaller than computed size"
            else: cat = "entry larger than computed (stale)" if a["sizes"] else "entry differs from stock for unmodified resource"
            bad[cat].append([n, have, v, a["where"]])
        seen = {binascii.crc32(n.encode()) for n in agg}
        for crc, val in tbl.crc32_map.items():
            if crc not in seen and stock.crc32_map.get(crc) != val: bad["orphan entry (no delivered resource has this name)"].append([crc, val, stock.crc32_map.get(crc), ""])
        for crc, val in stock.crc32_map.items():
            if crc not in seen and crc not in tbl.crc32_map: bad["orphan removal (stock entry removed, no delivered resource)"].append([crc, None, val, ""])
        return bad
    SELF = "System/Resource/ResourceSizeTable.product.rsizetable"
    def self_size(tbl):
        buf = io.BytesIO(); tbl.write(buf, False); return rstable.calculate_size(SELF, buf.getvalue(), guess=True)
    if SELF in agg: agg[SELF]["sizes"] = [self_size(table)]      # the table's own entry: sized from the table as it will be written
    bad = check(table)
    summary["rstb"] = dict(stock_entries=len(stock.crc32_map) + len(stock.name_map), table_entries_before=len(table.crc32_map) + len(table.name_map), resource_occurrences=len(res), distinct_resource_names=len(agg),
                           modded_names=sum(1 for a in agg.values() if a["sizes"]), mismatches_before={k: len(v) for k, v in bad.items()}, mismatch_examples_before={k: v[:8] for k, v in bad.items()})
    print("R before:", json.dumps(summary["rstb"]["mismatches_before"], indent=1), flush=True)
    if FIX and bad:
        for cat, lst in bad.items():
            for n, have, v, where in lst:
                if cat.startswith("orphan"):
                    if v is None: del table.crc32_map[n]
                    else: table.crc32_map[n] = v
                elif v is None: table.delete_entry(n)
                else: table.set_size(n, v)
        if SELF in agg:
            for _ in range(3):                                   # entry count may have changed: settle the self entry
                agg[SELF]["sizes"] = [self_size(table)]; k, v = expect(SELF, agg[SELF])
                if table.is_in_table(SELF) and table.get_size(SELF) == v: break
                table.set_size(SELF, v)
        buf = io.BytesIO(); table.write(buf, False); new = bytes(oead.yaz0.compress(buf.getvalue()))
        tpath.unlink(); tpath.write_bytes(new)                      # was a hard link into the BCML store: replace, never rewrite in place
        table = read_rstb(str(tpath), False); bad2 = check(table)
        summary["rstb"].update(fixed=sum(len(v) for v in bad.values()), mismatches_after={k: len(v) for k, v in bad2.items()}, mismatch_examples_after={k: v[:8] for k, v in bad2.items()})
        print("R after:", json.dumps(summary["rstb"]["mismatches_after"]), flush=True)
    noentry = collections.Counter(); removed = collections.Counter()
    for n, a in agg.items():
        if a["sizes"] and expect(n, a)[0] == "absent":
            (removed if stock.is_in_table(n) else noentry)[n.rsplit(".", 1)[-1]] += 1
    summary["rstb"].update(stock_entries_removed_by_ext=removed, modded_resources_without_entry_by_ext=noentry)
    summary["rstb"].update(table_entries_final=len(table.crc32_map) + len(table.name_map),
                           changed_vs_stock=sum(1 for c, v in table.crc32_map.items() if c in stock.crc32_map and stock.crc32_map[c] != v),
                           added_vs_stock=sum(1 for c in table.crc32_map if c not in stock.crc32_map), removed_vs_stock=sum(1 for c in stock.crc32_map if c not in table.crc32_map))
    # independent spot check: 300 random modded resources, sizes recomputed straight from the delivered files, read back from the written table
    random.seed(1160); table = read_rstb(str(tpath), False)
    cand = [(names, where) for names, size, modded, where in res if modded and size]
    sample = random.sample(cand, min(300, len(cand))); spot_bad = []
    for names, where in sample:
        parts = where.split("//"); d = (FINAL / parts[0]).read_bytes()
        if len(parts) == 1: s = rstable.calculate_size(FINAL / parts[0], guess=True)
        else:
            for part in parts[1:]:
                buf = unyaz(d); d = bytes(oead.Sarc(buf).get_file(part).data)
            canon = parts[-1].replace(".s", "."); s = rstable.calculate_size(canon, unyaz(d), guess=True)
            if parts[0].startswith("aoc1/") and canon.endswith(".bfres") and "Dungeon" in parts[-1]: s += 1000
        n = names[0]
        if n == ACTIVE_LANG_MSG: continue
        if not table.is_in_table(n) or table.get_size(n) < s: spot_bad.append([n, table.get_size(n) if table.is_in_table(n) else None, s, where])
    summary["rstb"]["spot_check"] = dict(sampled=len(sample), entry_missing_or_too_small=len(spot_bad), examples=spot_bad[:10])
    print("R spot:", summary["rstb"]["spot_check"], flush=True)
    # ---------- V
    tot = dict(counts=collections.Counter(), wiiu=[], unknown=[], errors=[], sarc_ok=0, byml_ok=0, aamp_ok=0, exempt=0)
    with Pool(4, maxtasksperchild=50) as pool:
        for o in pool.imap_unordered(scan_one, [f for f in files if (FINAL / f[0] / f[1]).stat().st_size > 0], chunksize=8):
            tot["counts"].update(o["counts"])
            for k in ("wiiu", "unknown", "errors"): tot[k] += o[k]
            for k in ("sarc_ok", "byml_ok", "aamp_ok", "exempt"): tot[k] += o[k]
    plat = collections.Counter(); kinds = collections.Counter()
    for k, v in tot["counts"].items(): plat[k.split("|")[2]] += v; kinds[k.split("|")[1] + "|" + k.split("|")[2]] += v
    wiiu_names = [f"{v}/{p}" for v, p in files if ".Tex1." in p or ".Tex2." in p]
    summary["scan"] = dict(leaves_by_platform=plat, leaves_by_kind=dict(kinds.most_common()), wiiu_format_not_stock=sorted(tot["wiiu"]), unknown_not_stock=tot["unknown"][:50], unknown_not_stock_count=len(tot["unknown"]),
                           flagged_but_identical_to_stock_entry=tot["exempt"], errors=tot["errors"], sarc_opened=tot["sarc_ok"], byml_parsed=tot["byml_ok"], aamp_parsed=tot["aamp_ok"],
                           wiiu_texture_names=wiiu_names, zero_byte_files=[f"{v}/{p}" for v, p in files if (FINAL / v / p).stat().st_size == 0])
    print("V:", json.dumps({k: v for k, v in summary["scan"].items() if k not in ("leaves_by_kind",)}, indent=1)[:3000], flush=True)
    # ---------- T
    lines = []; per = collections.Counter(); size = collections.Counter()
    for r in sorted(kept, key=lambda r: (r["vol"], r["path"])):
        p = FINAL / r["vol"] / r["path"]; d = p.read_bytes()
        lines.append("\t".join([r["vol"], r["path"], str(len(d)), sha(d), r["stock_sha256"]])); per[r["vol"]] += 1; size[r["vol"]] += len(d)
    (FINAL / "files.tsv").write_text("\n".join(lines) + "\n")
    summary["deliverable"] = dict(files=per, bytes=size, with_stock_hash=sum(1 for r in kept if r["stock_sha256"] != "-"),
                                  by_top_dir=collections.Counter(r["vol"] + "/" + r["path"].split("/")[0] for r in kept), by_decision=collections.Counter(r["vol"] + " | " + r["decision"] for r in kept))
    SUMMARY.write_text(json.dumps(summary, indent=1, default=str)); print("T:", json.dumps(summary["deliverable"], indent=1))
