# Learned auditor - held-out evaluation

4 dev configs x 20 fresh seeds (6000000+), never used in training; every policy runs through AuditEnv (tools, 100-step budget, grader).

| policy | micro P | micro R | micro F1 | mean return | return (clean) | TP/FP/FN | steps | invalid |
|---|---|---|---|---|---|---|---|---|
| simple_reconciler | 0.993 | 0.387 | 0.557 | 0.309 | 0.974 | 137/1/217 | 13.0 | 0 |
| learned_auditor | 0.997 | 1.000 | 0.999 | 0.965 | 0.964 | 354/1/0 | 17.5 | 0 |

Missed / false positives by type:

| policy | duplicate_invoice | payment_allocation | fx_error | period_cutoff |
|---|---|---|---|---|
| simple_reconciler | 0 / 1 | 0 / 0 | 102 / 0 | 115 / 0 |
| learned_auditor | 0 / 1 | 0 / 0 | 0 / 0 | 0 / 0 |

Learning curve: the detector retrained from scratch on N generated train-config episodes
(threshold picked by mean terminal reward on N more), evaluated on the same held-out episodes:

| train episodes | threshold | micro P | micro R | micro F1 | mean return | TP/FP/FN |
|---|---|---|---|---|---|---|
| 6 | 0.75 | 0.997 | 0.989 | 0.993 | 0.956 | 350/1/4 |
| 12 | 0.5 | 0.997 | 1.000 | 0.999 | 0.965 | 354/1/0 |
| 30 | 0.5 | 0.997 | 1.000 | 0.999 | 0.965 | 354/1/0 |
| 60 | 0.5 | 0.997 | 1.000 | 0.999 | 0.965 | 354/1/0 |
| 180 | 0.5 | 0.997 | 1.000 | 0.999 | 0.965 | 354/1/0 |
