#!/usr/bin/env bash
#
# CI: package the GUI of AMORPH with PyInstaller (packaging/amorph_gui.spec)
# together with the sampler of the same system, run the self-test of the
# packaged program, and pack it, with the READMEs and the licences, into
# dist/gui/AMORPH-GUI-SYSTEM.zip (.tar.gz on Linux).
#
# Usage: scripts/ci/gui_package.sh SYSTEM SAMPLER
#
# SYSTEM is windows-x64, linux-x64 or macos-arm64, and SAMPLER the AMORPH
# executable for it (in the artefacts AMORPH-windows, AMORPH-linux and
# AMORPH-macos of build.yml). The self-test runs the bundled example with
# tiny DNest4 options through the packaged program, without a screen and
# with the sampler that the program finds next to itself, and saves its
# screenshots and log to build/gui-package-test.
#
# GitHub Actions only (.github/workflows/build.yml), on a runner of each
# system, with Python set up by the workflow.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SYSTEM="${1:?usage: gui_package.sh SYSTEM SAMPLER}"
SAMPLER="${2:?usage: gui_package.sh SYSTEM SAMPLER}"
SAMPLER="$(cd "$(dirname "${SAMPLER}")" && pwd)/$(basename "${SAMPLER}")"
cd "${REPO_ROOT}"

# A path for a Windows program, which does not read those of Git Bash
native() {
    if command -v cygpath > /dev/null 2>&1; then
        cygpath -w "$1"
    else
        echo "$1"
    fi
}

case "${SYSTEM}" in
    windows-x64)
        app=build/gui-dist/AMORPH-GUI/AMORPH-GUI.exe
        program=build/gui-dist/AMORPH-GUI ;;
    linux-x64)
        app=build/gui-dist/AMORPH-GUI/AMORPH-GUI
        program=build/gui-dist/AMORPH-GUI
        . scripts/ci/common.sh
        # What Qt needs without a screen, and fonts with Cyrillic letters
        apt_install libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 \
            fonts-dejavu-core ;;
    macos-arm64)
        app=build/gui-dist/AMORPH-GUI.app/Contents/MacOS/AMORPH-GUI
        program=build/gui-dist/AMORPH-GUI.app ;;
    *)
        echo "gui_package: unknown system ${SYSTEM}" >&2
        exit 1 ;;
esac

python -m pip install -q --upgrade pip
python -m pip install -q pyinstaller PySide6-Essentials pyqtgraph numpy \
    matplotlib pandas pyyaml
python -c "import PyInstaller, PySide6; print('PyInstaller', \
PyInstaller.__version__, '- PySide6', PySide6.__version__)"

# Artefacts do not keep the permissions of their files
chmod +x "${SAMPLER}"
rm -rf build/gui-work build/gui-dist
AMORPH_BIN="$(native "${SAMPLER}")" python -m PyInstaller --noconfirm \
    --clean --workpath build/gui-work --distpath build/gui-dist \
    packaging/amorph_gui.spec
ls -l "$(dirname "${app}")"
du -sh "${program}"

# The self-test of the packaged program, with the sampler packed with it
test_dir="${REPO_ROOT}/build/gui-package-test"
rm -rf "${test_dir}"
mkdir -p "${test_dir}"
export QT_QPA_PLATFORM=offscreen
# Where a program without a console (Windows) writes its output
export AMORPH_GUI_LOG="$(native "${test_dir}/self-test.log")"
status=0
"${app}" --self-test "$(native "${test_dir}")" || status=$?
cat "${test_dir}/self-test.log" 2> /dev/null || true
if [ "${status}" -ne 0 ]; then
    echo "gui_package: the self-test of the packaged GUI failed (exit" \
         "status ${status})" >&2
    exit 1
fi
ls "${test_dir}"

# One folder, AMORPH-GUI, with the program, the READMEs and the licences
stage=build/gui-stage/AMORPH-GUI
rm -rf build/gui-stage
mkdir -p "${stage}/licenses"
if [ "${SYSTEM}" = macos-arm64 ]; then
    # ditto keeps the links and the signatures of the app
    ditto "${program}" "${stage}/AMORPH-GUI.app"
else
    cp -R "${program}/." "${stage}/"
fi
cp README.md README.ru.md LICENSE "${stage}/"
cp external/DNest4/LICENSE "${stage}/licenses/DNest4.txt"
cp external/yaml-cpp/LICENSE "${stage}/licenses/yaml-cpp.txt"
if [ -f "$(dirname "${SAMPLER}")/licenses/mingw-w64.txt" ]; then
    cp "$(dirname "${SAMPLER}")/licenses/mingw-w64.txt" "${stage}/licenses/"
fi
cat > "${stage}/licenses/README.txt" << 'EOF'
AMORPH-GUI bundles the AMORPH sampler (GNU GPL version 3, LICENSE; with
DNest4 and yaml-cpp, whose licences are here) and Python with the packages
that the program uses: Qt for Python (PySide6 and shiboken6, GNU LGPL
version 3, with Qt), pyqtgraph, NumPy, matplotlib, pandas and PyYAML. The
licences of these packages are in their *.dist-info folders inside the
program (the _internal folder, or Contents/Resources of the macOS app). Qt
is linked dynamically: its libraries are separate files of the program.
EOF

mkdir -p dist/gui
out="${REPO_ROOT}/dist/gui/AMORPH-GUI-${SYSTEM}"
rm -f "${out}".*
case "${SYSTEM}" in
    windows-x64)
        (cd build/gui-stage && python -m zipfile -c "$(native "${out}.zip")" \
             AMORPH-GUI) ;;
    linux-x64)
        tar -C build/gui-stage -czf "${out}.tar.gz" AMORPH-GUI ;;
    macos-arm64)
        (cd build/gui-stage && ditto -c -k --sequesterRsrc --keepParent \
             AMORPH-GUI "${out}.zip") ;;
esac
ls -l dist/gui
