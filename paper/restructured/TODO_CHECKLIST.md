# Experiment checklist for the restructured paper

`main.tex` is the full-prose paper. `skeleton.tex` is the earlier scaffold version.

## Done (free, post-hoc on existing EC2 outputs; `analysis/batches.py`, about 30 s on the Mac)
- **E1. Seed batches as the experimental unit.** Test seeds were dealt round-robin into 20 batches per (workload, size) cell and compared by paired per-batch F1 differences. Every ranking claim held in 20/20 batches. With 10 or 50 batches the mean differences are the same and the interval bounds move by at most 0.001. Limit: the thresholds were tuned once, so this replicates test-side sampling only.
- **E2. Paired TOST, safety margin vs exact lookahead.** The difference is −0.027 [−0.031, −0.023]. The 90% interval is [−0.030, −0.024], so the two are equivalent at δ = 0.05 (p < 0.001) and at any δ above 0.030. Top-3 lookahead is not equivalent at δ = 0.05 (p = 0.87). δ was chosen post hoc.
- **E8. Deadlock table on the common subset.** On identical sequences the rule-based score leads (F1 0.659). The state-based checks are among the weakest (0.30–0.37). The old table's ranking was an artefact of mixing populations.

Outputs are in `results_ec2_c/results/c_main/eval/batches/`.

## Not run (listed in §VI "Experiments not run")
| # | Experiment | Why it is needed | Where | Est. time / cost |
|---|---|---|---|---|
| E3 | Biased claims (all claims ×0.8, 0.9, 1.1, 1.2) | ±20% per-entry noise is zero-mean and cancels in sums | EC2 | ~3 h, ~$4–5 |
| E4 | Two-stage gating (cheap score triggers the margin) | the practitioner procedure in §VII is untested | EC2 (same run as E3) | +1–2 h, ~$2–3 |
| E1b | Re-tuning per batch | makes each batch a full replication | EC2 | ~1 h, ~$1.5 |
| E5 | Second (incremental) safety-check implementation | separates algorithm from instrument in the cost results | Mac | ~½ day, $0 |
| E6 | Real allocation traces | external validity; public traces lack Max claims and hold-and-wait, so only a semi-synthetic version is feasible | — | days–weeks |
| E7 | Pre-registered confirmatory campaign | all current results are exploratory | EC2 | ~6 h, ~$9 |

## Open-anomaly checks (§V-G)
- **A1:** trace waiting counts before spike onsets.
- **A2:** deadlock-target recall restricted to alarms raised while safe.
- **A3:** compute the state-based checks on unsafe steps too.
- **A4/A6:** per-size tuning.
- **A5:** extend the threshold grid above 95.

## Writing
- Data availability: replace "available on request" with a repository URL if the repo is made public.
