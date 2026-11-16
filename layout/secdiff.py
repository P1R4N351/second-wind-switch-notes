import sys,difflib
sys.path.insert(0,sys.argv[1]); from sec import secs
def desc(s):
    m,o,sz,d=s
    nm=''
    if m in('pan1','pic1','txt1','wnd1','prt1','bnd1'): nm=d[16:40].split(b'\0')[0].decode()
    if m=='grp1': nm=d[8:32].split(b'\0')[0].decode()
    return f'{m}:{nm}'
a=secs(open(sys.argv[2],'rb').read()); b=secs(open(sys.argv[3],'rb').read())
A=[(desc(s),s[3]) for s in a[4]]; B=[(desc(s),s[3]) for s in b[4]]
sm=difflib.SequenceMatcher(None,[x[0] for x in A],[x[0] for x in B],autojunk=False)
for tag,i1,i2,j1,j2 in sm.get_opcodes():
    if tag=='equal':
        for k in range(i2-i1):
            x=A[i1+k];y=B[j1+k]
            if x[1]!=y[1]:
                print('CHG',i1+k,x[0],len(x[1]),len(y[1]))
                if len(x[1])==len(y[1]):
                    df=[i for i in range(len(x[1])) if x[1][i]!=y[1][i]]
                    print('     bytes differ at',df[:40], len(df))
                    lo=df[0]&~3; hi=min(len(x[1]),(df[-1]|3)+1)
                    if hi-lo<=64: print('     mod',x[1][lo:hi].hex(' ',4),'\n     stk',y[1][lo:hi].hex(' ',4))
    else:
        print(tag,'mod',[(i,A[i][0],len(A[i][1])) for i in range(i1,i2)],'stock',[(j,B[j][0],len(B[j][1])) for j in range(j1,j2)])
