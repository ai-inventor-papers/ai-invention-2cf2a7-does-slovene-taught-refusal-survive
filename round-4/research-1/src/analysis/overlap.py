"""Exact / near-duplicate overlap between Heretic's default harmful prompts (mlabonne/harmful_behaviors)
and candidate external harmful benchmarks. Normalised exact match + token-Jaccard >= 0.8 near match."""
import re, json, os, pandas as pd
DATA=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data')
def norm(s): return re.sub(r'[^a-z0-9 ]','',str(s).lower()).strip()
def toks(s): return set(norm(s).split())
mt=pd.read_parquet(DATA+'/mlab_harmful_train.parquet').text.tolist()
ms=pd.read_parquet(DATA+'/mlab_harmful_test.parquet').text.tolist()
mlab=mt+ms; heretic_used=mt[:400]+ms[:100]   # config: train[:400] direction, test[:100] refusal scorer
adv=pd.read_csv(DATA+'/advbench.csv').goal.tolist()
jbb=pd.read_csv(DATA+'/jbb_harmful.csv'); jbbb=pd.read_csv(DATA+'/jbb_benign.csv')
sr=pd.read_csv(DATA+'/strongreject.csv')
hb=pd.read_csv(DATA+'/harmbench_all.csv')
ru=pd.read_parquet(DATA+'/refuseu_eval.parquet')
print('RefusEU eval cols',list(ru.columns), len(ru)); print(ru.head(3).to_dict('records'))
M=set(map(norm,mlab)); U=set(map(norm,heretic_used)); MT=[toks(x) for x in mlab]
def near(s):
    t=toks(s); 
    return any(len(t&m)/max(1,len(t|m))>=0.8 for m in MT)
def rep(name, items):
    items=[x for x in items if isinstance(x,str)]
    ex=sum(norm(x) in M for x in items); exu=sum(norm(x) in U for x in items); nr=sum(near(x) for x in items)
    r=dict(benchmark=name,n=len(items),exact_in_mlabonne=ex,exact_in_heretic_used_slices=exu,near_dup_jaccard08=nr,survive_after_near_dedup=len(items)-nr)
    print(r); return r
out=[]
out.append(rep('AdvBench harmful_behaviors (llm-attacks)',adv))
out.append(rep('JBB-Behaviors harmful (Goal)',jbb.Goal.tolist()))
print('JBB Source counts',jbb.Source.value_counts().to_dict())
out.append(rep('JBB harmful Source==AdvBench',jbb[jbb.Source=='AdvBench'].Goal.tolist()))
out.append(rep('StrongREJECT forbidden_prompt',sr.forbidden_prompt.tolist()))
print('StrongREJECT source counts',sr.source.value_counts().to_dict() if 'source' in sr else sr.columns.tolist())
fc=hb[hb.FunctionalCategory=='standard'] if 'FunctionalCategory' in hb else hb
out.append(rep('HarmBench standard (Behavior)',fc.Behavior.tolist()))
out.append(rep('HarmBench all text (Behavior)',hb.Behavior.tolist()))
col=[c for c in ru.columns if c.lower() in ('prompt','text','question','instruction')]
if col:
    lang=[c for c in ru.columns if 'lang' in c.lower()]
    en=ru[ru[lang[0]]=='en'] if lang else ru
    out.append(rep('RefusEU evaluation (en rows)',en[col[0]].tolist()))
json.dump(out,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'overlap_results.json'),'w'),indent=1)
print('mlab train==adv[:416]?', [norm(x) for x in mt]==[norm(x) for x in adv[:416]], 'set-equal all?', set(map(norm,mlab))==set(map(norm,adv)))
