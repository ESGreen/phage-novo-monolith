from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fake_python(path: Path, *, exit_code: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/usr/bin/env bash\n"
        ": > \"${LAUNCH_RECORD}\"\n"
        "for argument in \"$@\"; do printf '%s\\n' \"${argument}\" >> \"${LAUNCH_RECORD}\"; done\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


@pytest.mark.parametrize(
    ("launcher", "source_file"),
    [
        ("backup-thephage", "deploy_tools/backup.py"),
        ("restore-thephage", "deploy_tools/restore.py"),
    ],
)
def test_launcher_uses_explicit_python_and_forwards_arguments(
    launcher: str,
    source_file: str,
    tmp_path: Path,
) -> None:
    fake_python = _fake_python(tmp_path / "custom venv" / "bin" / "python")
    record = tmp_path / "record.json"
    env = os.environ.copy()
    env["THEPHAGE_PYTHON"] = str(fake_python)
    env["LAUNCH_RECORD"] = str(record)

    result = subprocess.run(
        [
            str(PROJECT_ROOT / "deploy" / "scripts" / launcher),
            "snapshot",
            "--output=/tmp/path with spaces.tar.gz",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert f"Using Python: {fake_python}" in result.stderr
    arguments = record.read_text().splitlines()
    assert Path(arguments[0]) == PROJECT_ROOT / source_file
    assert arguments[1:] == [
        "snapshot",
        "--output=/tmp/path with spaces.tar.gz",
    ]
    assert env["THEPHAGE_PYTHON"] == str(fake_python)


def test_launcher_uses_configured_virtualenv_before_checkout_virtualenv(tmp_path: Path) -> None:
    fake_venv = tmp_path / "production-venv"
    fake_python = _fake_python(fake_venv / "bin" / "python")
    record = tmp_path / "record.json"
    env = os.environ.copy()
    env.pop("THEPHAGE_PYTHON", None)
    env["THEPHAGE_VENV"] = str(fake_venv)
    env["LAUNCH_RECORD"] = str(record)

    result = subprocess.run(
        [str(PROJECT_ROOT / "deploy" / "scripts" / "backup-thephage"), "verify-tools"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert f"Using Python: {fake_python}" in result.stderr


def test_launcher_preserves_child_exit_status(tmp_path: Path) -> None:
    fake_python = _fake_python(tmp_path / "venv" / "bin" / "python", exit_code=23)
    env = os.environ.copy()
    env["THEPHAGE_PYTHON"] = str(fake_python)
    env["LAUNCH_RECORD"] = str(tmp_path / "record.json")

    result = subprocess.run(
        [str(PROJECT_ROOT / "deploy" / "scripts" / "backup-thephage"), "verify-tools"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 23


def test_launcher_reports_missing_interpreter(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    shutil.copytree(PROJECT_ROOT / "deploy", checkout / "deploy")
    launcher = checkout / "deploy" / "scripts" / "backup-thephage"
    launcher.chmod(0o755)
    env = os.environ.copy()
    env["THEPHAGE_PYTHON"] = str(tmp_path / "missing-python")
    env["THEPHAGE_VENV"] = str(tmp_path / "missing-venv")

    result = subprocess.run(
        [str(launcher), "verify-tools"],
        cwd=checkout,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "No usable The Phage Python interpreter" in result.stderr
    assert str(tmp_path / "missing-python") in result.stderr
