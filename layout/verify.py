"""Verify the delivered files, starting from the final packs in out/ (not from build intermediates).
usage: verify.py <lyt dir> <duo_decode binary>"""
import sys, os, struct, subprocess, json, glob, shutil
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, oead
from PIL import Image
import lyt, bntx, tex
from rstb import Rstb

L, DUO = sys.argv[1], sys.argv[2]
W = f'{L}/work'; OUT = f'{L}/out'; V = f'{W}/verify'; PREV = f'{OUT}/preview'
shutil.rmtree(V, ignore_errors=True); os.makedirs(V); os.makedirs(PREV, exist_ok=True)
MERGED = f'{L}/../swfinal/x/swfinal/romfs'
LOG = []; FAIL = []
def log(*a):
    s = ' '.join(str(x) for x in a); LOG.append(s); print(s)
def check(cond, msg):
    if not cond: FAIL.append(msg); log('  FAIL:', msg)
    return cond

def sarc_entries(b):
    """independent of oead: parse SARC tables by hand -> {name: (start,end)}, endianness, data offset"""
    assert b[:4] == b'SARC'; e = '<' if b[6:8] == b'\xff\xfe' else '>'
    hl, bom, fsz, doff = struct.unpack_from(e+'HHII', b, 4); assert fsz == len(b)
    assert b[0x14:0x18] == b'SFAT'; n, = struct.unpack_from(e+'H', b, 0x1a)
    nt = 0x20+16*n; assert b[nt:nt+4] == b'SFNT'; nt += 8
    out = {}
    for i in range(n):
        h, attr, s, en = struct.unpack_from(e+'IIII', b, 0x20+16*i)
        name = lyt.cstr(b, nt+(attr & 0xffffff)*4); out[name] = (doff+s, doff+en)
    return out, e

def dict_lookup(b, B, name):
    """look a texture up the way nn::util::ResDic does (trie walk), from the raw bytes"""
    n, info, datablk, dic = struct.unpack_from('<Iqqq', b, 0x24)
    def node(i): return struct.unpack_from('<IHHq', b, dic+8+16*i)
    def key(i):
        p = node(i)[3]; l, = struct.unpack_from('<H', b, p); return b[p+2:p+2+l]
    def bit(k, r):
        by = r >> 3
        return (k[len(k)-1-by] >> (r & 7)) & 1 if by < len(k) else 0
    k = name.encode(); prev = 0; cur = node(0)[1]
    while (node(prev)[0] if prev else -1) < node(cur)[0] if cur else False:
        prev = cur; cur = node(cur)[1+bit(k, node(cur)[0])]
    return cur-1 if cur and key(cur) == k else -1

def comp(rgba, bg=96):
    a = rgba[..., 3:4].astype(np.int32); return ((rgba[..., :3].astype(np.int32)*a+bg*(255-a))//255).astype(np.uint8)
def flim_rgba(path):
    F = tex.flim(open(path, 'rb').read()); lin = tex.gx2_detile(F.data, F.w, F.h, F.bpe, F.blk, F.tile, F.swz)
    k = {'RGBA8': 'RGBA8', 'RGBA8_SRGB': 'RGBA8', 'BC3': 'BC3', 'BC3_SRGB': 'BC3', 'BC4L': 'BC4', 'BC4A': 'BC4', 'A8': 'R8', 'L8': 'R8'}[F.fname]
    d = tex.decode(lin, F.w, F.h, k)
    if d.shape[2] == 4: return np.ascontiguousarray(d), F
    v = d[..., 0]; o = np.full((F.h, F.w, 4), 255, np.uint8)
    if F.fname in ('BC4A', 'A8'): o[..., 3] = v
    else: o[..., :3] = v[..., None]
    return o, F
def duo(bntx_path, names, tag):
    d = f'{V}/duo_{tag}'; os.makedirs(d, exist_ok=True)
    r = subprocess.run([DUO, bntx_path, d]+names, capture_output=True, text=True)
    check(r.returncode == 0, f'Eden Duo decoder failed on {tag}: {r.stderr.strip()}')
    out = {}
    for line in r.stdout.split('\n'):
        if not line.strip(): continue
        nm, dim = line.rsplit(' ', 1); w, h = map(int, dim.split('x'))
        out[nm] = np.fromfile(f'{d}/{nm}.{w}x{h}.rgba', np.uint8).reshape(h, w, 4)
    return out

res = json.load(open(f'{W}/build_result.json'))
# ---------------------------------------------------------------- packs
log('# packs')
tp_new = open(f'{OUT}/Pack/Title.pack', 'rb').read(); tp_old = open(f'{L}/stocksw/Title.pack', 'rb').read()
bp_new = open(f'{OUT}/Pack/Bootup.pack', 'rb').read(); bp_old = open(f'{MERGED}/Pack/Bootup.pack', 'rb').read()
sbl = {}
for nm, new, old, target in (('Pack/Title.pack', tp_new, tp_old, 'Layout/Title.sblarc'), ('Pack/Bootup.pack', bp_new, bp_old, 'Layout/Common.sblarc')):
    en, e1 = sarc_entries(new); eo, e0 = sarc_entries(old)
    check(e1 == e0 == '<', f'{nm} endianness'); check(list(en) == list(eo), f'{nm} entry names/order')
    check(new[:0x14][:8] == old[:8] and struct.unpack_from('<I', new, 0xc)[0] == struct.unpack_from('<I', old, 0xc)[0], f'{nm} data offset')
    diff = [k for k in en if new[en[k][0]:en[k][1]] != old[eo[k][0]:eo[k][1]]]
    check(diff == [target], f'{nm}: entries that differ = {diff}')
    mis = [k for k in en if k != target and en[k][0] != eo[k][0] and (en[k][0]-eo[k][0]) % 4]
    al_ok = all((en[k][0] % 4 == 0) for k in en)
    # alignment of every entry: same power-of-two class as before (offset of each entry keeps the alignment it had)
    def a2(x): return (x & -x)
    worse = [k for k in en if min(a2(en[k][0]), 0x2000) < min(a2(eo[k][0]), 0x2000) and k != target]
    log(f'  {nm}: {len(en)} entries, little-endian, names/order identical to source pack, only {diff} differs; size {len(old)} -> {len(new)}; entries whose offset alignment got smaller: {len(worse)}')
    sbl[target] = new[en[target][0]:en[target][1]]
check(open(f'{OUT}/Layout/BootUp.sblarc', 'rb').read() == open(f'{OUT}/BootUp.sblarc', 'rb').read(), 'Layout/BootUp.sblarc copy')
sbl['Layout/BootUp.sblarc'] = open(f'{OUT}/Layout/BootUp.sblarc', 'rb').read()
for a in ('Title', 'Common'):
    check(sbl[f'Layout/{a}.sblarc'] == open(f'{OUT}/{a}.sblarc', 'rb').read(), f'{a}.sblarc in pack == out/{a}.sblarc')

# ---------------------------------------------------------------- archives
allstats = {}
for arc in ('Title', 'BootUp', 'Common'):
    log(f'\n# {arc}.sblarc')
    c = sbl[f'Layout/{arc}.sblarc']
    check(c[:4] == b'Yaz0' and struct.unpack_from('>I', c, 8)[0] == 0x1000, 'Yaz0 header')
    u = bytes(oead.yaz0.decompress(c)); check(len(u) == struct.unpack_from('>I', c, 4)[0], 'Yaz0 size')
    su = bytes(oead.yaz0.decompress(open(f'{W}/sw/{arc}.sblarc.raw', 'rb').read()))
    en, e1 = sarc_entries(u); eo, e0 = sarc_entries(su)
    check(e1 == '<', 'endianness'); check(list(en) == list(eo), 'entry names/order == stock Switch (no additions)')
    diff = sorted(k for k in en if u[en[k][0]:en[k][1]] != su[eo[k][0]:eo[k][1]])
    check(diff == res[arc]['replaced'], f'changed entries {diff}')
    check(en['timg/__Combined.bntx'][0] % 0x1000 == 0 and eo['timg/__Combined.bntx'][0] % 0x1000 == 0, 'bntx 0x1000 alignment')
    check(all(en[k][0] % 4 == 0 for k in en), 'entry alignment 4')
    log(f'  decompresses ({len(c)} -> {len(u)}); {len(en)} entries, names and order identical to stock Switch; entries differing from stock: {diff}')
    # every bflyt / bflan parses as LE v8
    nl = na = 0; missing_new = set(); missing_old = set()
    nb = u[en['timg/__Combined.bntx'][0]:en['timg/__Combined.bntx'][1]]; ob = su[eo['timg/__Combined.bntx'][0]:eo['timg/__Combined.bntx'][1]]
    B = bntx.parse(nb); B0 = bntx.parse(ob)
    texnames = {t.name for t in B.tex}; texnames0 = {t.name for t in B0.tex}
    for k in en:
        d = u[en[k][0]:en[k][1]]
        if k.endswith('.bflyt'):
            e, v, ss = lyt.secs(d); check(e == '<' and v == 0x08000000 and d[:4] == b'FLYT', f'{k} header'); nl += 1
            T = []; nmat = 0
            for m, s in ss:
                if m == 'txl1':
                    n, = struct.unpack_from('<H', s, 8); T = [lyt.cstr(s, 12+o) for o in struct.unpack_from('<%dI' % n, s, 12)]
                    missing_new |= {x for x in T if x not in texnames}
                if m == 'mat1':
                    n, = struct.unpack_from('<H', s, 8); nmat = n
                    for o in struct.unpack_from('<%dI' % n, s, 12):
                        fl, = struct.unpack_from('<I', s, o+28)
                        for t in range(fl & 3):
                            ti, = struct.unpack_from('<H', s, o+44+4*t); check(ti < len(T), f'{k}: material {lyt.cstr(s, o)} texture index {ti} out of range')
                if m in ('pic1',):
                    mi, = struct.unpack_from('<H', s, 100); check(mi < nmat, f'{k}: pic1 material index')
            d0 = su[eo[k][0]:eo[k][1]]
            for m, s in lyt.secs(d0)[2]:
                if m == 'txl1':
                    n, = struct.unpack_from('<H', s, 8); missing_old |= {x for x in (lyt.cstr(s, 12+o) for o in struct.unpack_from('<%dI' % n, s, 12)) if x not in texnames0}
        elif k.endswith('.bflan'):
            e, v, ss = lyt.secs(d); check(e == '<' and v == 0x08000000 and d[:4] == b'FLAN' and [m for m, _ in ss] == ['pat1', 'pai1'], f'{k} header'); na += 1
            try: lyt.pai1_dump(ss[1][1], '<')
            except Exception as ex: check(False, f'{k} pai1 walk: {ex}')
    check(missing_new == missing_old, f'layout texture names not in BNTX changed: {missing_new ^ missing_old}')
    log(f'  {nl} bflyt + {na} bflan parse as little-endian v8.0.0.0, section sizes sum to file size, pai1 offset tables walk in bounds; every material texture index is inside its txl1; layout texture names missing from the BNTX: {len(missing_new)} (stock: {len(missing_old)}, same set)')
    # BNTX
    check(bntx.build(B) == nb, 'BNTX re-serialises identically')
    check(texnames0 <= texnames, 'stock texture names all present')
    added = sorted(texnames-texnames0)
    by0 = {t.name: t for t in B0.tex}; changed = []
    for t in B.tex:
        o = by0.get(t.name)
        if o is None: continue
        if bytes(t.hdr) != bytes(o.hdr) or t.data != o.data: changed.append(t.name)
    exp_changed = sorted(k for k, v in res[arc]['tex'].items() if not v['added']); exp_added = sorted(k for k, v in res[arc]['tex'].items() if v['added'])
    check(sorted(changed) == exp_changed and added == exp_added, f'texture changes {changed} added {added}')
    # relocation table: expands to exactly the set of non-null pointers
    secs = bntx.rlt_expand(nb[B.rlt:])
    ptrs = set(secs[0][2]) | set(secs[1][2]); ok = True
    for p in ptrs:
        v, = struct.unpack_from('<q', nb, p); ok &= 0 < v < len(nb)
    check(ok, 'relocation entries point at non-null in-file pointers')
    for t in B.tex:
        check(dict_lookup(nb, B, t.name) == B.tex.index(t), f'_DIC lookup {t.name}') if (t.name in res[arc]['tex'] or B.tex.index(t) % 37 == 0) else None
    nlook = sum(1 for t in B.tex if dict_lookup(nb, B, t.name) == B.tex.index(t)); check(nlook == len(B.tex), '_DIC lookups')
    for t in B.tex:
        check(t.off % 512 == 0 and t.off+t.size <= B.rlt, f'{t.name} data placement')
    log(f'  __Combined.bntx parses; {len(B.tex)} textures (stock {len(B0.tex)}); all {len(texnames0)} stock names present; added {added}; changed {changed}; the other {len(B0.tex)-len(changed)} stock textures are byte-identical (header fields + data); _DIC trie lookup finds all {nlook} names; {len(ptrs)} relocation entries all point in-file')
    # decode through the Eden Duo runtime's decoder (independent of the encoder used here)
    open(f'{V}/{arc}.new.bntx', 'wb').write(nb); open(f'{V}/{arc}.old.bntx', 'wb').write(ob)
    names = exp_changed+exp_added
    dn = duo(f'{V}/{arc}.new.bntx', names, arc+'_new'); do = duo(f'{V}/{arc}.old.bntx', exp_changed, arc+'_old')
    for nm in names:
        ref, F = flim_rgba(f'{W}/mod/{arc}.sblarc/timg/{nm}.bflim')
        got = dn[nm]; meta = res[arc]['tex'][nm]
        base = f'{PREV}/{arc}__{nm}'
        Image.fromarray(ref).save(base+'.mod_wiiu.png'); Image.fromarray(got).save(base+'.out_switch.png')
        if nm in do: Image.fromarray(do[nm]).save(base+'.stock_switch.png')
        resized = got.shape != ref.shape
        if resized:
            # independent reference: Pillow's own RGBA resize of the composite over grey (no premultiply code shared)
            r2 = np.asarray(Image.fromarray(comp(ref)).resize((got.shape[1], got.shape[0]), Image.LANCZOS)).astype(int)
            d = np.abs(comp(got).astype(int)-r2); what = f'vs mod {F.w}x{F.h} downscaled to {got.shape[1]}x{got.shape[0]} (composited on grey)'
            da = np.abs(got[..., 3].astype(int)-np.asarray(Image.fromarray(ref[..., 3]).resize((got.shape[1], got.shape[0]), Image.LANCZOS)).astype(int))
            extra = f'; alpha max {da.max()} mean {da.mean():.3f}'
        else:
            vis = ref[..., 3] > 0
            d = np.abs(got.astype(int)-ref.astype(int)); what = 'vs mod, all RGBA channels, same size'
            extra = f'; exact match: {bool((d == 0).all())}'
        log(f'  texture {nm}: {meta["fmt"]} {got.shape[1]}x{got.shape[0]} decoded by Eden Duo {what}: max diff {d.max()} mean {d.mean():.4f}{extra}')
        allstats[f'{arc}/{nm}'] = dict(max=int(d.max()), mean=float(d.mean()), resized=resized)
        check(d.mean() < 1.5, f'{nm} decoded image differs from the mod source')
        # contact strip: stock | mod | output, on grey
        tiles = ([do[nm]] if nm in do else [])+[ref, got]
        hmax = 300; ims = []
        for t in tiles:
            im = Image.fromarray(comp(t)); im.thumbnail((460, hmax)); ims.append(im)
        strip = Image.new('RGB', (sum(i.width for i in ims)+10*(len(ims)-1), max(i.height for i in ims)), (20, 20, 20)); x = 0
        for im in ims: strip.paste(im, (x, 0)); x += im.width+10
        strip.save(base+'.compare.png')

# ---------------------------------------------------------------- size table
log('\n# ResourceSizeTable')
p = f'{OUT}/System/Resource/ResourceSizeTable.product.srsizetable'
if os.path.exists(p):
    R = Rstb(open(p, 'rb').read()); R0 = Rstb(open(f'{MERGED}/System/Resource/ResourceSizeTable.product.srsizetable', 'rb').read())
    check(len(R.d) == len(R0.d) and R.ncrc == R0.ncrc, 'table shape')
    d = [i for i in range(0, len(R.d), 4) if R.d[i:i+4] != R0.d[i:i+4]]
    check(len(d) == 3, f'{len(d)} words differ')
    for arc in ('Title', 'BootUp', 'Common'):
        k = f'Layout/{arc}.blarc'; u = len(oead.yaz0.decompress(sbl[f'Layout/{arc}.sblarc']))
        check(R.get(k) >= tex.al(u, 32)+0x1000, k)
        log(f'  {k}: {R0.get(k)} -> {R.get(k)} (uncompressed archive {u}, +{R.get(k)-u})')
    log(f'  table has the same {R.ncrc} entries as the merged table; exactly {len(d)} values differ')
else:
    log('  no updated table delivered')
log('\nRESULT:', 'ALL CHECKS PASSED' if not FAIL else f'{len(FAIL)} FAILURE(S): {FAIL}')
open(f'{W}/verify.log', 'w').write('\n'.join(LOG)+'\n')
json.dump(allstats, open(f'{W}/verify_tex.json', 'w'), indent=1)
sys.exit(1 if FAIL else 0)
