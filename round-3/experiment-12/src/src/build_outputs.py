#!/usr/bin/env python3
"""STEP 10: method_out.json (exp_gen_sol_out schema) with per-item predictions across conditions + headline metadata,
results/gates.json (what artifacts 2-4 cite), results/cuts.json passthrough, results/RESULTS.md (gate table first)."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

from common import DATA, ITEMS, MODELS, PRIMARY_METRIC, RESULTS, UTIL_TASKS, WS, read_jsonl, sha256_file  # noqa: E402

A = json.loads((RESULTS / "analysis.json").read_text())
AUD = json.loads((RESULTS / "audit.json").read_text()) if (RESULTS / "audit.json").exists() else {}


def fmt(x, nd=3):
    if x is None:
        return "–"
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(fmt(v, nd) for v in x) + "]"
    if isinstance(x, float) and np.isnan(x):
        return "nan"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def pred_of(r: dict) -> int:
    """argmax per the task's primary metric (acc: raw loglik; acc_norm: loglik / choice byte length)."""
    return int(np.argmax(r["lls"])) if PRIMARY_METRIC[r["task"]] == "acc" or "norm_lls" not in r else int(np.argmax(r["norm_lls"]))


CONSIST = [0, 0]


def method_out() -> dict:
    datasets = []
    # utility (+ belebele): one dataset per task x lang; predictions per model x condition
    for kind, tasks in (("util", UTIL_TASKS), ("bele", ["belebele"])):
        rows_by = defaultdict(dict)  # (task, lang) -> {item_id: {key: row}}
        for f in sorted(ITEMS.glob(f"{kind}_*.jsonl")):
            for r in read_jsonl(f):
                rows_by[(r["task"], r["lang"])].setdefault(r["item_id"], {})[f"{r['model']}__{r['cond']}"] = r
        for (task, lang), items in sorted(rows_by.items()):
            src = DATA / ("belebele" if task == "belebele" else "util") / (f"belebele_{lang}.jsonl" if task == "belebele" else f"{task}_{lang}.jsonl")
            meta = {r["id"]: r for r in read_jsonl(src)}
            exs = []
            for iid, conds in items.items():
                d = meta[iid]
                inp = d["query"] + "\n" + "\n".join(f"({k}) {c}" for k, c in enumerate(d["choices"]))
                ex = {"input": inp, "output": str(d["gold"]), "metadata_item_id": iid, "metadata_pair_id": d.get("pair_id") or "",
                      "metadata_task": task, "metadata_lang": lang, "metadata_primary_metric": PRIMARY_METRIC[task]}
                for key, r in sorted(conds.items()):
                    k = key.replace("-", "_").replace(".", "p")
                    lls = np.array(r["lls"])
                    if PRIMARY_METRIC[task] == "acc_norm":  # lm-eval acc_norm: loglik / len(choice string)
                        lls = lls / np.array([float(len(c)) for c in d["choices"]])
                    pred = int(np.argmax(lls))
                    ex[f"predict_{k}"] = str(pred)
                    ex[f"metadata_correct_{k}"] = int(r[PRIMARY_METRIC[task]])
                    ex[f"metadata_lls_{k}"] = [round(v, 4) for v in r["lls"]]
                    CONSIST[0] += int((pred == d["gold"]) == bool(r[PRIMARY_METRIC[task]]))
                    CONSIST[1] += 1
                exs.append(ex)
            datasets.append({"dataset": f"{'belebele' if task == 'belebele' else 'slovenian_llm_eval_paired'}__{task}__{lang}",
                             "examples": exs})
    # KL rows
    for m in MODELS:
        rows = read_jsonl(ITEMS / f"kl_{m}.jsonl")
        if not rows:
            continue
        mt = {r["id"]: r for r in read_jsonl(DATA / "harmless" / "harmless_mt.jsonl")}
        exs = []
        for r in rows:
            ex = {"input": mt[r["item_id"]][r["arm"]], "output": "first-token KL(p_orig||p_cond); prediction strings = first|multi",
                  "metadata_item_id": r["item_id"], "metadata_arm": r["arm"], "metadata_model": m}
            for c, v in r["kl"].items():
                ex[f"predict_{c.replace('.', 'p')}"] = f"{v['first']:.6g}|{v['multi']:.6g}"
            exs.append(ex)
        datasets.append({"dataset": f"dolly_harmless_kl__{m}", "examples": exs})
    # generations
    for m in MODELS:
        g = defaultdict(dict)
        for f in sorted(ITEMS.glob(f"gen_{m}_*.jsonl")):
            for r in read_jsonl(f):
                g[(r["item_id"], r["arm"])][r["cond"]] = r["text"]
        if not g:
            continue
        mt = {r["id"]: r for r in read_jsonl(DATA / "harmless" / "harmless_mt.jsonl")}
        exs = []
        for (iid, arm), cc in sorted(g.items()):
            ex = {"input": mt[iid][arm], "output": cc.get("orig", ""), "metadata_item_id": iid, "metadata_arm": arm, "metadata_model": m}
            for c, txt in cc.items():
                ex[f"predict_{c.replace('.', 'p')}"] = txt
            exs.append(ex)
        datasets.append({"dataset": f"dolly_harmless_generations__{m}", "examples": exs})
    u = A["utility"]
    meta = {
        "method_name": "RQ3 capability control: headroom-normalised MC utility + KL/BPB/fluency footprint of English-objective Heretic abliteration (GaMS3 vs Gemma-3, EN/SL/HU)",
        "description": "Original vs iter-1 selected Heretic edit (lambda 1, plus 0.5/1.5/2.0) vs norm-matched random-direction edits (same Heretic params, only directions random). predict_<model>__<cond> = 1 if the item is answered correctly under the task's primary metric; metadata_lls_* hold per-choice logliks.",
        "protocol_sha256": (WS / "protocol.sha256").read_text().split()[0] if (WS / "protocol.sha256").exists() else None,
        "gates": {m: {c: g["verdict"] for c, g in gm.items()} for m, gm in A["gates"].items()},
        "macros": u["macros"], "interaction": u["interaction"], "random_adjusted": u["random_adjusted"],
        "lambda_gate_curve": A.get("lambda_gate_curve"),
        "kl_ratios": {m: {c: {k: {"sl_over_enbt": v[k].get("sl_over_enbt"), "hu_over_enbt": v[k].get("hu_over_enbt"),
                                  "readable": v[k].get("readable")} for k in v} for c, v in d["ratios"].items()}
                      for m, d in A.get("kl", {}).items()},
        "kl_self_floor": {m: d["self_floor"] for m, d in A.get("kl", {}).items()},
        "competence_covariates": A.get("competence_covariates"),
        "audit_all_pass": AUD.get("all_pass"),
        "adapters_workspace_path": str(WS / "adapters"),
    }
    return {"metadata": meta, "datasets": datasets}


def gates_json() -> dict:
    conds = {}
    for m in MODELS:
        p = RESULTS / "models" / m / "conditions.json"
        if p.exists():
            conds[m] = json.loads(p.read_text())
    out = {"rule": "CATASTROPHIC if macro headroom-normalised loss > 0.20 in EN or SL (point); POSSIBLY_CATASTROPHIC if only the 95% upper bound exceeds 0.20; F6 raw-pp 5 pp rule if >=3 tasks ineligible",
           "gates": {}, "lambda_gate_curve": A.get("lambda_gate_curve"),
           "E_art2": "artifact 2 = iter_3/gen_art_experiment_9/selected/<model>/adapter; verdict PENDING wherever it was not scored (run_late_edits.sh resumes it)"}
    for m, gm in A["gates"].items():
        out["gates"][m] = {}
        mcp = RESULTS / "models" / m / "manipulation_check.json"
        mcj = json.loads(mcp.read_text()) if mcp.exists() else {"checks": {}, "heretic_style_kl": {}}
        for c, g in gm.items():
            cm = conds.get(m, {}).get(c, {})
            chk = mcj["checks"].get(c, {})
            g = {**g, "manipulation_check": {"heretic_style_first_token_kl_bs1": mcj["heretic_style_kl"].get(c),
                                             "pass": chk.get("pass"),
                                             "label": ("UNVERIFIED (KL +39-40% vs logged Heretic value; batching and empty-system rendering ruled out; adapter sha256 matches iter-1)"
                                                       if chk.get("pass") is False else ("VERIFIED" if chk.get("pass") else "no logged reference / not applicable"))}}
            out["gates"][m][c] = {**g, "adapter_path": cm.get("saved_adapter_dir") or cm.get("adapter_dir"),
                                  "adapter_sha256": cm.get("saved_sha256") or cm.get("sha256"), "lambda": cm.get("lambda"),
                                  "kind": cm.get("kind")}
        for c in ("E_art2",):
            if c not in out["gates"][m]:
                out["gates"][m][c] = {"verdict": "PENDING"}
    return out


def results_md() -> str:
    u = A["utility"]
    L = ["# RESULTS — RQ3 capability control (iter-3 exp12)", "",
         "All numbers below are read from `results/analysis.json` (recomputed by `src/audit.py`, path B). NF4 precision, zero-shot, lm-eval 0.4.13, 300 paired EN/SL items per task.", "",
         *([(RESULTS / "findings.md").read_text(), ""] if (RESULTS / "findings.md").exists() else []),
         "## 1. Catastrophe gate (pre-registered: macro headroom-normalised loss > 0.20 in EN or SL)", "",
         "| model | condition | EN loss (95% hi) | SL loss (95% hi) | verdict | source | raw-pp sensitivity EN / SL loss (95% hi), 5-pp rule |", "|---|---|---|---|---|---|---|"]
    for m, gm in A["gates"].items():
        for c, g in gm.items():
            pl = g["per_lang"]
            sens = " / ".join(f"{fmt(pl[l]['sensitivity_raw_pp']['loss_pp'], 2)} ({fmt(pl[l]['sensitivity_raw_pp']['loss_pp_hi95'], 2)}) {pl[l]['sensitivity_raw_pp']['verdict_5pp']}"
                              for l in ("en", "sl") if l in pl and "sensitivity_raw_pp" in pl[l])
            L.append(f"| {m} | {c} | {fmt(pl.get('en', {}).get('loss'))} ({fmt(pl.get('en', {}).get('loss_hi95'))}) | "
                     f"{fmt(pl.get('sl', {}).get('loss'))} ({fmt(pl.get('sl', {}).get('loss_hi95'))}) | **{g['verdict']}** | {g['source']} | {sens} |")
    for m in MODELS:
        if "E_art2" in A["gates"].get(m, {}):
            L.append(f"- E_art2 on {m}: scored (artifact 2 = iter_3/gen_art_experiment_9 selected adapter; random reference = rand_nm_j1, iter-1 parameters).")
        else:
            L.append(f"- E_art2 on {m}: **PENDING** (not scored in this run; `run_late_edits.sh` resumes it).")
    L.append("")
    L += ["## 2. Macro H, language asymmetry A = H_SL − H_EN, interaction I = A_GaMS − A_Gemma", "",
          "| model | cond | macro H EN [95% CI] | macro H SL [95% CI] | A [95% CI] | raw-pp EN | raw-pp SL | ineligible (EN/SL) |", "|---|---|---|---|---|---|---|---|"]
    for m, cc in u["macros"].items():
        for c, d in cc.items():
            L.append(f"| {m} | {c} | {fmt(d['en']['macro_H'])} {fmt(d['en']['macro_H_ci95'])} | {fmt(d['sl']['macro_H'])} {fmt(d['sl']['macro_H_ci95'])} | "
                     f"{fmt(d.get('A_sl_minus_en'))} {fmt(d.get('A_ci95'))} | {fmt(d['en']['raw_pp_macro'], 2)} | {fmt(d['sl']['raw_pp_macro'], 2)} | "
                     f"{','.join(d['en']['ineligible_tasks']) or '–'} / {','.join(d['sl']['ineligible_tasks']) or '–'} |")
    L += ["", "| cond | I (GaMS − Gemma) | 95% CI | 90% CI |", "|---|---|---|---|"]
    for c, d in u["interaction"].items():
        L.append(f"| {c} | {fmt(d['I'])} | {fmt(d['I_ci95'])} | {fmt(d['I_ci90'])} |")
    L += ["", "Resolution limit: the interaction is resolvable only to ~0.10–0.12 of headroom at n=300/task; a smaller |I| is an estimate, not evidence of no asymmetry.", ""]
    L += ["### Random-adjusted (H_edit − H_rand, rand = norm-matched random edit j=1)", ""]
    for m, cc in u["random_adjusted"].items():
        for c, d in cc.items():
            L.append(f"- {m}/{c}: EN {fmt(d.get('en', {}).get('H_excess'))} {fmt(d.get('en', {}).get('ci95'))}; SL {fmt(d.get('sl', {}).get('H_excess'))} {fmt(d.get('sl', {}).get('ci95'))}; A_excess {fmt(d.get('A_excess', {}).get('value'))} {fmt(d.get('A_excess', {}).get('ci95'))}")
    L += ["", "## 3. Per-task cells (E_iter1 vs original)", "", "| model | lang | task | acc orig | acc edit | chance | H [95% CI] | raw pp | McNemar p (Holm) | eligible |", "|---|---|---|---|---|---|---|---|---|---|"]
    for m, cc in u["cells"].items():
        for l in ("en", "sl"):
            for t, d in cc.get("E_iter1", {}).get(l, {}).items():
                L.append(f"| {m} | {l} | {t} | {fmt(d['acc_orig'])} | {fmt(d['acc'])} | {fmt(d['chance'], 2)} | {fmt(d['H'])} {fmt(d['H_ci95'])} | {fmt(d['raw_pp'], 1)} | {fmt(d['mcnemar_p_holm'], 3)} | {d['eligible']} |")
    curve = A.get("lambda_gate_curve") or {}
    if curve:
        L += ["", "## 4. λ gate curve (100 items × ARC/BoolQ/OBQA/Winogrande)", "", "| model | λ | macro H EN | macro H SL | verdict |", "|---|---|---|---|---|"]
        for m, d in curve.items():
            for p in d["points"]:
                L.append(f"| {m} | {p['lambda']} | {fmt(p['macro_H_en'])} {fmt(p['ci95_en'])} | {fmt(p['macro_H_sl'])} {fmt(p['ci95_sl'])} | {p['verdict']} |")
            L.append(f"| {m} | largest λ OK | {d['largest_lambda_OK']} | monotone SL damage: {d['monotone_damage_sl']} | |")
    b = A.get("belebele")
    if b:
        L += ["", "## 5. Belebele (human-translated, 200 parallel items; three-language axis)", "", "| model | cond | EN acc (H) | SL acc (H) | HU acc (H) |", "|---|---|---|---|---|"]
        for m, cc in b["cells"].items():
            first = next(iter(cc.values()))
            L.append(f"| {m} | orig | {fmt(first['en']['belebele']['acc_orig'])} | {fmt(first['sl']['belebele']['acc_orig'])} | {fmt(first['hu']['belebele']['acc_orig'])} |")
            for c, d in cc.items():
                L.append(f"| {m} | {c} | " + " | ".join(f"{fmt(d[l]['belebele']['acc'])} ({fmt(d[l]['belebele']['H'])} {fmt(d[l]['belebele']['H_ci95'])})" for l in ("en", "sl", "hu")) + " |")
    kl = A.get("kl") or {}
    if kl:
        L += ["", "## 6. KL footprint (batch size 1, fp32, full vocab; fresh Dolly harmless set)", "",
              "| model | cond | first-token KL EN-BT | SL-MT | HU-MT | 32-tok KL EN-BT | SL-MT | SL/EN ratio | EXCESS vs random [95% CI] | HU/EN ratio |", "|---|---|---|---|---|---|---|---|---|---|"]
        for m, d in kl.items():
            if not all(a in d["arms"] for a in ("en_bt", "sl_mt", "hu_mt")):
                L.append(f"| {m} | (KL incomplete: arms {d['arms']}) | | | | | | | | |")
                continue
            for c in [c for c in d["means"] if c not in ("rand_nm_j2", "rand_nm_j3", "rand_nm_j4", "rand_nm_j5")]:
                mm = d["means"][c]
                r = d["ratios"].get(c, {}).get("first", {})
                ex = r.get("sl_over_enbt", {}).get("excess_vs_rand", {})
                L.append(f"| {m} | {c} | {mm['en_bt']['first']['mean']:.2e} | {mm['sl_mt']['first']['mean']:.2e} | {mm['hu_mt']['first']['mean']:.2e} | "
                         f"{mm['en_bt']['multi']['mean']:.2e} | {mm['sl_mt']['multi']['mean']:.2e} | {fmt(r.get('sl_over_enbt', {}).get('ratio'))} | "
                         f"{fmt(ex.get('excess'))} {fmt(ex.get('ci95'))} | {fmt(r.get('hu_over_enbt', {}).get('ratio'))} |")
            L.append(f"| {m} | self-KL floor | mean {d['self_floor']['mean_first']:.2e} | max {d['self_floor']['max_first']:.2e} | | | | readable: {d['ratios'].get('E_iter1', {}).get('first', {}).get('readable')} | | |")
    bpb = A.get("bpb") or {}
    if bpb:
        L += ["", "## 7. Bits-per-byte on human-translated FLORES passages (150/lang)", "", "| model | lang | cond | BPB | Δ vs orig [95% CI] | rel Δ % | Δ vs random |", "|---|---|---|---|---|---|---|"]
        for m, d in bpb.items():
            for l in ("en", "sl", "hu"):
                for c, v in d.get(l, {}).items():
                    L.append(f"| {m} | {l} | {c} | {v['bpb']:.4f} | {v['delta_vs_orig']:+.4f} {fmt(v['delta_ci95'], 4)} | {v['rel_delta_pct']:+.2f} | {fmt(v.get('delta_vs_rand_nm_j1'), 4)} |")
    gen = A.get("generations") or {}
    if gen:
        L += ["", "## 8. Harmless generations (128 tokens, greedy): language consistency and degeneracy", "", "| model | cond | arm | n | lang-consistent | S-Slavic (SL) | consistent incl. S-Slavic | degenerate |", "|---|---|---|---|---|---|---|---|"]
        for m, cc in gen.items():
            for c, arms in cc.items():
                for a, v in arms.items():
                    L.append(f"| {m} | {c} | {a} | {v['n']} | {v['lang_consistency']:.3f} | {fmt(v['south_slavic_rate'])} | {fmt(v['consistency_sl_or_southslavic'])} | {v['degenerate_rate']:.3f} |")
    ch, chr_ = A.get("chat_sensitivity"), A.get("chat_sensitivity_nochat_reference")
    if ch and chr_:
        L += ["", "## 8b. Chat-template sensitivity (ARC-C + BoolQ, same 100 items, orig vs E_iter1)", "",
              "| model | lang | task | H with chat template [95% CI] | H without (same items) [95% CI] |", "|---|---|---|---|---|"]
        for m, cc in ch["cells"].items():
            for l in ("en", "sl"):
                for t, d in cc.get("E_iter1", {}).get(l, {}).items():
                    r = chr_["cells"].get(m, {}).get("E_iter1", {}).get(l, {}).get(t, {})
                    L.append(f"| {m} | {l} | {t} | {fmt(d['H'])} {fmt(d['H_ci95'])} (acc {fmt(d['acc_orig'])}→{fmt(d['acc'])}) | {fmt(r.get('H'))} {fmt(r.get('H_ci95'))} |")
    fm = A.get("exploratory_flip_margin")
    if fm:
        L += ["", "## 8c. EXPLORATORY: are flips near-ties? (primary-metric margin between best and 2nd choice under orig)", "",
              "| model | cond | flip rate | flip rate, margin < p10 | flip rate, margin ≥ median | share of flips in bottom-quartile margin | median max|Δll| |", "|---|---|---|---|---|---|---|"]
        for m, cc in fm.items():
            for c, d in cc.items():
                L.append(f"| {m} | {c} | {d['flip_rate']:.3f} | {d['flip_rate_margin_lt_p10']:.3f} | {d['flip_rate_margin_ge_p50']:.3f} | {d['share_of_flips_in_bottom_quartile_margin']:.2f} | {d['median_abs_max_dloglik']:.3f} |")
    L += ["", "## 9. Checks", ""]
    L.append(f"- Published-anchor check (orig SL vs GaMS3 paper bf16 numbers): `{json.dumps(A.get('published_anchor_check'))[:1500]}`")
    L.append(f"- Second-path scorer agreement: `{json.dumps(A.get('scorer2_agreement'))}`")
    for m in MODELS:
        p = RESULTS / "models" / m / "manipulation_check.json"
        if p.exists():
            mc = json.loads(p.read_text())
            L.append(f"- Manipulation check {m}: all_pass={mc['checks']['all_pass']}; E_iter1 KL {mc['checks']['E_iter1']['kl']:.4f} vs iter-1 pick {mc['checks']['E_iter1']['iter1_pick_kl']:.4f}")
        p = RESULTS / "screen" / f"pilot_{m}.json"
        if p.exists():
            pc = json.loads(p.read_text())
            L.append(f"- Pilot {m}: batch-vs-single max |Δloglik| = {pc['batch_vs_single_max_abs_dloglik']:.3f} nats, pair argmax agreement {pc['batch_vs_single_pair_argmax_agree']}, BOS first={pc['bos_first']} doubled={pc['bos_doubled']}")
    if AUD:
        L.append(f"- Audit (path B): {AUD.get('n_checks')} recomputation checks, {AUD.get('n_failed')} failed; placebos centred: {AUD.get('placebos_all_centred')}")
        for k, v in AUD.get("placebos", {}).items():
            L.append(f"  - placebo {k}: observed {v['observed']:.4f}, permutation mean {v['perm_mean']:.4f} (sd {v['perm_sd']:.4f}), p={v['p_two_sided']:.3f}")
    cuts = RESULTS / "cuts.json"
    if cuts.exists():
        L += ["", "## 10. Cuts / deviations (logged)", ""] + [f"- {c}" for c in json.loads(cuts.read_text())]
    return "\n".join(L) + "\n"


def main() -> None:
    mo = method_out()
    (WS / "method_out.json").write_text(json.dumps(mo, ensure_ascii=False))
    (RESULTS / "gates.json").write_text(json.dumps(gates_json(), indent=2, default=float))
    (RESULTS / "RESULTS.md").write_text(results_md())
    print("method_out datasets:", len(mo["datasets"]), "examples:", sum(len(d["examples"]) for d in mo["datasets"]),
          f"| predicted-index vs lm-eval correctness consistency {CONSIST[0]}/{CONSIST[1]}")


if __name__ == "__main__":
    main()
