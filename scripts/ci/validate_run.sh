#!/usr/bin/env bash
#
# CI: build the AMORPH sources in SRC_DIR, run them on one of the bundled
# datasets and summarise the posterior in OUT_DIR/summary.json.
# Used by .github/workflows/validate.yml.
#
# Usage: scripts/ci/validate_run.sh SRC_DIR DATA_FILE SAVES OUT_DIR
#
# DATA_FILE is the name of a dataset in SRC_DIR/src. The post-processing
# always uses the scripts next to this file, so that two versions of the
# sampler are compared with the same post-processing.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
. "${REPO_ROOT}/scripts/ci/common.sh"

SRC="$(cd "$1" && pwd)"
DATA="$2"
SAVES="$3"
mkdir -p "$4"
OUT="$(cd "$4" && pwd)"

require cmake:cmake g++:g++ make:make
setup_python "${REPO_ROOT}/build/venv"

cmake -B "${SRC}/build" -S "${SRC}" -DCMAKE_BUILD_TYPE=Release
cmake --build "${SRC}/build" -j "$(nproc)"

WORK="${SRC}/build/run"
rm -rf "${WORK}"
mkdir -p "${WORK}"
cp "${SRC}/src/config.yaml" "${SRC}/src/OPTIONS_AGGRESSIVE" "${WORK}/"
cp "${SRC}/src/${DATA}" "${WORK}/"

# Use all the cores of the runner and stop after SAVES saved samples.
sed -i \
    -e "s|^num_threads: .*|num_threads: $(nproc)|" \
    -e "s|^data_file: .*|data_file: \"${DATA}\"|" \
    -e 's|^dnest4_options_file: .*|dnest4_options_file: "OPTIONS_AGGRESSIVE"|' \
    "${WORK}/config.yaml"
sed -i -e "s|^[0-9]*\([[:space:]]*# Maximum number of saves\)|${SAVES}\1|" \
    "${WORK}/OPTIONS_AGGRESSIVE"

cd "${WORK}"
echo "validate: running AMORPH on ${DATA} (${SAVES} saves, $(nproc) threads)"
start=$(date +%s)
"${SRC}/build/AMORPH" > run.log
seconds=$(( $(date +%s) - start ))
tail -n 3 run.log
cp run.log "${OUT}/"

echo "validate: post-processing"
MPLBACKEND=Agg python3 "${REPO_ROOT}/scripts/ci/summarize_run.py" \
    --data "${DATA}" --seconds "${seconds}" --out "${OUT}/summary.json"
cat "${OUT}/summary.json"
