#!/usr/bin/env bash
#
# Smoke test for AMORPH.
#
# Runs the sampler on the bundled example dataset with a deliberately tiny
# configuration and checks that it produced the expected output files.
#
# Usage: scripts/smoke_test.sh [path/to/AMORPH] [work/dir]
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${1:-${REPO_ROOT}/build/AMORPH}"
WORK="${2:-${REPO_ROOT}/build/smoke}"

if [ ! -f "${BIN}" ]; then
    echo "smoke_test: executable not found: ${BIN}" >&2
    exit 1
fi

# Resolve to absolute paths: the script changes directory further down.
BIN="$(cd "$(dirname "${BIN}")" && pwd)/$(basename "${BIN}")"
rm -rf "${WORK}"
mkdir -p "${WORK}"
WORK="$(cd "${WORK}" && pwd)"

echo "smoke_test: binary   = ${BIN}"
echo "smoke_test: workdir  = ${WORK}"

# The sampler reads config.yaml from the current directory.
cp "${REPO_ROOT}/src/config.yaml" "${WORK}/config.yaml"
cp "${REPO_ROOT}/src/easy_data.txt" "${WORK}/easy_data.txt"

# A sampler configuration that terminates after a handful of levels.
cat > "${WORK}/OPTIONS_SMOKE" <<'EOF'
# Smoke test options for DNest4
1	# Number of particles
50	# new level interval
50	# save interval
20	# threadSteps
5	# maximum number of levels
5	# Backtracking scale length (lambda in the paper)
100	# Strength of effect to force histogram to equal push
100	# Maximum number of saves
sample.txt	# file for the posterior samples
sample_info.txt	# file for information about the samples
levels.txt	# file for information about the levels
EOF

# Point the config at the smoke-test options and keep the run small.
sed -i \
    -e 's/^num_threads: .*/num_threads: 2/' \
    -e 's/^dnest4_options_file: .*/dnest4_options_file: "OPTIONS_SMOKE"/' \
    -e 's/^    max_num_narrow_peaks: .*/    max_num_narrow_peaks: 20/' \
    -e 's/^    max_num_wide_peaks: .*/    max_num_wide_peaks: 10/' \
    "${WORK}/config.yaml"

cd "${WORK}"

echo "smoke_test: running the sampler..."
"${BIN}"

echo "smoke_test: files produced:"
ls -l

for f in sample.txt sample_info.txt levels.txt; do
    if [ ! -s "${f}" ]; then
        echo "smoke_test: FAILED - ${f} is missing or empty" >&2
        exit 1
    fi
done

# The posterior sample file is produced by the Python post-processing.
if command -v python3 >/dev/null 2>&1; then
    if python3 -c "import numpy, matplotlib, pandas, yaml" >/dev/null 2>&1; then
        echo "smoke_test: running the Python post-processing..."
        cp "${REPO_ROOT}/src/showresults.py" "${REPO_ROOT}/src/display.py" \
           "${REPO_ROOT}/src/dnest_functions.py" \
           "${REPO_ROOT}/src/amorph_stats.py" "${WORK}/"
        ( cd "${WORK}" && MPLBACKEND=Agg python3 showresults.py > postprocess.log 2>&1 ) \
            || { echo "smoke_test: FAILED - post-processing crashed" >&2; \
                 tail -n 40 "${WORK}/postprocess.log" >&2; exit 1; }
        if [ ! -s "${WORK}/posterior_sample.txt" ]; then
            echo "smoke_test: FAILED - posterior_sample.txt is missing or empty" >&2
            exit 1
        fi
        echo "smoke_test: posterior_sample.txt OK"
    else
        echo "smoke_test: Python post-processing skipped (missing numpy/matplotlib/pandas/yaml)"
    fi
fi

echo "smoke_test: PASSED"
