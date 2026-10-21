#!/usr/bin/env bash
# Resume the full-paper pipeline from step 6 (tune) with one thread per worker process:
# scikit-learn/OpenMP otherwise starts one thread per core inside every worker.
set -euo pipefail
cd ~/pdw
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export INSTANCE_TYPE=c7i.8xlarge PDW_GIT_COMMIT=$(git rev-parse HEAD)
TUNING_RUN=results/c_tuning_small; MAIN_RUN=results/c_main; PY=.venv/bin/python
echo "== 6/10 tune (resumed)";  $PY -m experiments.tune --run "$TUNING_RUN"
echo "== 7/10 evaluate";       $PY -m experiments.evaluate --run "$MAIN_RUN" --params "$TUNING_RUN/best_params.json"
echo "== 8/10 scaling";        $PY -m experiments.scaling --config configs/scaling.yaml
echo "== 9/10 tables+figs"
$PY -m analysis.make_tables --run "$MAIN_RUN" --tuning "$TUNING_RUN"
$PY -m analysis.make_figures --run "$MAIN_RUN" --params "$TUNING_RUN/best_params.json"
echo "== 10/10 deliverables"
tar czf results/deliverables.tgz "$MAIN_RUN/eval" "$MAIN_RUN/meta.json" "$MAIN_RUN/summary.parquet" "$MAIN_RUN/traces" \
    "$MAIN_RUN/run.log" "$TUNING_RUN/best_params.json" "$TUNING_RUN/tuning_grid.csv" "$TUNING_RUN/meta.json" \
    "$TUNING_RUN/ml_models.pkl" "$TUNING_RUN/ml_meta.json" "$TUNING_RUN/summary.parquet" "$TUNING_RUN/run.log" \
    results/calibration.txt results/scaling paper/tables paper/figures
echo "PIPELINE DONE: results/deliverables.tgz"
