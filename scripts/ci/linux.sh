#!/usr/bin/env bash
#
# CI: build AMORPH for Linux, run the unit tests and the smoke test, and
# collect the distribution in dist/linux.
#
# Shared by GitHub Actions (.github/workflows/build.yml) and GitVerse CI
# (.gitverse/workflows/build.yml).
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
. "${REPO_ROOT}/scripts/ci/common.sh"
cd "${REPO_ROOT}"

require cmake:cmake g++:g++ make:make
setup_python "${REPO_ROOT}/build/venv"

cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build -j "$(nproc)"

# Unit tests, once the build defines any
if [ -f build/CTestTestfile.cmake ]; then
    (cd build && ctest --output-on-failure)
fi

bash scripts/smoke_test.sh build/AMORPH build/smoke

# Tests of the Python post-processing
MPLBACKEND=Agg python3 -m pytest -q tests

mkdir -p dist/linux
cp build/AMORPH dist/linux/
cp src/OPTIONS src/OPTIONS_AGGRESSIVE src/config.yaml dist/linux/
cp src/showresults.py src/display.py src/dnest_functions.py \
   src/amorph_stats.py dist/linux/
cp src/easy_data.txt dist/linux/
ls -l dist/linux
