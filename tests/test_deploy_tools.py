from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from deploy_tools import backup, restore
from thephage.config import load_config


def configured_snapshot(tmp_path: Path):
    config = load_config("tests/fixtures/thephage.test.toml")
    media_root = tmp_path / "media"
    media_root.mkdir()
    (media_root / "profile.jpg").write_bytes(b"profile")
    reimbursement_receipt_root = tmp_path / "reimbursement-receipts"
    reimbursement_receipt_root.mkdir()
    (reimbursement_receipt_root / "receipt.pdf").write_bytes(b"receipt")
    return config.__class__(
        path=config.path,
        site=config.site,
        database=config.database,
        paths=config.paths.__class__(
            public_root=config.paths.public_root,
            static_root=config.paths.static_root,
            media_root=media_root,
            tmp_root=config.paths.tmp_root,
            reimbursement_receipt_root=reimbursement_receipt_root,
        ),
        stripe=config.stripe,
        backups=config.backups.__class__(
            database_backups_enabled=config.backups.database_backups_enabled,
            config_backups_enabled=config.backups.config_backups_enabled,
            media_backups_enabled=config.backups.media_backups_enabled,
            s3_bucket=config.backups.s3_bucket,
            s3_prefix=config.backups.s3_prefix,
            local_backup_dir=tmp_path / "backups",
            database_retention_days=config.backups.database_retention_days,
            config_retention_days=config.backups.config_retention_days,
            media_retention_days=config.backups.media_retention_days,
            config_paths=(),
        ),
    )


def test_backup_help_exits_successfully(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        backup.build_parser().parse_args(["--help"])

    assert exc_info.value.code == 0
    assert "Back up The Phage" in capsys.readouterr().out


def test_restore_help_exits_successfully(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        restore.build_parser().parse_args(["--help"])

    assert exc_info.value.code == 0
    assert "Restore The Phage" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("output", "kind", "value"),
    [
        (None, "normal", ""),
        ("/tmp/snapshot.tar.gz", "local", "/tmp/snapshot.tar.gz"),
        ("s3://bucket/path/snapshot.tar.gz", "s3", "s3://bucket/path/snapshot.tar.gz"),
    ],
)
def test_backup_destination_parsing(output: str | None, kind: str, value: str) -> None:
    destination = backup.parse_destination(output)

    assert destination.kind == kind
    assert destination.value == value


def test_pg_dump_command_uses_custom_format(tmp_path) -> None:
    config = configured_snapshot(tmp_path)

    command = backup.pg_dump_command(config, tmp_path / "database.dump")

    assert command[0] == "pg_dump"
    assert "-Fc" in command
    assert f"--dbname={config.database.name}" not in command
    assert command[-1] == config.database.name


def test_pg_dump_uses_configured_password_in_environment(monkeypatch, tmp_path) -> None:
    config = configured_snapshot(tmp_path)
    captured = {}

    def fake_run(command: list[str], check: bool, env: dict[str, str]) -> None:
        captured["command"] = command
        captured["check"] = check
        captured["env"] = env

    monkeypatch.setattr(backup.subprocess, "run", fake_run)

    command = backup.pg_dump_command(config, tmp_path / "database.dump")
    backup.run_pg_command(config, command)

    assert captured["command"] == command
    assert captured["check"] is True
    assert captured["env"]["PGPASSWORD"] == config.database.password
    assert config.database.password not in command


def test_migration_inventory_uses_django_loader(mocker) -> None:
    loader = mocker.patch("django.db.migrations.loader.MigrationLoader")
    loader.return_value.applied_migrations = {
        ("content", "0001_initial"),
        ("reimbursements", "0001_initial"),
    }

    inventory = backup.migration_inventory()

    assert inventory == ["content.0001_initial", "reimbursements.0001_initial"]


def test_git_commit_uses_app_root_and_is_nonfatal(monkeypatch, tmp_path) -> None:
    captured = {}

    class Result:
        returncode = 128
        stdout = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        return Result()

    monkeypatch.setattr(backup.subprocess, "run", fake_run)

    assert backup.git_commit(tmp_path) == "unknown"
    assert captured["command"] == ["git", "-C", str(tmp_path), "rev-parse", "HEAD"]


def test_app_root_uses_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("THEPHAGE_APP_ROOT", str(tmp_path))
    assert backup.app_root() == tmp_path.resolve()


def test_local_output_must_be_absolute() -> None:
    with pytest.raises(SystemExit) as exc_info:
        backup.validate_local_output_path(Path("b.tar.gz"))

    assert "Local --output must be an absolute path" in str(exc_info.value)


def test_support_bundle_contains_database_media_manifest_and_redacted_config(
    monkeypatch,
    tmp_path,
) -> None:
    config = configured_snapshot(tmp_path)
    output_path = tmp_path / "snapshot.tar.gz"

    def fake_run_pg_command(config, command: list[str]) -> None:
        file_arg = next(arg for arg in command if arg.startswith("--file="))
        Path(file_arg.removeprefix("--file=")).write_bytes(b"database")

    monkeypatch.setattr(backup, "run_pg_command", fake_run_pg_command)

    backup.create_support_bundle(config, output_path, "2026-08-13-1530")

    with tarfile.open(output_path, "r:gz") as tar:
        names = set(tar.getnames())
        assert "thephage-snapshot-2026-08-13-1530/database.dump" in names
        assert "thephage-snapshot-2026-08-13-1530/media/profile.jpg" in names
        assert "thephage-snapshot-2026-08-13-1530/manifest.json" in names
        assert "thephage-snapshot-2026-08-13-1530/config-redacted.json" in names
        config_file = tar.extractfile("thephage-snapshot-2026-08-13-1530/config-redacted.json")
        assert config_file is not None
        assert b"<redacted>" in config_file.read()


def test_s3_output_uploads_single_support_bundle(monkeypatch, tmp_path) -> None:
    config = configured_snapshot(tmp_path)
    commands: list[list[str]] = []

    monkeypatch.setattr(backup, "load_config", lambda: config)
    monkeypatch.setattr(backup, "verify_tools", lambda needs_s3=True: None)

    def fake_run_command(command: list[str]) -> None:
        commands.append(command)

    def fake_run_pg_command(config, command: list[str]) -> None:
        commands.append(command)
        file_arg = next(arg for arg in command if arg.startswith("--file="))
        Path(file_arg.removeprefix("--file=")).write_bytes(b"database")

    monkeypatch.setattr(backup, "run_command", fake_run_command)
    monkeypatch.setattr(backup, "run_pg_command", fake_run_pg_command)

    backup.run_backup("s3://bucket/support/snapshot.tar.gz", created_at="2026-08-13-1530")

    assert commands[-1][:3] == ["aws", "s3", "cp"]
    assert commands[-1][-1] == "s3://bucket/support/snapshot.tar.gz"


def test_normal_backup_uses_configured_s3_layout(monkeypatch, tmp_path) -> None:
    config = configured_snapshot(tmp_path)
    commands: list[list[str]] = []

    def fake_run_command(command: list[str]) -> None:
        commands.append(command)

    def fake_run_pg_command(config, command: list[str]) -> None:
        commands.append(command)
        file_arg = next(arg for arg in command if arg.startswith("--file="))
        Path(file_arg.removeprefix("--file=")).write_bytes(b"database")

    monkeypatch.setattr(backup, "run_command", fake_run_command)
    monkeypatch.setattr(backup, "run_pg_command", fake_run_pg_command)

    backup.run_normal_backup(config, "2026-08-13-1530")

    destinations = [
        command[-1]
        for command in commands
        if command[:3] == ["aws", "s3", "cp"]
    ]
    assert any("/database/2026-08-13-1530.dump" in destination for destination in destinations)
    assert any("/config/2026-08-13-1530.tar.gz" in destination for destination in destinations)
    assert any(
        "/media-manifests/2026-08-13-1530.json" in destination
        for destination in destinations
    )
    assert any(command[:3] == ["aws", "s3", "sync"] for command in commands)
    assert any(
        "private/reimbursement-receipts" in command[-2]
        for command in commands
        if command[:3] == ["aws", "s3", "sync"]
    )


def test_portable_snapshot_contains_database_media_and_private_receipts(
    monkeypatch,
    tmp_path,
) -> None:
    config = configured_snapshot(tmp_path)
    output_path = tmp_path / "portable.tar.gz"

    def fake_run_pg_command(config, command: list[str]) -> None:
        file_arg = next(arg for arg in command if arg.startswith("--file="))
        Path(file_arg.removeprefix("--file=")).write_bytes(b"database")

    monkeypatch.setattr(backup, "run_pg_command", fake_run_pg_command)
    monkeypatch.setattr(backup, "git_commit", lambda app_root: "abc123")
    monkeypatch.setattr(backup, "migration_inventory", lambda: ["a.0001"])

    backup.create_portable_snapshot(
        config,
        output_path,
        "2026-09-17T120000Z",
        app_root=tmp_path,
    )

    with tarfile.open(output_path, "r:gz") as tar:
        root = "thephage-snapshot-2026-09-17T120000Z"
        names = set(tar.getnames())
        assert f"{root}/database.dump" in names
        assert f"{root}/media/profile.jpg" in names
        assert f"{root}/private/reimbursement-receipts/receipt.pdf" in names
        assert not any("/public/" in name for name in names)
        manifest_file = tar.extractfile(f"{root}/manifest.json")
        assert manifest_file is not None
        manifest = json.load(manifest_file)
        assert manifest["format"] == backup.SNAPSHOT_FORMAT
        assert manifest["git_commit"] == "abc123"
        assert manifest["trees"]["media"]["file_count"] == 1
        assert manifest["trees"]["reimbursement_receipts"]["file_count"] == 1
        archive_bytes = output_path.read_bytes()
        assert config.database.password.encode() not in archive_bytes
        assert config.stripe.live_secret_key.encode() not in archive_bytes


def test_portable_snapshot_refuses_existing_output(monkeypatch, tmp_path) -> None:
    config = configured_snapshot(tmp_path)
    output_path = tmp_path / "portable.tar.gz"
    output_path.write_bytes(b"existing")

    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        backup.create_portable_snapshot(config, output_path, "2026-09-17T120000Z")


def test_generated_local_config_uses_restored_paths(tmp_path) -> None:
    snapshot_root = tmp_path / "restored"
    runtime_root = tmp_path / "runtime"
    config_text = restore.generated_local_config(
        snapshot_root=snapshot_root,
        runtime_root=runtime_root,
        database="thephage_snapshot_test",
        host="127.0.0.1",
        port=5432,
        user="localuser",
        password="localpass",
        web_port=8123,
        timezone="America/Los_Angeles",
    )

    assert 'base_url = "http://127.0.0.1:8123"' in config_text
    assert f'media_root = "{snapshot_root / "media"}"' in config_text
    assert "private/reimbursement-receipts" in config_text
    assert 'live_secret_key = "disabled"' in config_text


def test_portable_restore_command_uses_transactional_safety(tmp_path) -> None:
    command = restore.pg_restore_command("thephage_snapshot_test", tmp_path / "database.dump")
    assert "--exit-on-error" in command
    assert "--single-transaction" in command
    assert "--no-owner" in command
    assert "--no-privileges" in command


def test_snapshot_database_name_is_restricted() -> None:
    restore.assert_snapshot_database_name("thephage_snapshot_test")
    with pytest.raises(SystemExit):
        restore.assert_snapshot_database_name("thephage")
    with pytest.raises(SystemExit):
        restore.assert_snapshot_database_name("postgresql://server/db")


def test_portable_manifest_detects_tampered_receipt(monkeypatch, tmp_path) -> None:
    config = configured_snapshot(tmp_path)
    output_path = tmp_path / "portable.tar.gz"

    def fake_run_pg_command(config, command: list[str]) -> None:
        file_arg = next(arg for arg in command if arg.startswith("--file="))
        Path(file_arg.removeprefix("--file=")).write_bytes(b"database")

    monkeypatch.setattr(backup, "run_pg_command", fake_run_pg_command)
    monkeypatch.setattr(backup, "git_commit", lambda app_root: "abc123")
    monkeypatch.setattr(backup, "migration_inventory", lambda: ["a.0001"])
    backup.create_portable_snapshot(
        config,
        output_path,
        "2026-09-17T120000Z",
        app_root=tmp_path,
    )

    extract_root = tmp_path / "extract"
    restore.safe_extract_tarball(output_path, extract_root)
    snapshot_root = restore.find_snapshot_root(extract_root)
    receipt = snapshot_root / "private/reimbursement-receipts/receipt.pdf"
    receipt.write_bytes(b"tampered")

    with pytest.raises(SystemExit, match="does not match manifest"):
        restore.load_portable_manifest(snapshot_root)


def test_portable_manifest_accepts_valid_snapshot(monkeypatch, tmp_path) -> None:
    config = configured_snapshot(tmp_path)
    output_path = tmp_path / "portable.tar.gz"

    def fake_run_pg_command(config, command: list[str]) -> None:
        file_arg = next(arg for arg in command if arg.startswith("--file="))
        Path(file_arg.removeprefix("--file=")).write_bytes(b"database")

    monkeypatch.setattr(backup, "run_pg_command", fake_run_pg_command)
    monkeypatch.setattr(backup, "git_commit", lambda app_root: "abc123")
    monkeypatch.setattr(backup, "migration_inventory", lambda: ["a.0001"])
    backup.create_portable_snapshot(
        config,
        output_path,
        "2026-09-17T120000Z",
        app_root=tmp_path,
    )

    extract_root = tmp_path / "extract"
    restore.safe_extract_tarball(output_path, extract_root)
    manifest = restore.load_portable_manifest(restore.find_snapshot_root(extract_root))

    assert manifest["format"] == backup.SNAPSHOT_FORMAT
    assert manifest["trees"]["reimbursement_receipts"]["file_count"] == 1


@pytest.mark.parametrize("database", ["thephage", "thephage_prod", "production_snapshot"])
def test_restore_refuses_unsafe_database_names(database: str) -> None:
    with pytest.raises(SystemExit):
        restore.assert_safe_local_database(database)


def test_restore_local_extracts_snapshot_and_runs_pg_restore(monkeypatch, tmp_path) -> None:
    snapshot_path = tmp_path / "snapshot.tar.gz"
    root_name = "thephage-snapshot-2026-08-13-1530"
    database_bytes = b"database"
    with tarfile.open(snapshot_path, "w:gz") as tar:
        data = io.BytesIO(database_bytes)
        info = tarfile.TarInfo(f"{root_name}/database.dump")
        info.size = len(database_bytes)
        tar.addfile(info, data)

    commands: list[list[str]] = []
    monkeypatch.setattr(restore, "run_command", lambda command: commands.append(command))
    restore_root = tmp_path / "current"

    snapshot_root = restore.restore_local(
        source=str(snapshot_path),
        database="thephage_snapshot",
        restore_root=restore_root,
    )

    assert snapshot_root == restore_root / root_name
    assert commands == [
        restore.pg_restore_command("thephage_snapshot", snapshot_root / "database.dump")
    ]


def test_restore_rejects_unsafe_tar_member(monkeypatch, tmp_path) -> None:
    snapshot_path = tmp_path / "snapshot.tar.gz"
    with tarfile.open(snapshot_path, "w:gz") as tar:
        data = io.BytesIO(b"bad")
        info = tarfile.TarInfo("../bad")
        info.size = 3
        tar.addfile(info, data)
    monkeypatch.setattr(restore, "run_command", lambda command: None)

    with pytest.raises(SystemExit):
        restore.restore_local(
            source=str(snapshot_path),
            database="thephage_snapshot",
            restore_root=tmp_path / "current",
        )
