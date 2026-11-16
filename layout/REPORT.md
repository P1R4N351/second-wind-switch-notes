# Second Wind v1.9.14-alpha-6 layout archives: Wii U -> Switch 1.6.0

Nothing here has run in the game. Everything below was checked on files only.

## Result

All three archives are converted. No item had to stay stock for lack of a conversion; the only stock
entries kept are ones the mod did not really change (see "Stayed stock").

| Deliverable (under `out/`) | Goes to | Built from |
|---|---|---|
| `Pack/Title.pack` | `romfs/Pack/Title.pack` | stock Switch Title.pack, `Layout/Title.sblarc` replaced |
| `Pack/Bootup.pack` | `romfs/Pack/Bootup.pack` | the merged `swfinal` Bootup.pack, `Layout/Common.sblarc` replaced |
| `Layout/BootUp.sblarc` | `romfs/Layout/BootUp.sblarc` | stock Switch file (see correction below) |
| `System/Resource/ResourceSizeTable.product.srsizetable` | same path | the merged `swfinal` table, 3 values raised |
| `Title.sblarc`, `BootUp.sblarc`, `Common.sblarc` | (the bare archives, same bytes as inside the above) | |
| `preview/` | before / mod / after PNGs, `_contact_sheet_1.png`, `_contact_sheet_2.png` | |

**Correction to the brief:** on Switch, `Layout/BootUp.sblarc` is not inside `Bootup.pack`. It is a loose
romfs file (`/data/local/tmp/botw/romfs/Layout/BootUp.sblarc`, 1,166,082 bytes); stock and merged
`Bootup.pack` hold only `Layout/Common.sblarc` and `Layout/MultiFilter.ssarc`. So `Bootup.pack` has one
entry replaced, and the boot logo needs the extra loose file installed. The merged output has no
`romfs/Layout/` directory yet.

## What the mod changed (mod vs stock Wii U v208)

Stock Wii U files were read from the owner's dump
`/sdcard/Games/Wii U/The Legend of Zelda - Breath of the Wild (USA) (DLC) (v208).wua` (ZArchive). Only the
four packs were read, by byte range (`dd`, read-only, about 64 MB in total), not the 13.6 GB file.
The mod's archives are BCML-style partial archives: they contain only the entries the mod touched
(Title 4, BootUp 2, Common 19). The Shrine Overhaul option's `Bootup.pack` is byte-identical to the main one.

### Title.sblarc
- `timg/Logo_W_00^l`: new logo, RGBA8 sRGB, 993x780 (stock 382x300).
- `blyt/Title_00.bflyt`: 11 panes moved/resized (of 245 sections):
  `N_Capture_00` T(0,0)->(-1,33); `N_0_00`..`N_6_00` T(0,0)->(1,-33); `P_MainV_02` T(9.98,-30)->(119.98,-6);
  `N_CaptureLogo_00` Ty 221->110, H 300->480; `Logo_W_01` T(466,230)->(400,260), scale 0.67->1, H 300->382.
  45 further sections (usd1, txt1, prt1) differ in bytes only because the mod's editor re-serialised them
  (string pool order, a dropped zero word); parsed content is equal.
- `anim/Title_00_In`, `anim/Title_00_LoopRandom`: not really changed (pai1 byte-identical; pat1 has the same
  fields with 8 bytes of trailing padding dropped).

### BootUp.sblarc
- `timg/Logo_W_00^l`: new logo, RGBA8 sRGB, 2056x1632 (stock 382x300).
- `blyt/BootUp_00.bflyt`: `Logo_W_03` T(466,230)->(428,173), scale 0.67->1.

### Common.sblarc
- `timg/Logo3DGameTitle_00^l`: new logo, RGBA8 sRGB, 2102x1561 (stock 412x306).
- `timg/Logo2D_00^d`: A8 -> RGBA8, 360x257 (new 2D logo).
- `timg/LogoDLC^q`: BC3 sRGB 414x314, new content.
- Added textures: `DLCLogoPack1_JPja3^s` (BC4 alpha), `DLCLogoPack12LR_USen3^s` (BC4 luminance),
  `DLCLogoPack1_USen3^s` (BC3), all 494x154.
- `blyt/PaPauseQuest_00.bflyt`: texture list gains `DLCLogoPack1_JPja3^s` (index 18); materials
  `P_DLCLogo1_00`..`_03` switch their texture from index 3/4 to 18. Nothing else.
- `anim/PaPauseQuest_00_DLCLogo.bflan`: frames 2->3; `N_DLCLogo_00` gets a 4th key (frame 3 = hidden); a new
  entry for pane `N_DLCLogo_03` (that pane exists in no layout on either platform, so the entry is inert).
- 11 other animations shipped by the mod are stock re-saves, same as the two Title ones.

## What was converted and how

Method: three-way. Start from the stock Switch archive; for each entry the mod ships, diff mod against
stock Wii U and apply only the real differences to the stock Switch entry.

- **Textures.** Wii U BFLIM is de-tiled (GX2 tile modes 2 and 4, pipe/bank swizzle from the BFLIM flags) and
  written with the Tegra block-linear swizzle into a rebuilt `__Combined.bntx`.
  - Lossless (no re-encode, element/block data moved as-is): Title `Logo_W_00^l` (RGBA8 sRGB 993x780),
    `Logo2D_00^d` (now RGBA8_UNORM; stock was R8), `LogoDLC^q` (BC3 sRGB blocks), the three added
    `DLCLogoPack*3^s` (BC4 / BC4 / BC3 blocks, with the component selectors stock uses for the matching
    Wii U format).
  - Resampled: BootUp `Logo_W_00^l` 2056x1632 -> 1024x813 and `Logo3DGameTitle_00^l` 2102x1561 -> 1024x760,
    premultiplied-alpha Lanczos, kept RGBA8 sRGB as stock. **This is a judgement call, not the brief's
    "stock size".** Reasons: the panes that show them are 382x300 and 412x306 layout units on a 1280x720
    canvas (about 575 and 465 px wide at 1080p), so 1024 still oversamples; stock size (382 / 412 px) would
    be visibly soft at the mod's scale 1.0; full size would add 12.5 MB to the always-loaded Common
    archive (+10 MB to BootUp) for no visible gain. The cap is the second argument of `tools/build.py`
    (`build.py <lyt dir> 4096` builds full size; that variant was not built or checked).
  - All textures keep 1 mip, alignment 512, like every stock texture in these archives.
- **BNTX.** Rebuilt whole (string pool, `_DIC` trie, BRTI blocks, data, `_RLT`). The same code rebuilds all
  three stock files byte-identically. New textures are inserted in name order, as stock.
- **Layouts.** `Title_00`, `BootUp_00`: the changed floats are written into the stock Switch (v8, LE)
  sections; file sizes unchanged. `PaPauseQuest_00`: `txl1` rebuilt with the extra name, 4 texture
  indices patched in `mat1`; 23,836 -> 23,864 bytes. For every ported pane the stock Switch pane header
  equalled the byte-swapped stock Wii U one, so there were no Switch-specific values to lose.
- **Animation.** `PaPauseQuest_00_DLCLogo`: `pai1` converted field by field BE->LE; `pat1` is the stock
  Switch section with end frame 2->3.
- **Containers.** SARC rebuilt with oead from the stock archive (stock archives and packs round-trip
  byte-identically through the same call), Yaz0 with the stock header alignment 0x1000.

## Stayed stock, and why

- 13 animations (Title: `Title_00_In`, `Title_00_LoopRandom`; Common: `AmiiboWindow_00_Illust`,
  `DLCWindow_00_BeforeAfter`, `DLCWindow_00_Out`, `DLCWindow_00_SlowOut`, `DoCommand_00_GuideNum`,
  `PaPauseQuest_00_Loop`, `PaPauseQuest_00_PicLoad`, `PaPauseQuest_00_State`, `PaQuestName_00_Loop`,
  `Pa_AppMapOpenEf_00_Download`, `SystemWindow_01_ToSaving`): the mod's copies carry no change.
- 45 re-serialised sections of `Title_00.bflyt`: same reason.
- Every entry the mod does not ship.

## Verification (from the final packs; `work/verify.log`, `work/build.log`)

Tool validation against stock data:
- GX2 de-tile + NX swizzle: of the textures present in both stock Wii U and stock Switch archives with the
  same size, all 137 uncompressed ones (R8 102, R8G8 24, RGBA8 11) come out byte-identical. The 791
  block-compressed ones were re-encoded by Nintendo, so they are compared after decoding: mean abs
  difference median 0.26, worst 3.9 of 255 (no scrambled tiles). 3 RGB565 textures are not comparable
  byte-wise (different channel layout) and are not used here. (`work/validate_tex.log`)
- NX block-height rule and image size: predicted correctly for all 942 stock textures.
- `pai1` BE->LE converter: output equals the stock Switch section for 1225 of 1299 stock animations; the
  other 74 are 68 texture-pattern animations (texture names differ by the `.bflim` suffix) and 6 that
  Nintendo changed on Switch. (`work/validate_lyt.log`)
- bflyt/bflan writer reproduces all 1632 stock Switch layout files byte-exactly.

Output checks (all passed):
- Each `.sblarc` decompresses; SARC entry names and order equal stock Switch, no additions
  (Title 9, BootUp 4, Common 1624). Entries differing from stock are exactly: Title `blyt/Title_00.bflyt`,
  `timg/__Combined.bntx`; BootUp `blyt/BootUp_00.bflyt`, `timg/__Combined.bntx`; Common
  `anim/PaPauseQuest_00_DLCLogo.bflan`, `blyt/PaPauseQuest_00.bflyt`, `timg/__Combined.bntx`.
- All 333 bflyt and 1299 bflan parse as little-endian v8.0.0.0 with section sizes summing to the file
  size; every material texture index is inside its `txl1`; every texture name a layout references exists
  in the BNTX.
- BNTX: parses; all stock names present (18/18, 3/3, 921/921 + 3 added); `_DIC` lookup finds every name;
  every relocation entry points at an in-file pointer. Unchanged textures are byte-identical to stock
  (17, 2 and 918 of them).
- Changed textures decoded back out of the output BNTX by the Eden Duo runtime's decoder
  (`mod_nx_assets.cpp` + `bc_decoder`, compiled unmodified into `work/duo/duo_decode`; independent of the
  encoder) versus the mod's Wii U BFLIM:

  | Texture | Output | max diff | mean diff |
  |---|---|---|---|
  | Title `Logo_W_00^l` | RGBA8_SRGB 993x780 | 0 | 0 |
  | Common `Logo2D_00^d` | RGBA8_UNORM 360x257 | 0 | 0 |
  | Common `LogoDLC^q` | BC3_SRGB 414x314 | 0 | 0 |
  | Common `DLCLogoPack1_JPja3^s` | BC4_UNORM 494x154 | 0 | 0 |
  | Common `DLCLogoPack12LR_USen3^s` | BC4_UNORM 494x154 | 0 | 0 |
  | Common `DLCLogoPack1_USen3^s` | BC3_UNORM 494x154 | 0 | 0 |
  | BootUp `Logo_W_00^l` | RGBA8_SRGB 1024x813 | 31 | 0.25 |
  | Common `Logo3DGameTitle_00^l` | RGBA8_SRGB 1024x760 | 30 | 0.26 |

  The last two are compared with the mod image downscaled by Pillow (a different resize path, composited
  on grey); the maxima sit on single edge pixels. I looked at all eight before/mod/after sets: same
  artwork, colours and edges, no tiling artefacts.
- Packs: little-endian, entry names and order equal to their source pack; only `Layout/Title.sblarc`
  resp. `Layout/Common.sblarc` differ; all other 143 Bootup.pack entries byte-identical.

## Resource size table: changed

Layout archives are listed without the `s` (`Layout/Common.blarc`). Stock values are
`round_up(uncompressed size, 32) + 0x1000` for Title, BootUp and Horse exactly; Common's stock value is
320 below that rule. New values use the rule on the new uncompressed size:

| Entry | Old | New | Uncompressed archive |
|---|---|---|---|
| `Layout/Title.blarc` | 14,046,176 | 17,069,024 | 14,042,056 -> 17,064,904 |
| `Layout/BootUp.blarc` | 2,736,256 | 5,816,448 | 2,732,152 -> 5,812,344 |
| `Layout/Common.blarc` | 32,710,368 | 35,901,472 | 32,706,576 -> 35,897,360 |

Based on the merged `swfinal` table; exactly these 3 values differ. There are no table entries for the
packs or for files inside a layout archive.

## Not verified

- Loading and rendering in the game or the port.
- Whether the layout/resource heaps take the larger archives (Common +3.2 MB, BootUp +3.1 MB, Title
  +3.0 MB uncompressed) and whether the size-table rule is sufficient; it is inferred from four stock
  entries.
- That the game tolerates the inert `N_DLCLogo_03` animation entry on Switch (it is in the mod's Wii U
  file too). If the quest pause screen misbehaves, the stock `PaPauseQuest_00_DLCLogo.bflan` is the first
  thing to put back.
- Whether the game ever requests `DLCLogoPack1_USen3^s` / `DLCLogoPack12LR_USen3^s`; no layout names them.
- The 2x downscale of the two large logos is a visual choice; judge it on the device.

## Reproduce

    P=tools/venv/bin/python
    $P -I tools/build.py  <lyt dir> [max side, default 1024]
    $P -I tools/verify.py <lyt dir> <lyt dir>/work/duo/duo_decode

Inputs: `mod/` (from `sw.bnp`), `stockwiiu/` (from the .wua, `tools/wua.py`), `stocksw/` (adb pull),
unpacked into `work/{mod,wu,sw}` by `tools/ex.py`.
