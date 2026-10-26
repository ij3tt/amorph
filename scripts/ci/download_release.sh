#!/usr/bin/env bash
#
# Download and verify the files of an AMORPH GitHub Release.
#
# Usage: scripts/ci/download_release.sh TAG OUT [GITHUB_REPOSITORY]
#
# The default repository is ij3tt/amorph. A newly pushed tag has no complete
# release until .github/workflows/release.yml has built it, which took about
# 16 minutes for v1.0.0: the script waits until every file can be
# downloaded, for up to DOWNLOAD_RELEASE_WAIT minutes (20 by default),
# checking every DOWNLOAD_RELEASE_PAUSE seconds (20 by default). Then it
# downloads each file once and checks the SHA-256 checksums.
#
# Used by .gitverse/workflows/release.yml, and by hand to publish a release
# on GitVerse (see "Releases" in the README).

set -euo pipefail

TAG="${1:?usage: download_release.sh TAG OUT [GITHUB_REPOSITORY]}"
OUT="${2:?usage: download_release.sh TAG OUT [GITHUB_REPOSITORY]}"
REPOSITORY="${3:-ij3tt/amorph}"
WAIT="${DOWNLOAD_RELEASE_WAIT:-20}"
PAUSE="${DOWNLOAD_RELEASE_PAUSE:-20}"
BASE="https://github.com/${REPOSITORY}/releases/download/${TAG}"

files=(
    "AMORPH-${TAG}-windows-x64.zip"
    "AMORPH-${TAG}-linux-x64.tar.gz"
    "AMORPH-${TAG}-macos-arm64.zip"
    "AMORPH-GUI-${TAG}-windows-x64.zip"
    "AMORPH-GUI-${TAG}-linux-x64.tar.gz"
    "AMORPH-GUI-${TAG}-macos-arm64.zip"
    "AMORPH-${TAG}-SHA256SUMS.txt"
)

# The first file of the release that cannot be downloaded yet, or nothing.
# Only its first byte is asked for: the packages of the GUI are large.
missing() {
    local name
    for name in "${files[@]}"; do
        if ! curl --fail --location --silent --range 0-0 \
                --output /dev/null "${BASE}/${name}"; then
            echo "${name}"
            return
        fi
    done
}

mkdir -p "${OUT}"
OUT="$(cd "${OUT}" && pwd)"

SECONDS=0
while name="$(missing)" && [ -n "${name}" ]; do
    if [ "${SECONDS}" -ge $((WAIT * 60)) ]; then
        echo "download_release: after ${WAIT} minutes the GitHub Release" \
             "${TAG} still has no ${name}. Run this again once" \
             "https://github.com/${REPOSITORY}/releases/tag/${TAG} has" \
             "all ${#files[@]} files (on GitVerse: \"Run workflow\" for" \
             "Release, on the tag ${TAG})." >&2
        exit 1
    fi
    echo "download_release: ${TAG} has no ${name} yet," \
         "waited $((SECONDS / 60)) of ${WAIT} minutes" >&2
    sleep "${PAUSE}"
done

for name in "${files[@]}"; do
    echo "download_release: ${name}" >&2
    curl --fail --location --silent --show-error --retry 3 --retry-delay 10 \
        "${BASE}/${name}" --output "${OUT}/${name}"
done

cd "${OUT}"
if command -v sha256sum > /dev/null 2>&1; then
    sha256sum -c "AMORPH-${TAG}-SHA256SUMS.txt"
else
    shasum -a 256 -c "AMORPH-${TAG}-SHA256SUMS.txt"
fi
