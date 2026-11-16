#!/usr/bin/env python3
"""Headless BCML (Switch mode) install + merge of the converted Second Wind mod.
usage: merge_sw.py <staged mod dir> <export dir> <report.json>
HOME must point at a dir whose .config/bcml/settings.json is the Switch config; TMPDIR must be on /dev/shm."""
import sys, json, time, os, traceback
from pathlib import Path
import bcml.util as util
from bcml import install, mergers
from bcml.install import find_modded_files
from bcml.mergers.rstable import RstbMerger

STAGE, EXPORT, REPORT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
rep = {"steps": []}
def step(name, fn):
    t = time.time(); print(f"=== {name}", flush=True)
    try:
        r = fn(); rep["steps"].append(dict(step=name, ok=True, seconds=round(time.time() - t, 1), result=r)); return r
    except Exception as e:
        traceback.print_exc(); rep["steps"].append(dict(step=name, ok=False, seconds=round(time.time() - t, 1), error=repr(e)[:2000]))
    finally:
        REPORT.write_text(json.dumps(rep, indent=1, default=str))

if __name__ == "__main__":
    util.sanity_check(); util.get_aoc_dir()
    s = util.get_settings(); assert not s["wiiu"] and s["no_cemu"]
    rep["settings"] = dict(s); rep["langs"] = sorted(util.get_user_languages())
    def rstb_logs():
        out = {}
        with util.start_pool() as pool:
            for d in [STAGE] + sorted(x for x in (STAGE / "options").glob("*") if x.is_dir()):
                files = find_modded_files(d, pool)
                old = json.loads((d / "logs/rstb.json").read_text()) if (d / "logs/rstb.json").exists() else {}
                (d / "logs/rstb.json").unlink(missing_ok=True)      # staged file is a hard link: never rewrite in place
                m = RstbMerger(); m.set_pool(pool); m.log_diff(d, files)
                new = json.loads((d / "logs/rstb.json").read_text()) if (d / "logs/rstb.json").exists() else {}
                out[d.name] = dict(modded_files=len(files), entries_before=len(old), entries_after=len(new),
                                   changed=sum(1 for k in new if k in old and old[k] != new[k]), added=len(set(new) - set(old)), removed=len(set(old) - set(new)))
        return out
    step("regenerate rstb logs (main + options)", rstb_logs)
    def inst():
        mod = install.install_mod(STAGE, options={"options": {"texts": {"all_langs": True}}, "disable": []},
                                  selects=["Eventide Fix", "Shrine Overhaul"], merge_now=False)
        return dict(path=str(mod.path), priority=mod.priority, name=mod.name)
    step("install_mod (both options selected)", inst)
    with util.start_pool() as pool:
        for mc in mergers.sort_mergers([m() for m in mergers.get_mergers()]):
            def run(mc=mc):
                mc.set_pool(pool)
                if mc.NAME == "texts": mc.set_options({"all_langs": True})
                logged = [m.name for m in util.get_installed_mods() if mc.is_mod_logged(m) or any((o / "logs" / mc.log_name).exists() for o in (m.path / "options").glob("*"))]
                mc.perform_merge(); return dict(mods_logged=logged)
            step(f"merger {mc.NAME}", run)
    def export():
        EXPORT.mkdir(parents=True, exist_ok=True)
        install.link_master_mod(EXPORT)
        return dict(files=sum(1 for f in EXPORT.rglob("*") if f.is_file()))
    step("link_master_mod export", export)
    master = util.get_master_modpack_dir()
    rep["master_files"] = sorted(str(f.relative_to(master)) for f in master.rglob("*") if f.is_file())
    REPORT.write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps([{k: v for k, v in s.items() if k != "result"} for s in rep["steps"]], indent=1)); print("master files:", len(rep["master_files"]))
