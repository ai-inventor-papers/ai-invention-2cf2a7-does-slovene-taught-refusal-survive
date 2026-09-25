#!/usr/bin/env python3
"""Record the wall-budget amendments (A0_gams3_it short DEV grid; gate condition on 650 pairs) in the amendment log."""
from freeze import record_amendment

record_amendment("A0_gams3_it", {"what": "GaMS DEV dose grid restricted to lambda in {0, 1.0}",
                                 "why": "measured throughput (gen 2.2-2.8 rows/s, PolyGuard 3.7 rows/s, 3 guards x "
                                        "every row, 2 models) projected past the 6 h wall budget",
                                 "rule": "the frozen gate rule needs only {0, 1.0} unless rel_cut(1.0) < 0.5; the "
                                         "chain extends the grid before a gate session if that happens",
                                 "cut_order_item": "not on the frozen NEVER-CUT list"})
record_amendment("A2_gate_pairs", {"what": "the edit@lambda_gate condition, if triggered, covers the first 650 FINAL "
                                          "pairs by frozen hash order", "cut_order_item": "wall cut 3"})
record_amendment("A3_no_paid", {"what": "no paid readout is executed; R0 local substitutes carry every readout",
                                "why": "run-level OpenRouter budget exhausted before this artifact started (403 "
                                       "aii_run_budget_exhausted, recorded in results/inputs_check.json)",
                                "spend_usd": 0.0})
