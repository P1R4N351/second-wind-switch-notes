"""GX2 (Wii U) de-tiling, NX (Tegra block-linear) swizzle, BFLIM parsing. numpy-vectorised."""
import struct, numpy as np
def al(x,a): return (x+a-1)//a*a
# ---------- BFLIM ----------
# format id -> (name, bytes per element, block dim)
BFLIM_FMT={0x00:('L8',1,1),0x01:('A8',1,1),0x02:('LA4',1,1),0x03:('LA8',2,1),0x05:('RGB565',2,1),0x06:('RGB8',4,1),0x07:('RGB5A1',2,1),0x08:('RGBA4',2,1),
 0x09:('RGBA8',4,1),0x0c:('BC1',8,4),0x0d:('BC2',16,4),0x0e:('BC3',16,4),0x0f:('BC4L',8,4),0x10:('BC4A',8,4),0x11:('BC5',16,4),
 0x14:('RGBA8_SRGB',4,1),0x15:('BC1_SRGB',8,4),0x16:('BC2_SRGB',16,4),0x17:('BC3_SRGB',16,4)}
class Flim: pass
def flim(b):
    F=Flim()
    dsz,=struct.unpack('>I',b[-4:]); o=len(b)-0x28
    assert b[o:o+4]==b'FLIM' and b[o+4:o+6]==b'\xfe\xff' and b[o+0x14:o+0x18]==b'imag', b[o:o+0x28].hex()
    F.ver,=struct.unpack('>I',b[o+8:o+12])
    F.w,F.h,F.align,F.fmt,F.flag=struct.unpack('>HHHBB',b[o+0x1c:o+0x24])
    assert dsz==o, (dsz,o)
    F.data=b[:o]; F.tile=F.flag&0x1f; F.swz=F.flag>>5
    F.fname,F.bpe,F.blk=BFLIM_FMT[F.fmt]
    return F
# ---------- GX2 addrlib (thin tile modes) ----------
def _pix_index(x,y,bpp):
    x0=x&1;x1=(x>>1)&1;x2=(x>>2)&1;y0=y&1;y1=(y>>1)&1;y2=(y>>2)&1
    if bpp==8: b=(x0,x1,x2,y1,y0,y2)
    elif bpp==16: b=(x0,x1,x2,y0,y1,y2)
    elif bpp==64: b=(x0,y0,x1,x2,y1,y2)
    elif bpp==128: b=(y0,x0,x1,x2,y1,y2)
    else: b=(x0,x1,y0,x2,y1,y2)
    return b[0]|(b[1]<<1)|(b[2]<<2)|(b[3]<<3)|(b[4]<<4)|(b[5]<<5)
def gx2_surface_dims(wb,hb,tile,bpp=32):
    if tile in (2,3): return al(wb,max(8,8*(256//bpp//8))),al(hb,8)   # micro-tiled pitch align (fitted: 8bpp -> 32)
    if tile==4: return al(wb,max(32,32*(256//bpp//8))),al(hb,16)
    raise NotImplementedError('tile mode %d'%tile)
def gx2_addr(wb,hb,bpe,tile,swz):
    """returns element index array (hb,wb) into the tiled surface (in units of elements)."""
    bpp=bpe*8
    pitch,height=gx2_surface_dims(wb,hb,tile,bpp)
    y,x=np.mgrid[0:hb,0:wb].astype(np.int64)
    pix=_pix_index(x,y,bpp)
    if tile in (2,3):
        mtb=64*bpe
        addr=mtb*((x>>3)+(y>>3)*(pitch>>3))+pix*bpe
    else:
        pipe=((y>>3)^(x>>3))&1
        bank=(((y//32)^(x>>3))&1)|(2*(((y//16)^(x>>4))&1))
        bp=pipe+2*bank
        pipeS=swz&1; bankS=(swz>>1)&3
        bp=(bp^(pipeS+2*bankS))%8
        pipe=bp%2; bank=bp//2
        mtp,mth=32,16
        mbytes=bpe*mtp*mth
        moff=((x//mtp)+(pitch//mtp)*(y//mth))*mbytes
        total=pix*bpe+(moff>>3)
        addr=(bank<<9)|(pipe<<8)|(total&0xff)|((total&~0xff)<<3)
    assert (addr%bpe==0).all()
    return addr//bpe, pitch*height
def gx2_detile(data,w,h,bpe,blk,tile,swz):
    wb,hb=(w+blk-1)//blk,(h+blk-1)//blk
    idx,n=gx2_addr(wb,hb,bpe,tile,swz)
    assert len(data)>=n*bpe,(len(data),n*bpe)
    src=np.frombuffer(data,np.uint8)[:n*bpe].reshape(n,bpe)
    return src[idx.reshape(-1)].reshape(hb,wb,bpe)   # linear elements
# ---------- NX ----------
def nx_block_height_log2(hb):
    # rule fitted to all 942 stock textures of the three archives: halve while 1.5*rows <= GOB rows
    bh=16
    while bh>1 and hb*3<=bh*16: bh//=2
    return bh.bit_length()-1
def nx_addr(wb,hb,bpe,bhl2):
    bh=1<<bhl2
    y,x=np.mgrid[0:hb,0:wb].astype(np.int64)
    gobs_w=(wb*bpe+63)//64
    xb=x*bpe
    gob=(y//(8*bh))*512*bh*gobs_w+(xb//64)*512*bh+((y%(8*bh))//8)*512
    addr=gob+((xb%64)//32)*256+((y%8)//2)*64+((xb%32)//16)*32+(y%2)*16+(xb%16)
    size=al(wb*bpe,64)*al(hb,8*bh)
    assert (addr%bpe==0).all()
    return addr//bpe,size
def nx_swizzle(lin,bhl2):
    hb,wb,bpe=lin.shape
    idx,size=nx_addr(wb,hb,bpe,bhl2)
    out=np.zeros((size//bpe,bpe),np.uint8); out[idx.reshape(-1)]=lin.reshape(-1,bpe)
    return out.tobytes()
def nx_deswizzle(data,wb,hb,bpe,bhl2):
    idx,size=nx_addr(wb,hb,bpe,bhl2)
    assert len(data)>=size,(len(data),size)
    return np.frombuffer(data,np.uint8)[:size].reshape(-1,bpe)[idx.reshape(-1)].reshape(hb,wb,bpe)
NXFMT={0x02:('R8',1,1),0x07:('B5G6R5',2,1),0x09:('R8G8',2,1),0x0b:('RGBA8',4,1),0x1a:('BC1',8,4),0x1b:('BC2',16,4),0x1c:('BC3',16,4),0x1d:('BC4',8,4),0x1e:('BC5',16,4)}

# ---------- BC decoders (numpy) -> RGBA uint8 (h,w,4) ----------
def _c565(c):
    r=(c>>11)&31; g=(c>>5)&63; b=c&31
    return np.stack([(r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)],-1).astype(np.int32)
def _unblock(px,hb,wb):  # px (hb,wb,16,C) -> (hb*4,wb*4,C)
    C=px.shape[-1]
    return px.reshape(hb,wb,4,4,C).transpose(0,2,1,3,4).reshape(hb*4,wb*4,C)
def bc_color(blk,bc1=True):  # blk (hb,wb,8)
    hb,wb,_=blk.shape; b=blk.astype(np.uint32)
    c0=b[...,0]|(b[...,1]<<8); c1=b[...,2]|(b[...,3]<<8)
    bits=b[...,4]|(b[...,5]<<8)|(b[...,6]<<16)|(b[...,7]<<24)
    p0=_c565(c0);p1=_c565(c1)
    four=(c0>c1)|(not bc1)
    f=four[...,None]
    p2=np.where(f,(2*p0+p1)//3,(p0+p1)//2); p3=np.where(f,(p0+2*p1)//3,0)
    pal=np.stack([p0,p1,p2,p3],-2)  # hb,wb,4,3
    a3=np.where(four,255,0)
    idx=np.stack([(bits>>(2*i))&3 for i in range(16)],-1)  # hb,wb,16
    rgb=np.take_along_axis(pal,idx[...,None].repeat(3,-1),axis=-2)
    alpha=np.where(idx==3,a3[...,None],255)
    return _unblock(np.concatenate([rgb,alpha[...,None]],-1),hb,wb).astype(np.uint8)
def bc_alpha(blk):  # blk (hb,wb,8) -> (h,w)
    hb,wb,_=blk.shape; b=blk.astype(np.uint64)
    a0=b[...,0].astype(np.int32); a1=b[...,1].astype(np.int32)
    bits=sum(b[...,2+i]<<np.uint64(8*i) for i in range(6))
    pal=[a0,a1]
    g=a0>a1
    for i in range(1,7): pal.append(np.where(g,((7-i)*a0+i*a1)//7, ((5-i)*a0+i*a1)//5 if i<5 else (0 if i==5 else 255)))
    pal=np.stack(pal,-1)
    idx=np.stack([((bits>>np.uint64(3*i))&np.uint64(7)).astype(np.int64) for i in range(16)],-1)
    v=np.take_along_axis(pal,idx,axis=-1)
    return _unblock(v[...,None],hb,wb)[...,0].astype(np.uint8)
def decode(lin,w,h,fmt,chan='rgba'):
    """lin: linear elements (hb,wb,bpe); fmt in R8,RG8,RGBA8,BC1,BC3,BC4,BC5 -> raw channels array (h,w,C)"""
    if fmt in('R8','RGBA8','RG8'): return lin[:h,:w]
    if fmt=='BC1': return bc_color(lin,True)[:h,:w]
    if fmt=='BC3':
        o=bc_color(lin[...,8:],False); o[...,3]=bc_alpha(lin[...,:8]); return o[:h,:w]
    if fmt=='BC4': return bc_alpha(lin)[:h,:w,None]
    if fmt=='BC5': return np.stack([bc_alpha(lin[...,:8]),bc_alpha(lin[...,8:])],-1)[:h,:w]
    raise NotImplementedError(fmt)
