#!/bin/sh
# Build amidst_experiment_record.pdf with XeLaTeX (xeCJK, macOS Songti TC / PingFang TC).
set -eu
cd "$(dirname "$0")"
PATH="/Library/TeX/texbin:$PATH"
latexmk -xelatex -interaction=nonstopmode -halt-on-error amidst_experiment_record.tex
if grep -E "undefined references|Reference .* undefined|Citation .* undefined|Missing character" amidst_experiment_record.log; then
  echo "build.sh: undefined reference or missing glyph" >&2
  exit 1
fi
latexmk -c amidst_experiment_record.tex
echo "build.sh: OK -> $(pwd)/amidst_experiment_record.pdf"
