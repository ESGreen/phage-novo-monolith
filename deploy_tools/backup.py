from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from thephage.config import ThePhageConfig, load_config


@dataclass(frozen=True)
class Destination:
    kind: str
    value: str


SNAPSHOT_FORMAT = "thephage-portable-snapshot"
SNAPSHOT_VERSION = 1


def parse_destination(output: str | None) -> Destination:
    if not output:
        return Destination("normal", "")
    if output.startswith("s3://"):
        return Destination("s3", output)
    return Destination("local", output)


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")


def run_command(command: list[str]) -> None:
    subprocess.run(command, check=True)


def run_pg_command(config: ThePhageConfig, command: list[str]) -> None:
    env = os.environ.copy()
    env["PGPASSWORD"] = config.database.password
    subprocess.run(command, check=True, env=env)


def pg_dump_command(config: ThePhageConfig, output_path: Path) -> list[str]:
    return [
        "pg_dump",
        "-Fc",
        f"--host={config.database.host}",
        f"--port={config.database.port}",
        f"--username={config.database.user}",
        f"--file={output_path}",
        config.database.name,
    ]


def validate_local_output_path(output_path: Path) -> None:
    if not output_path.is_absolute():
        raise SystemExit(
            "Local --output must be an absolute path. "
            "Use something like --output=/var/backups/thephage/snapshot.tar.gz.",
        )
    parent = output_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except PermissionError as error:
        raise SystemExit(
            f"Cannot create output directory '{parent}': permission denied."
        ) from error
    try:
        if not parent.is_dir():
            raise SystemExit(f"Output parent is not a directory: {parent}")
    except PermissionError as error:
        raise SystemExit(
            f"Cannot access output directory '{parent}': permission denied."
        ) from error
    if not os.access(parent, os.W_OK):
        raise SystemExit(f"Output directory is not writable: {parent}")


def s3_uri(bucket: str, prefix: str, *parts: str) -> str:
    key_parts = [prefix.strip("/"), *(part.strip("/") for part in parts)]
    key = "/".join(part for part in key_parts if part)
    return f"s3://{bucket}/{key}"


def redacted_config(config: ThePhageConfig) -> dict[str, object]:
    return {
        "site": {
            "base_url": config.site.base_url,
            "debug": config.site.debug,
            "allowed_hosts": list(config.site.allowed_hosts),
            "timezone": config.site.timezone,
        },
        "database": {
            "host": config.database.host,
            "port": config.database.port,
            "name": config.database.name,
            "user": config.database.user,
            "password": "<redacted>",
        },
        "paths": {
            "public_root": str(config.paths.public_root),
            "static_root": str(config.paths.static_root),
            "media_root": str(config.paths.media_root),
            "tmp_root": str(config.paths.tmp_root),
            "reimbursement_receipt_root": str(config.paths.reimbursement_receipt_root),
        },
        "backups": {
            "database_backups_enabled": config.backups.database_backups_enabled,
            "config_backups_enabled": config.backups.config_backups_enabled,
            "media_backups_enabled": config.backups.media_backups_enabled,
            "s3_bucket": config.backups.s3_bucket,
            "s3_prefix": config.backups.s3_prefix,
            "local_backup_dir": str(config.backups.local_backup_dir),
            "database_retention_days": config.backups.database_retention_days,
            "config_retention_days": config.backups.config_retention_days,
            "media_retention_days": config.backups.media_retention_days,
            "config_paths": [str(path) for path in config.backups.config_paths],
        },
    }


def media_manifest(media_root: Path) -> dict[str, object]:
    file_count = 0
    total_bytes = 0
    if media_root.is_dir():
        for path in media_root.rglob("*"):
            if path.is_file():
                file_count += 1
                total_bytes += path.stat().st_size
    return {
        "media_root": str(media_root),
        "file_count": file_count,
        "total_bytes": total_bytes,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_inventory(root: Path) -> dict[str, object]:
    files = []
    total_bytes = 0
    if root.is_dir():
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            size = path.stat().st_size
            total_bytes += size
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size_bytes": size,
                    "sha256": sha256_file(path),
                }
            )
    return {"file_count": len(files), "total_bytes": total_bytes, "files": files}


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_media_to_tar(tar: tarfile.TarFile, media_root: Path, snapshot_name: str) -> None:
    if not media_root.is_dir():
        return
    for path in media_root.rglob("*"):
        if path.is_file():
            tar.add(path, arcname=f"{snapshot_name}/media/{path.relative_to(media_root)}")


def add_tree_to_tar(
    tar: tarfile.TarFile,
    source_root: Path,
    archive_root: str,
) -> None:
    if not source_root.is_dir():
        return
    for path in source_root.rglob("*"):
        if path.is_file():
            tar.add(path, arcname=f"{archive_root}/{path.relative_to(source_root)}")


def git_commit(app_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(app_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def app_root() -> Path:
    configured = os.environ.get("THEPHAGE_APP_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path.cwd().resolve()


def migration_inventory() -> list[str]:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thephage.settings")

    import django
    from django.db import connections
    from django.db.migrations.loader import MigrationLoader

    django.setup()
    loader = MigrationLoader(connections["default"], ignore_no_migrations=True)
    return [
        f"{app_label}.{migration_name}"
        for app_label, migration_name in sorted(loader.applied_migrations)
    ]


def write_django_data_export(output_path: Path) -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thephage.settings")

    import django
    from django.apps import apps
    from django.core import serializers

    django.setup()
    excluded_models = {
        ("auth", "permission"),
        ("contenttypes", "contenttype"),
        ("sessions", "session"),
    }
    objects = []
    for model in apps.get_models():
        if (model._meta.app_label, model._meta.model_name) in excluded_models:
            continue
        objects.extend(model._default_manager.all().iterator())
    with output_path.open("w", encoding="utf-8") as output_file:
        serializers.serialize(
            "json",
            objects,
            stream=output_file,
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True,
            indent=2,
        )


def create_portable_snapshot(
    config: ThePhageConfig,
    output_path: Path,
    created_at: str,
    *,
    app_root: Path | None = None,
) -> Path:
    validate_local_output_path(output_path)
    if output_path.exists():
        raise SystemExit(f"Refusing to overwrite existing snapshot: {output_path}")
    app_root = app_root or globals()["app_root"]()
    snapshot_name = f"thephage-snapshot-{created_at}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="thephage-portable-snapshot-",
        dir=output_path.parent,
    ) as temp_dir:
        temp_path = Path(temp_dir)
        database_dump = temp_path / "database.dump"
        database_json = temp_path / "database.json"
        manifest_path = temp_path / "manifest.json"
        staged_archive = temp_path / "snapshot.tar.gz"

        run_pg_command(config, pg_dump_command(config, database_dump))
        write_django_data_export(database_json)
        manifest = {
            "format": SNAPSHOT_FORMAT,
            "version": SNAPSHOT_VERSION,
            "created_at": created_at,
            "git_commit": git_commit(app_root),
            "timezone": config.site.timezone,
            "database": {
                "name": config.database.name,
                "dump_format": "postgres-custom",
                "size_bytes": database_dump.stat().st_size,
                "sha256": sha256_file(database_dump),
            },
            "database_json": {
                "size_bytes": database_json.stat().st_size,
                "sha256": sha256_file(database_json),
                "excluded_models": [
                    "auth.permission",
                    "contenttypes.contenttype",
                    "sessions.session",
                ],
            },
            "trees": {
                "media": tree_inventory(config.paths.media_root),
                "reimbursement_receipts": tree_inventory(
                    config.paths.reimbursement_receipt_root
                ),
            },
            "migrations": migration_inventory(),
        }
        write_json(manifest_path, manifest)

        with tarfile.open(staged_archive, "w:gz") as tar:
            tar.add(database_dump, arcname=f"{snapshot_name}/database.dump")
            tar.add(database_json, arcname=f"{snapshot_name}/database.json")
            tar.add(manifest_path, arcname=f"{snapshot_name}/manifest.json")
            add_tree_to_tar(tar, config.paths.media_root, f"{snapshot_name}/media")
            add_tree_to_tar(
                tar,
                config.paths.reimbursement_receipt_root,
                f"{snapshot_name}/private/reimbursement-receipts",
            )

        with tarfile.open(staged_archive, "r:gz") as tar:
            names = set(tar.getnames())
            required = {
                f"{snapshot_name}/database.dump",
                f"{snapshot_name}/database.json",
                f"{snapshot_name}/manifest.json",
            }
            if not required <= names:
                raise SystemExit("Portable snapshot verification failed")
        os.chmod(staged_archive, 0o600)
        os.replace(staged_archive, output_path)
    print(f"Created snapshot: {output_path}")
    print(f"SHA-256: {sha256_file(output_path)}")
    return output_path


def create_support_bundle(config: ThePhageConfig, output_path: Path, created_at: str) -> Path:
    validate_local_output_path(output_path)
    snapshot_name = f"thephage-snapshot-{created_at}"
    with tempfile.TemporaryDirectory(prefix="thephage-backup-") as temp_dir:
        temp_path = Path(temp_dir)
        database_dump = temp_path / "database.dump"
        run_pg_command(config, pg_dump_command(config, database_dump))
        media_data = media_manifest(config.paths.media_root)
        manifest = {
            "created_at": created_at,
            "kind": "support-snapshot",
            "database": config.database.name,
            "media": media_data,
        }
        manifest_path = temp_path / "manifest.json"
        config_path = temp_path / "config-redacted.json"
        write_json(manifest_path, manifest)
        write_json(config_path, redacted_config(config))

        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(database_dump, arcname=f"{snapshot_name}/database.dump")
            tar.add(manifest_path, arcname=f"{snapshot_name}/manifest.json")
            tar.add(config_path, arcname=f"{snapshot_name}/config-redacted.json")
            add_media_to_tar(tar, config.paths.media_root, snapshot_name)
    return output_path


def create_config_tarball(config: ThePhageConfig, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output_path, "w:gz") as tar:
        for path in config.backups.config_paths:
            if path.exists():
                tar.add(path, arcname=str(path).lstrip("/"))


def run_normal_backup(config: ThePhageConfig, created_at: str) -> None:
    backup_root = config.backups.local_backup_dir / created_at
    backup_root.mkdir(parents=True, exist_ok=True)

    if config.backups.database_backups_enabled:
        database_dump = backup_root / f"{created_at}.dump"
        run_pg_command(config, pg_dump_command(config, database_dump))
        run_command(
            [
                "aws",
                "s3",
                "cp",
                str(database_dump),
                s3_uri(
                    config.backups.s3_bucket,
                    config.backups.s3_prefix,
                    "database",
                    database_dump.name,
                ),
            ]
        )

    if config.backups.config_backups_enabled:
        config_tarball = backup_root / f"{created_at}.tar.gz"
        create_config_tarball(config, config_tarball)
        run_command(
            [
                "aws",
                "s3",
                "cp",
                str(config_tarball),
                s3_uri(
                    config.backups.s3_bucket,
                    config.backups.s3_prefix,
                    "config",
                    config_tarball.name,
                ),
            ]
        )

    if config.backups.media_backups_enabled:
        manifest = {
            "created_at": created_at,
            **media_manifest(config.paths.media_root),
            "s3_prefix": f"{config.backups.s3_prefix.strip('/')}/media/",
        }
        manifest_path = backup_root / f"{created_at}.json"
        write_json(manifest_path, manifest)
        run_command(
            [
                "aws",
                "s3",
                "sync",
                f"{config.paths.media_root}/",
                s3_uri(config.backups.s3_bucket, config.backups.s3_prefix, "media") + "/",
                "--delete",
            ]
        )
        run_command(
            [
                "aws",
                "s3",
                "sync",
                f"{config.paths.reimbursement_receipt_root}/",
                s3_uri(
                    config.backups.s3_bucket,
                    config.backups.s3_prefix,
                    "private",
                    "reimbursement-receipts",
                )
                + "/",
                "--delete",
            ]
        )
        run_command(
            [
                "aws",
                "s3",
                "cp",
                str(manifest_path),
                s3_uri(
                    config.backups.s3_bucket,
                    config.backups.s3_prefix,
                    "media-manifests",
                    manifest_path.name,
                ),
            ]
        )


def verify_tools(needs_s3: bool = True) -> None:
    required = ["pg_dump", "tar"]
    if needs_s3:
        required.append("aws")
    missing = [tool for tool in required if shutil.which(tool) is None]
    if missing:
        raise SystemExit("Missing required tools: " + ", ".join(missing))


def run_backup(output: str | None, created_at: str | None = None) -> None:
    config = load_config()
    created_at = created_at or timestamp()
    destination = parse_destination(output)
    if destination.kind == "normal":
        verify_tools(needs_s3=True)
        run_normal_backup(config, created_at)
        return

    with tempfile.TemporaryDirectory(prefix="thephage-support-bundle-") as temp_dir:
        bundle_path = (
            Path(destination.value)
            if destination.kind == "local"
            else Path(temp_dir) / "snapshot.tar.gz"
        )
        create_support_bundle(config, bundle_path, created_at)
        if destination.kind == "s3":
            verify_tools(needs_s3=True)
            run_command(["aws", "s3", "cp", str(bundle_path), destination.value])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Back up The Phage production data.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="Run a backup.")
    run_parser.add_argument(
        "--output",
        help="Optional local tarball path or s3:// URI for a single support snapshot.",
    )
    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="Create one portable production snapshot for local diagnosis.",
    )
    snapshot_parser.add_argument(
        "--output",
        required=True,
        help="Absolute local tarball path or s3:// URI.",
    )
    subparsers.add_parser("verify-tools", help="Verify required backup tools are available.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify-tools":
        verify_tools(needs_s3=True)
        print("Backup tools OK.")
        return 0
    if args.command == "run":
        run_backup(args.output)
        return 0
    if args.command == "snapshot":
        output_is_s3 = args.output.startswith("s3://")
        verify_tools(needs_s3=output_is_s3)
        created_at = timestamp()
        if output_is_s3:
            with tempfile.TemporaryDirectory(prefix="thephage-portable-upload-") as temp_dir:
                snapshot_path = Path(temp_dir) / f"thephage-snapshot-{created_at}.tar.gz"
                create_portable_snapshot(load_config(), snapshot_path, created_at)
                run_command(["aws", "s3", "cp", str(snapshot_path), args.output])
                print(f"Uploaded snapshot: {args.output}")
            return 0
        create_portable_snapshot(load_config(), Path(args.output), created_at)
        return 0
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
