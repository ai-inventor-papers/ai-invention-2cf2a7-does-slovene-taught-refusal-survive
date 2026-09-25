# RESULTS

All numbers are generated from `results/analysis.json` (raw counts and bootstrap), re-derived independently by `src/rederive.py` (`results/audit.json`: 160/160 checks < 1e-6). Tables: `results/RESULTS_tables.md`.

## Headline: does Slovene refusal follow the prompt or the reply?

**Within Gemma-3-12B-IT, the residual refusal follows the REPLY language, not the prompt (M-OUT).** At matched English->English refusal = 50%, the edit-induced lag is carried by the output side: **OUT_SL = 1.14 [0.60, 1.56]** (logit; 95% item-bootstrap CI excludes 0) versus **IN_SL = -0.60 [-1.02, -0.18]** (negative: a Slovene *prompt* answered in English refuses no more than English->English). The within-item in/out-swap placebo for OUT-IN centres at 0 (obs 1.73, null -0.00, p = 0.000).

## Judge-independent confirmation (kills the 'judge mis-scores Slovene' rival)

The primary automated judge (J1, a local gemini-distilled classifier used because the paid judges were blocked mid-run) over-calls refusal (Se about 0.89, Sp about 0.73). But the SAME output-side pattern appears in the blind author-model adjudication, which reads the actual Slovene/Hungarian/English text: gold refusal is **0.50** for a non-English reply (n=90) vs **0.33** for an English reply (n=30), and only **0.38** for a non-English *prompt* answered in English (n=21). So the lag is a property of the reply the model is forced to write, not of the language it reads, and it is not an artifact of scoring Slovene text. The lag is Slovene-specific (Slovene reply > Hungarian reply).

## Translate-then-judge (English-side) confirmation

Judging the NLLB English translation of the reply (so the judged text is always English, request = English source) at the edited doses, Gemma refusal by reply language is EN 0.37, SL 0.88, HU 0.76: the output-language lag survives English-side scoring, so it is not an artifact of the judge mis-reading non-English text. The sibling GaMS is flat (EN 0.30, SL 0.32, HU 0.40), and the public abliterated checkpoint p-e-w/heretic still shows a Slovene-reply residual (EN 0.03, SL 0.23), so the output-side effect generalises beyond our edit. C-EXT residual SL->SL minus EN->EN = 16.0 pp.

## Robustness and honest caveats

Pre-registration required the call to survive raw, Rogan-Gladen, PPI++ and translate-then-judge readouts to be labelled *robust*. It does not: False. Rogan-Gladen is **numerically degenerate** here (min Se+Sp-1 = 0.29, OUT_SL bootstrap SE = 3.04) because the low-specificity local judge makes the 1/(Se+Sp-1) correction explode; PPI++ keeps the sign (OUT_SL point 0.20, IN_SL -0.42) but its CIs include 0 because the fresh gold set is small. **Verdict: M-OUT is strongly supported by the raw readout and the judge-independent gold adjudication, and corroborated by the translate-then-judge arm where available, but does not reach the pre-registered multi-readout 'robust' bar given the blocked paid judges.**

See `RESULTS_tables.md` for per-cell rates, GaMS (sibling) G3 contrasts, SDT, the random-edit and MT-noise controls, C-EXT and the full readout table.
