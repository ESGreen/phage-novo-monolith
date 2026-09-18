from __future__ import annotations

from pathlib import Path

SCRIPT = Path("deploy/scripts/runTestServer.sh").read_text(encoding="utf-8")


def test_use_sqlite_requires_snapshot() -> None:
    assert 'if [[ "${USE_SQLITE}" == "true" && -z "${SNAPSHOT_SOURCE}" ]]' in SCRIPT
    assert "--use-sqlite requires --snapshot" in SCRIPT


def test_sqlite_mode_uses_sqlite_restore_without_postgres_tools() -> None:
    postgres_guard = 'if [[ "${USE_SQLITE}" != "true" ]]; then'
    sqlite_restore = "prepare-sqlite-test-server"
    assert postgres_guard in SCRIPT
    assert sqlite_restore in SCRIPT
    assert 'export THEPHAGE_SQLITE_PATH="${SNAPSHOT_RUNTIME_ROOT}/thephage.sqlite3"' in SCRIPT
    assert 'manage.py" loaddata' in SCRIPT


def test_postgres_remains_default_snapshot_mode() -> None:
    assert "USE_SQLITE=false" in SCRIPT
    assert "prepare-test-server" in SCRIPT
