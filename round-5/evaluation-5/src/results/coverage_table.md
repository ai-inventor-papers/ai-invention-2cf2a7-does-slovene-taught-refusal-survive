# Coverage table

| component | status | artifact(s) | reason |
|---|---|---|---|
| RQ1 (does English-objective abliteration remove Slovene refusal?) | DONE (screen) | exp9, exp11, exp15 | EN and SL refusal both fall under the edit in every body; lag estimates in the decomposition table |
| RQ2 (frozen-core confirmation) | NOT DONE in iteration 4 | exp13 | GPU loss (A1); iteration 5: PENDING - iteration-5 experiment, not an input of this artifact |
| RQ3 (mechanism: input vs output side) | DONE (exploratory) | exp14 | M-OUT on raw readout for Gemma; not robust across readouts |
| RQ4 (geometry / induction) | DONE (replication-grade) | exp10 | u_lang induction; relabelled as replication/source-separability |
| Frozen-core edit (fresh 200/60-trial Heretic run) | not executed (GPU loss) | exp13 | respecified per research_extended.json: Heretic has no auto-selection; 200/60 trial defaults |
| Random-direction control | DONE | exp9, exp14, exp15 | norm-matched random LoRAs; first scored GaMS random control in exp15 |
| C1-C5 | see verdict table | various |  |
| Utility suite | DONE (partial) | exp11, exp12 | Belebele, FLORES NLL/byte, first-token/multi-token KL |
| ASR protocol (StrongREJECT-style) | PARTIAL | eval3 (paid gemini), exp15 (unaffordable) | exp15 A4 key limit |
| C-EXT (public abliterated checkpoints) | PARTIAL | exp14 (1 checkpoint, descriptive); exp11 (not generated) | cache reclaimed / time |
| Human (native-speaker) audit | HUMAN-INPUT REQUIRED | exp14 human_audit_request.json | REQUESTED, NOT PERFORMED - no human review is claimed anywhere in this artifact |
