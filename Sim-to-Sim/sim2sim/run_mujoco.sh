#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
STAMP="$VENV_DIR/stackforce-requirements.sha256"

step() {
  printf '[StackForce] %s\n' "$1"
}

apt_install() {
  if ! command -v apt-get >/dev/null 2>&1; then
    return 1
  fi
  if [ "$(id -u)" -eq 0 ]; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
  else
    return 1
  fi
}

find_python() {
  override_python="$(printenv STACKFORCE_MUJOCO_PYTHON 2>/dev/null || true)"
  if [ -n "$override_python" ] && [ -x "$override_python" ]; then
    printf '%s\n' "$override_python"
    return 0
  fi
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

step "Checking the local Python and MuJoCo environment..."
if ! PYTHON_BIN="$(find_python)"; then
  step "Python 3.10+ was not found. Installing Python with apt..."
  if ! apt_install python3 python3-venv python3-pip; then
    printf '%s\n' '[StackForce] Python 3.10+ is required. Install python3, python3-venv and python3-pip, then run this file again.' >&2
    exit 1
  fi
  PYTHON_BIN="$(find_python)" || { printf '%s\n' '[StackForce] Installed Python is older than 3.10.' >&2; exit 1; }
fi

if command -v apt-get >/dev/null 2>&1 && command -v dpkg-query >/dev/null 2>&1; then
  missing_packages=""
  for package in libgl1 libglfw3 libosmesa6; do
    if ! dpkg-query -W "$package" >/dev/null 2>&1; then
      missing_packages="$missing_packages $package"
    fi
  done
  if [ -n "$missing_packages" ]; then
    step "Installing Ubuntu graphics libraries required by the MuJoCo viewer..."
    # shellcheck disable=SC2086
    apt_install $missing_packages || printf '%s\n' '[StackForce] Warning: system graphics libraries could not be installed automatically.' >&2
  fi
fi

if [ ! -x "$VENV_PYTHON" ]; then
  step "Creating an isolated environment in sim2sim/.venv..."
  if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
    step "The Python venv module is missing; installing it with apt..."
    apt_install python3-venv || { printf '%s\n' '[StackForce] Could not install python3-venv.' >&2; exit 1; }
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
fi

requirement_hash="$($VENV_PYTHON -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$REQUIREMENTS")"
installed_hash=""
if [ -f "$STAMP" ]; then installed_hash="$(cat "$STAMP")"; fi

imports_ready=0
reinstall="$(printenv STACKFORCE_MUJOCO_REINSTALL 2>/dev/null || true)"
if [ "$reinstall" != "1" ] && "$VENV_PYTHON" -c 'import mujoco, numpy, onnxruntime; from PIL import Image' >/dev/null 2>&1; then
  imports_ready=1
fi

if [ "$imports_ready" != "1" ] || [ "$installed_hash" != "$requirement_hash" ]; then
  step "Installing MuJoCo and the required Python packages. The first run needs internet access..."
  "$VENV_PYTHON" -m pip install --disable-pip-version-check --upgrade pip
  "$VENV_PYTHON" -m pip install --disable-pip-version-check -r "$REQUIREMENTS"
  printf '%s' "$requirement_hash" > "$STAMP"
else
  step "The packaged MuJoCo environment is ready; reusing it."
fi

"$VENV_PYTHON" -c 'import mujoco; print("[StackForce] MuJoCo " + mujoco.__version__ + " is ready.")'
setup_only="$(printenv STACKFORCE_MUJOCO_SETUP_ONLY 2>/dev/null || true)"
if [ "$setup_only" = "1" ]; then exit 0; fi

step "Starting the exported MuJoCo project..."
exec "$VENV_PYTHON" "$SCRIPT_DIR/run_mujoco.py" --validate-policy --viewer "$@"
