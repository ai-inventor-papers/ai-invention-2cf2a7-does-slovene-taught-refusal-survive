## Design (frozen in `protocol.yaml`, sha256 in `protocol.sha256`, git-committed before any grid row)

**Question.** In iter 3 an English-objective Heretic edit, applied at matched *English* strength, left Gemma-3-12B-IT
refusing more in Slovene than in English (the "lag"), and less so GaMS3-12B-Instruct. Does that residual Slovene
refusal follow the **prompt** language (M-IN), the **reply** language (M-OUT), or only their match (M-MATCH)?

**Grid.** Every harmful / benign item is shown in each input language *i* ∈ {EN, SL, HU} (EN = NLLB back-translation
EN_BT, SL/HU = NLLB MT of one English source) with a one-line suffix *in the input language* forcing the output
language *o* ∈ {EN, SL, HU}: 9 cells, suffix present in all of them (so "respond in X" — itself a known jailbreak
family — is held constant). Hungarian is a third language absent from GaMS3's CPT (model card check,
`results/inputs_check.json`).

**Edit and dose.** exp9's selected Heretic LoRA (r = 3, o_proj + down_proj) is applied as bf16 forward hooks,
ΔW(λ) = λ·ΔW (λ = 0 is bit-identical to the base: max|Δlogit| = 0 asserted). Each model is run at λ = 0 and at two
steps λ_lo / λ_hi chosen on 60 DEV items (exp9 P300, never confirmation) so that EN→EN refusal (with suffix)
brackets 50 % (amendments A1 / A2).

**Estimands** (x = logit R(EN,EN), y = logit R(i,o); Hautus rates):
* a(i,o): y at x = 0 by linear interpolation between λ_lo and λ_hi — the refusal log-odds in cell (i,o) when
  English→English refusal is 50 %; L = a (raw lag), b = y₀(i,o) − x₀ (baseline cell gap at λ = 0), L* = a − b
  (edit-induced lag).
* OUT = ½[(L*(EN,SL) − L*(EN,EN)) + (L*(SL,SL) − L*(SL,EN))], IN = ½[(L*(SL,EN) − L*(EN,EN)) + (L*(SL,SL) − L*(EN,SL))],
  INT = L*(SL,SL) − L*(SL,EN) − L*(EN,SL) + L*(EN,EN); the same with HU. Note OUT − IN = L*(EN,SL) − L*(SL,EN).
* G3(i,o) = a_GaMS − a_Gemma, G3_edit = L*_GaMS − L*_Gemma, dOUT / dIN.
* 2,000-draw fully paired item bootstrap (one item draw applied to all cells, doses and models), MDE = 2.8·SE,
  5,000-draw within-item permutation placebos.
