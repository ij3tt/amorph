#!/usr/bin/env bash
#
# CI: cross-compile AMORPH.exe with mingw-w64, check that it needs no MinGW
# DLLs, and collect the distribution in dist/windows.
#
# Shared by GitHub Actions (.github/workflows/build.yml) and GitVerse CI
# (.gitverse/workflows/build.yml).
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
. "${REPO_ROOT}/scripts/ci/common.sh"
cd "${REPO_ROOT}"

require cmake:cmake make:make file:file \
    x86_64-w64-mingw32-g++:g++-mingw-w64-x86-64 \
    x86_64-w64-mingw32-objdump:binutils-mingw-w64-x86-64

# Prefer the POSIX thread model: older mingw-w64 releases have no std::thread
# in the win32 one.
CXX=x86_64-w64-mingw32-g++
if command -v x86_64-w64-mingw32-g++-posix >/dev/null 2>&1; then
    CXX=x86_64-w64-mingw32-g++-posix
fi
"${CXX}" --version | head -n 1

cmake -B build-win -S . -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_SYSTEM_NAME=Windows \
    -DCMAKE_CXX_COMPILER="${CXX}" \
    -DCMAKE_RC_COMPILER=x86_64-w64-mingw32-windres
cmake --build build-win -j "$(nproc)"

file build-win/AMORPH.exe

# Users get the bare executable, so it must not need MinGW runtime DLLs.
dlls="$(x86_64-w64-mingw32-objdump -p build-win/AMORPH.exe \
        | awk '/DLL Name/ {print $3}')"
echo "DLLs imported by AMORPH.exe:"
echo "${dlls}"
if echo "${dlls}" | grep -qiE 'libwinpthread|libstdc\+\+|libgcc'; then
    echo "AMORPH.exe depends on MinGW runtime DLLs: static linking failed" >&2
    exit 1
fi

mkdir -p dist/windows
cp build-win/AMORPH.exe dist/windows/
cp src/OPTIONS src/OPTIONS_AGGRESSIVE src/config.yaml dist/windows/
cp src/showresults.py src/display.py src/dnest_functions.py \
   src/amorph_stats.py dist/windows/
cp src/easy_data.txt dist/windows/
ls -l dist/windows
