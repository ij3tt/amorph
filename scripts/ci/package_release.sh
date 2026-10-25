#!/usr/bin/env bash
#
# Pack the three command-line distributions of a release, add the three
# packages of the GUI, and write their SHA-256 checksums.
#
# Usage: scripts/ci/package_release.sh TAG DIST OUT
#
# DIST holds the artefacts of .github/workflows/build.yml, AMORPH-windows,
# AMORPH-linux and AMORPH-macos, and AMORPH-GUI-windows-x64,
# AMORPH-GUI-linux-x64 and AMORPH-GUI-macos-arm64, as download-artifact puts
# them. OUT gets
#
#   AMORPH-TAG-windows-x64.zip
#   AMORPH-TAG-linux-x64.tar.gz
#   AMORPH-TAG-macos-arm64.zip
#   AMORPH-GUI-TAG-windows-x64.zip
#   AMORPH-GUI-TAG-linux-x64.tar.gz
#   AMORPH-GUI-TAG-macos-arm64.zip
#   AMORPH-TAG-SHA256SUMS.txt
#
# Each command-line archive holds one folder, AMORPH-TAG-SYSTEM, with the
# executable, the Python post-processing scripts, config.yaml, the OPTIONS
# files, easy_data.txt, the READMEs, the licence of AMORPH and, in
# licenses/, those of the libraries linked into the executable. The GUI
# archives are those of scripts/ci/gui_package.sh, renamed after the tag.
#
# Used by .github/workflows/release.yml.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

TAG="${1:?usage: package_release.sh TAG DIST OUT}"
DIST="$(cd "${2:?usage: package_release.sh TAG DIST OUT}" && pwd)"
OUT="${3:?usage: package_release.sh TAG DIST OUT}"
mkdir -p "${OUT}"
OUT="$(cd "${OUT}" && pwd)"
STAGE="${OUT}/stage"
rm -rf "${STAGE}"

# What every distribution must hold, besides the executable
FILES="showresults.py display.py dnest_functions.py amorph_stats.py
       amorph_results.py amorph_archive.py config.yaml OPTIONS
       OPTIONS_AGGRESSIVE easy_data.txt"

# Usage: pack ARTEFACT EXECUTABLE SYSTEM FORMAT PATTERN [LICENCE ...]
# PATTERN is what file(1) must say about the executable; each LICENCE is a
# file that the artefact must hold besides FILES.
pack() {
    local artefact="$1" exe="$2" system="$3" format="$4" pattern="$5"
    shift 5
    local name="AMORPH-${TAG}-${system}"
    local from="${DIST}/${artefact}" to="${STAGE}/${name}" f

    echo "== ${name}"
    for f in "${exe}" ${FILES} "$@"; do
        if [ ! -f "${from}/${f}" ]; then
            echo "package_release: ${artefact} has no ${f}" >&2
            exit 1
        fi
    done
    file "${from}/${exe}"
    if ! file -b "${from}/${exe}" | grep -qE "${pattern}"; then
        echo "package_release: ${artefact}/${exe} is not a ${system}" \
             "executable" >&2
        exit 1
    fi

    mkdir -p "${to}/licenses"
    cp -R "${from}/." "${to}/"
    cp "${REPO_ROOT}/README.md" "${REPO_ROOT}/README.ru.md" \
       "${REPO_ROOT}/LICENSE" "${to}/"
    cp "${REPO_ROOT}/external/DNest4/LICENSE" "${to}/licenses/DNest4.txt"
    cp "${REPO_ROOT}/external/yaml-cpp/LICENSE" "${to}/licenses/yaml-cpp.txt"
    # Artefacts do not keep the permissions of their files
    find "${to}" -type d -exec chmod 755 {} +
    find "${to}" -type f -exec chmod 644 {} +
    chmod 755 "${to}/${exe}"

    rm -f "${OUT}/${name}.${format}"
    case "${format}" in
        zip)    (cd "${STAGE}" && zip -q -r -X "${OUT}/${name}.zip" "${name}") ;;
        tar.gz) tar -C "${STAGE}" -czf "${OUT}/${name}.tar.gz" \
                    --owner=0 --group=0 --numeric-owner "${name}" ;;
    esac
    ls -l "${OUT}/${name}.${format}"
}

pack AMORPH-windows AMORPH.exe windows-x64 zip 'PE32\+ executable.*x86-64' \
    licenses/mingw-w64.txt
pack AMORPH-linux AMORPH linux-x64 tar.gz 'ELF 64-bit LSB.*x86-64'
pack AMORPH-macos AMORPH macos-arm64 zip 'Mach-O 64-bit.*arm64'

# The newest glibc and libstdc++ symbol versions that the Linux executable
# needs: it runs on systems with these or newer
echo "== AMORPH-${TAG}-linux-x64 needs:"
objdump -T "${STAGE}/AMORPH-${TAG}-linux-x64/AMORPH" \
    | grep -oE '(GLIBC|GLIBCXX)_[0-9.]+' | sort -u -V \
    | awk -F_ '{newest[$1] = $0} END {for (k in newest) print newest[k]}'

rm -rf "${STAGE}"

# The packages of the GUI, built and tested by gui_package.sh
for package in windows-x64.zip linux-x64.tar.gz macos-arm64.zip; do
    from="${DIST}/AMORPH-GUI-${package%%.*}/AMORPH-GUI-${package}"
    if [ ! -f "${from}" ]; then
        echo "package_release: no ${from}" >&2
        exit 1
    fi
    cp "${from}" "${OUT}/AMORPH-GUI-${TAG}-${package}"
    ls -l "${OUT}/AMORPH-GUI-${TAG}-${package}"
done

(cd "${OUT}" && sha256sum "AMORPH-${TAG}-"*.zip "AMORPH-${TAG}-"*.tar.gz \
     "AMORPH-GUI-${TAG}-"*.zip "AMORPH-GUI-${TAG}-"*.tar.gz \
     > "AMORPH-${TAG}-SHA256SUMS.txt" && cat "AMORPH-${TAG}-SHA256SUMS.txt")
