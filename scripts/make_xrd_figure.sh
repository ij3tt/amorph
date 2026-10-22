#!/bin/bash
# Draw the "fit" figure with TikZ/PGFPlots from the results of an AMORPH run.
#
#     bash scripts/make_xrd_figure.sh [data file] [title]
#
# The posterior samples (src/posterior_sample.txt) have to exist; run
# "python showresults.py" in the src folder first.

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${1:-easy_data.txt}"
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

echo "Exporting the tables ..."
if [ -n "$2" ]; then
    "${PY}" "${ROOT}/src/export_pgf.py" --data "${DATA}" \
        --posterior "${ROOT}/src/posterior_sample.txt" --out "${OUT}" \
        --title "$2"
else
    "${PY}" "${ROOT}/src/export_pgf.py" --data "${DATA}" \
        --posterior "${ROOT}/src/posterior_sample.txt" --out "${OUT}"
fi

echo "Compiling the figure ..."
cd "${ROOT}/doc/figures"
pdflatex -interaction=nonstopmode xrd_fit.tex >/dev/null
echo "doc/figures/xrd_fit.pdf written"
