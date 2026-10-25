#!/usr/bin/env bash
#
# CI: the graphical interface (src/amorph_gui). Build AMORPH for Linux, run
# the tests of the GUI without a screen, and run its self-test, which runs
# the bundled example through the GUI and saves a screenshot of every
# screen to build/gui-self-test.
#
# GitHub Actions only (.github/workflows/build.yml).
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
. "${REPO_ROOT}/scripts/ci/common.sh"
cd "${REPO_ROOT}"

require cmake:cmake g++:g++ make:make
# What Qt needs without a screen, and fonts with Cyrillic letters
apt_install libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 \
    fonts-dejavu-core
setup_python "${REPO_ROOT}/build/venv"
python3 -m pip install -q PySide6-Essentials pyqtgraph pytest-qt
python3 -c "import PySide6, pyqtgraph; print('PySide6', PySide6.__version__, '- pyqtgraph', pyqtgraph.__version__)"

cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build -j "$(nproc)" --target AMORPH

export QT_QPA_PLATFORM=offscreen
MPLBACKEND=Agg python3 -m pytest -q tests/gui

rm -rf build/gui-self-test
(cd src && python3 -m amorph_gui --self-test ../build/gui-self-test \
     --amorph ../build/AMORPH)
ls -l build/gui-self-test
