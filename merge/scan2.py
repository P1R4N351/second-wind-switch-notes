#!/usr/bin/env python3
"""Deep platform scan: walk a tree, recurse into SARCs, classify every leaf as NX / WIIU / neutral / unknown.
usage: scan2.py <root> <out.json> [--parse]   (--parse also parses every BYML/AAMP and opens every SARC)"""
import sys, json, collections, struct
from pathlib import Path
from multiprocessing import Pool
import oead

PARSE = "--parse" in sys.argv

def classify(d):
    m = d[:4]
    if m == b"SARC": return ("sarc", "NX" if d[6:8] == b"\xff\xfe" else "WIIU")
    if m[:2] == b"BY" and d[2:4] in (b"\x00\x02", b"\x00\x03", b"\x00\x04"): return ("byml", "WIIU")
    if m[:2] == b"YB" and d[2:4] in (b"\x02\x00", b"\x03\x00", b"\x04\x00"): return ("byml", "NX")
    if m == b"AAMP": return ("aamp", "NX" if d[4:8] == b"\x02\x00\x00\x00" else "WIIU")
    if m == b"FRES": return ("bfres", "NX" if d[4:8] == b"    " else "WIIU")
    if d[:8] == b"\x57\xe0\xe0\x57\x10\xc0\xc0\x10": return ("havok", "NX" if (d[0x11] == 1 and d[0x10] == 8) else "WIIU")
    if m == b"BARS": return ("bars", "WIIU" if d[8:10] == b"\xfe\xff" else "NX")
    if m == b"BLAL": return ("blal", "WIIU" if d[4:6] == b"\xfe\xff" else "NX")
    if m == b"\x00\x11\x22\x33": return ("beco", "WIIU")
    if m == b"\x33\x22\x11\x00": return ("beco", "NX")
    if m in (b"FSTM", b"FWAV", b"FSTP", b"FSAR", b"FLYT", b"FLAN", b"FLIM", b"FFNT", b"FGRP", b"FWSD", b"FBNK", b"FSEQ", b"FWAR"):
        return (m.decode().lower(), "WIIU" if d[4:6] == b"\xfe\xff" else "NX")
    if d[:8] == b"MsgStdBn": return ("msbt", "WIIU" if d[8:10] == b"\xfe\xff" else "NX")
    if m == b"EFTB": return ("effect-eftb", "WIIU")
    if m == b"VFXB": return ("effect-vfxb", "NX")
    if m == b"BNTX": return ("bntx", "NX")
    if m == b"Gfx2": return ("gtx", "WIIU")
    if m == b"BNSH": return ("bnsh", "NX")
    if m == b"FSHA": return ("fsha", "WIIU")
    if m == b"PrOD": return ("blwp", "neutral")   # big-endian on Switch too (stock 1.6.0 Dungeon000 checked)
    if d[:6] == b"BFEVFL": return ("bfevfl", "neutral")
    if m == b"RSTB" or m == b"RSTC": return ("rstb", "neutral")
    if m == b"AMTA": return ("amta", "WIIU" if d[4:6] == b"\xfe\xff" else "NX")
    if m == b"\xff\xd8\xff\xe0" or m[:3] == b"\xff\xd8\xff": return ("jpeg", "neutral")
    if m == b"\x89PNG": return ("png", "neutral")
    return (None, "unknown")

def walk(name, raw, out, depth=0):
    d = bytes(raw); ext = name.rsplit(".", 1)[-1] if "." in name.rsplit("/", 1)[-1] else ""
    if d[:4] == b"Yaz0":
        try: d = bytes(oead.yaz0.decompress(d))
        except Exception as e:
            out["errors"].append([name, "yaz0: " + str(e)[:80]]); return
    kind, plat = classify(d)
    if kind is None:
        try:
            d.decode("utf-8"); kind, plat = "text", "neutral"
        except Exception: kind = "?" + d[:4].hex()
    out["counts"][f"{ext}|{kind}|{plat}"] += 1
    if plat == "WIIU": out["wiiu"].append(name)
    if plat == "unknown": out["unknown"].append([name, d[:8].hex(), len(d)])
    if kind == "sarc":
        try: s = oead.Sarc(d)
        except Exception as e:
            out["errors"].append([name, "sarc: " + str(e)[:80]]); return
        out["sarc_ok"] += 1
        for f in s.get_files(): walk(name + "//" + f.name, f.data, out, depth + 1)
    elif PARSE and kind == "byml" and plat == "NX":
        try: oead.byml.from_binary(d); out["byml_ok"] += 1
        except Exception as e: out["errors"].append([name, "byml: " + str(e)[:80]])
    elif PARSE and kind == "aamp" and plat == "NX":
        try: oead.aamp.ParameterIO.from_binary(d); out["aamp_ok"] += 1
        except Exception as e: out["errors"].append([name, "aamp: " + str(e)[:80]])

def one(args):
    root, rel = args
    out = dict(counts=collections.Counter(), wiiu=[], unknown=[], errors=[], sarc_ok=0, byml_ok=0, aamp_ok=0)
    walk(rel, (Path(root) / rel).read_bytes(), out)
    return out

if __name__ == "__main__":
    root = Path(sys.argv[1])
    files = sorted(str(f.relative_to(root)) for f in root.rglob("*") if f.is_file() and "logs" not in f.relative_to(root).parts and f.stat().st_size > 0)
    tot = dict(counts=collections.Counter(), wiiu=[], unknown=[], errors=[], sarc_ok=0, byml_ok=0, aamp_ok=0)
    with Pool(4, maxtasksperchild=50) as p:
        for o in p.imap_unordered(one, [(str(root), f) for f in files], chunksize=8):
            tot["counts"].update(o["counts"])
            for k in ("wiiu", "unknown", "errors"): tot[k] += o[k]
            for k in ("sarc_ok", "byml_ok", "aamp_ok"): tot[k] += o[k]
    tot["files"] = len(files); tot["counts"] = dict(sorted(tot["counts"].items(), key=lambda kv: -kv[1]))
    tot["wiiu"].sort(); json.dump(tot, open(sys.argv[2], "w"), indent=1)
    plat = collections.Counter(); 
    for k, v in tot["counts"].items(): plat[k.split("|")[2]] += v
    wk = collections.Counter(n.rsplit(".", 1)[-1] for n in tot["wiiu"])
    uk = collections.Counter((n.rsplit(".", 1)[-1], h[:8]) for n, h, l in tot["unknown"])
    print(json.dumps(dict(files=len(files), leaves_by_platform=plat, wiiu_by_ext=wk, unknown_by_ext_magic={f"{a}:{b}": c for (a, b), c in uk.most_common(40)},
                          errors=len(tot["errors"]), sarc_ok=tot["sarc_ok"], byml_ok=tot["byml_ok"], aamp_ok=tot["aamp_ok"]), indent=1))
