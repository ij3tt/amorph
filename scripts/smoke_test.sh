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

# Point the config at the example data and the smoke-test options, whatever
# src/config.yaml names, and keep the run small. (Not sed -i, which differs
# between GNU and BSD sed, on macOS.)
sed -e 's/^data_file: .*/data_file: "easy_data.txt"/' \
    -e 's/^num_threads: .*/num_threads: 2/' \
    -e 's/^dnest4_options_file: .*/dnest4_options_file: "OPTIONS_SMOKE"/' \
    -e 's/^    max_num_narrow_peaks: .*/    max_num_narrow_peaks: 20/' \
    -e 's/^    max_num_wide_peaks: .*/    max_num_wide_peaks: 10/' \
    "${REPO_ROOT}/src/config.yaml" > "${WORK}/config.yaml"

# A config.yaml that names a missing data file must stop AMORPH at once with
# exit status 1 and an error message on stderr. On Windows this also checks
# that AMORPH.exe does not wait for Enter when it shares the console with a
# shell: the time limit turns a hang into a failure.
BAD="${WORK}/missing_data"
mkdir -p "${BAD}"
cp "${WORK}/OPTIONS_SMOKE" "${BAD}/"
sed -e 's/^data_file: .*/data_file: "no_such_file.txt"/' \
    "${WORK}/config.yaml" > "${BAD}/config.yaml"

# GNU timeout, where there is one (Git Bash on Windows has it too)
with_time_limit() {
    if timeout --version >/dev/null 2>&1; then
        timeout "$@"
    else
        shift
        "$@"
    fi
}

echo "smoke_test: running with a missing data file..."
LIMIT=60
status=0
( cd "${BAD}" && with_time_limit "${LIMIT}" "${BIN}" \
      > stdout.txt 2> stderr.txt ) || status=$?
cat "${BAD}/stderr.txt"
if [ "${status}" -eq 124 ]; then
    echo "smoke_test: FAILED - AMORPH did not exit within ${LIMIT} s" \
         "(waiting for Enter?)" >&2
    exit 1
fi
if [ "${status}" -ne 1 ]; then
    echo "smoke_test: FAILED - exit status ${status} with a missing data" \
         "file, expected 1" >&2
    exit 1
fi
if ! grep -q "AMORPH: error: .*no_such_file\.txt" "${BAD}/stderr.txt"; then
    echo "smoke_test: FAILED - no error message about the missing data" \
         "file on stderr" >&2
    exit 1
fi
echo "smoke_test: missing data file rejected OK"

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
           "${REPO_ROOT}/src/amorph_stats.py" \
           "${REPO_ROOT}/src/amorph_results.py" \
           "${REPO_ROOT}/src/amorph_archive.py" "${WORK}/"
        ( cd "${WORK}" && MPLBACKEND=Agg python3 showresults.py > postprocess.log 2>&1 ) \
            || { echo "smoke_test: FAILED - post-processing crashed" >&2; \
                 tail -n 40 "${WORK}/postprocess.log" >&2; exit 1; }
        if [ ! -s "${WORK}/posterior_sample.txt" ]; then
            echo "smoke_test: FAILED - posterior_sample.txt is missing or empty" >&2
            exit 1
        fi
        echo "smoke_test: posterior_sample.txt OK"
        if ! ls "${WORK}"/easy_data_*.amorph >/dev/null 2>&1; then
            echo "smoke_test: FAILED - no run archive (.amorph)" >&2
            exit 1
        fi
        echo "smoke_test: run archive OK"
    else
        echo "smoke_test: Python post-processing skipped (missing numpy/matplotlib/pandas/yaml)"
    fi
fi

echo "smoke_test: PASSED"
