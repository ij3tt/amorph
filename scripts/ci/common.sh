# Helpers shared by the CI scripts. Source this file, don't run it.
#
# The scripts run both on GitHub Actions (a VM with passwordless sudo) and on
# GitVerse CI (a Docker container that may run as root without sudo), so they
# install what they need themselves.

# Run a command as root.
as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

# Install Debian packages.
apt_install() {
    as_root apt-get update -q
    as_root env DEBIAN_FRONTEND=noninteractive \
        apt-get install -y -q --no-install-recommends "$@"
}

# Install the packages that provide missing commands.
# Usage: require command:package [command:package ...]
require() {
    local spec missing=()
    for spec in "$@"; do
        command -v "${spec%%:*}" >/dev/null 2>&1 || missing+=("${spec#*:}")
    done
    if [ ${#missing[@]} -gt 0 ]; then
        apt_install "${missing[@]}"
    fi
}

# Create a Python virtual environment with the packages the post-processing
# scripts need, and put it first on the PATH.
# Usage: setup_python path/to/venv
setup_python() {
    local venv="$1"
    require python3:python3
    if ! python3 -m venv "${venv}" >/dev/null 2>&1; then
        # Debian/Ubuntu ship the venv module separately
        apt_install python3-venv
        rm -rf "${venv}"
        python3 -m venv "${venv}"
    fi
    "${venv}/bin/python" -m pip install -q --upgrade pip
    "${venv}/bin/python" -m pip install -q numpy matplotlib pandas pyyaml
    export PATH="${venv}/bin:${PATH}"
}
