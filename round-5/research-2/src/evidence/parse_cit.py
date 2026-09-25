import sys,re,json,glob
old=set()
for f in glob.glob(str(__import__("pathlib").Path(__file__).resolve().parents[4] / 'round-4/research-1/src/evidence/search_logs/cit_*.json')):
    t=open(f).read(); old|=set(re.findall(r'\d{4}\.\d{4,5}',t))
for f in sys.argv[1:]:
    t=open(f).read()
    items=re.findall(r'"title":\s*"(.*?)",\s*"publicationDate":\s*"?([\d-]*|null)"?',t)
    ids=re.findall(r'"ArXiv":\s*"([\d.]+)"',t)
    # rough per-item parse
    chunks=re.split(r'\{"citingPaper"',t)
    n=0;res=[]
    for c in chunks[1:]:
        tm=re.search(r'"title":\s*"(.*?)"',c); dm=re.search(r'"publicationDate":\s*"([\d-]+)"',c); am=re.search(r'"ArXiv":\s*"([\d.]+)"',c)
        n+=1
        if dm and dm.group(1).startswith('2026'):
            a=am.group(1) if am else '-'
            res.append((dm.group(1),a,('OLD' if a in old else 'NEW'),tm.group(1) if tm else ''))
    print(f"=== {f}: {n} citing, {len(res)} in 2026")
    for r in sorted(res): print('  ',*r)
