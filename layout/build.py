"""Port Second Wind's three Wii U layout archives onto the stock Switch 1.6.0 archives.

usage: build.py <lyt dir> [max_texture_side]
Inputs (already extracted by ex.py):  work/mod  (mod, Wii U, only changed entries)
                                      work/wu   (stock Wii U v208)      work/sw (stock Switch 1.6.0)
Method: three-way.  For every entry the mod ships, compare mod vs stock Wii U; whatever really changed is
applied to the stock Switch entry; everything else in the Switch archive is left byte-identical.
"""
import sys, os, struct, bisect, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, oead
from PIL import Image
import lyt, bntx, tex
from rstb import Rstb

L = sys.argv[1]
MAXSIDE = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
W = f'{L}/work'; OUT = f'{L}/out'
LOG = []
def log(*a):
    s = ' '.join(str(x) for x in a); LOG.append(s); print(s)

# ------------------------------------------------------------------ layouts
def swap_words(b):  # big-endian u32/f32 words -> little-endian
    return b''.join(b[i:i+4][::-1] for i in range(0, len(b), 4))

def txl_names(d, e):
    n, = struct.unpack_from(e+'H', d, 8); offs = struct.unpack_from(e+'%dI' % n, d, 12)
    return [lyt.cstr(d, 12+o) for o in offs]
def txl_build(names):
    tab = b''; strs = b''; base = 4*len(names)
    for n in names:
        tab += struct.pack('<I', base+len(strs)); strs += n.encode()+b'\0'
    body = struct.pack('<HH', len(names), 0)+tab+strs
    body += b'\0'*(-len(body) % 4)
    return b'txl1'+struct.pack('<I', 8+len(body))+body
def mat_offs(d, e):
    n, = struct.unpack_from(e+'H', d, 8); return list(struct.unpack_from(e+'%dI' % n, d, 12))

def port_bflyt(rel):
    """returns new Switch bflyt bytes"""
    mod = open(f'{W}/mod/{rel}', 'rb').read(); wu = open(f'{W}/wu/{rel}', 'rb').read(); sw = open(f'{W}/sw/{rel}', 'rb').read()
    em, vm, M = lyt.secs(mod); ew, vw, U = lyt.secs(wu); es, vs, S = lyt.secs(sw)
    assert (em, ew, es) == ('>', '>', '<') and vm == vw == 0x05020000 and vs == 0x08000000
    assert [m for m, _ in M] == [m for m, _ in U] == [m for m, _ in S], 'section sequence differs'
    out = []; stats = dict(identical=0, reserialised=0, ported=0)
    log(f'## {rel}: {len(S)} sections; mod/WiiU v{vm:08x} BE, Switch v{vs:08x} LE')
    for i, ((m, dm), (_, du), (_, ds)) in enumerate(zip(M, U, S)):
        if dm == du:
            out.append(ds); stats['identical'] += 1; continue
        nm = lyt.pane_name(dm) if m in lyt.PANES else ''
        if m == 'txl1':
            a, b, c = txl_names(dm, '>'), txl_names(du, '>'), txl_names(ds, '<')
            assert [x.replace('.bflim', '') for x in b] == c, 'stock texture lists differ'
            assert a[:len(b)] == b, 'mod reorders textures'
            add = [x.replace('.bflim', '') for x in a[len(b):]]
            out.append(txl_build(c+add)); stats['ported'] += 1
            log(f'  [{i}] txl1: texture list +{add} (index {len(b)}..)')
            continue
        if m == 'mat1':
            assert len(dm) == len(du)
            om = mat_offs(du, '>'); os_ = mat_offs(ds, '<'); assert mat_offs(dm, '>') == om and len(om) == len(os_)
            ns = bytearray(ds)
            diffs = [k for k in range(len(dm)) if dm[k] != du[k]]
            done = set()
            for k in diffs:
                mi = bisect.bisect_right(om, k)-1; rel_ = k-om[mi]
                flags, = struct.unpack_from('>I', du, om[mi]+36); ntex = flags & 3
                assert 40 <= rel_ < 40+4*ntex and (rel_-40) % 4 < 2, f'unsupported mat1 change at material {mi} +{rel_}'
                t = (rel_-40)//4
                if (mi, t) in done: continue
                done.add((mi, t))
                new, = struct.unpack_from('>H', dm, om[mi]+40+4*t); old, = struct.unpack_from('>H', du, om[mi]+40+4*t)
                name = lyt.cstr(du, om[mi]); assert lyt.cstr(ds, os_[mi]) == name
                sflags, = struct.unpack_from('<I', ds, os_[mi]+28); assert sflags & 3 == ntex
                cur, = struct.unpack_from('<H', ds, os_[mi]+44+4*t); assert cur == old, (cur, old)
                assert ds[os_[mi]+46+4*t:os_[mi]+48+4*t] == du[om[mi]+42+4*t:om[mi]+44+4*t]  # wrap modes agree
                struct.pack_into('<H', ns, os_[mi]+44+4*t, new)
                log(f'  [{i}] mat1: material {name} texture map {t}: texture index {old} -> {new}')
            out.append(bytes(ns)); stats['ported'] += 1
            continue
        # semantic comparison (the mod's editor re-serialises usd1 / txt1 / prt1 without changing content)
        if m in ('usd1', 'txt1', 'prt1') and lyt.norm_any(m, dm) == lyt.norm_any(m, du):
            out.append(ds); stats['reserialised'] += 1; continue
        if m in lyt.PANES:
            bm, bu = dm[8:84], du[8:84]
            if m in ('txt1', 'prt1'):
                # content after the pane base must still be semantically equal
                x = list(lyt.norm_any(m, dm)); y = list(lyt.norm_any(m, du)); x[1] = y[1] = None
                assert x == y, f'unsupported change in {m} {nm} beyond the pane base'
            else:
                assert len(dm) == len(du) and dm[84:] == du[84:] and dm[:8] == du[:8], f'unsupported change in {m} {nm}'
            ns = bytearray(ds)
            # pane base: 4 flag bytes, name[24], userinfo[8] are raw; 10 floats are byte-swapped
            def base_le(b): return b[:36]+swap_words(b[36:])
            pre = base_le(bu)
            if bytes(ds[8:84]) != pre:
                log(f'  [{i}] {m} {nm}: NOTE stock Switch pane base differs from stock Wii U; only the fields the mod changed are overwritten')
            fields = [('flags', 0, 1), ('origin', 1, 1), ('alpha', 2, 1), ('magflags', 3, 1)] + \
                     [(f, 36+4*j, 4) for j, f in enumerate(('Tx', 'Ty', 'Tz', 'Rx', 'Ry', 'Rz', 'Sx', 'Sy', 'W', 'H'))]
            assert bm[4:36] == bu[4:36], 'pane renamed / user info changed'
            ch = []
            for f, o, n in fields:
                if bm[o:o+n] != bu[o:o+n]:
                    if n == 4:
                        ns[8+o:8+o+4] = bm[o:o+4][::-1]
                        ch.append(f'{f} {struct.unpack(">f", bu[o:o+4])[0]:g}->{struct.unpack(">f", bm[o:o+4])[0]:g}')
                    else:
                        ns[8+o] = bm[o]; ch.append(f'{f} {bu[o]}->{bm[o]}')
            assert ch
            log(f'  [{i}] {m} {nm}: ' + ', '.join(ch))
            out.append(bytes(ns)); stats['ported'] += 1
            continue
        raise SystemExit(f'unsupported change in section {i} {m}')
    new = lyt.build(b'FLYT', vs, out)
    log(f'  => {stats["identical"]} sections identical to stock Wii U (stock Switch kept), {stats["reserialised"]} re-serialised only (stock Switch kept), {stats["ported"]} ported; size {len(sw)} -> {len(new)}')
    lyt.secs(new)
    return new

def pat1_sem(d, e, sw):
    order, cnt, no, go = struct.unpack_from(e+'HHII', d, 8)
    o = 24 if sw else 20
    start, end, child = struct.unpack_from(e+'HHB', d, o)
    name = lyt.cstr(d, no); groups = [d[go+28*i:go+28*i+28].split(b'\0')[0].decode() if not sw else d[go+36*i:go+36*i+36].split(b'\0')[0].decode() for i in range(cnt)]
    return dict(order=order, name=name, groups=groups, start=start, end=end, child=child)

def port_bflan(rel):
    """returns None when the mod's file is semantically the stock Wii U one, else new Switch bytes"""
    mod = open(f'{W}/mod/{rel}', 'rb').read(); wu = open(f'{W}/wu/{rel}', 'rb').read(); sw = open(f'{W}/sw/{rel}', 'rb').read()
    em, vm, M = lyt.secs(mod); ew, vw, U = lyt.secs(wu); es, vs, S = lyt.secs(sw)
    assert [m for m, _ in M] == [m for m, _ in U] == [m for m, _ in S] == ['pat1', 'pai1']
    pm, pu, ps = pat1_sem(M[0][1], '>', False), pat1_sem(U[0][1], '>', False), pat1_sem(S[0][1], '<', True)
    assert pu == ps, ('stock pat1 differ', pu, ps)
    same_pai = M[1][1] == U[1][1]
    if pm == pu and same_pai:
        return None
    npat = bytearray(S[0][1])
    ch = [k for k in pm if pm[k] != pu[k]]
    assert set(ch) <= {'start', 'end'}, ch
    struct.pack_into('<HH', npat, 24, pm['start'], pm['end'])
    assert lyt.pai1_be2le(U[1][1]) == S[1][1], 'stock pai1 does not convert exactly; refusing'
    npai = lyt.pai1_be2le(M[1][1])
    new = lyt.build(b'FLAN', vs, [bytes(npat), npai])
    log(f'## {rel}: pat1 {", ".join(f"{k} {pu[k]}->{pm[k]}" for k in ch)}; pai1 converted BE->LE ({len(U[1][1])} -> {len(npai)} bytes)')
    a = lyt.pai1_dump(U[1][1], '>'); b = lyt.pai1_dump(M[1][1], '>'); c = lyt.pai1_dump(npai, '<')
    assert b == c, 'converted pai1 does not read back equal'
    for x in b:
        if x not in a: log('     mod  :', x)
    for x in a:
        if x not in b: log('     stock:', x)
    return new

# ------------------------------------------------------------------ textures
FIELDS = [(0x0c, 4), (0x14, 4), (0x18, 4), (0x24, 4), (0x40, 4), (0x48, 4)]   # fmt, w, h, layout, size, compsel (hdr-relative)
def masked(h):
    h = bytearray(h)
    for o, n in FIELDS: h[o:o+n] = bytes(n)
    return bytes(h)
# Wii U BFLIM format -> (Switch format, component selector); every pair below occurs in the stock archives
# (see validate_tex.py 'fmt map').
FMTMAP = {'RGBA8_SRGB': (0x0b06, 0x05040302, 'RGBA8'), 'RGBA8': (0x0b01, 0x05040302, 'RGBA8'), 'BC3_SRGB': (0x1c06, 0x05040302, 'BC3'),
          'BC3': (0x1c01, 0x05040302, 'BC3'), 'BC4A': (0x1d01, 0x02010101, 'BC4'), 'BC4L': (0x1d01, 0x01020202, 'BC4')}

def resample_rgba(rgba, w, h):
    """premultiplied-alpha Lanczos (avoids dark/bright fringes from RGB under alpha 0)"""
    a = rgba.astype(np.float32)/255.0
    pm = a[..., :3]*a[..., 3:4]
    ch = [np.asarray(Image.fromarray(np.ascontiguousarray(c), 'F').resize((w, h), Image.LANCZOS)) for c in (pm[..., 0], pm[..., 1], pm[..., 2], a[..., 3])]
    al = np.clip(ch[3], 0, 1)
    rgb = np.stack(ch[:3], -1)/np.maximum(al, 1e-6)[..., None]
    out = np.concatenate([np.clip(rgb, 0, 1), al[..., None]], -1)
    out[al <= 0] = 0
    return np.round(out*255).astype(np.uint8)

def port_bntx(arc, plan):
    """plan: list of mod texture names (without .bflim). returns new bntx bytes"""
    stock = open(f'{W}/sw/{arc}.sblarc/timg/__Combined.bntx', 'rb').read()
    B = bntx.parse(stock); assert bntx.build(B) == stock, 'stock BNTX does not round-trip'
    names = [t.name for t in B.tex]; assert names == sorted(names, key=lambda s: s.encode()), 'stock textures not byte-sorted'
    assert len({masked(t.hdr) for t in B.tex}) == 1, 'BRTI headers vary outside the known fields'
    log(f'## {arc}.sblarc timg/__Combined.bntx: {len(B.tex)} stock textures; stock file rebuilds byte-identically')
    meta = {}
    for name in plan:
        F = tex.flim(open(f'{W}/mod/{arc}.sblarc/timg/{name}.bflim', 'rb').read())
        lin = tex.gx2_detile(F.data, F.w, F.h, F.bpe, F.blk, F.tile, F.swz)
        fmt, compsel, kind = FMTMAP[F.fname]
        w, h = F.w, F.h; how = 'data transplanted losslessly (GX2 de-tile -> NX swizzle)'
        old = next((t for t in B.tex if t.name == name), None)
        if kind == 'RGBA8':
            lin = lin[:h, :w]
            if max(w, h) > MAXSIDE:
                s = MAXSIDE/max(w, h); nw, nh = round(w*s), round(h*s)
                lin = resample_rgba(lin, nw, nh); how = f'resampled {w}x{h} -> {nw}x{nh} (premultiplied Lanczos), then NX swizzle'
                w, h = nw, nh
        lin = np.ascontiguousarray(lin)
        hb, wb, bpe = lin.shape
        bhl2 = tex.nx_block_height_log2(hb)
        data = tex.nx_swizzle(lin, bhl2)
        t = bntx.Tex(); t.name = name
        hdr = bytearray(B.tex[0].hdr)
        struct.pack_into('<I', hdr, 0x0c, fmt); struct.pack_into('<ii', hdr, 0x14, w, h); struct.pack_into('<I', hdr, 0x24, bhl2)
        struct.pack_into('<I', hdr, 0x40, len(data)); struct.pack_into('<I', hdr, 0x48, compsel)
        t.hdr = hdr; t.data = data; t.rel = [0]; t.talign = 512; t.fmt = fmt; t.w = w; t.h = h; t.layout = bhl2; t.size = len(data); t.compsel = compsel; t.mips = 1
        if old is not None:
            log(f'  replace {name}: stock {bntx.fmtname(old.fmt)} {old.w}x{old.h} ({old.size} B) <- mod {F.fname} {F.w}x{F.h} => {bntx.fmtname(fmt)} {w}x{h} ({len(data)} B); {how}')
            B.tex[names.index(name)] = t
        else:
            k = bisect.bisect_left([n.encode() for n in names], name.encode())
            B.tex.insert(k, t); names.insert(k, name); B.strs.append(name)
            log(f'  add     {name}: mod {F.fname} {F.w}x{F.h} => {bntx.fmtname(fmt)} {w}x{h} ({len(data)} B), index {k}; {how}')
        meta[name] = dict(src_fmt=F.fname, src_w=F.w, src_h=F.h, fmt=bntx.fmtname(fmt), w=w, h=h, added=old is None)
    new = bntx.build(B)
    B2 = bntx.parse(new)   # re-parse: asserts structure
    log(f'  => {len(stock)} -> {len(new)} bytes, {len(B2.tex)} textures')
    return new, meta

# ------------------------------------------------------------------ archives
def rebuild_sarc(stock_bytes, repl):
    s = oead.Sarc(stock_bytes); assert s.get_endianness() == oead.Endianness.Little
    wr = oead.SarcWriter.from_sarc(s)
    a0, chk = wr.write(); assert bytes(chk) == bytes(stock_bytes), 'stock SARC does not round-trip'
    have = {f.name for f in s.get_files()}
    for k, v in repl.items():
        assert k in have, k
        wr.files[k] = v
    al_, o = wr.write()
    return bytes(o)

def main():
    os.makedirs(f'{OUT}/Pack', exist_ok=True); os.makedirs(f'{OUT}/Layout', exist_ok=True); os.makedirs(f'{OUT}/System/Resource', exist_ok=True)
    plan = {
        'Title': dict(blyt=['Title_00'], anim=['Title_00_In', 'Title_00_LoopRandom'], timg=['Logo_W_00^l']),
        'BootUp': dict(blyt=['BootUp_00'], anim=[], timg=['Logo_W_00^l']),
        'Common': dict(blyt=['PaPauseQuest_00'], anim=None, timg=['Logo2D_00^d', 'Logo3DGameTitle_00^l', 'LogoDLC^q', 'DLCLogoPack12LR_USen3^s', 'DLCLogoPack1_JPja3^s', 'DLCLogoPack1_USen3^s']),
    }
    result = {}
    for arc, p in plan.items():
        log(f'\n# ===== {arc}.sblarc =====')
        # the plan must cover exactly what the mod ships
        shipped = sorted(os.path.relpath(os.path.join(r, f), f'{W}/mod/{arc}.sblarc') for r, _, fs in os.walk(f'{W}/mod/{arc}.sblarc') for f in fs)
        anims = sorted(x[5:-6] for x in shipped if x.startswith('anim/'))
        if p['anim'] is None: p['anim'] = anims
        want = sorted([f'blyt/{x}.bflyt' for x in p['blyt']]+[f'anim/{x}.bflan' for x in p['anim']]+[f'timg/{x}.bflim' for x in p['timg']])
        assert want == shipped, (want, shipped)
        repl = {}
        for b in p['blyt']:
            repl[f'blyt/{b}.bflyt'] = port_bflyt(f'{arc}.sblarc/blyt/{b}.bflyt')
        kept = []
        for a in p['anim']:
            r = port_bflan(f'{arc}.sblarc/anim/{a}.bflan')
            if r is None: kept.append(a)
            else: repl[f'anim/{a}.bflan'] = r
        if kept: log(f'## {len(kept)} animation(s) shipped by the mod are the stock Wii U animation re-saved (pai1 byte-identical, pat1 same fields, only trailing padding dropped) -> stock Switch file kept: {", ".join(kept)}')
        nb, meta = port_bntx(arc, p['timg'])
        repl['timg/__Combined.bntx'] = nb
        stock_raw = open(f'{W}/sw/{arc}.sblarc.raw', 'rb').read()
        stock_u = bytes(oead.yaz0.decompress(stock_raw))
        new_u = rebuild_sarc(stock_u, repl)
        new_c = bytes(oead.yaz0.compress(new_u, 0x1000, 7))
        assert struct.unpack_from('>I', stock_raw, 8)[0] == 0x1000
        open(f'{OUT}/{arc}.sblarc', 'wb').write(new_c)
        log(f'## {arc}.sblarc: uncompressed {len(stock_u)} -> {len(new_u)}, Yaz0 {len(stock_raw)} -> {len(new_c)}; replaced entries: {sorted(repl)}')
        result[arc] = dict(stock_u=len(stock_u), new_u=len(new_u), replaced=sorted(repl), tex=meta, kept_anims=kept)
    # ---- packs
    tp = open(f'{L}/stocksw/Title.pack', 'rb').read()
    open(f'{OUT}/Pack/Title.pack', 'wb').write(rebuild_sarc(tp, {'Layout/Title.sblarc': open(f'{OUT}/Title.sblarc', 'rb').read()}))
    merged = f'{L}/../swfinal/x/swfinal/romfs'
    bp = open(f'{merged}/Pack/Bootup.pack', 'rb').read()
    assert oead.Sarc(bp).get_file('Layout/BootUp.sblarc') is None
    open(f'{OUT}/Pack/Bootup.pack', 'wb').write(rebuild_sarc(bp, {'Layout/Common.sblarc': open(f'{OUT}/Common.sblarc', 'rb').read()}))
    open(f'{OUT}/Layout/BootUp.sblarc', 'wb').write(open(f'{OUT}/BootUp.sblarc', 'rb').read())
    log('\n# packs: Pack/Title.pack (stock + Layout/Title.sblarc), Pack/Bootup.pack (merged + Layout/Common.sblarc), Layout/BootUp.sblarc (loose romfs file on Switch; it is NOT inside Bootup.pack)')
    # ---- resource size table
    log('\n# ===== ResourceSizeTable =====')
    R = Rstb(open(f'{merged}/System/Resource/ResourceSizeTable.product.srsizetable', 'rb').read())
    changed = False
    for arc in plan:
        key = f'Layout/{arc}.blarc'; cur = R.get(key); need = tex.al(result[arc]['new_u'], 32)+0x1000
        stock_rule = tex.al(result[arc]['stock_u'], 32)+0x1000
        log(f'  {key}: table {cur} (stock rule al32(size)+0x1000 = {stock_rule}); new uncompressed {result[arc]["new_u"]} -> needs {need}: {"RAISED" if need > cur else "kept"}')
        if need > cur: R.set(key, need); changed = True
        result[arc]['rstb'] = dict(key=key, old=cur, new=max(cur, need))
    if changed:
        open(f'{OUT}/System/Resource/ResourceSizeTable.product.srsizetable', 'wb').write(R.pack())
    result['rstb_changed'] = changed
    json.dump(result, open(f'{W}/build_result.json', 'w'), indent=1)
    open(f'{W}/build.log', 'w').write('\n'.join(LOG)+'\n')

main()
