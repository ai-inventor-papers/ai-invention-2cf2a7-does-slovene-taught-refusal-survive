# TODO (tracked here; no todo tool in this session) — ALL COMPLETE
TODO 1. Read and STRICTLY follow skills (aii-python, aii-long-running-tasks, aii-json, aii-file-size-limit, aii-use-hardware, aii-parallel-computing). [done]
TODO 2. Read dependency previews; use ALL datasets; read domain handbook; test with uv. [done — RefusEU dependency used for contamination filter; item body built from exp1 pairs; mech-interp handbook practices applied via exp9/exp11 code]
TODO 3. Fully implement method AND baseline in method.py (entry point) + src/; validate exp_gen_sol_out. [done — method (Heretic edit lambda-ladder on GaMS) + baselines (unedited lambda 0, sibling Gemma, norm-matched random control) in one pipeline; method_out.json schema-validated; audit 81/81; 10/10 unit tests]

RESULT: G3 = -0.70 [-1.01,-0.42] (raw J1, MDE 0.42, best power in run). Decomposition: G3_edit = +0.47 [-0.96,2.14] (R-BASE supported) — the Slovene lag is a PRE-EDIT baseline offset (G3_orig -1.17), not created by the English edit. Verdict ESTIMATE (SCREEN; J1 fallback fails SL-edited Sp gate after OpenRouter key limit).
