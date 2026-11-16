#!/usr/bin/env python3
"""Convert the unpacked Second Wind BNP from Wii U to Switch with BCML's own converter.

One change from stock BCML: while actor packs are converted, "is this Havok file modded?" is
answered against BCML's Wii U hash table (the mod's source platform). Stock BCML asks the Switch
table, so every unmodified Wii U Havok file looks modded and is left in place instead of being
swapped for the stock Switch one.
"""
import json, sys, time, collections
from pathlib import Path
import xxhash
import bcml.util as util
import bcml.dev as dev

MOD = Path(sys.argv[1])
ORIG_CONVERT = dev._convert_actorpack
ORIG_MODDED = util.is_file_modded


def modded_vs_wiiu(name, file, count_new=True):
    table = util.get_hash_table(True)
    if name not in table:
        return count_new
    data = file if isinstance(file, bytes) else file.read_bytes() if isinstance(file, Path) else bytes(file)
    if data[0:4] == b"Yaz0":
        data = util.decompress(data)
    return xxhash.xxh64_intdigest(data) not in table[name]


def convert_actorpack(actor_pack, to_wiiu):
    util.is_file_modded = modded_vs_wiiu
    try:
        return ORIG_CONVERT(actor_pack, to_wiiu)
    finally:
        util.is_file_modded = ORIG_MODDED


dev._convert_actorpack = convert_actorpack

if __name__ == "__main__":
    util.sanity_check()
    t = time.time()
    warnings = dev.convert_mod(MOD, to_wiiu=False, warn_only=True)
    flat = []
    def walk(w):
        if isinstance(w, (list, tuple)):
            for x in w: walk(x)
        elif w: flat.append(str(w))
    walk(warnings)
    kinds = collections.Counter()
    for w in flat:
        if "Havok" in w: kinds["havok file left unconverted"] += 1
        elif "does not support" in w: kinds["unsupported file type: " + w.rsplit(".", 1)[-1]] += 1
        else: kinds[w[:60]] += 1
    Path(sys.argv[2]).write_text(json.dumps({"seconds": round(time.time() - t), "count": len(flat), "kinds": kinds, "warnings": flat}, indent=1))
    print("done", round(time.time() - t), "s; warnings", len(flat))
    for k, v in kinds.most_common(): print(v, k)
