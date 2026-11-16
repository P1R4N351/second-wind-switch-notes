# Second Wind: Wii U to Switch conversion notes

Scripts and measurements from an attempt to convert the Breath of the Wild mod
*Second Wind* (1.9.14-alpha-6, a Wii U BCML package) to Switch format, for use
with a native Android port of BotW 1.6.0.

This repository holds **no mod files and no game files**. You need your own copy
of the mod and your own game dump.

## Status

Incomplete. The data stage works; the binary assets do not convert with BCML.

- `convert_sw.py` runs BCML's own `convert_mod` on an unpacked `.bnp`, with one
  change: while actor packs are converted, "is this Havok file modded?" is
  checked against BCML's Wii U hash table (the mod's source platform). Stock
  BCML checks the Switch table, so unmodified Wii U Havok files are never
  swapped for the stock Switch ones.
- BCML needs these stock Switch files: `Actor/ActorInfo.product.sbyml`,
  `System/Resource/ResourceSizeTable.product.srsizetable`, `Actor/Pack/*`,
  `Pack/Dungeon000.pack`, and the DLC folder (`Pack/AocMainField.pack`) for the
  RSTB step.
- `scan_sw.py` walks the converted tree, including nested archives, and counts
  what is still big-endian. Result after the data stage:
  `scan-after-data-stage.json`.

Still Wii U format after BCML (it has no converter for them): 1,103 `.sbfres`
models and textures, 995 `.hkrb`, 232 `.shksc`, 132 `.shknm2`, 90 `.hkcl`,
30 `.hkrg`, 86 `.bcamanim`, 317 `.sbitemico`, 5 `.sblarc`.

Not done: converting those files, the mod's two options, the RSTB log, and any
in-game test.

## Licence

The two scripts are MIT. BCML is GPL-3.0 and is used as an installed package.
