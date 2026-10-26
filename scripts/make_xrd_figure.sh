#!/bin/bash
# Draw the "fit" figure with TikZ/PGFPlots from the results of an AMORPH run.
#
#     bash scripts/make_xrd_figure.sh [data file] [title]
#
# The posterior samples (src/posterior_sample.txt) have to exist; run
# "python showresults.py" in the src folder first. Without a data file (or
# with ""), the data file is the one src/config.yaml names; without a
# title, the title is the name of the data file.

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${1:-}"
OUT="${ROOT}/doc/figures/pgf"

if command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    PY=python
fi

if [ ! -f "${ROOT}/src/posterior_sample.txt" ]; then
    echo "src/posterior_sample.txt not found - run 'python showresults.py' first" >&2
    exit 1
fi

args=(--posterior "${ROOT}/src/posterior_sample.txt" --out "${OUT}")
if [ -n "${DATA}" ]; then
    args+=(--data "${DATA}")
else
    args+=(--config "${ROOT}/src/config.yaml")
fi
if [ -n "${2:-}" ]; then
    args+=(--title "$2")
fi

echo "Exporting the tables ..."
"${PY}" "${ROOT}/src/export_pgf.py" "${args[@]}"

echo "Compiling the figure ..."
cd "${ROOT}/doc/figures"
pdflatex -interaction=nonstopmode xrd_fit.tex >/dev/null
echo "doc/figures/xrd_fit.pdf written"
