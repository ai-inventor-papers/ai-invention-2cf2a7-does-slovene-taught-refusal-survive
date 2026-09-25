#!/usr/bin/env python3
"""STEP 4 - regenerate the exp14 tables ONLY from exp14 results/analysis.json (+ protocol_amendments.jsonl), with an
independent count cross-check from rows_final.jsonl. Output: results/exp14_tables_regenerated.{json,md}."""
from __future__ import annotations

import json
from collections import defaultdict

from loguru import logger

import re

from common import EXP14, PAPER, RES, read_json, read_jsonl, rel, setup_logging, write_json

MODELS3 = ("gemma_it", "gams3_it")
CELLS = [f"{i}{o}" for i in ("en", "sl", "hu") for o in ("en", "sl", "hu")]
DOSES = ("zero", "lo", "hi")


def f(x, nd=2):
    if x is None:
        return "NA"
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(f(v, nd) for v in x) + "]"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def est(d: dict | None) -> str:
    if not d or d.get("est") is None:
        return "NA"
    return f"{d['est']:.2f} {f(d.get('ci95'))}"


def crosscheck(an: dict) -> dict:
    """independent filter over rows_final.jsonl: (model, cond=edit|ext, dose, in, out, kind) -> REFUSE count / labelled n."""
    rows = read_jsonl(EXP14 / "results/rows_final.jsonl")
    cnt = defaultdict(lambda: [0, 0, 0])
    for r in rows:
        if r["cond"] not in ("edit", "ext"):  # 'rand' (random-direction control) and 'mtnoise' (EN_orig) are separate arms
            continue
        key = f"{r['model']}|{r['dose'] if r['cond'] != 'ext' else 'ext'}|{r['in_lang']}{r['out_lang']}|{r['kind']}"
        cnt[key][0] += 1
        if r.get("L_primary"):
            cnt[key][1] += 1
            cnt[key][2] += int(r["L_primary"] == "REFUSE")
    mism = []
    for key, c in an["cell_table"].items():
        n, nl, k = cnt.get(key, [0, 0, 0])
        k_saved = round(c["R"] * c["n_labelled"])
        if n != c["n"] or nl != c["n_labelled"] or k != k_saved:
            mism.append({"cell": key, "rows_final": [n, nl, k], "analysis": [c["n"], c["n_labelled"], k_saved]})
    return {"n_cells_checked": len(an["cell_table"]), "n_mismatch": len(mism), "mismatches": mism[:50],
            "pass": not mism, "rule": "rows_final counts must equal cell_table n, n_labelled and round(R*n_labelled)"}


def paper_diff(an: dict) -> dict:
    """Cell-by-cell diff of paper Tables 28 (Gemma) and 29 (GaMS3) against cell_table / compliance_gate.
    A cell differs when |paper - verified| exceeds half a unit of the paper's last shown digit."""
    lines = PAPER.read_text().splitlines()
    out, diffs = [], []
    for title, m in (("**Table 28.", "gemma_it"), ("**Table 29.", "gams3_it")):
        start = next((i for i, x in enumerate(lines) if x.startswith(title)), None)
        if start is None:
            continue
        for i in range(start + 1, min(start + 20, len(lines))):
            row = lines[i]
            if row.startswith("**Table"):  # next table begins: stop
                break
            mt = re.match(r"\|\s*(EN|SL|HU)->(EN|SL|HU)\s*\|(.*)", row)
            if not mt:
                continue
            cell = (mt.group(1) + mt.group(2)).lower()
            parts = [p_.strip() for p_ in mt.group(3).split("|") if p_.strip()]
            for d, txt in zip(("zero", "lo", "hi"), parts[:3]):
                nums = [float(x) for x in re.findall(r"-?\d+\.\d+", txt)]
                ver = an["cell_table"].get(f"{m}|{d}|{cell}|harmful", {})
                for lab, pv, vv in (("R", nums[0] if nums else None, ver.get("R")),
                                    ("R_ci_lo", nums[1] if len(nums) > 1 else None, (ver.get("R_ci") or [None])[0]),
                                    ("R_ci_hi", nums[2] if len(nums) > 2 else None, (ver.get("R_ci") or [None, None])[1])):
                    if pv is None or vv is None:
                        continue
                    ok = abs(pv - vv) <= 0.005 + 1e-9
                    rec = {"table": title.strip("*."), "line": i + 1, "model": m, "cell": cell, "dose": d, "field": lab,
                           "paper": pv, "verified": vv, "match": ok}
                    out.append(rec)
                    if not ok:
                        diffs.append(rec)
            if len(parts) >= 4:
                cn = re.findall(r"\d+\.\d+", parts[3])
                vv = an.get("compliance_gate", {}).get(f"{m}|{cell}", {}).get("compliance")
                if cn and vv is not None:
                    ok = abs(float(cn[0]) - vv) <= 0.005 + 1e-9
                    rec = {"table": title.strip("*."), "line": i + 1, "model": m, "cell": cell, "dose": "pooled",
                           "field": "compliance", "paper": float(cn[0]), "verified": vv, "match": ok}
                    out.append(rec)
                    if not ok:
                        diffs.append(rec)
    return {"n_cells_compared": len(out), "n_differ": len(diffs), "differing": diffs,
            "rule": "differs if |paper - verified| > 0.005 (half a unit of the 2nd decimal)"}


def main() -> dict:
    setup_logging("exp14_tables")
    p = EXP14 / "results/analysis.json"
    an = read_json(p)
    ct, comp = an["cell_table"], an.get("compliance_gate", {})
    L = [f"# exp14 tables regenerated from `{rel(p)}` (no hand-typed numbers)\n",
         "Readout: local J1 (mdeberta distilled from gemini) unless stated; adjudication = author model, NOT human.\n"]
    # (a) refusal rates
    L.append("## (a) Refusal rate per model x cell x dose (harmful items; Wilson 95% CI; n labelled; output-language compliance)\n")
    L.append("| model | cell (in->out) | zero | lo | hi | compliance gate (pooled doses) | benign FA zero / lo / hi |")
    L.append("|---|---|---|---|---|---|---|")
    table_a = []
    for m in MODELS3:
        for c in CELLS:
            vals = []
            for d in DOSES:
                x = ct.get(f"{m}|{d}|{c}|harmful")
                vals.append("NA" if not x else f"{x['R']:.3f} {f(x['R_ci'])} n={x['n_labelled']} comp={x['compliance']:.2f}")
            bvals = [ct.get(f"{m}|{d}|{c}|benign") for d in DOSES]
            g = comp.get(f"{m}|{c}", {})
            gate = "NA" if not g else f"{g['compliance']:.3f} ({'pass' if g.get('pass90') else 'FAIL'} 0.90)"
            L.append(f"| {m} | {c[:2]}->{c[2:]} | " + " | ".join(vals) + f" | {gate} | "
                     + " / ".join("NA" if b is None else f"{b['R']:.3f}" for b in bvals) + " |")
            table_a.append({"model": m, "cell": c, "harmful": {d: ct.get(f"{m}|{d}|{c}|harmful") for d in DOSES},
                            "benign": {d: ct.get(f"{m}|{d}|{c}|benign") for d in DOSES}, "compliance_gate": g})
    cext = an.get("c_ext", {})
    for ck, cells in cext.items():
        L.append(f"| {ck} (C-EXT public checkpoint, descriptive) | " + "; ".join(
            f"{c}: {v['R']:.3f} {f(v['ci'])}" for c, v in cells.items() if isinstance(v, dict) and "R" in v) + " | | | | |")
    # (b) mechanism contrasts
    L.append("\n## (b) Mechanism contrasts per readout (NA where a readout does not exist)\n")
    contrasts = ["OUT_SL", "IN_SL", "INT_SL", "OUTminusIN_SL", "OUTshare_SL", "L_OUT_SL", "L_IN_SL", "L_OUTminusIN_SL",
                 "OUT_HU", "IN_HU", "OUTminusIN_HU", "L_OUT_HU", "L_IN_HU"]
    rds = list(an.get("readouts", {}).keys())
    L.append("| contrast | model | " + " | ".join(rds) + " |")
    L.append("|---|---|" + "---|" * len(rds))
    table_b = {}
    for cn in contrasts:
        for m in MODELS3:
            row = [est(an["readouts"][r].get(f"{cn}|{m}")) for r in rds]
            table_b[f"{cn}|{m}"] = {r: an["readouts"][r].get(f"{cn}|{m}") for r in rds}
            L.append(f"| {cn} | {m} | " + " | ".join(row) + " |")
    gold = an.get("gold_out_vs_in", {})
    for m, g in gold.items():
        L.append(f"| gold (author-model adjudication) R nonEN-output / EN-output / nonEN-input+EN-output | {m} | "
                 f"{f(g.get('R_nonEN_output'))} (n={g.get('n_nonEN_output')}) / {f(g.get('R_EN_output'))} (n={g.get('n_EN_output')}) / "
                 f"{f(g.get('R_nonEN_input_EN_output'))} (n={g.get('n_nonEN_input_EN_output')}) |" + " |" * (len(rds) - 1))
    dec = an.get("decisions", {})
    L.append("\nMechanism calls per readout: " + "; ".join(
        f"{r}: SL={dec[r].get('mechanism_SL', {}).get('verdict')}, HU={dec[r].get('mechanism_HU', {}).get('verdict')}"
        for r in dec if isinstance(dec[r], dict)))
    # (c) L* G3 table
    L.append("\n## (c) L* cross-model G3 and G3_edit per cell (GaMS - Gemma; flagged where GaMS compliance fails)\n")
    L.append("| cell | readout | G3 | G3_edit | GaMS compliance gate |")
    L.append("|---|---|---|---|---|")
    table_c = []
    for c in CELLS:
        for r in rds:
            g3, ge = an["readouts"][r].get(f"G3|{c}"), an["readouts"][r].get(f"G3edit|{c}")
            if g3 is None and ge is None:
                continue
            g = comp.get(f"gams3_it|{c}", {})
            flag = "INVALID-MANIPULATION" if g and not g.get("pass90") else "ok"
            L.append(f"| {c[:2]}->{c[2:]} | {r} | {est(g3)} | {est(ge)} | {f(g.get('compliance'), 3)} {flag} |")
            table_c.append({"cell": c, "readout": r, "G3": g3, "G3_edit": ge, "gams_compliance": g.get("compliance"), "flag": flag})
    # (d) SDT
    L.append("\n## (d) SDT difference-in-differences (Gemma - GaMS; d' and c; c = -(z_H+z_FA)/2 as saved by exp14)\n")
    L.append("| dose / language position | d' DiD [95% CI] | c DiD [95% CI] | c Gemma | c GaMS |")
    L.append("|---|---|---|---|---|")
    for k, v in an.get("sdt", {}).get("DiD", {}).items():
        L.append(f"| {k} | {f(v[chr(100) + chr(39)]['DiD_gemma_minus_gams'])} {f(v[chr(100) + chr(39)]['ci95'])} | "
                 f"{f(v['c']['DiD_gemma_minus_gams'])} {f(v['c']['ci95'])} | {f(v['c']['gemma'])} | {f(v['c']['gams'])} |")
    # (e) amendments, support, MT noise, robust call, RG stability
    L.append("\n## (e) Amendments, support, MT-noise, robust call, RG stability\n")
    am = []
    ap = EXP14 / "results/protocol_amendments.jsonl"
    if ap.exists():
        am = read_jsonl(ap)
        for a in am:
            L.append(f"- **{a.get('id')}** ({a.get('ts')}): {a.get('text', '')[:400]}")
    L.append(f"\n- support: `{json.dumps(an.get('support'))}`")
    for k, v in an.get("mt_noise", {}).items():
        L.append(f"- MT-noise {k}: EN_orig {v['R_EN_orig']:.3f} vs EN_BT {v['R_EN_BT']:.3f}, discordant {v['discordant_orig_only']}/"
                 f"{v['discordant_bt_only']}, McNemar p={v['mcnemar_p']:.4f}")
    L.append(f"- robust_call_SL: `{json.dumps(an.get('robust_call_SL'))[:600]}`")
    L.append(f"- rg_stability: `{json.dumps(an.get('rg_stability'))[:400]}`")
    cc = crosscheck(an)
    pdiff = paper_diff(an)
    L.append(f"\n## Diff against paper Tables 28-29 (iteration-4 draft)\n\n{pdiff['n_cells_compared']} values compared, "
             f"{pdiff['n_differ']} differ beyond rounding ({pdiff['rule']}).\n")
    if pdiff["differing"]:
        L.append("| table | line | model | cell | dose | field | paper | verified |\n|---|---|---|---|---|---|---|---|")
        for r in pdiff["differing"]:
            L.append(f"| {r['table']} | {r['line']} | {r['model']} | {r['cell']} | {r['dose']} | {r['field']} | {r['paper']:.2f} | {r['verified']:.4f} |")
    L.append(f"\n## Cross-check (independent filter over rows_final.jsonl)\n\n{cc['n_cells_checked']} cells checked, "
             f"{cc['n_mismatch']} mismatches -> {'PASS' if cc['pass'] else 'FAIL (logged, not fixed)'}")
    (RES / "exp14_tables_regenerated.md").write_text("\n".join(L) + "\n")
    res = {"source": rel(p), "table_a": table_a, "table_b": table_b, "table_c": table_c, "sdt_DiD": an.get("sdt", {}).get("DiD"),
           "amendments": am, "support": an.get("support"), "mt_noise": an.get("mt_noise"), "robust_call_SL": an.get("robust_call_SL"),
           "rg_stability": an.get("rg_stability"), "crosscheck": cc, "paper_table_diff": pdiff,
           "compliance_failures": {k: v for k, v in comp.items() if not v.get("pass90")}}
    write_json(RES / "exp14_tables_regenerated.json", res)
    logger.info(f"exp14 tables: crosscheck {cc['pass']} ({cc['n_mismatch']} mismatches); compliance failures {list(res['compliance_failures'])}")
    return res


if __name__ == "__main__":
    main()
