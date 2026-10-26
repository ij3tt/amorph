#!/usr/bin/env bash
#
# Make the GitVerse Release of a tag, if it has none, and upload the files of
# a folder to it.
#
# Usage: scripts/ci/gitverse_release.sh TAG DIR NOTES [GITVERSE_REPOSITORY]
#
# NOTES is a file with the notes of a new release; the title is "AMORPH
# <version>". The default repository is ijjjjke/amorph, and the API key,
# with Repositories → Write, comes from RELEASE_API_KEY.
#
# The release action of GitVerse gave up on the GUI package for Windows
# (64 MB) after about 10 seconds ("context deadline exceeded") and left the
# release of v1.0.2 with one file of six. This script uses the API
# (https://gitverse.ru/docs/developers/public-api) with curl, allowing
# GITVERSE_UPLOAD_TIMEOUT seconds per file (600 by default) and retrying. A
# file that the release has already, with the same size, is skipped, and
# one of another size is replaced: a second run completes what a first one
# left half done.
#
# Used by .gitverse/workflows/release.yml.

set -euo pipefail

usage="usage: gitverse_release.sh TAG DIR NOTES [GITVERSE_REPOSITORY]"
TAG="${1:?${usage}}"
DIR="${2:?${usage}}"
NOTES="${3:?${usage}}"
REPOSITORY="${4:-ijjjjke/amorph}"
API="${GITVERSE_API_URL:-https://api.gitverse.ru}"
TIMEOUT="${GITVERSE_UPLOAD_TIMEOUT:-600}"
: "${RELEASE_API_KEY:?gitverse_release: set RELEASE_API_KEY to a GitVerse API key}"

# curl a path of the API: the body goes to the file OUT, the HTTP status to
# the output. Time-outs and 5xx are retried.
request() {
    local method="$1" path="$2" out="$3"
    shift 3
    curl --silent --show-error --request "${method}" \
        --header "Authorization: Bearer ${RELEASE_API_KEY}" \
        --header "Accept: application/vnd.gitverse.object+json;version=1" \
        --retry 3 --retry-delay 15 \
        --output "${out}" --write-out '%{http_code}' \
        "$@" "${API}${path}"
}

# The same, printing the body; fails with the status and the start of the
# body unless the status is 2xx
api() {
    local method="$1" path="$2"
    shift 2
    local body status
    body="$(mktemp)"
    status="$(request "${method}" "${path}" "${body}" "$@")" || status=000
    if [ "${status}" -lt 200 ] || [ "${status}" -ge 300 ]; then
        echo "gitverse_release: ${method} ${path}: HTTP ${status}:" \
             "$(head -c 500 "${body}")" >&2
        rm -f "${body}"
        return 1
    fi
    cat "${body}"
    rm -f "${body}"
}

json() {
    python3 -c "import json, sys; d = json.load(sys.stdin); $1"
}

# The release of the tag, or a new one
found="$(mktemp)"
status="$(request GET "/repos/${REPOSITORY}/releases/tags/${TAG}" "${found}")" \
    || status=000
if [ "${status}" = 404 ]; then
    payload="$(mktemp)"
    TAG="${TAG}" NOTES="${NOTES}" python3 -c '
import json, os
with open(os.environ["NOTES"], encoding="utf-8") as f:
    notes = f.read()
tag = os.environ["TAG"]
print(json.dumps({"tag_name": tag, "name": "AMORPH " + tag[1:],
                  "body": notes, "draft": False, "prerelease": False}))
' > "${payload}"
    release_id="$(api POST "/repos/${REPOSITORY}/releases" \
                  --header "Content-Type: application/json" \
                  --data-binary "@${payload}" | json 'print(d["id"])')"
    rm -f "${payload}"
    echo "gitverse_release: made the release ${TAG} (id ${release_id})"
elif [ "${status}" -ge 200 ] && [ "${status}" -lt 300 ]; then
    release_id="$(json 'print(d["id"])' < "${found}")"
    echo "gitverse_release: the release ${TAG} is there (id ${release_id})"
else
    echo "gitverse_release: GET the release ${TAG}: HTTP ${status}:" \
         "$(head -c 500 "${found}")" >&2
    exit 1
fi
rm -f "${found}"

# "id size name" of each file of the release
attachments() {
    api GET "/repos/${REPOSITORY}/releases/${release_id}/assets" \
        | json 'd = d if isinstance(d, list) else d.get("data") or []
for a in d: print(a["id"], a["size"], a["name"])'
}

failed=0
for f in "${DIR}"/*; do
    [ -f "${f}" ] || continue
    name="$(basename "${f}")"
    size="$(stat -c %s "${f}")"
    existing="$(attachments | awk -v n="${name}" '$3 == n')"
    if [ -n "${existing}" ]; then
        if [ "$(echo "${existing}" | awk 'NR == 1 {print $2}')" = "${size}" ]
        then
            echo "gitverse_release: ${name} is there already"
            continue
        fi
        echo "gitverse_release: ${name} is there with another size:" \
             "replacing it"
        for id in $(echo "${existing}" | awk '{print $1}'); do
            api DELETE "/repos/${REPOSITORY}/releases/${release_id}/assets/${id}" \
                > /dev/null
        done
    fi
    echo "gitverse_release: uploading ${name}, $((size / 1000000)) MB"
    SECONDS=0
    if api POST "/repos/${REPOSITORY}/releases/${release_id}/assets?name=${name}" \
            --max-time "${TIMEOUT}" --form "attachment=@${f};filename=${name}" \
            > /dev/null; then
        echo "gitverse_release: ${name} uploaded in ${SECONDS} s"
    else
        failed=1
    fi
done

if [ "${failed}" -ne 0 ]; then
    echo "gitverse_release: some files were not uploaded; run this again" \
         "(\"Run workflow\" for Release on GitVerse) for the rest" >&2
    exit 1
fi
echo "gitverse_release: the release ${TAG} has every file of ${DIR}"
