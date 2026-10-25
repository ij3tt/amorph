#!/usr/bin/env bash
#
# CI: build AMORPH for macOS, run the unit tests and the smoke test, and
# collect the distribution in dist/macos.
#
# GitHub Actions only (.github/workflows/build.yml): GitVerse CI has no macOS
# runners. macOS comes with bash 3.2 and BSD tools, which the scripts allow
# for.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
. "${REPO_ROOT}/scripts/ci/common.sh"
cd "${REPO_ROOT}"

setup_python "${REPO_ROOT}/build/venv"

cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build -j "$(sysctl -n hw.ncpu)"
(cd build && ctest --output-on-failure)

bash scripts/smoke_test.sh build/AMORPH build/smoke

mkdir -p dist/macos
cp build/AMORPH dist/macos/
cp src/OPTIONS src/OPTIONS_AGGRESSIVE src/config.yaml dist/macos/
cp src/showresults.py src/display.py src/dnest_functions.py \
   src/amorph_stats.py src/amorph_results.py src/amorph_archive.py \
   dist/macos/
cp src/easy_data.txt dist/macos/
ls -l dist/macos
