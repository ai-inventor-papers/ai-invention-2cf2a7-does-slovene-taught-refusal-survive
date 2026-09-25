# P0 table

## RQ1 original-model FINAL refusal (reused from iter-2 exp5)

| model | block | arm | n | refusal | Wilson 95% |
|---|---|---|---|---|---|
| gams3_it | refuseu_nat | EN_nat | 1300 | 0.972 | [0.962, 0.980] |
| gams3_it | refuseu_nat | SL_nat | 1300 | 0.922 | [0.906, 0.936] |
| gams3_it | refuseu_x | EN_BT | 1296 | 0.972 | [0.962, 0.980] |
| gams3_it | refuseu_x | SL_MT | 1296 | 0.968 | [0.956, 0.976] |
| gemma_it | refuseu_nat | EN_nat | 1300 | 0.979 | [0.970, 0.986] |
| gemma_it | refuseu_nat | SL_nat | 1300 | 0.958 | [0.945, 0.967] |
| gemma_it | refuseu_x | EN_BT | 1296 | 0.975 | [0.964, 0.982] |
| gemma_it | refuseu_x | SL_MT | 1296 | 0.995 | [0.989, 0.997] |

## RQ2 post-edit refusal: PENDING

PROVISIONAL, lexical marker only: PROVISIONAL (lexical refusal marker from artifact 4 final generations; its judge labels were not yet available)

| model / set / arm / is_harmful | n | orig | edit (λ1) | Δ | rel. cut | McNemar p |
|---|---|---|---|---|---|---|
| gams3_it|hard|L3_MT|False | 60 | 0.367 | 0.067 | -0.300 | 0.82 | 7.6e-06 |
| gams3_it|hard|L3_MT|True | 60 | 0.867 | 0.100 | -0.767 | 0.88 | 2.8e-14 |
| gams3_it|refuseu_x|L3_MT|True | 250 | 0.940 | 0.100 | -0.840 | 0.89 | 1.7e-60 |
| gemma_it|hard|L3_MT|False | 100 | 0.390 | 0.160 | -0.230 | 0.59 | 6.6e-05 |
| gemma_it|hard|L3_MT|True | 100 | 0.910 | 0.260 | -0.650 | 0.71 | 5.4e-20 |
| gemma_it|refuseu_x|L3_MT|True | 247 | 0.951 | 0.215 | -0.737 | 0.77 | 1.5e-53 |

## RQ3 capability gate (this artifact)

- gams3_it: E_art2=OK, E_iter1=OK, rand_nm_j1=OK, E_iter1_l0.5=OK, E_iter1_l1.5=OK, E_iter1_l2.0=OK
- gemma_it: E_art2=OK, E_iter1=OK, rand_nm_j1=OK, rand_nm_j2=OK, E_iter1_l0.5=OK, E_iter1_l1.5=OK, E_iter1_l2.0=POSSIBLY_CATASTROPHIC

## RQ4: see artifact 3

