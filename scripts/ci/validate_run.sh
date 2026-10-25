#!/usr/bin/env bash
#
# CI: build the AMORPH sources in SRC_DIR, run them on one of the bundled
# datasets, summarise the posterior in OUT_DIR/summary.json and archive the
# run in OUT_DIR/run.amorph (src/amorph_archive.py).
# Used by .github/workflows/validate.yml.
#
# Usage: scripts/ci/validate_run.sh SRC_DIR DATA_FILE SAVES MINUTES OUT_DIR \
#            [KEY=VALUE ...]
#
# DATA_FILE is the name of a dataset in SRC_DIR/src. The sampler stops after
# SAVES saved samples or after MINUTES minutes, whichever comes first; what
# it saved by then is post-processed. The post-processing always uses the
# scripts next to this file, so that two versions of the sampler are
# compared with the same post-processing.
#
# Each KEY=VALUE sets a setting of config.yaml, such as
# max_num_narrow_peaks=100 or seed=7; a commented-out setting (# seed: 42)
# is switched on.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
. "${REPO_ROOT}/scripts/ci/common.sh"

SRC="$(cd "$1" && pwd)"
DATA="$2"
SAVES="$3"
MINUTES="$4"
mkdir -p "$5"
OUT="$(cd "$5" && pwd)"
shift 5

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

for setting in "$@"; do
    key="${setting%%=*}"
    value="${setting#*=}"
    pattern="^\([[:space:]]*\)\(# \)\?${key}:"
    if ! grep -q "${pattern}" "${WORK}/config.yaml"; then
        echo "validate: config.yaml has no setting '${key}'" >&2
        exit 1
    fi
    sed -i -e "s|${pattern}.*|\1${key}: ${value}|" "${WORK}/config.yaml"
done
if [ $# -gt 0 ]; then
    echo "validate: config.yaml after the settings $*:"
    grep -v '^[[:space:]]*#' "${WORK}/config.yaml" | grep -v '^[[:space:]]*$'
fi

cd "${WORK}"
echo "validate: running AMORPH on ${DATA}: at most ${SAVES} saves or" \
     "${MINUTES} minutes, $(nproc) threads"

# Number of data lines in a DNest4 output file
count_lines() {
    if [ -f "$1" ]; then
        grep -vc '^#' "$1" || true
    else
        echo 0
    fi
}

progress() {
    echo "validate: $(( ($(date +%s) - start) / 60 )) min," \
         "$(count_lines sample_info.txt) saves," \
         "$(count_lines levels.txt) levels"
}

start=$(date +%s)
"${SRC}/build/AMORPH" > run.log &
pid=$!

# Report the progress every 10 minutes (the first time after one), and stop
# the sampler when the time budget is used up.
stopped=""
next_report=60
while kill -0 "${pid}" 2>/dev/null; do
    sleep 15
    elapsed=$(( $(date +%s) - start ))
    if [ "${elapsed}" -ge "${next_report}" ]; then
        progress
        next_report=$(( next_report + 600 ))
    fi
    if [ "${elapsed}" -ge $(( MINUTES * 60 )) ] \
            && kill -0 "${pid}" 2>/dev/null; then
        echo "validate: the time budget of ${MINUTES} minutes is used up," \
             "stopping the sampler"
        kill "${pid}" 2>/dev/null || true
        stopped="--stopped"
        break
    fi
done

code=0
wait "${pid}" || code=$?
seconds=$(( $(date +%s) - start ))
progress
tail -n 3 run.log
cp run.log "${OUT}/"
if [ -z "${stopped}" ] && [ "${code}" -ne 0 ]; then
    echo "validate: AMORPH failed with exit code ${code}" >&2
    exit 1
fi

echo "validate: post-processing"
MPLBACKEND=Agg python3 "${REPO_ROOT}/scripts/ci/summarize_run.py" \
    --data "${DATA}" --seconds "${seconds}" ${stopped} \
    --out "${OUT}/summary.json" --archive "${OUT}/run.amorph"
cat "${OUT}/summary.json"
