import json, sys, re, collections
from pathlib import Path
import oead
M = Path("/dev/shm/swmod"); G = Path("/dev/shm/swgame")
for base in [M, M/"options/Eventide Fix", M/"options/Shrine Overhaul"]:
    L = base/"logs"; print("=====", base.name)
    if (L/"packs.json").exists():
        p = json.loads((L/"packs.json").read_text())
        ext = collections.Counter(k.rsplit(".",1)[-1] for k in p); print("packs", ext)
        non = [k for k in p if not k.endswith("bactorpack")]; print(" non-actor:", non)
        miss = [v for k, v in p.items() if not (G/v.split("romfs/",1)[1]).exists()]
        print(" packs without stock in swgame:", len(miss), [m for m in miss if "Actor/Pack" not in m])
        nofile = [v for v in p.values() if not (base/v).exists()]; print(" log entries with no file:", len(nofile), nofile[:5])
    for n in ["deepmerge.aamp", "aslist.aamp", "shop.aamp"]:
        if (L/n).exists():
            pio = oead.aamp.ParameterIO.from_binary((L/n).read_bytes())
            print(n, "lists:", [ (str(k), len(v.objects), len(v.lists)) for k, v in pio.lists.items()], "objs:", [(str(k), len(v.params)) for k, v in pio.objects.items()])
            if "FileTable" in [str(k) for k in pio.objects.keys()] or True:
                for k, v in pio.objects.items():
                    vals = [str(x.v) for x in v.params.values()]
                    roots = collections.Counter(re.sub(r"[^/]+$", "*", s.split("//")[0]) for s in vals)
                    print("  ", str(k), len(vals), roots.most_common(12))
                    odd = [s for s in vals if not s.startswith("Actor/Pack")]
                    print("   non-actorpack:", odd[:60])
    if (L/"drops.json").exists():
        d = json.loads((L/"drops.json").read_text()); print("drops", len(d), list(d)[:5])
    if (L/"texts.json").exists():
        t = json.loads((L/"texts.json").read_text()); print("texts langs", {k: (len(v), sum(len(x) for x in v.values())) for k, v in t.items()})
    for n in ["map.yml", "dstatic.yml", "mainstatic.yml", "areadata.yml", "eventinfo.yml", "gamedata.yml", "savedata.yml", "quests.yml", "residents.yml", "actorinfo.yml"]:
        if (L/n).exists():
            txt = (L/n).read_text()
            top = re.findall(r"^([^\s#][^\n]*?):", txt, re.M)
            print(n, len(txt), "top keys:", len(top), top[:400] if n == "map.yml" else top[:12])
    if (L/"rstb.json").exists(): print("rstb", len(json.loads((L/"rstb.json").read_text())))
print("AocMainField size", (M/"01007EF00011F001/romfs/Pack/AocMainField.pack").stat().st_size)
