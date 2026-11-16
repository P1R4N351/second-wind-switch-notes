#!/usr/bin/env python3
"""Check that the diffs in the mod's logs/ (main + both options) are present in the merged files.
usage: evidence.py <mod dir> <romfs dir> <aoc dir> <out.json>"""
import sys, json, binascii, collections, traceback
from pathlib import Path
import oead
from bcml import util
MOD, ROM, AOC, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
GAME, DLC = Path("/dev/shm/swgame"), Path("/dev/shm/swdlc")
LOGDIRS = [MOD / "logs", MOD / "options/Eventide Fix/logs", MOD / "options/Shrine Overhaul/logs"]   # later ones win, as in BCML
def unyaz(d):
    d = bytes(d); return bytes(oead.yaz0.decompress(d)) if d[:4] == b"Yaz0" else d
def nested(path, *parts):
    d = Path(path).read_bytes()
    for p in parts:
        buf = unyaz(d); d = bytes(oead.Sarc(buf).get_file(p).data)
    return unyaz(d)
def yml(name):
    return [(d.parent.name if d.parent != MOD else "main", oead.byml.from_text(Path(d / name).read_text("utf-8"))) for d in LOGDIRS if (d / name).exists()]
def plain(x):
    if isinstance(x, (oead.byml.Hash, dict)): return {k: plain(v) for k, v in dict(x).items()}
    if isinstance(x, (oead.byml.Array, list)): return [plain(v) for v in x]
    if hasattr(x, "v"): return x.v
    return x
R = {}
def section(name):
    def deco(fn):
        try: R[name] = fn()
        except Exception as e: R[name] = dict(ERROR=repr(e)[:500], tb=traceback.format_exc()[-800:])
        print(name, json.dumps(R[name], default=str)[:700], flush=True)
    return deco

@section("actorinfo")
def _():
    info = oead.byml.from_binary(unyaz((ROM / "Actor/ActorInfo.product.sbyml").read_bytes())); st = oead.byml.from_binary(unyaz((GAME / "Actor/ActorInfo.product.sbyml").read_bytes()))
    by = {binascii.crc32(str(a["name"]).encode()): a for a in info["Actors"]}; stock_names = {str(a["name"]) for a in st["Actors"]}
    c = collections.Counter(); bad = []
    for src, log in yml("actorinfo.yml"):
        for h, diff in dict(log).items():
            a = by.get(int(h))
            if a is None: c["actor missing"] += 1; bad.append(h); continue
            c["new actors" if str(a["name"]) not in stock_names else "modified stock actors"] += 1
            for k, v in dict(diff).items():
                if (plain(a[k]) if k in a else None) != plain(v):
                    if isinstance(plain(v), dict) and k in a and all(plain(a[k]).get(kk) == vv for kk, vv in plain(v).items()): continue
                    c["field differs"] += 1; bad.append([str(a["name"]), k])
    hashes_sorted = list(info["Hashes"]) == sorted(info["Hashes"], key=lambda x: x.v)
    return dict(stock_actors=len(st["Actors"]), merged_actors=len(info["Actors"]), log_entries=sum(len(dict(l)) for _, l in yml("actorinfo.yml")), result=c, problems=bad[:10], hashes_sorted=hashes_sorted, hashes_len=len(info["Hashes"]))

def gamedata_flags(bootup):
    buf = nested(bootup, "GameData/gamedata.ssarc"); s = oead.Sarc(buf); out = collections.defaultdict(dict)
    for f in s.get_files():
        b = oead.byml.from_binary(bytes(f.data))
        for k, lst in dict(b).items():
            for fl in lst: out[k][str(fl["DataName"])] = fl
    return out
@section("gamedata")
def _():
    m = gamedata_flags(ROM / "Pack/Bootup.pack"); st = gamedata_flags(GAME / "Pack/Bootup.pack"); c = collections.Counter(); bad = []
    final = {}
    for src, log in yml("gamedata.yml"):
        for typ, d in dict(log).items():
            for name, fl in dict(d["add"]).items(): final[(typ, name)] = ("add", fl)
            for name in d["del"]: final[(typ, str(name))] = ("del", None)
    for (typ, name), (op, fl) in final.items():
        if op == "del": c["deleted ok" if name not in m[typ] else "deletion NOT applied"] += 1
        elif name not in m[typ]: c["add missing"] += 1; bad.append(name)
        elif plain(m[typ][name]) != plain(fl): c["add present but differs"] += 1; bad.append(name)
        else: c["added/modified ok"] += 1
    return dict(stock_flags=sum(len(v) for v in st.values()), merged_flags=sum(len(v) for v in m.values()), result=c, problems=bad[:10])

def save_flags(bootup):
    buf = nested(bootup, "GameData/savedataformat.ssarc"); s = oead.Sarc(buf); names = set(); n = 0
    for f in s.get_files():
        b = oead.byml.from_binary(bytes(f.data)); fl = b["file_list"]
        if str(fl[0]["file_name"]) == "game_data.sav":
            for x in fl[1]: names.add(str(x["DataName"])); n += 1
    return names, n
@section("savedata")
def _():
    m, n = save_flags(ROM / "Pack/Bootup.pack"); st, sn = save_flags(GAME / "Pack/Bootup.pack"); c = collections.Counter(); final = {}
    for src, log in yml("savedata.yml"):
        for x in log["add"]: final[str(x["DataName"])] = "add"
        for x in log["del"]: final[str(x)] = "del"
    for name, op in final.items():
        if op == "add": c["added ok" if name in m else "add missing"] += 1
        else: c["deleted ok" if name not in m else "deletion NOT applied"] += 1
    return dict(stock_flags=sn, merged_flags=n, result=c)

@section("maps")
def _():
    c = collections.Counter(); bad = []; units = set(); final = {}
    for src, log in yml("map.yml"):
        for unit, d in dict(log).items(): final.setdefault(unit, []).append(d)
    for unit, ds in final.items():
        sec = unit.split("_")[0]; p = AOC / f"Map/MainField/{sec}/{unit}.smubin"
        if not p.exists(): c["unit file missing"] += 1; bad.append(unit); continue
        mu = oead.byml.from_binary(unyaz(p.read_bytes())); su = oead.byml.from_binary(unyaz((DLC / f"Map/MainField/{sec}/{unit}.smubin").read_bytes())); units.add(unit)
        c["objs stock"] += len(su["Objs"]); c["objs merged"] += len(mu["Objs"])
        for kind in ("Objs", "Rails"):
            have = {x["HashId"].v: x for x in mu[kind]} if kind in mu else {}
            dels = set(); adds = {}; mods = {}
            for d in ds:
                if kind not in d: continue
                dk = dict(d[kind])
                for h in dk.get("del", []): dels.add(h.v)
                for x in dk.get("add", []): adds[x["HashId"].v] = x
                for h, x in dict(dk.get("mod", {})).items(): mods[int(h)] = x
            for h in adds: c[f"{kind} add ok" if h in have else f"{kind} add MISSING"] += 1
            for h, x in mods.items():
                if h in dels and h not in have: c[f"{kind} mod superseded by an option's deletion"] += 1; continue
                c[f"{kind} mod ok" if h in have and plain(have[h]) == plain(x) else f"{kind} mod differs/missing"] += 1
            for h in dels - set(adds): c[f"{kind} del ok" if h not in have else f"{kind} del NOT applied"] += 1
    return dict(units=len(units), result=c, problems=bad[:10])

@section("eventinfo")
def _():
    m = oead.byml.from_binary(nested(ROM / "Pack/Bootup.pack", "Event/EventInfo.product.sbyml")); st = oead.byml.from_binary(nested(GAME / "Pack/Bootup.pack", "Event/EventInfo.product.sbyml")); c = collections.Counter(); final = {}
    for src, log in yml("eventinfo.yml"): final.update(dict(log))
    for k, v in final.items(): c["ok" if k in m and oead.byml.to_text(m[k]) == oead.byml.to_text(v) else "missing/differs"] += 1
    return dict(stock_events=len(st), merged_events=len(m), result=c)

@section("quests")
def _():
    m = oead.byml.from_binary(nested(ROM / "Pack/TitleBG.pack", "Quest/QuestProduct.sbquestpack")); st = oead.byml.from_binary(nested(GAME / "Pack/TitleBG.pack", "Quest/QuestProduct.sbquestpack"))
    names = {str(q["Name"]): q for q in m}; c = collections.Counter(); final_add = {}; final_mod = {}; dels = set()
    for src, log in yml("quests.yml"):
        for q in log["add"]: final_add[str(q["Name"])] = q
        for n, q in dict(log["mod"]).items(): final_mod[n] = q
        for n in log["del"]: dels.add(str(n))
    for n, q in final_add.items(): c["add ok" if n in names and plain(names[n]) == {k: v for k, v in plain(q).items() if k != "prev_quest"} else ("add present, content differs" if n in names else "add MISSING")] += 1   # prev_quest is BCML's ordering hint, not game data
    for n, q in final_mod.items(): c["mod ok" if n in names and oead.byml.to_text(names[n]) == oead.byml.to_text(q) else "mod missing/differs"] += 1
    for n in dels: c["del ok" if n not in names else "del NOT applied"] += 1
    return dict(stock_quests=len(st), merged_quests=len(m), result=c)

@section("areadata")
def _():
    m = oead.byml.from_binary(nested(ROM / "Pack/Bootup.pack", "Ecosystem/AreaData.sbyml")); by = {str(a["AreaNumber"].v if hasattr(a["AreaNumber"], "v") else a["AreaNumber"]): a for a in m}; c = collections.Counter(); final = {}
    for src, log in yml("areadata.yml"): final.update(dict(log))
    for num, d in final.items():
        a = by.get(num)
        if a is None: c["area missing"] += 1; continue
        for k, v in dict(d).items(): c["field ok" if k in a and oead.byml.to_text(a[k]) == oead.byml.to_text(v) else "field differs"] += 1
    return dict(areas=len(m), result=c)

@section("residents")
def _():
    m = oead.byml.from_binary(nested(ROM / "Pack/Bootup.pack", "Actor/ResidentActors.byml")); st = oead.byml.from_binary(nested(GAME / "Pack/Bootup.pack", "Actor/ResidentActors.byml")); names = {str(a["name"]) for a in m}; c = collections.Counter()
    for src, log in yml("residents.yml"):
        for k in dict(log): c["ok" if k in names else "missing"] += 1
    return dict(stock=len(st), merged=len(m), result=c)

@section("dungeonstatic")
def _():
    m = oead.byml.from_binary(unyaz((AOC / "Map/CDungeon/Static.smubin").read_bytes())); st = oead.byml.from_binary(unyaz((DLC / "Map/CDungeon/Static.smubin").read_bytes()))
    have = {f'{str(x["Map"])}___{str(x["PosName"])}': x for x in m["StartPos"]}; c = collections.Counter()
    for src, log in yml("dstatic.yml"):
        for k, v in dict(log).items(): c["ok" if k in have and oead.byml.to_text(have[k]["Translate"]) == oead.byml.to_text(v["Translate"]) else "missing/differs"] += 1
    return dict(stock_startpos=len(st["StartPos"]), merged_startpos=len(m["StartPos"]), result=c)

@section("mainstatic")
def _():
    m = oead.byml.from_binary(unyaz((AOC / "Map/MainField/Static.smubin").read_bytes())); st = oead.byml.from_binary(unyaz((DLC / "Map/MainField/Static.smubin").read_bytes())); c = collections.Counter()
    for src, log in yml("mainstatic.yml"):
        for cat, entries in dict(log).items():
            texts = {oead.byml.to_text(x) for x in m[cat]} if cat in m else set()
            for k, v in dict(entries).items(): c[f"{cat} ok" if oead.byml.to_text(v) in texts else f"{cat} missing/differs"] += 1
    return dict(sizes={k: [len(st[k]) if k in st else 0, len(m[k])] for k in dict(m) if isinstance(m[k], oead.byml.Array)}, result=c)

@section("texts")
def _():
    out = {}
    logs = [json.loads((d / "texts.json").read_text("utf-8")) for d in LOGDIRS if (d / "texts.json").exists()]
    diff = {}
    for l in logs:
        for lang, files in l.items():
            for f, e in files.items(): diff.setdefault(f, {}).update(e)
    for pack in sorted((ROM / "Pack").glob("Bootup_????.pack")):
        lang = pack.stem.split("_")[1]
        if lang == "Graphics": continue
        buf = nested(pack, f"Message/Msg_{lang}.product.ssarc"); s = oead.Sarc(buf); sb = oead.Sarc(nested(GAME / "Pack" / pack.name, f"Message/Msg_{lang}.product.ssarc"))
        files = {f.name: bytes(f.data) for f in s.get_files()}; c = collections.Counter()
        for f, entries in diff.items():
            msbt = files.get(f.replace(".msyt", ".msbt"))
            if msbt is None: c["msbt file missing"] += 1; continue
            for label, e in entries.items():
                if label.encode() not in msbt: c["label missing"] += 1; continue
                frag = next((x["text"] for x in e.get("contents", []) if "text" in x and x["text"].strip()), None)
                if frag is None: c["label ok (no text fragment to compare)"] += 1
                else: c["label+text ok" if frag.split("\n")[0].encode("utf-16-le") in msbt else "label ok, text differs"] += 1
        out[lang] = dict(stock_msbt=len(list(sb.get_files())), merged_msbt=len(files), result=c)
    return dict(log_files=len(diff), log_entries=sum(len(v) for v in diff.values()), per_language=out)

@section("packs_and_aamp")
def _():
    NX = util.get_hash_table(False); import xxhash
    c = collections.Counter(); diff_ext = collections.Counter(); ex = []
    packs = {}
    for d in LOGDIRS:
        if (d / "packs.json").exists():
            for canon, rel in json.loads((d / "packs.json").read_text()).items(): packs[rel] = d.parent / rel
    for rel, src in sorted(packs.items()):
        sub = rel.split("romfs/", 1)[1]; fin = (AOC if "F001" in rel else ROM) / sub
        if not fin.exists(): c["pack not delivered (identical to stock after merge)"] += 1; ex.append(sub); continue
        c["packs delivered"] += 1
        b1 = unyaz(src.read_bytes()); b2 = unyaz(fin.read_bytes()); s1 = oead.Sarc(b1); s2 = oead.Sarc(b2); fin_files = {f.name: f for f in s2.get_files()}
        for f in s1.get_files():
            if f.name[f.name.rindex("."):] in util.SARC_EXTS: continue
            d1 = unyaz(f.data); canon = f.name.replace(".s", ".")
            if canon in NX and xxhash.xxh64_intdigest(d1) in NX[canon]: continue
            if f.name not in fin_files: c["modded entry MISSING from merged pack"] += 1; continue
            if unyaz(fin_files[f.name].data) == d1: c["modded entry carried over unchanged"] += 1
            else: c["modded entry further changed by a merger"] += 1; diff_ext[f.name.rsplit(".", 1)[-1]] += 1
    tot = collections.Counter()
    for name in ("deepmerge.aamp", "aslist.aamp", "shop.aamp"):
        for d in LOGDIRS:
            if not (d / name).exists(): continue
            pio = oead.aamp.ParameterIO.from_binary((d / name).read_bytes())
            for k, o in pio.objects.items():
                for p in o.params.values():
                    path = str(p.v); parts = path.split("//"); sub = parts[0].split("romfs/", 1)[1]; fin = (AOC if "F001" in parts[0] else ROM) / sub
                    try:
                        data = nested(fin, *parts[1:]); stock = None
                        try: stock = nested((DLC if "F001" in parts[0] else GAME) / sub, *parts[1:])
                        except Exception: pass
                        oead.aamp.ParameterIO.from_binary(data)
                        tot[f"{name}: target present, parses, " + ("differs from stock" if stock is not None and stock != data else "new file" if stock is None else "IDENTICAL TO STOCK")] += 1
                    except Exception as e: tot[f"{name}: target MISSING"] += 1
    dr = collections.Counter()
    for d in LOGDIRS:
        if (d / "drops.json").exists():
            for path, tables in json.loads((d / "drops.json").read_text()).items():
                parts = path.split("//"); fin = ROM / parts[0].split("romfs/", 1)[1]
                try:
                    pio = oead.aamp.ParameterIO.from_binary(nested(fin, *parts[1:])); have = {str(p.v) for o in pio.objects.values() for p in o.params.values() if isinstance(p.v, (str, oead.FixedSafeString64)) or "String" in type(p.v).__name__}
                    for t, body in tables.items():
                        items = set(body.get("items", {})) if isinstance(body, dict) else set()
                        dr["drop table ok" if items <= have else "drop table items missing"] += 1
                except Exception as e: dr["drop target missing/unparsed"] += 1
    return dict(packs=c, changed_by_merger_by_ext=diff_ext, not_delivered=ex[:10], aamp_logs=tot, drops=dr)
OUT.write_text(json.dumps(R, indent=1, default=str))
