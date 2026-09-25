import sys,re
f=sys.argv[1]; pat=re.compile(sys.argv[2],re.I); n=int(sys.argv[3]) if len(sys.argv)>3 else 6
t=open(f).read().split('--- Content ---',1)[-1]
blocks=[b for b in re.split(r'\n--\n',t) if pat.search(b)]
print(f"## {f}: {len(blocks)} blocks match")
for b in blocks[:n]: print(re.sub(r'\s+',' ',b)[:600]); print('  --')
