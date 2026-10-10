#!/bin/sh
# Usage: sh scripts/install.sh [package-source]
# Installs this checkout by default; accepts a wheel, directory, or Git URL.
set -eu

if [ "$#" -gt 1 ]; then
    echo "Usage: sh scripts/install.sh [package-source]" >&2
    exit 2
fi
if ! command -v git >/dev/null 2>&1; then
    echo "Git is required. Install Git and run this installer again." >&2
    exit 1
fi

source_path=${1:-git+https://github.com/Kingsmai/lazy-commit.git}
if [ "$#" -eq 0 ] && [ -f "$0" ]; then
    checkout=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
    if [ -f "$checkout/pyproject.toml" ]; then
        source_path=$checkout
    fi
fi
uv_bin=$(command -v uv || true)
if [ -z "$uv_bin" ]; then
    uv_dir=${UV_INSTALL_DIR:-"$HOME/.local/bin"}
    if [ -x "$uv_dir/uv" ]; then
        uv_bin="$uv_dir/uv"
    else
        bootstrap=$(mktemp)
        trap 'rm -f "$bootstrap"' EXIT HUP INT TERM
        if command -v curl >/dev/null 2>&1; then
            curl -LsSf https://astral.sh/uv/install.sh -o "$bootstrap"
        elif command -v wget >/dev/null 2>&1; then
            wget -q https://astral.sh/uv/install.sh -O "$bootstrap"
        else
            echo "Install curl or wget, or install uv from https://docs.astral.sh/uv/." >&2
            exit 1
        fi
        UV_INSTALL_DIR="$uv_dir" sh "$bootstrap"
        uv_bin="$uv_dir/uv"
    fi
fi

"$uv_bin" tool install --python 3.13 --upgrade --reinstall-package lazy-commit "$source_path"
"$uv_bin" tool update-shell
bin_dir=$("$uv_bin" tool dir --bin)
"$bin_dir/lazy-commit" --version
echo "Installed. Open a new terminal and run: lazy-commit --help"
