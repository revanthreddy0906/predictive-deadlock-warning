#!/usr/bin/env bash
# Full pipeline: tests -> smoke -> calibration -> tuning runs -> test runs -> tune
# -> evaluate -> scaling -> tables + figures -> deliverables archive.
# Safe to re-run: finished batch chunks are skipped.
#
#   ./run_all.sh                                   # Mac-scale configs
#   TUNING_CFG=configs/b_tuning.yaml MAIN_CFG=configs/b_main.yaml \
#   TUNING_RUN=results/b_tuning MAIN_RUN=results/b_main \
#   INSTANCE_TYPE=c7i.8xlarge ./run_all.sh          # Option B on EC2
#   ... TRAIN_ML=1 with configs/c_*.yaml            # full paper: extras + learned baselines
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-.venv/bin/python}
TUNING_CFG=${TUNING_CFG:-configs/tuning.yaml}
MAIN_CFG=${MAIN_CFG:-configs/main.yaml}
TUNING_RUN=${TUNING_RUN:-results/tuning}
MAIN_RUN=${MAIN_RUN:-results/main_test}
mkdir -p results

echo "== 1/10 tests";       $PY -m pytest -q
echo "== 2/10 smoke";       $PY -m experiments.run_batch --config configs/smoke.yaml
echo "== 3/10 calibration"; $PY -m experiments.calibrate --config configs/calibrate.yaml | tee results/calibration.txt
echo "== 4/10 tuning runs"; $PY -m experiments.run_batch --config "$TUNING_CFG"
echo "== 5/10 test runs";   $PY -m experiments.run_batch --config "$MAIN_CFG"
if [ "${TRAIN_ML:-0}" = "1" ]; then
    echo "== 5b/10 train learned baselines"; $PY -m experiments.train_ml --run "$TUNING_RUN"
fi
echo "== 6/10 tune";        $PY -m experiments.tune --run "$TUNING_RUN"
echo "== 7/10 evaluate";    $PY -m experiments.evaluate --run "$MAIN_RUN" --params "$TUNING_RUN/best_params.json"
echo "== 8/10 scaling";     $PY -m experiments.scaling --config configs/scaling.yaml
echo "== 9/10 tables+figs"
$PY -m analysis.make_tables --run "$MAIN_RUN" --tuning "$TUNING_RUN"
$PY -m analysis.make_figures --run "$MAIN_RUN" --params "$TUNING_RUN/best_params.json"
echo "== 10/10 deliverables"
tar czf results/deliverables.tgz \
    "$MAIN_RUN/eval" "$MAIN_RUN/meta.json" "$MAIN_RUN/summary.parquet" "$MAIN_RUN/traces" "$MAIN_RUN/run.log" \
    "$TUNING_RUN/best_params.json" "$TUNING_RUN/tuning_grid.csv" "$TUNING_RUN/meta.json" \
    $( [ -f "$TUNING_RUN/ml_models.pkl" ] && echo "$TUNING_RUN/ml_models.pkl $TUNING_RUN/ml_meta.json" ) \
    "$TUNING_RUN/summary.parquet" "$TUNING_RUN/run.log" \
    results/calibration.txt results/scaling paper/tables paper/figures
echo "PIPELINE DONE: results/deliverables.tgz"
