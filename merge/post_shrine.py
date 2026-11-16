#!/usr/bin/env python3
"""After the 120 rebuilt Shrine Overhaul packs are in the working mod's option folder: link them into the installed BCML mod
(option folder + merged-in main folder, exactly what install_mod does for a selected option), regenerate that option's RSTB log,
re-run BCML's RSTB merger and re-export. usage: post_shrine.py <working mod> <export dir> <out.json>"""
import os, sys, json, shutil
from pathlib import Path
import bcml.util as util
from bcml import install
from bcml.install import find_modded_files
from bcml.mergers.rstable import RstbMerger
WORK, EXPORT, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SRC = WORK / "options/Shrine Overhaul/01007EF00011E000/romfs/Pack"
util.sanity_check(); mod = util.get_installed_mods()[0]; rep = dict(mod=str(mod.path))
od = mod.path / "options/Shrine Overhaul"; n = 0
for p in sorted(SRC.glob("Dungeon*.pack")):
    for d in (od / "01007EF00011E000/romfs/Pack", mod.path / "01007EF00011E000/romfs/Pack"):
        t = d / p.name
        if t.exists(): t.unlink()
        os.link(p, t)
    n += 1
rep["packs_linked"] = n
with util.start_pool() as pool:
    files = find_modded_files(od, pool); old = json.loads((od / "logs/rstb.json").read_text()) if (od / "logs/rstb.json").exists() else {}
    (od / "logs/rstb.json").unlink(missing_ok=True)
    m = RstbMerger(); m.set_pool(pool); m.log_diff(od, files)
    new = json.loads((od / "logs/rstb.json").read_text()); rep.update(option_modded_files=len(files), option_rstb_entries_before=len(old), option_rstb_entries_after=len(new))
    m2 = RstbMerger(); m2.set_pool(pool); m2.perform_merge()
for rel in ("logs/rstb.json", "options/Eventide Fix/logs/rstb.json", "options/Shrine Overhaul/logs/rstb.json"):
    if (mod.path / rel).exists(): shutil.copyfile(mod.path / rel, WORK / rel)      # refresh the working mod's stale RSTB logs
shutil.rmtree(EXPORT, ignore_errors=True); EXPORT.mkdir(parents=True); install.link_master_mod(EXPORT)
rep["export_files"] = sum(1 for f in EXPORT.rglob("*") if f.is_file()); rep["export_dungeon_packs"] = len(list((EXPORT / "01007EF00011E000/romfs/Pack").glob("Dungeon*.pack")))
OUT.write_text(json.dumps(rep, indent=1)); print(rep)
