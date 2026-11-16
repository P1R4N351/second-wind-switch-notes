# Second Wind v1.9.14-alpha-6 — merged Switch overlay for BotW 1.6.0 + DLC 3.0

Built 2026-11-16 in the cauldron. Nothing here has been loaded in a game.

## What is delivered

| volume | files | bytes | added (absent from stock) | modified stock files |
|---|---|---|---|---|
| `romfs/` (01007EF00011E000) | 3,935 | 2,348,447,184 | 3,309 | 626 |
| `aoc1/` (DLC index 1) | 115 | 127,953,485 | 12 | 103 |
| total | 4,050 | 2,476,400,669 | 3,321 | 729 |

`romfs/`: Actor 2,531 (ActorInfo + 2,530 actor packs), Event 254, Model 543, Pack 136 (Bootup, TitleBG, 14 language packs, 120 shrine packs), Physics 96, System 2 (RSTB, Version.txt), UI 373.
`aoc1/`: Map 101 (97 main-field map units, MainField/Static, CDungeon/Static, AocField/Static, AocField/I-7), Pack 13 (12 new shrine packs Dungeon200–218, and AocMainField.pack), Physics 1.

`files.tsv` has one line per file: volume, path, size, sha256, stock sha256. A stock hash is given for the 492 files whose stock copy was actually pulled; `-` for the 3,321 added files and for 237 modified files whose stock copy was not pulled (119 shrine packs, 118 others).

Added/modified was decided against real stock where pulled, otherwise against BCML's 1.6.0 content-hash table, and cross-checked against a name listing of the full stock trees: all 729 "modified" paths exist in stock, none of the 3,321 "added" paths do.

Three exported files were left out because they equal stock: `Pack/Title.pack` (see losses), `Actor/Pack/DgnObj_DungeonWater50x50_A_01.sbactorpack` (same content after decompression), `aoc1/System/AocVersion.txt`.

## Things a loader must know

- **`aoc1/Pack/AocMainField.pack` is 0 bytes on purpose.** That is how BCML makes the game read the loose merged map units in `aoc1/Map/MainField/` instead of the copies inside the pack. If the port's overlay cannot handle an empty pack, the alternative is a rebuilt AocMainField.pack containing the 97 merged units; that was not built.
- `romfs/System/Version.txt` is the mod's own file and reads `1.9.14-alpha-6` instead of `1.6.0`. Drop it if the port parses that file.
- Only 97 of the main-field map units are delivered; the rest come from the stock DLC RomFS, so the stock `aoc1/Map/MainField` loose files must remain visible under the overlay.

## How it was merged

BCML 3.10 ran headless in Switch mode (game dir = stock base files, DLC dir = stock DLC files, store on /dev/shm). The converted mod was installed with `install_mod` with both options selected (Eventide Fix, Shrine Overhaul), then all 18 mergers ran without error, then `link_master_mod` exported the result. Text merging used BCML's "all languages" option.

The 120 Shrine Overhaul packs were kept out of the install copy to save RAM (the container's tmpfs counts against its 8 GB) and hard-linked into the installed mod afterwards, in both the option folder and the main folder, which is what `install_mod` does for a selected option. BCML never merges `Dungeon*` packs; it passes them through. Their RSTB log was regenerated with BCML's own code and the RSTB merger re-run before the export.

Each log was checked against the merged files (`/dev/shm/sw2/evidence.json`):

| log | result |
|---|---|
| packs.json (2,444 packs) | 2,443 delivered, 1 equals stock (Title.pack). 7,542 modded entries carried over unchanged, 7 further changed by a later merger (5 drop tables, 1 byml, quest pack), 0 missing |
| deepmerge.aamp / aslist.aamp | 482 + 2 targets present, parse, differ from stock. shop.aamp is empty |
| drops.json | 517 drop tables present with their items |
| actorinfo.yml (2,607) | 2,228 new actors + 379 modified, all fields match. ActorInfo 7,934 → 10,162 actors, hash list sorted |
| gamedata.yml | 2,271 flags added/changed, 1,251 deleted, all applied. 45,014 → 46,008 flags |
| savedata.yml | 2,234 added, 1,252 deleted, all applied. 43,668 → 44,651 |
| map.yml (97 units) | 3,223 object adds, 2,294 mods, 1,489 deletes, 2 rail adds applied. 8 main-mod edits are to objects that Eventide Fix deletes (expected) |
| mainstatic.yml / dstatic.yml | 61 / 12 entries present |
| eventinfo.yml | 762 entries match. 5,784 → 6,424 events |
| quests.yml | 31 added, 170 modified, all match. 170 → 201 quests |
| areadata.yml / residents.yml | 174 fields / 6 entries match |
| texts.json (219 files, 7,100 entries, EUen only) | every label present in all 14 language packs; 1,091 → 1,225 message files each |
| rstb.json | regenerated, see below |

## Substitutions and lost changes

Lost (no tool converts Wii U layout archives; the stock Switch archive is used instead):

1. `Pack/Bootup.pack//Layout/Common.sblarc` — the mod's `PaPauseQuest_00.bflyt` (quest pause screen layout), 6 logo textures (`Logo3DGameTitle_00`, `Logo2D_00`, `LogoDLC`, three `DLCLogoPack*`) and 12 animations.
2. `Pack/Bootup.pack//Layout/BootUp.sblarc` — `BootUp_00.bflyt` and `Logo_W_00` texture.
3. `Pack/Title.pack//Layout/Title.sblarc` — `Title_00.bflyt`, `Logo_W_00` texture, 2 animations. This was Title.pack's only change, so Title.pack is not delivered at all.

The same two Bootup archives were also in the Shrine Overhaul option's Bootup.pack (5 archives in total, 3 distinct). Effect: stock title/boot logos, and the quest pause layout is stock, which may not suit the mod's quest list.

Substituted without loss (the mod's copy was a byte-for-byte stock Wii U file, replaced by the stock Switch file of the same name):

4. `Event/Demo822_0.sbeventpack//Sound/Resource/Event_Demo008.bars` (from stock TitleBG.pack)
5. `Event/Demo822_2.sbeventpack//Sound/Resource/Event_Demo008.bars` (same)
6. `Event/OrdonRecruit02.sbeventpack//Sound/Resource/Event_CookingAllResult.bars` (same)
7. Four effect lists the earlier pass had missed: `Demo030_0//Effect/Event_Demo030_0.sesetlist`, `Demo034_0//Effect/Event_Demo034_0.sesetlist`, `Demo821_0//Effect/Event_Demo602_0.sesetlist`, `Demo823_0//Effect/Event_Demo029_0.sesetlist` (from the stock event packs).
8. In 119 shrine packs (all but Dungeon000) the model, texture, nav-mesh and collision entries were unmodified Wii U stock; the rebuilt packs are the stock Switch pack with the mod's entries on top (732 entries overridden, 1 added, 475 taken from stock).

Converted here (mod change kept), also missed by the earlier pass:

9. `Pack/Bootup.pack//Sound/LoopAssetList.blal` — byte-swapped; adds one hash (0x59efe9e3) to stock's 1,153.
10. `Pack/Bootup.pack//Ecosystem/LoadBalancer.sbeco` — byte-swapped; 749 of 800 rows equal stock Switch, row widths all 1000 as in stock.

Text: the mod only ships English (EUen) text. In the 12 non-English packs the mod's new and changed entries are in English (BCML's behaviour).

Corrections to the earlier report: its scan read the audio archive byte-order mark at the wrong offset, so "no big-endian data left" was not established; this scan found the 3 audio archives, 4 effect lists, the .blal and the .sbeco. `.sblwp` files are big-endian on Switch too (checked against stock Dungeon000) and are not a defect.

## Resource size table

Regenerated after all conversions: the stale logs were rebuilt with BCML's RSTB code (main log 10,099 → 9,732 entries, 2,742 values changed), BCML's RSTB merger produced the table, then every delivered and pack-nested resource was re-sized with BCML's calculator (Switch sizes) and compared.

- 44,576 resource occurrences, 18,885 distinct names, 11,669 modified or new.
- Against BCML's table: 187 mismatches, all corrected, 0 after correction:
  - 76 un-prefixed `Map/MainField/...` names were smaller than the delivered DLC map unit (BCML sizes that name from the base-game copy); raised.
  - 108 resources nested in the 12 new DLC shrine packs had only an `Aoc/0010/`-prefixed entry. Stock uses un-prefixed names for some of these (models), so the un-prefixed name was added as well. This goes beyond what BCML does.
  - 3 entries BCML had added for unmodified resources were removed.
- Independent spot check of 300 random modified resources re-read from the delivered files: 0 missing or too small.
- Final table: 75,197 entries (stock 65,818): 9,490 added, 1,236 changed, 111 removed.
- Following BCML's rule, a resource whose size its calculator cannot compute gets no entry: 111 stock entries removed (98 `.hksc`, 6 `.bmodellist`, 3 `.batcl`, 2 `.bphyssb`, 1 `.bbonectrl`, and the US English message archive, which BCML always removes), and 579 new resources have no entry (469 `.bmodellist`, 19 `.bcamanim`, 18 `.blifecondition`, 17 `.bchemical`, 12 `.hksc`, 12 `.hknm2`, 10 `.hkcl`, 9 `.batcllist`, 7 `.batcl`, 6 `.bbonectrl`). Where an occurrence of a name had several sizes the largest was used.

## Format verification of `swfinal`

- 4,049 non-empty files scanned recursively, 65,056 leaves: 63,602 Switch format, 1,191 platform-neutral (event flows, `.sblwp`, JPEG, text), 263 flagged (35 `.gtx`, 228 of unrecognised type). All 263 are byte-identical to the same entry in the stock Switch Bootup.pack/TitleBG.pack, so 0 Wii U-format files remain that are not stock Switch data.
- No file or entry uses the Wii U texture names `.Tex1.` / `.Tex2.`.
- 3,150 SARC archives opened (every pack and nested pack), 920 BYML and 37,596 AAMP files parsed, 0 errors; every Yaz0 stream decompressed.
- Havok files 1,726, all little-endian with 8-byte pointers; BFRES 1,325, all Switch header.

## Not verified

- Nothing was run in a game or in the port. In particular the 0-byte AocMainField.pack and the RSTB choices above are BCML conventions for a real Switch, untested on the native port.
- The scan checks container format and endianness, not content. Models, textures and Havok files converted by BfresPlatformConverter and HKXConvert in the earlier pass were not re-validated beyond their headers; message files, audio archives and layouts were identified by header only.
- RSTB sizes agree with BCML's calculator, which estimates some types (models, parameter files); they are not the game's own measurements.
- 237 modified files were classified against BCML's hash table rather than a pulled stock copy.
- The stock files in the cauldron were copied over a slow link; sizes of the large packs were checked against the handheld, hashes were not (the handheld was in use).

## Where things are

- Work files, scripts and JSON results: `/dev/shm/sw2/` (`merge_report.json`, `final.json`, `evidence.json`, `fix_leftovers.json`, `post_shrine.json`, `scan2.py`, `finalize.py`, `evidence.py`, `merge_sw.py`, `fix_leftovers.py`, `smallconv.py`).
- BCML store with the installed mod and merged output: `/dev/shm/sw2/store/`. Files in `swfinal` are hard links into it and into `/dev/shm/swmod`; do not edit them in place.
- `/dev/shm/swmod` now has the fixes above, the 120 rebuilt shrine packs in the Shrine Overhaul option and fresh RSTB logs. The 119 superseded Wii U-format shrine packs were removed from it; they remain in the build host /var/tmp/sw_secondwind_switch.tar`.
