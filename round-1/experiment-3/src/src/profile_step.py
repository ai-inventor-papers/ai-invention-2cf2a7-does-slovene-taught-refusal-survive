import time, torch, sys
sys.path.insert(0, 'src')
from common import setup_logging, read_jsonl, DATA
from engine import Engine
setup_logging('profile')
E = Engine('gams')
c = read_jsonl(DATA/'construct200.jsonl')
ids = [E.encode_prompt(p['prompt_en'])[0] for p in c[:64]]
for B in (1, 8, 32, 64):
    x = ids[:B]
    torch.cuda.synchronize(); t=time.time()
    E.run_batch(x, 'en', 1, False); torch.cuda.synchronize(); tp=time.time()-t
    t=time.time(); E.run_batch(x, 'en', 33, False); torch.cuda.synchronize(); tg=time.time()-t
    t=time.time(); E.run_batch(x, 'en', 1, True); torch.cuda.synchronize(); ts=time.time()-t
    print(f'B={B} prefill={tp:.2f}s decode_step={(tg-tp)/32*1000:.0f}ms s_extra={ts-tp:.2f}s', flush=True)
