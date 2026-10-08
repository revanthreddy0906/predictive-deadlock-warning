#!/usr/bin/env bash
# Rebuild every document from one set of results:
#   tables, figures, number macros, paper PDF (tectonic) and plain-language report PDF (pandoc).
#   analysis/build_docs.sh <main_run_dir> <tuning_run_dir> <scaling_dir>
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
MAIN=${1:-results/main_test}
TUNE=${2:-results/tuning}
SCALE=${3:-results/scaling}

$PY -m analysis.make_tables  --run "$MAIN" --tuning "$TUNE" --scaling "$SCALE"
$PY -m analysis.make_figures --run "$MAIN" --params "$TUNE/best_params.json" --scaling "$SCALE"
$PY -m analysis.make_numbers --run "$MAIN" --tuning "$TUNE" --scaling "$SCALE"
$PY -m analysis.make_report  --run "$MAIN" --tuning "$TUNE" --scaling "$SCALE"

cd paper
tectonic -X compile main.tex
pandoc REPORT.md -o REPORT.pdf --pdf-engine=tectonic --toc \
    -V geometry:margin=2cm -V fontsize=10pt -V colorlinks=true \
    -V mainfont=texgyretermes-regular.otf \
    -V 'mainfontoptions=BoldFont=texgyretermes-bold.otf,ItalicFont=texgyretermes-italic.otf,BoldItalicFont=texgyretermes-bolditalic.otf' \
    -V monofont=texgyrecursor-regular.otf
echo "built paper/main.pdf and paper/REPORT.pdf"
