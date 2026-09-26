#!/usr/bin/env bash
# GPU chain after the Gemma grid: J1 labels (GPU, between model loads) -> GaMS (mini, DEV, KL, grid) -> J1 ->
# C-EXT (p-e-w heretic) -> J1 -> NLLB TTJ translations -> J1 on translations.
cd "$(dirname "$0")/src"
export HF_HUB_OFFLINE=1 AII_DEV_JUDGE=j1
GP=$(cat ../logs/gen_gemma.pid)
while kill -0 $GP 2>/dev/null; do sleep 10; done
J1="../.venv/bin/python judge_j1.py --mode label --models gemma_it,gams3_it,pew_heretic"
$J1 > ../logs/j1_a.out 2>&1
AII_SKIP_BENIGN_LO=1 ../.venv/bin/python gen.py --model gams3_it --phases mini,dev,kl,grid > ../logs/gen_gams.out 2>&1
$J1 > ../logs/j1_b.out 2>&1
../.venv/bin/python gen.py --model pew_heretic --phases ext > ../logs/gen_pew.out 2>&1
$J1 > ../logs/j1_c.out 2>&1
../.venv/bin/python build_items.py --mode ttj --models gemma_it,gams3_it,pew_heretic --only_edited > ../logs/ttj.out 2>&1
$J1 > ../logs/j1_d.out 2>&1
echo CHAIN_DONE > ../logs/chain.done
