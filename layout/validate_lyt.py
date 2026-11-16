# Validate the pai1 BE->LE converter against every stock animation (Wii U v208 vs Switch 1.6.0), and tabulate
# how stock Switch bflyt sections relate to stock Wii U ones.
import sys,os,glob; sys.path.insert(0,os.path.dirname(__file__)); import lyt
from collections import Counter
W=sys.argv[1]; st=Counter(); bad=[]
for a in ('Title','BootUp','Common'):
    for f in sorted(glob.glob(f'{W}/sw/{a}.sblarc/anim/*.bflan')):
        g=f.replace('/sw/','/wu/')
        if not os.path.exists(g): st['no wiiu counterpart']+=1; continue
        es,vs,ss=lyt.secs(open(f,'rb').read()); ew,vw,sw=lyt.secs(open(g,'rb').read())
        assert es=='<' and ew=='>'; st['ver sw %x wu %x'%(vs,vw)]+=1
        pw=[d for m,d in sw if m=='pai1'][0]; ps=[d for m,d in ss if m=='pai1'][0]
        try: c=lyt.pai1_be2le(pw)
        except NotImplementedError as e: st['unsupported '+str(e)]+=1; continue
        if c==ps: st['pai1 converted == stock Switch']+=1
        else: st['pai1 MISMATCH']+=1; bad.append(os.path.basename(f))
for k in sorted(st): print(k,st[k])
print(bad[:20])
