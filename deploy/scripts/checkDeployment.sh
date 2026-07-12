#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_APP_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

APP_ROOT="${THEPHAGE_APP_ROOT:-${DEFAULT_APP_ROOT}}"
CONFIG_PATH="${THEPHAGE_CONFIG:-/etc/thephage/thephage.toml}"
VENV_ROOT="${THEPHAGE_VENV:-/opt/thephage/venv}"
PYTHON="${VENV_ROOT}/bin/python"
PIP="${VENV_ROOT}/bin/pip"
MANAGE="${APP_ROOT}/manage.py"

usage() {
  cat <<EOF
Usage: $0

Read-only deployment health check for The Phage.

Optional environment overrides:
  THEPHAGE_APP_ROOT   App checkout path. Defaults to this script's repo root.
  THEPHAGE_CONFIG     TOML config path. Defaults to /etc/thephage/thephage.toml.
  THEPHAGE_VENV       Virtualenv path. Defaults to /opt/thephage/venv.
EOF
}

for arg in "$@"; do
  case "${arg}" in
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      usage >&2
      exit 1
      ;;
  esac
done

require_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    echo "Missing file: ${path}" >&2
    exit 1
  fi
}

require_executable() {
  local path="$1"
  if [[ ! -x "${path}" ]]; then
    echo "Missing executable: ${path}" >&2
    exit 1
  fi
}

run_step() {
  local label="$1"
  shift
  echo
  echo "==> ${label}"
  "$@"
}

export THEPHAGE_CONFIG="${CONFIG_PATH}"

require_file "${CONFIG_PATH}"
require_file "${MANAGE}"
require_executable "${PYTHON}"
require_executable "${PIP}"

cd "${APP_ROOT}"

echo "The Phage deployment check"
echo "App root: ${APP_ROOT}"
echo "Config:   ${CONFIG_PATH}"
echo "Python:   ${PYTHON}"

run_step "Python package dependency check" "${PIP}" check
run_step "Deployment config check" "${PYTHON}" "${MANAGE}" check_config
run_step "Django system check" "${PYTHON}" "${MANAGE}" check
run_step "Unapplied migration check" "${PYTHON}" "${MANAGE}" migrate --check
run_step "Stripe config check" "${PYTHON}" "${MANAGE}" check_stripe

run_step "Configured path check" "${PYTHON}" - <<'PY'
from pathlib import Path

from thephage.config import load_config

config = load_config()
paths = {
    "public_root": config.paths.public_root,
    "static_root": config.paths.static_root,
    "media_root": config.paths.media_root,
    "tmp_root": config.paths.tmp_root,
    "local_backup_dir": config.backups.local_backup_dir,
}

missing = []
for label, path in paths.items():
    if not Path(path).is_dir():
        missing.append(f"{label}: {path}")

if missing:
    raise SystemExit("Missing configured directories:\n" + "\n".join(missing))

for label, path in paths.items():
    print(f"{label}: {path}")
PY

echo
echo "Deployment check OK."
