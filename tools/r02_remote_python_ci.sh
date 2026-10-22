#!/usr/bin/env bash
# Run the portable, non-Xcode gate on a Linux/macOS SSH host.
# It never prepares private R02 resources and intentionally cannot replace a
# macOS/Xcode runtime test or a physical-device smoke.
set -euo pipefail

repo_dir="${1:-$PWD}"
python_bin="${PYTHON_BIN:-python3}"
venv_dir="${REMOTE_CI_VENV_DIR:-$repo_dir/.venv-remote-python-ci}"

if [[ ! -f "$repo_dir/Makefile" || ! -f "$repo_dir/requirements-dev.txt" ]]; then
  echo "ERROR: first argument must be the repository root" >&2
  exit 2
fi
if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "ERROR: Python executable not found: $python_bin" >&2
  exit 2
fi

"$python_bin" -m venv "$venv_dir"
"$venv_dir/bin/python" -m pip install --disable-pip-version-check --quiet -r "$repo_dir/requirements-dev.txt"
export PATH="$venv_dir/bin:$PATH"

make -C "$repo_dir" PYTHON="$venv_dir/bin/python" quality py-compile r02-audit-privacy verify-synthetic
