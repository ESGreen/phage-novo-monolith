from __future__ import annotations

import argparse
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

DEFAULT_RESTORE_ROOT = Path("var/production-snapshots/current")
UNSAFE_DATABASE_NAMES = {"thephage", "postgres", "template0", "template1"}


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
        "--clean",
        "--if-exists",
        "--no-owner",
        f"--dbname={database}",
        str(dump_path),
    ]


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
            member_path = (destination / member.name).resolve()
            if not member_path.is_relative_to(destination_root):
                raise SystemExit(f"Refusing unsafe tar member path: {member.name}")
        tar.extractall(destination, filter="data")


def find_snapshot_root(destination: Path) -> Path:
    roots = [path for path in destination.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise SystemExit(f"Expected exactly one snapshot root in {destination}")
    return roots[0]


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
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
