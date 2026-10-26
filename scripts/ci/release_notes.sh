#!/usr/bin/env bash
#
# Print the notes of the release of a tag: the message of the tag, if it is
# an annotated tag whose message has more than one line, else the section of
# its version in CHANGELOG.md ("## 1.0.0" up to the next "## "). A
# pre-release (v1.1.0-rc.1) without a section of its own takes that of its
# version (1.1.0). Exits with status 1 if there are neither.
#
# Usage: scripts/ci/release_notes.sh v1.0.0
#
# Used by .github/workflows/release.yml.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

TAG="${1:?usage: release_notes.sh TAG}"
VERSION="${TAG#v}"

if [ "$(git cat-file -t "refs/tags/${TAG}" 2>/dev/null)" = tag ]; then
    body="$(git tag -l --format='%(contents:body)' "${TAG}")"
    if [ -n "${body//[[:space:]]/}" ]; then
        git tag -l --format='%(contents:subject)' "${TAG}"
        echo
        printf '%s\n' "${body}"
        exit 0
    fi
fi

# The lines between the heading of the version and the next heading, without
# the blank lines at the start ($(...) drops those at the end)
section() {
    awk -v v="$1" '
        $1 == "##" { inside = ($2 == v || $2 == "[" v "]"); next }
        inside' CHANGELOG.md | sed -e '/./,$!d'
}
notes="$(section "${VERSION}")"
if [ -z "${notes//[[:space:]]/}" ] && [ "${VERSION%%-*}" != "${VERSION}" ]; then
    notes="$(section "${VERSION%%-*}")"
fi
if [ -z "${notes//[[:space:]]/}" ]; then
    echo "release_notes: ${TAG} is not an annotated tag with a message of" \
         "more than one line, and CHANGELOG.md has no section" \
         "'## ${VERSION}'" >&2
    exit 1
fi
printf '%s\n' "${notes}"
