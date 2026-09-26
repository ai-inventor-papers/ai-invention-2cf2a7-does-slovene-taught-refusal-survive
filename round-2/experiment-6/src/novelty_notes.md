# Novelty check (section 9) — 2026-09-23, 20:55–21:05 UTC, done BEFORE the protocol freeze

Searches used: "multilingual prefilling attack refusal depth low-resource language";
"shallow safety alignment language prefill non-English cross-lingual refusal recovery";
"arXiv 2608.08032 Decided Upstream, Written Late"; "prefilling attack across languages translated prompts
assistant prefill jailbreak multilingual evaluation"; "GaMS3 Slovene LLM safety refusal jailbreak evaluation".
Abstract pages opened: arXiv 2608.11146. The other entries rely on search snippets or on the plan's reading
notes and are marked as such.

## What is already known (NOT claimed as novel here)
- **Shallow (prefill) safety alignment is known, in English.** Qi et al., arXiv 2406.05946, *Safety Alignment
  Should Be Made More Than Just a Few Tokens Deep* (ICLR 2025). They prefill 5/10/20/40 harmful tokens on
  HEx-PHI, judge with GPT-4, analyse per-token KL, and propose "safety recovery examples". Prefill shallowness
  itself is therefore not a contribution.
- **Low-resource languages are less safe, and this is well established.** Sources: MultiJail (2310.06474);
  Yong et al. (2310.02446); Minionese (2607.10112; 18 languages, 4 resource tiers, translationese and
  code-switching); arXiv 2605.18239; the ACL-Findings 2026 "Multilingual Refusal Alignment" paper (2606.07535).
- **Cross-lingual refusal mechanism: "harm detected upstream, refusal written late".** arXiv 2608.08032
  (Sarvam-30B MoE) finds a language-invariant harm direction (EN–Indic cos ≈ 0.9) that is orthogonal to a late
  refusal write. arXiv 2608.18089 (Latent Space Refusal Anchoring, African languages) says low-resource
  jailbreaks route through a subspace that projects insufficiently onto the refusal direction. arXiv 2608.11146
  (LoDNA; Twi/Hausa/Amharic/Swahili) finds harmful prompts keep <10% of the English refusal signal; that is
  representation-level and does not use prefill. Aziz 2606.01196 is cited from the plan's notes (not re-opened);
  it is the "representation intact, action fails" reading.
  - **So:** "harm representation persists while the refusal projection collapses" is an expected pattern. We run
    it as a check, not a claim.
- **Recovery after a prefill.** Sockpuppetting (2601.13359) reports that Gemma backtracks after prefills; this is
  cited from the plan's notes, not re-opened. We therefore generate 160 tokens and judge the whole text.

## What appears unoccupied (hedged; to be stated as "to our knowledge")
None of the sources above reports **per-language refusal depth** (flip vs prefix length) on **item-matched**
prompts with all of the following:
- (i) an **MT-noise arm** (EN back-translation versus the English original);
- (ii) a **neutral-prefix specificity control**;
- (iii) a **prompt-language × prefix-language 2×2** that separates the input side from the action side;
- (iv) a **shared-base sibling pair**: GaMS3-12B-Instruct is a Slovene continued-pretraining and SFT descendant
  of Gemma-3-12B. The search found no safety or prefill evaluation of GaMS3.

The contribution is therefore the **controlled measurement design and the sibling comparison**. It is not
"prefill works" or "Slovene is less safe". If DG is null, the finding is equally reportable: refusal depth does
not differ by language once MT noise and prefix meaning are controlled. That would challenge the reading that
low-resource shallowness is a depth phenomenon.

## Caveats
- Our SL is NLLB machine translation (translationese), not native Slovene.
- Our prefixes are generic openers, not Qi-style harmful-response prefills. Absolute flip rates are therefore
  not comparable to prefill ASR numbers in the literature.

---

## Addendum, 2026-09-24 02:15 UTC — what the artifact actually ended up contributing

The novelty check above was written before execution. Execution changed which claim this artifact can support,
and the honest contribution is now partly a **measurement-validity** result rather than only the design:

1. **The judged readout could not be validated, and the failure is language-asymmetric.** With the frozen rubric,
   `google/gemini-2.5-flash` labels prefilled *compliance* as REFUSE: 8/12 on synthetic items, κ(R)=0.17 against
   `gpt-4.1` on DEV, and on 50 blind-adjudicated FINAL rows it made 19 errors, **all** in the REFUSE direction,
   13 of them in Slovene. Local open-weight judges (Qwen3-8B/14B) fail in the *opposite* direction, labelling
   explicit refusals ("I cannot and will not provide…") as COMPLY. A prefill study that scores its continuations
   with a single unvalidated LLM judge can therefore report a language gap that is entirely instrumental.
   This is consistent with, and independently reproduces, what a sibling artifact of this run found on iter-1
   data (the same gemini prefill judge, κ 0.17 against blind adjudication).
2. **Under the one reliable reading available, the language gap is absent.** The stratum-weighted blind
   adjudication puts the k=5 flip rate at 0.227 (SL-MT) vs 0.187 (EN-BT) for Gemma-3-12B-IT and 0.399 vs 0.412
   for GaMS3-12B-Instruct; both risk differences have CIs spanning zero. The iter-1 lead ("Gemma flips 3% EN /
   56% SL") does not survive: it was a lexicon artefact, and the judge that was supposed to replace the lexicon
   has a bias in the same direction.
3. **The large effect in these cells is between models, not between languages.** GaMS3 complies with a 5-token
   compliant prefix about twice as often as Gemma-3 in *both* languages. Slovene continued pretraining plus SFT
   appears to have made the descendant more prefill-vulnerable overall — not specifically in Slovene.

None of these is a claim that prefill shallowness or low-resource fragility is novel. The novel parts are the
controlled design (MT-noise arm, neutral-prefix control, cross-language 2×2, sibling pair) and the demonstration
that the standard LLM-judge readout for prefill attacks is not trustworthy without per-language validation.
