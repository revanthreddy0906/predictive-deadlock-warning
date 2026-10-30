# Predictive Deadlock Warning

**Early Detection of Unsafe States from Resource-Request Patterns**

Revanth Reddy Lingala, Padigela Srujan, Prathima Tirumalareddy, A. Sirisha
Dept. of Information Technology, Chaitanya Bharathi Institute of Technology, Hyderabad

Banker's algorithm tells an operating system whether the current allocation state is
safe *now*. It gives no warning that the system is drifting towards an unsafe state.
This project measures **how early, how reliably and at what compute cost** that
transition can be predicted, using a discrete-event simulator that grants every valid
request (so unsafe states can actually happen) and Banker's algorithm as ground truth.

- Paper: [`paper/restructured/Predictive_Deadlock_Warning.pdf`](paper/restructured/Predictive_Deadlock_Warning.pdf) (LaTeX source: `paper/restructured/main.tex`)
- Plain-language explanation of every table and figure: [`paper/restructured/EXPLAINED.pdf`](paper/restructured/EXPLAINED.pdf)

## Main results

Test set: 150,000 sequences, 338.3 million simulation steps, 3 workloads, 10-200
processes. Task: warn up to 20 steps before an unsafe transition.

| Method | F1 | Median warning (steps) | Extra compute per step (200 processes) |
|---|---|---|---|
| Random alarms (matched rate) | 0.006 | 11 | ~0 |
| Free-resource threshold | 0.162 | 8 | ~0 |
| **Rule-based score (5 indicators)** | **0.280** | **10** | ~0 |
| Contention (single indicator) | 0.338 | 7 | ~0 |
| Logistic regression | 0.310 | 12 | ~0 |
| Gradient-boosted trees | 0.477 | 11 | ~0 |
| Safety margin (Banker-based, at most 7 checks)* | 0.718 | 4 | 1.7x a simulation step |
| Full one-step lookahead (Banker-based)* | 0.745 | 4 | 43.5x a simulation step |

\* On the common subset of 61,350 sequences where full lookahead was computed.

- The rule-based score beat the free-resource threshold in **20 of 20** independent replications.
- The safety margin is within 0.027 F1 of full lookahead (equivalent within a post-hoc
  margin of ±0.05) at about 1/25 of the cost, but both warn later than the lightweight
  indicators.
- Boosted trees on the same five indicators nearly double the rule-based F1: the
  indicators hold more information than a weighted average extracts.

## Quick start

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest                       # 134 tests
```

**Rebuild the paper's analyses from the included data** (no simulation needed, under a minute):

```bash
.venv/bin/python -m analysis.batches --run data/c_main --batches 20 --delta 0.05
.venv/bin/python -m analysis.make_figures --run data/c_main \
    --params data/c_tuning_small/best_params.json --scaling data/scaling --out paper/restructured/figures
.venv/bin/python -m analysis.make_numbers --run data/c_main --tuning data/c_tuning_small \
    --scaling data/scaling --out paper/numbers.tex
```

The batch analysis, the four paper figures and `numbers.tex` regenerate identically from `data/`.
(Bootstrap interval bounds in `deadlock_common_subset.csv` can differ in the fourth
decimal; point estimates are identical.)

**Re-run the whole pipeline** (simulation, tuning, training, evaluation, tables, figures):

```bash
./run_all.sh                                     # laptop-scale configs
```

The paper's run used the full-scale configs on one AWS EC2 c7i.8xlarge (32 vCPUs):

```bash
TUNING_CFG=configs/c_tuning_small.yaml MAIN_CFG=configs/c_main.yaml \
TUNING_RUN=results/c_tuning_small MAIN_RUN=results/c_main \
TRAIN_ML=1 INSTANCE_TYPE=c7i.8xlarge ./run_all.sh
```

That run took 5 h 40 min and about US$8.39 (see `deployment/aws_run.json`). Finished
batch chunks are skipped, so the pipeline resumes after a crash.

## Repository layout

```
pdw/                       the library
  state.py                 system state model, invariants, random safe initial states
  banker.py                Banker's safety check (vectorised + textbook reference), deadlock
                           detection, full / partial lookahead, safety margin
  scenarios.py             normal, bursty ("spike") and deadlock-prone workload generators
  simulator.py             discrete-event simulator: grants every valid request, records
                           safety and deadlock at every step (event-driven detection)
  indicators.py            the five indicators: resource utilisation, demand ratio,
                           contention, blocked-process ratio, request rate
  warning.py               rule-based score, alarm rule (threshold, persistence k,
                           refractory R), baselines
  learned.py               logistic regression and gradient-boosted trees: features,
                           labels, prior correction
  events.py, metrics.py    event extraction, event-based metrics, bootstrap intervals
  io.py                    chunked Parquet storage
experiments/               run_batch, calibrate, train_ml, tune, evaluate, scaling
analysis/                  batches (replications, TOST, common subset), make_figures,
                           make_tables, make_numbers, make_report
configs/                   run configurations (c_main, c_tuning_small, scaling, ...)
deployment/                AWS EC2 launch / watch / teardown / audit scripts, run records
tests/                     134 tests (every row of the edge-case matrix)
data/                      results of the main run reported in the paper (see below)
proofs/                    evidence of the AWS cloud runs (logs, machine records, CloudTrail)
paper/restructured/        paper source, tables, figures, PDFs
run_all.sh                 the full pipeline in one command
```

## Data (`data/`)

| Path | Contents |
|---|---|
| `data/c_main/meta.json`, `run.log` | Test run: config, seeds 100,000-109,999 per cell, git commit, machine (c7i.8xlarge, 32 vCPUs), timings, totals |
| `data/c_main/summary.parquet` | One row per test sequence (150,000): length, end reason, events, timings |
| `data/c_main/eval/rows.parquet` | Per-sequence evaluation counts for every method, target and horizon |
| `data/c_main/eval/*.csv` | All result tables (listed below) |
| `data/c_main/eval/batches/` | 20 (also 10 and 50) independent replications, paired differences, TOST, common-subset deadlock table |
| `data/c_tuning_small/` | Tuning run (45,000 sequences): tuned thresholds (`best_params.json`), full tuning grid, trained models (`ml_models.pkl`, `ml_meta.json`) |
| `data/scaling/` | Safety-check timing against system size, with fitted slopes |
| `data/pipeline_main_run.log`, `data/calibration.txt` | Full log of the cloud run; workload calibration |

The raw simulation chunks and sample per-step traces are not included; `run_all.sh`
regenerates them from the configs and seeds.

## Where each table and figure comes from

All files are under `data/c_main/eval/` unless stated.

| Paper | Source file | Produced by |
|---|---|---|
| Table V (setup) | `setup.csv` | `experiments.evaluate` |
| Table VI (per-method results) | `overall.csv` | `experiments.evaluate` |
| Table VII (replications) | `batches/paired_B20.csv`; equivalence test: `batches/tost_B20.csv` | `analysis.batches` |
| Table VIII (common subset) | `lookahead_subset.csv` | `experiments.evaluate` |
| Table IX (ablation) | `ablation.csv` | `experiments.evaluate` |
| Table X (per workload) | `per_scenario.csv` | `experiments.evaluate` |
| Table XI (compute cost) | `cost.csv` | `experiments.evaluate` |
| Table XII (deadlock target) | `batches/deadlock_common_subset.csv`, `deadlock_target.csv` | `analysis.batches`, `experiments.evaluate` |
| Table XIII (episode outcomes) | `episode_outcomes.csv` | `experiments.evaluate` |
| Table XIV (claim noise) | `noisy_claims.csv` | `experiments.evaluate` |
| Table XV (horizon) | `hmax_sensitivity.csv` | `experiments.evaluate` |
| Table XVI (safety-check timing) | `data/scaling/scaling.csv`, `scaling_fits.csv` | `experiments.scaling` |
| Fig. 1 (precision-recall) | `pr_curves.csv` | `analysis.make_figures` |
| Fig. 2 (cost-accuracy frontier) | `lookahead_subset.csv`, `cost.csv` | `analysis.make_figures` |
| Fig. 3 (precision vs lead time) | `pr_curves.csv` | `analysis.make_figures` |
| Fig. 4 (safety-check scaling) | `data/scaling/scaling.csv` | `analysis.make_figures` |
| Results by size, paired lead times, burst timing | `per_size.csv`, `paired_leads.csv`, `spike_timing.csv` | `experiments.evaluate` |
| Numbers quoted in the text | `paper/numbers.tex` | `analysis.make_numbers` |

Tables I-IV (related work, methods, scope of claims, runs) are written by hand. The
tables in `paper/restructured/tables/` are formatted copies of `analysis.make_tables`
output with readable method names.

## Design choices that keep the evaluation honest

- **Disjoint seeds.** Tuning uses seeds 0-2,999, testing 100,000-109,999; the learned
  models train on even tuning seeds and their thresholds are tuned on odd ones. The code
  asserts each split.
- **Same task for every method.** All methods use the same alarm rule and are scored
  only on steps where the state is still safe.
- **Event-based metrics.** Alarm precision, event recall, lead time, false alarms per
  1,000 steps and an NAB-style score, not per-step accuracy (unsafe transitions are
  rare: 0.5% of steps).
- **Replications.** Test seeds are dealt into 20 stratified batches and methods are
  compared by paired per-batch differences.
- **Recorded provenance.** Every run directory records its config hash, seeds, git
  commit and machine. The main run used commit `328caf6`.

## Cloud runs

| Run | Date | Instance | Sequences | Steps | Cost |
|---|---|---|---|---|---|
| Exploratory | 8 Oct 2026 | AWS EC2 c7i.8xlarge, ap-south-2 | 300,000 | 676.2 M | ~US$4.11 |
| Main (reported) | 21 Oct 2026 | AWS EC2 c7i.8xlarge, ap-south-2 | 195,000 | 439.6 M | ~US$8.39 |

Launch, watch, teardown and audit scripts are in `deployment/`; each run ended with an
audit confirming that no AWS resources were left running. Evidence that the runs took
place (server logs, machine records, run records, AWS CloudTrail) is
collected in [`proofs/`](proofs/README.md).

## Limitations

One simulator, synthetic workloads with declared maximum claims, and one NumPy
implementation. Real allocation traces, biased claim misdeclaration and a second
safety-check implementation are untested; all results are exploratory (no
pre-registration). See Section VI of the paper.
