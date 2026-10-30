#!/usr/bin/env bash
# Build Predictive_Deadlock_Warning.docx from main.tex (needs pandoc 3 and a prior
# LaTeX build of main.tex, whose main.aux supplies the table, figure and section numbers).
set -euo pipefail
cd "$(dirname "$0")"
R=..
T=$(mktemp -d)
pandoc -o "$T/ref.docx" --print-default-data-file reference.docx
python3 style_ref.py "$T/ref.docx" "$T/ref_ieee.docx"
python3 tex2docx.py "$R" "$T/body.tex"
sed -i '' 's#width=4.6in\]{figures/fig7_scaling#width=6.2in]{figures/fig7_scaling#; s#\\frac{1}{m}#(1/m)#' "$T/body.tex"
pandoc "$T/body.tex" -f latex -o "$R/Predictive_Deadlock_Warning.docx" --metadata-file=meta.yaml \
    --citeproc --bibliography="$R/../refs.bib" --csl=ieee.csl --resource-path="$R" --reference-doc="$T/ref_ieee.docx"
echo "written $R/Predictive_Deadlock_Warning.docx"
