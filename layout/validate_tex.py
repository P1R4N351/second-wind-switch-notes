# Mass validation: every texture present in both stock Wii U and stock Switch archives with identical dims and
# byte-compatible format must de-tile (GX2) and de-swizzle (NX) to the same linear data.
import sys,os,glob,struct; sys.path.insert(0,os.path.dirname(__file__)); import bntx,tex
from collections import Counter
import numpy as np
W=sys.argv[1]
bcm=[]; stat=Counter(); bhfit=Counter(); cs=Counter(); bad=[]
COMPAT={'L8':'R8','A8':'R8','LA8':'R8G8','RGBA8':'RGBA8','RGBA8_SRGB':'RGBA8','BC1':'BC1','BC1_SRGB':'BC1','BC3':'BC3','BC3_SRGB':'BC3','BC4L':'BC4','BC4A':'BC4','BC5':'BC5','RGB565':'B5G6R5'}
for a in ('Title','BootUp','Common'):
    B=bntx.parse(open(f'{W}/sw/{a}.sblarc/timg/__Combined.bntx','rb').read())
    for t in B.tex:
        nm,bpe,blk=tex.NXFMT[t.fmt>>8]
        wb,hb=(t.w+blk-1)//blk,(t.h+blk-1)//blk
        pred=tex.nx_block_height_log2(hb)
        bhfit[(pred==t.layout)]+=1
        if pred!=t.layout: bad.append(('bh',t.name,t.w,t.h,nm,t.layout,pred))
        idx,size=tex.nx_addr(wb,hb,bpe,t.layout)
        stat['size_ok' if size==t.size else 'size_BAD']+=1
        if size!=t.size: bad.append(('size',t.name,t.w,t.h,nm,t.size,size))
        p=f'{W}/wu/{a}.sblarc/timg/{t.name}.bflim'
        if not os.path.exists(p): stat['no_wiiu']+=1; continue
        F=tex.flim(open(p,'rb').read())
        cs[(F.fname,bntx.fmtname(t.fmt),hex(t.compsel))]+=1
        if (F.w,F.h)!=(t.w,t.h): stat['dims_differ']+=1; continue
        if COMPAT.get(F.fname)!=nm: stat['fmt_differ']+=1; continue
        try: g=tex.gx2_detile(F.data,F.w,F.h,F.bpe,F.blk,F.tile,F.swz)
        except NotImplementedError as e: stat['tile_unsupported_'+str(F.tile)]+=1; continue
        except IndexError as e: stat['gx2_oob_tile%d'%F.tile]+=1; bad.append(('oob',t.name,F.w,F.h,F.fname,F.tile,len(F.data))); continue
        s=tex.nx_deswizzle(t.data,wb,hb,bpe,t.layout)
        if nm in('B5G6R5',): g=g[:,:,::-1]   # 16-bit big-endian elements on Wii U
        if np.array_equal(g,s): stat[f'IDENT tile{F.tile} {nm}']+=1
        else:
            if nm.startswith('BC'):
                m=np.abs(tex.decode(g,t.w,t.h,nm).astype(int)-tex.decode(s,t.w,t.h,nm).astype(int)).mean()
                bcm.append((m,t.name,nm,F.tile,t.w,t.h)); stat[f'BC re-encoded, decoded-pixel compare tile{F.tile} {nm}']+=1
            else:
                d=(g!=s).any(axis=2).mean(); stat[f'DIFF tile{F.tile} {nm}']+=1; bad.append(('data',t.name,t.w,t.h,F.fname,F.tile,F.swz,round(float(d),4)))
for k in sorted(stat): print(k,stat[k])
print('block-height rule fit',dict(bhfit))
for k in sorted(cs): print('  fmt map',k,cs[k])
print(len(bad)); [print(' ',b) for b in bad[:60]]

bcm.sort(); print('BC decoded mean abs diff (0-255): n',len(bcm),'median',round(bcm[len(bcm)//2][0],3),'p99',round(bcm[int(len(bcm)*.99)][0],3),'worst',[(round(r[0],2),)+r[1:] for r in bcm[-6:]])
