# Second Wind on Switch: conversion and merge notes

Notes and scripts from converting the Breath of the Wild mod **Second Wind v1.9.14-alpha-6** (a Wii U BCML bundle)
into a merged Switch 1.6.0 overlay, and loading it in a native Android port of the game
([P1R4N351/totk-android, branch `botw-android`](https://github.com/P1R4N351/totk-android/tree/botw-android)).

**This repository holds no mod files and no game files.** Second Wind belongs to its team; the game belongs to
Nintendo. Everything here is scripts, counts and reports. To use any of it you need your own copy of the mod, your own
Wii U and Switch dumps, and the patience to read the scripts first: they were written for one machine setup and one
run, not as a tool.

## Result

On one device (AYN Thor), in the native port: the merged overlay loads, the title screen shows the Second Wind logo
and version, a save loads onto the Great Plateau, and the game runs. **Nothing of the mod's content has been played or
verified beyond that.**

| | |
|---|---|
| Base-game files delivered | 3,937 (3,309 added, 628 replacing stock) |
| DLC files delivered | 115 (12 added, 103 replacing stock) |
| BCML mergers run | 18, Switch mode, both options (Eventide Fix, Shrine Overhaul) |
| Wii U-format data left | none that is not stock Switch data |
| Resource size table | regenerated after all conversions; 75,197 entries |

Known losses and caveats are in the reports. The main ones: the mod's new text is English in every language pack;
579 new resources have no size-table entry because BCML cannot size their types; the two largest logo textures were
downscaled to 1,024 px; converted models, textures and physics were checked by header and parsing, not by content.

## How it was done

1. **Data stage** (`convert_sw.py`, `scan_sw.py`, earlier files in the root): BCML's `convert_mod` for the formats it
   knows, then a scan for what is still Wii U format.
2. **Binaries BCML cannot convert**: Havok with HKXConvert, models/textures/icons with BfresPlatformConverter (both
   built from source on .NET 8); provably unmodified Wii U stock files replaced by the stock Switch file.
3. **Merge** (`merge/`): BCML run headless in Switch mode against the stock game and DLC, every change log checked
   against the merged files, the size table rebuilt and re-verified. See `merge/REPORT.md`.
4. **Layout archives** (`layout/`): `Title.sblarc`, `BootUp.sblarc` and `Common.sblarc` have no general converter.
   The mod's actual changes were found by diffing against stock Wii U, then transplanted into the stock Switch
   archives: textures de-tiled from GX2 and re-swizzled for NX into the combined BNTX, layout and animation changes
   ported field by field. See `layout/REPORT.md`.
5. **Loading in the port** (`port/`): `sw_stage.py` writes the overlay manifest the port checks at start (size and
   SHA-256 of every replacement and of the stock file it replaces) and builds a modded DLC volume: the stock image
   with the mod's files appended and an index that points replaced names at the new data. `botw_aoc_index.py` and
   `botw_romfs_index.py` index the stock images.

## Licence

The scripts here are MIT. They call or adapt BCML (GPL-3.0), HKXConvert (GPL-3.0) and BfresPlatformConverter (MIT),
which are not included.
