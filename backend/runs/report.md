# Baseline report

Diagnostics only. P, R, F1, return: means over episodes (per the case, P = R = 0 when the denominator is 0,
so clean episodes pull the mean P/R down even for a perfect answer); micro P/R/F1 pool TP/FP/FN over
episodes. Time is wall-clock seconds per episode (not part of any deterministic artefact).

## train (train mode, 10 episodes)

| policy | P | R | F1 | micro P/R/F1 | return | return (clean) | steps | time, s | TP/FP/FN | invalid |
|---|---|---|---|---|---|---|---|---|---|---|
| random_explorer | 0.000 | 0.000 | 0.000 | 0.00/0.00/0.00 | -1.000 | -1.000 | 22.9 | 0.004 | 0/13/48 | 0 |
| simple_reconciler | 0.800 | 0.313 | 0.644 | 1.00/0.38/0.55 | 0.259 | 0.973 | 15.5 | 0.005 | 18/0/30 | 0 |
| flag_all | 0.000 | 0.000 | 0.000 | 0.00/0.00/0.00 | -1.000 | -1.000 | 4.0 | 0.003 | 0/300/48 | 0 |
| oracle | 0.800 | 0.800 | 1.000 | 1.00/1.00/1.00 | 1.000 | 1.000 | 1.0 | 0.003 | 48/0/0 | 0 |

Recall by issue type / false positives by claimed type:

| policy | duplicate_invoice | payment_allocation | fx_error | period_cutoff | FP duplicate / payment / fx / period |
|---|---|---|---|---|---|
| random_explorer | 0.000 | 0.000 | 0.000 | 0.000 | 2 / 3 / 3 / 5 |
| simple_reconciler | 1.000 | 1.000 | 0.000 | 0.000 | 0 / 0 / 0 / 0 |
| flag_all | 0.000 | 0.000 | 0.000 | 0.000 | 80 / 80 / 70 / 70 |
| oracle | 1.000 | 1.000 | 1.000 | 1.000 | 0 / 0 / 0 / 0 |

## dev (eval mode, 10 episodes)

| policy | P | R | F1 | micro P/R/F1 | return | return (clean) | steps | time, s | TP/FP/FN | invalid |
|---|---|---|---|---|---|---|---|---|---|---|
| random_explorer | 0.000 | 0.000 | 0.100 | 0.00/0.00/0.00 | -0.807 | -0.037 | 21.2 | 0.008 | 0/14/54 | 0 |
| simple_reconciler | 0.800 | 0.321 | 0.644 | 1.00/0.39/0.56 | 0.266 | 0.978 | 12.1 | 0.008 | 21/0/33 | 0 |
| flag_all | 0.000 | 0.000 | 0.000 | 0.00/0.00/0.00 | -1.000 | -1.000 | 4.0 | 0.008 | 0/300/54 | 0 |
| oracle | 0.800 | 0.800 | 1.000 | 1.00/1.00/1.00 | 1.000 | 1.000 | 1.0 | 0.007 | 54/0/0 | 0 |

Recall by issue type / false positives by claimed type:

| policy | duplicate_invoice | payment_allocation | fx_error | period_cutoff | FP duplicate / payment / fx / period |
|---|---|---|---|---|---|
| random_explorer | 0.000 | 0.000 | 0.000 | 0.000 | 1 / 8 / 3 / 2 |
| simple_reconciler | 1.000 | 1.000 | 0.000 | 0.000 | 0 / 0 / 0 / 0 |
| flag_all | 0.000 | 0.000 | 0.000 | 0.000 | 80 / 80 / 70 / 70 |
| oracle | 1.000 | 1.000 | 1.000 | 1.000 | 0 / 0 / 0 / 0 |
