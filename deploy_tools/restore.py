from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

DEFAULT_RESTORE_ROOT = Path("var/production-snapshots/current")
UNSAFE_DATABASE_NAMES = {"thephage", "postgres", "template0", "template1"}
SAFE_DATABASE_RE = re.compile(r"^thephage_snapshot_[a-z0-9_]+$")
SNAPSHOT_FORMAT = "thephage-portable-snapshot"
SNAPSHOT_VERSION = 1


def run_command(command: list[str]) -> None:
    subprocess.run(command, check=True)


def source_is_s3(source: str) -> bool:
    return source.startswith("s3://")


def assert_safe_local_database(database: str, force: bool = False) -> None:
    if force:
        return
    normalized = database.strip().lower()
    if normalized in UNSAFE_DATABASE_NAMES or "prod" in normalized or "production" in normalized:
        raise SystemExit(
            f"Refusing to restore into unsafe database name '{database}'. "
            "Use a scratch database name or pass --force-dangerous-database.",
        )


def pg_restore_command(database: str, dump_path: Path) -> list[str]:
    return [
        "pg_restore",
        "--exit-on-error",
        "--single-transaction",
        "--no-owner",
        "--no-privileges",
        f"--dbname={database}",
        str(dump_path),
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_source(source: str, work_dir: Path) -> Path:
    if not source_is_s3(source):
        source_path = Path(source)
        if not source_path.is_file():
            raise SystemExit(f"Snapshot does not exist: {source}")
        return source_path

    local_path = work_dir / "snapshot.tar.gz"
    run_command(["aws", "s3", "cp", source, str(local_path)])
    return local_path


def safe_extract_tarball(tarball: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    with tarfile.open(tarball, "r:gz") as tar:
        for member in tar.getmembers():
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise SystemExit(f"Refusing unsafe tar member type: {member.name}")
            member_path = (destination / member.name).resolve()
            if not member_path.is_relative_to(destination_root):
                raise SystemExit(f"Refusing unsafe tar member path: {member.name}")
        tar.extractall(destination, filter="data")


def find_snapshot_root(destination: Path) -> Path:
    roots = [path for path in destination.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise SystemExit(f"Expected exactly one snapshot root in {destination}")
    return roots[0]


def load_portable_manifest(
    snapshot_root: Path,
    *,
    require_database_json: bool = False,
) -> dict[str, object]:
    manifest_path = snapshot_root / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"Snapshot is missing manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != SNAPSHOT_FORMAT or manifest.get("version") != SNAPSHOT_VERSION:
        raise SystemExit("Unsupported portable snapshot format or version")
    dump_path = snapshot_root / "database.dump"
    database = manifest.get("database", {})
    if not dump_path.is_file() or not isinstance(database, dict):
        raise SystemExit("Portable snapshot is missing database metadata")
    if dump_path.stat().st_size != database.get("size_bytes"):
        raise SystemExit("Portable snapshot database size does not match manifest")
    if sha256_file(dump_path) != database.get("sha256"):
        raise SystemExit("Portable snapshot database checksum does not match manifest")
    database_json_path = snapshot_root / "database.json"
    database_json = manifest.get("database_json", {})
    if require_database_json and (
        not database_json_path.is_file() or not isinstance(database_json, dict)
    ):
        raise SystemExit("Portable snapshot does not support SQLite mode: database.json is missing")
    if database_json_path.is_file():
        if not isinstance(database_json, dict):
            raise SystemExit("Portable snapshot JSON metadata is invalid")
        if database_json_path.stat().st_size != database_json.get("size_bytes"):
            raise SystemExit("Portable snapshot JSON size does not match manifest")
        if sha256_file(database_json_path) != database_json.get("sha256"):
            raise SystemExit("Portable snapshot JSON checksum does not match manifest")
    for tree_name, relative_root in (
        ("media", Path("media")),
        ("reimbursement_receipts", Path("private/reimbursement-receipts")),
    ):
        tree_data = manifest.get("trees", {}).get(tree_name, {})
        if not isinstance(tree_data, dict):
            raise SystemExit(f"Portable snapshot is missing {tree_name} inventory")
        for item in tree_data.get("files", []):
            path = snapshot_root / relative_root / item["path"]
            if not path.is_file():
                raise SystemExit(f"Portable snapshot is missing file: {path}")
            if path.stat().st_size != item["size_bytes"] or sha256_file(path) != item["sha256"]:
                raise SystemExit(f"Portable snapshot file does not match manifest: {path}")
    return manifest


def assert_snapshot_database_name(database: str) -> None:
    if not SAFE_DATABASE_RE.fullmatch(database):
        raise SystemExit(
            "Snapshot database names must start with 'thephage_snapshot_' and contain only "
            "lowercase letters, numbers, and underscores."
        )


def generated_local_config(
    *,
    snapshot_root: Path,
    runtime_root: Path,
    database: str,
    host: str,
    port: int,
    user: str,
    password: str,
    web_port: int,
    timezone: str,
) -> str:
    config_password = password or "unused-peer-auth"
    return f'''[site]
base_url = "http://127.0.0.1:{web_port}"
secret_key = "{secrets.token_urlsafe(48)}"
debug = true
allowed_hosts = ["127.0.0.1", "localhost", "testserver"]
timezone = "{timezone.replace('"', '')}"

[database]
host = "{host}"
port = {port}
name = "{database}"
user = "{user}"
password = "{config_password}"

[paths]
public_root = "{runtime_root / 'public'}"
static_root = "{runtime_root / 'static'}"
media_root = "{snapshot_root / 'media'}"
tmp_root = "{runtime_root / 'tmp'}"
reimbursement_receipt_root = "{snapshot_root / 'private/reimbursement-receipts'}"

[stripe]
test_secret_key = "sk_test_dummy"
test_publishable_key = "pk_test_dummy"
test_webhook_secret = "whsec_test_dummy"
live_secret_key = "disabled"
live_publishable_key = "disabled"
live_webhook_secret = "disabled"

[backups]
database_backups_enabled = false
config_backups_enabled = false
media_backups_enabled = false
s3_bucket = "disabled"
s3_prefix = "disabled"
local_backup_dir = "{runtime_root / 'backups'}"
database_retention_days = 0
config_retention_days = 0
media_retention_days = 0
config_paths = []
'''


def restore_portable_snapshot(
    *,
    source: str,
    database: str,
    runtime_root: Path,
    database_host: str,
    database_port: int,
    database_user: str,
    database_password: str,
    web_port: int,
) -> tuple[Path, Path, dict[str, object]]:
    assert_snapshot_database_name(database)
    runtime_root = runtime_root.resolve()
    allowed_base = Path("/tmp/thephage-snapshot-server").resolve()
    if runtime_root != allowed_base and allowed_base not in runtime_root.parents:
        raise SystemExit(f"Snapshot runtime root must be under {allowed_base}")
    runtime_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    stage_root = runtime_root.parent / f".{runtime_root.name}-staging"
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(mode=0o700)
    with tempfile.TemporaryDirectory(prefix="thephage-snapshot-fetch-") as temp_dir:
        tarball = fetch_source(source, Path(temp_dir))
        safe_extract_tarball(tarball, stage_root)
    snapshot_root = find_snapshot_root(stage_root)
    manifest = load_portable_manifest(snapshot_root)

    env = os.environ.copy()
    env["PGHOST"] = database_host
    env["PGPORT"] = str(database_port)
    env["PGUSER"] = database_user
    env["PGPASSWORD"] = database_password
    subprocess.run(["dropdb", "--if-exists", database], check=True, env=env)
    subprocess.run(["createdb", database], check=True, env=env)
    subprocess.run(
        pg_restore_command(database, snapshot_root / "database.dump"),
        check=True,
        env=env,
    )

    restored_root = runtime_root / "restored"
    if restored_root.exists():
        shutil.rmtree(restored_root)
    os.replace(snapshot_root, restored_root)
    shutil.rmtree(stage_root)
    for directory in ("public", "static", "tmp", "backups"):
        (runtime_root / directory).mkdir(parents=True, exist_ok=True)
    config_path = runtime_root / "thephage.toml"
    config_path.write_text(
        generated_local_config(
            snapshot_root=restored_root,
            runtime_root=runtime_root,
            database=database,
            host=database_host,
            port=database_port,
            user=database_user,
            password=database_password,
            web_port=web_port,
            timezone=str(manifest.get("timezone", "America/Los_Angeles")),
        ),
        encoding="utf-8",
    )
    os.chmod(config_path, 0o600)
    return restored_root, config_path, manifest


def prepare_sqlite_snapshot(
    *,
    source: str,
    runtime_root: Path,
    web_port: int,
) -> tuple[Path, Path, Path, dict[str, object]]:
    runtime_root = runtime_root.resolve()
    allowed_base = Path("/tmp/thephage-snapshot-server").resolve()
    if runtime_root != allowed_base and allowed_base not in runtime_root.parents:
        raise SystemExit(f"Snapshot runtime root must be under {allowed_base}")
    runtime_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    stage_root = runtime_root.parent / f".{runtime_root.name}-staging"
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(mode=0o700)
    with tempfile.TemporaryDirectory(prefix="thephage-snapshot-fetch-") as temp_dir:
        tarball = fetch_source(source, Path(temp_dir))
        safe_extract_tarball(tarball, stage_root)
    snapshot_root = find_snapshot_root(stage_root)
    manifest = load_portable_manifest(snapshot_root, require_database_json=True)

    restored_root = runtime_root / "restored"
    if restored_root.exists():
        shutil.rmtree(restored_root)
    os.replace(snapshot_root, restored_root)
    shutil.rmtree(stage_root)
    for directory in ("public", "static", "tmp", "backups"):
        (runtime_root / directory).mkdir(parents=True, exist_ok=True)
    sqlite_path = runtime_root / "thephage.sqlite3"
    config_path = runtime_root / "thephage.toml"
    config_path.write_text(
        generated_local_config(
            snapshot_root=restored_root,
            runtime_root=runtime_root,
            database="unused_sqlite_snapshot",
            host="localhost",
            port=5432,
            user="unused",
            password="unused",
            web_port=web_port,
            timezone=str(manifest.get("timezone", "America/Los_Angeles")),
        ),
        encoding="utf-8",
    )
    os.chmod(config_path, 0o600)
    return restored_root, config_path, sqlite_path, manifest


def restore_local(
    source: str,
    database: str,
    restore_root: Path = DEFAULT_RESTORE_ROOT,
    force_dangerous_database: bool = False,
) -> Path:
    assert_safe_local_database(database, force=force_dangerous_database)
    with tempfile.TemporaryDirectory(prefix="thephage-restore-") as temp_dir:
        tarball = fetch_source(source, Path(temp_dir))
        if restore_root.exists():
            shutil.rmtree(restore_root)
        safe_extract_tarball(tarball, restore_root)

    snapshot_root = find_snapshot_root(restore_root)
    dump_path = snapshot_root / "database.dump"
    if not dump_path.is_file():
        raise SystemExit(f"Snapshot is missing database dump: {dump_path}")
    run_command(pg_restore_command(database, dump_path))
    print(f"Restored database '{database}' from {dump_path}")
    print(f"Snapshot media is available at {snapshot_root / 'media'}")
    return snapshot_root


def verify_tools(needs_s3: bool = False) -> None:
    required = ["pg_restore"]
    if needs_s3:
        required.append("aws")
    missing = [tool for tool in required if shutil.which(tool) is None]
    if missing:
        raise SystemExit("Missing required tools: " + ", ".join(missing))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restore The Phage backups for diagnostics.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    restore_parser = subparsers.add_parser(
        "restore-local",
        help="Restore a support snapshot into a local scratch database.",
    )
    restore_parser.add_argument("--source", required=True, help="Local tarball path or s3:// URI.")
    restore_parser.add_argument(
        "--database",
        required=True,
        help="Scratch database name to restore into.",
    )
    portable_parser = subparsers.add_parser(
        "prepare-test-server",
        help="Restore a portable snapshot into an isolated local runtime.",
    )
    portable_parser.add_argument("--source", required=True)
    portable_parser.add_argument("--database", required=True)
    portable_parser.add_argument(
        "--runtime-root",
        default="/tmp/thephage-snapshot-server",
    )
    portable_parser.add_argument("--database-host", default="127.0.0.1")
    portable_parser.add_argument("--database-port", type=int, default=5432)
    portable_parser.add_argument("--database-user", required=True)
    portable_parser.add_argument("--database-password", default="")
    portable_parser.add_argument("--web-port", type=int, default=8000)
    sqlite_parser = subparsers.add_parser(
        "prepare-sqlite-test-server",
        help="Extract a portable snapshot for a local SQLite diagnostic server.",
    )
    sqlite_parser.add_argument("--source", required=True)
    sqlite_parser.add_argument(
        "--runtime-root",
        default="/tmp/thephage-snapshot-server",
    )
    sqlite_parser.add_argument("--web-port", type=int, default=8000)
    restore_parser.add_argument(
        "--restore-root",
        default=str(DEFAULT_RESTORE_ROOT),
        help="Directory where the snapshot should be extracted.",
    )
    restore_parser.add_argument(
        "--force-dangerous-database",
        action="store_true",
        help="Allow restoring into a production-looking database name.",
    )
    subparsers.add_parser("verify-tools", help="Verify required restore tools are available.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify-tools":
        verify_tools()
        print("Restore tools OK.")
        return 0
    if args.command == "restore-local":
        verify_tools(needs_s3=source_is_s3(args.source))
        restore_local(
            source=args.source,
            database=args.database,
            restore_root=Path(args.restore_root),
            force_dangerous_database=args.force_dangerous_database,
        )
        return 0
    if args.command == "prepare-test-server":
        verify_tools(needs_s3=source_is_s3(args.source))
        restored_root, config_path, _manifest = restore_portable_snapshot(
            source=args.source,
            database=args.database,
            runtime_root=Path(args.runtime_root),
            database_host=args.database_host,
            database_port=args.database_port,
            database_user=args.database_user,
            database_password=args.database_password,
            web_port=args.web_port,
        )
        print(f"Restored snapshot root: {restored_root}")
        print(f"Generated config: {config_path}")
        return 0
    if args.command == "prepare-sqlite-test-server":
        verify_tools(needs_s3=source_is_s3(args.source))
        restored_root, config_path, sqlite_path, _manifest = prepare_sqlite_snapshot(
            source=args.source,
            runtime_root=Path(args.runtime_root),
            web_port=args.web_port,
        )
        print(f"Restored snapshot root: {restored_root}")
        print(f"Generated config: {config_path}")
        print(f"SQLite database: {sqlite_path}")
        return 0
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
