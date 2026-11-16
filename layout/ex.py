import oead,sys,os,hashlib
def sarc(b):
    if b[:4]==b'Yaz0': b=oead.yaz0.decompress(b)
    return oead.Sarc(b)
def dump(pack,names,out):
    s=sarc(open(pack,'rb').read())
    print(pack,'endian',s.get_endianness(),'nfiles',s.get_num_files(), 'align',s.guess_min_alignment())
    for n in names:
        f=s.get_file(n)
        if f is None: print('  missing',n); continue
        d=bytes(f.data); a=sarc(d)
        od=os.path.join(out,os.path.basename(n)); 
        print('  ',n,len(d),'yaz0' if d[:4]==b'Yaz0' else 'raw', a.get_endianness(), a.get_num_files(),'align',a.guess_min_alignment())
        os.makedirs(out,exist_ok=True); open(od+'.raw','wb').write(d)
        for e in a.get_files():
            p=os.path.join(od,e.name); os.makedirs(os.path.dirname(p),exist_ok=True); open(p,'wb').write(bytes(e.data))
dump(sys.argv[1],sys.argv[3:],sys.argv[2])
