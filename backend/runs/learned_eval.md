# Learned auditor - held-out evaluation

4 dev configs x 20 fresh seeds (6000000+), never used in training; every policy runs through AuditEnv (tools, 100-step budget, grader).

| policy | micro P | micro R | micro F1 | mean return | return (clean) | TP/FP/FN | steps | invalid |
|---|---|---|---|---|---|---|---|---|
| simple_reconciler | 1.000 | 0.387 | 0.558 | 0.310 | 0.974 | 137/0/217 | 13.0 | 0 |
| learned_auditor | 1.000 | 1.000 | 1.000 | 0.967 | 0.964 | 354/0/0 | 17.5 | 0 |

Missed / false positives by type:

| policy | duplicate_invoice | payment_allocation | fx_error | period_cutoff |
|---|---|---|---|---|
| simple_reconciler | 0 / 0 | 0 / 0 | 102 / 0 | 115 / 0 |
| learned_auditor | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

Learning curve: the detector retrained from scratch on N generated train-config episodes
(threshold picked by mean terminal reward on N more), evaluated on the same held-out episodes:

| train episodes | threshold | micro P | micro R | micro F1 | mean return | TP/FP/FN |
|---|---|---|---|---|---|---|
| 6 | 0.75 | 1.000 | 0.989 | 0.994 | 0.958 | 350/0/4 |
| 12 | 0.5 | 1.000 | 1.000 | 1.000 | 0.967 | 354/0/0 |
| 30 | 0.5 | 1.000 | 1.000 | 1.000 | 0.967 | 354/0/0 |
| 60 | 0.5 | 1.000 | 1.000 | 1.000 | 0.967 | 354/0/0 |
| 180 | 0.5 | 1.000 | 1.000 | 1.000 | 0.967 | 354/0/0 |
