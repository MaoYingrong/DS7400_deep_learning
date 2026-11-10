### Main experiment: 40 epochs, mean ± std over 10 seeds (accuracy in %, test diff = paired mean ± standard error)

| Variant | Params | Train acc | Val acc | Test acc | Test macro-F1 | Train-val gap | Test diff vs baseline | Best epoch |
|---|---|---|---|---|---|---|---|---|
| HW2 baseline (untied, fixed add) | 161,417 | 92.7 | 74.7 ± 0.6 | 77.2 ± 0.3 | 0.613 ± 0.003 | 18.0 | +0.0 ± 0.0 | 31.5 |
| Tied + per-paper gate (my design) | 81,674 | 89.9 | 76.4 ± 0.5 | 76.3 ± 0.7 | 0.610 ± 0.012 | 13.5 | -0.9 ± 0.3 | 36.8 |
| Tied, fixed add (no gate) | 81,545 | 89.6 | 76.2 ± 0.5 | 76.3 ± 0.7 | 0.606 ± 0.008 | 13.4 | -0.9 ± 0.2 | 35.1 |
| Untied + per-paper gate | 161,610 | 92.0 | 74.2 ± 0.6 | 76.6 ± 0.6 | 0.606 ± 0.009 | 17.7 | -0.6 ± 0.2 | 34.6 |
| Tied + one global gate | 81,546 | 90.5 | 75.1 ± 0.8 | 75.4 ± 0.9 | 0.594 ± 0.011 | 15.4 | -1.8 ± 0.3 | 37.2 |
| Tied, neighbour branch removed | 81,545 | 90.4 | 73.7 ± 0.5 | 72.1 ± 0.6 | 0.556 ± 0.009 | 16.7 | -5.1 ± 0.2 | 37.4 |

### Gate diagnostics (per-paper gate g, all 2,000 papers, final weights)

| Variant | mean g | std of g across papers | min | max | corr(g, log(1+degree)) | mean g, degree 0 | test: g when correct | test: g when wrong |
|---|---|---|---|---|---|---|---|---|
| Tied + per-paper gate (my design) | 0.971 | 0.011 | 0.886 | 0.994 | -0.02 | 0.969 (n=197) | 0.973 | 0.966 |
| Untied + per-paper gate | 0.976 | 0.008 | 0.918 | 0.993 | -0.06 | 0.976 (n=197) | 0.977 | 0.972 |

### Test accuracy by number of citation neighbours (mean over seeds, %)

| Variant | degree 0–5 (n=102) | degree 6–15 (n=82) | degree 16–30 (n=58) | degree 31–∞ (n=58) |
|---|---|---|---|---|
| Tied + per-paper gate (my design) | 72.9 | 73.7 | 83.8 | 78.4 |
| Tied, fixed add (no gate) | 74.4 | 72.6 | 83.4 | 77.6 |
| Untied + per-paper gate | 74.7 | 74.3 | 82.2 | 77.6 |
| Tied + one global gate | 72.7 | 72.0 | 82.1 | 78.3 |
| Tied, neighbour branch removed | 69.5 | 67.6 | 74.3 | 80.9 |

### Training-budget check: 80 epochs (same seeds)

| Variant | Params | Train acc | Val acc | Test acc | Test macro-F1 | Train-val gap | Test diff vs baseline | Best epoch |
|---|---|---|---|---|---|---|---|---|
| HW2 baseline (untied, fixed add) | 161,417 | 92.7 | 74.7 ± 0.6 | 77.2 ± 0.3 | 0.613 ± 0.003 | 18.0 | +0.0 ± 0.0 | 31.5 |
| Tied + per-paper gate (my design) | 81,674 | 90.4 | 76.4 ± 0.5 | 76.4 ± 0.7 | 0.611 ± 0.011 | 14.0 | -0.8 ± 0.2 | 38.5 |
| Tied, fixed add (no gate) | 81,545 | 90.0 | 76.3 ± 0.6 | 76.5 ± 0.9 | 0.610 ± 0.011 | 13.6 | -0.6 ± 0.3 | 36.6 |

Final-epoch train−val gap (no best-epoch selection): HW2 baseline (untied, fixed add) 24.9, Tied + per-paper gate (my design) 22.5, Tied, fixed add (no gate) 22.7

Final-epoch train−val gap in the main experiment: HW2 baseline (untied, fixed add) 19.6, Tied + per-paper gate (my design) 14.1, Tied, fixed add (no gate) 14.5, Untied + per-paper gate 19.1, Tied + one global gate 15.8, Tied, neighbour branch removed 17.8

Mean training time per run (s): HW2 baseline (untied, fixed add) 1.07, Tied + per-paper gate (my design) 1.35, Tied, fixed add (no gate) 1.25, Untied + per-paper gate 1.49, Tied + one global gate 1.28, Tied, neighbour branch removed 1.23
