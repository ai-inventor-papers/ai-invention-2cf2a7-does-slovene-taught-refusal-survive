import re,sys
for f in sys.argv[1:]:
    t=open(f).read()
    m=re.search(r'Length: (\d+)',t)
    parts=re.split(r'(http://arxiv\.org/abs/\d{4}\.\d{4,5}v\d+)',t)
    print(f"=== {f}: {(len(parts)-1)//2} hits")
    for i in range(1,len(parts),2):
        body=parts[i+1]
        tm=re.match(r'\s*(.*?)\s(\d{4}-\d\d-\d\dT)',body)
        print(" ",parts[i].split('/abs/')[1], tm.group(2)[:10] if tm else '', (tm.group(1) if tm else body[:120])[:150])
