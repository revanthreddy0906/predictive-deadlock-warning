# Predictive Deadlock Warning

Early detection of unsafe states from resource-request patterns. A rule-based (no ML)
early-warning algorithm is evaluated against Banker's algorithm as ground truth, with
event-based metrics (alarm precision, event recall, lead time) and explicit baselines.

CBIT Operating Systems case study, Revanth Reddy Lingala and Sujju.
The full plan is in `IMPLEMENTATION_PLAN.md`; `PLAN_FIXES.md` overrides it where they differ.

## Layout

| Path | Contents |
|---|---|
| `pdw/state.py` | System state model and invariants, random safe initial states |
| `pdw/banker.py` | Banker's safety check (vectorised + reference), request classification, deadlock detection, lookahead baseline |
| `pdw/scenarios.py` | `normal`, `spike`, `deadlock_prone` workload generators (calibrated parameters) |
| `pdw/simulator.py` | Observer-mode simulator, event-driven deadlock detection |
| `pdw/indicators.py` | Five indicators in [0, 1] |
| `pdw/warning.py` | Risk score, alarm-onset rule, methods and baselines |
| `pdw/events.py`, `pdw/metrics.py` | Event extraction, event-based metrics, bootstrap CIs |
| `pdw/io.py` | Chunked Parquet storage |
| `experiments/` | `calibrate`, `run_batch`, `tune`, `evaluate`, `scaling` |
| `analysis/` | `make_tables` (LaTeX), `make_figures` (PDF/PNG) |
| `configs/` | `smoke`, `calibrate`, `tuning`, `main`, `scaling` |

## Reproduce

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
./run_all.sh
```

`run_all.sh` runs tests, smoke, calibration, the tuning split (seeds 0-1,999), the test
split (seeds 100,000-101,999), tuning, evaluation, scaling, then writes
`paper/tables/*.tex` and `paper/figures/*.pdf`. Results land in `results/` (gitignored);
every run directory has a `meta.json` (git commit, config hash, machine, totals) and
`run.log`. Batch runs resume after a crash and skip chunks already written.

Individual steps:

```bash
.venv/bin/python -m experiments.run_batch --config configs/main.yaml
.venv/bin/python -m experiments.tune --run results/tuning
.venv/bin/python -m experiments.evaluate --run results/main_test --params results/tuning/best_params.json
```

Tuning only ever reads tuning seeds and evaluation only test seeds (asserted in code).

## Running on AWS EC2

See `deployment/EC2_SETUP.md`.
