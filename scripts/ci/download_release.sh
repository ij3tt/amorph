#!/usr/bin/env bash
#
# Download and verify the files of an AMORPH GitHub Release.
#
# Usage: scripts/ci/download_release.sh TAG OUT [GITHUB_REPOSITORY]
#
# The default repository is ij3tt/amorph. DOWNLOAD_RELEASE_ATTEMPTS and
# DOWNLOAD_RELEASE_PAUSE override the number of attempts and the pause in
# seconds between them while a newly tagged release is still being built.

set -euo pipefail

TAG="${1:?usage: download_release.sh TAG OUT [GITHUB_REPOSITORY]}"
OUT="${2:?usage: download_release.sh TAG OUT [GITHUB_REPOSITORY]}"
REPOSITORY="${3:-ij3tt/amorph}"
ATTEMPTS="${DOWNLOAD_RELEASE_ATTEMPTS:-45}"
PAUSE="${DOWNLOAD_RELEASE_PAUSE:-20}"

files=(
    "AMORPH-${TAG}-windows-x64.zip"
    "AMORPH-${TAG}-linux-x64.tar.gz"
    "AMORPH-${TAG}-macos-arm64.zip"
    "AMORPH-GUI-${TAG}-windows-x64.zip"
    "AMORPH-GUI-${TAG}-linux-x64.tar.gz"
    "AMORPH-GUI-${TAG}-macos-arm64.zip"
    "AMORPH-${TAG}-SHA256SUMS.txt"
)

mkdir -p "${OUT}"
OUT="$(cd "${OUT}" && pwd)"

for ((attempt = 1; attempt <= ATTEMPTS; attempt++)); do
    complete=1
    for name in "${files[@]}"; do
        url="https://github.com/${REPOSITORY}/releases/download/${TAG}/${name}"
        rm -f "${OUT}/${name}"
        if ! curl --fail --location --silent --show-error --retry 3 \
                "${url}" --output "${OUT}/${name}"; then
            complete=0
            break
        fi
    done

    if [ "${complete}" -eq 1 ]; then
        cd "${OUT}"
        if command -v sha256sum > /dev/null 2>&1; then
            sha256sum -c "AMORPH-${TAG}-SHA256SUMS.txt"
        else
            shasum -a 256 -c "AMORPH-${TAG}-SHA256SUMS.txt"
        fi
        exit 0
    fi

    if [ "${attempt}" -lt "${ATTEMPTS}" ]; then
        echo "download_release: ${TAG} is not ready, attempt ${attempt}/${ATTEMPTS}" >&2
        sleep "${PAUSE}"
    fi
done

echo "download_release: could not download the complete release ${TAG}" >&2
exit 1
