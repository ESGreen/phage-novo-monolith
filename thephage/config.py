"""TOML configuration loading for The Phage website."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - used only on older supported Pythons
    import tomli as tomllib  # type: ignore[no-redef]


DEFAULT_CONFIG_PATH = Path("/etc/thephage/thephage.toml")
CONFIG_ENV_VAR = "THEPHAGE_CONFIG"


class ConfigError(RuntimeError):
    """Raised when the deployment TOML config is missing or invalid."""


@dataclass(frozen=True)
class SiteConfig:
    base_url: str
    secret_key: str
    debug: bool
    allowed_hosts: tuple[str, ...]
    timezone: str


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


@dataclass(frozen=True)
class PathsConfig:
    public_root: Path
    static_root: Path
    media_root: Path
    tmp_root: Path


@dataclass(frozen=True)
class StripeConfig:
    test_secret_key: str
    test_publishable_key: str
    test_webhook_secret: str
    live_secret_key: str
    live_publishable_key: str
    live_webhook_secret: str


@dataclass(frozen=True)
class BackupsConfig:
    database_backups_enabled: bool
    config_backups_enabled: bool
    media_backups_enabled: bool
    s3_bucket: str
    s3_prefix: str
    local_backup_dir: Path
    database_retention_days: int
    config_retention_days: int
    media_retention_days: int
    config_paths: tuple[Path, ...]


@dataclass(frozen=True)
class ThePhageConfig:
    path: Path
    site: SiteConfig
    database: DatabaseConfig
    paths: PathsConfig
    stripe: StripeConfig
    backups: BackupsConfig


def get_config_path() -> Path:
    """Return the configured TOML path, defaulting to the production path."""

    return Path(os.environ.get(CONFIG_ENV_VAR, DEFAULT_CONFIG_PATH))


def load_config(path: str | os.PathLike[str] | None = None) -> ThePhageConfig:
    """Load and validate the deployment TOML config."""

    config_path = Path(path) if path is not None else get_config_path()

    if not config_path.exists():
        raise ConfigError(f"Config file does not exist: {config_path}")

    try:
        with config_path.open("rb") as config_file:
            raw = tomllib.load(config_file)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Config file is not valid TOML: {config_path}") from exc

    _reject_aws_key_config(raw)

    return ThePhageConfig(
        path=config_path,
        site=_load_site(raw),
        database=_load_database(raw),
        paths=_load_paths(raw),
        stripe=_load_stripe(raw),
        backups=_load_backups(raw),
    )


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name)
    if not isinstance(value, dict):
        raise ConfigError(f"Missing required [{name}] config section")
    return value


def _required_str(section: dict[str, Any], section_name: str, key: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"Missing required config value: [{section_name}] {key}")
    return value


def _required_bool(section: dict[str, Any], section_name: str, key: str) -> bool:
    value = section.get(key)
    if not isinstance(value, bool):
        raise ConfigError(f"Missing required boolean config value: [{section_name}] {key}")
    return value


def _required_int(section: dict[str, Any], section_name: str, key: str) -> int:
    value = section.get(key)
    if not isinstance(value, int):
        raise ConfigError(f"Missing required integer config value: [{section_name}] {key}")
    return value


def _required_str_list(section: dict[str, Any], section_name: str, key: str) -> tuple[str, ...]:
    value = section.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"Missing required string list config value: [{section_name}] {key}")
    return tuple(value)


def _load_site(raw: dict[str, Any]) -> SiteConfig:
    section = _section(raw, "site")
    return SiteConfig(
        base_url=_required_str(section, "site", "base_url").rstrip("/"),
        secret_key=_required_str(section, "site", "secret_key"),
        debug=_required_bool(section, "site", "debug"),
        allowed_hosts=_required_str_list(section, "site", "allowed_hosts"),
        timezone=_required_str(section, "site", "timezone"),
    )


def _load_database(raw: dict[str, Any]) -> DatabaseConfig:
    section = _section(raw, "database")
    return DatabaseConfig(
        host=_required_str(section, "database", "host"),
        port=_required_int(section, "database", "port"),
        name=_required_str(section, "database", "name"),
        user=_required_str(section, "database", "user"),
        password=_required_str(section, "database", "password"),
    )


def _load_paths(raw: dict[str, Any]) -> PathsConfig:
    section = _section(raw, "paths")
    return PathsConfig(
        public_root=Path(_required_str(section, "paths", "public_root")),
        static_root=Path(_required_str(section, "paths", "static_root")),
        media_root=Path(_required_str(section, "paths", "media_root")),
        tmp_root=Path(_required_str(section, "paths", "tmp_root")),
    )


def _load_stripe(raw: dict[str, Any]) -> StripeConfig:
    section = _section(raw, "stripe")
    return StripeConfig(
        test_secret_key=_required_str(section, "stripe", "test_secret_key"),
        test_publishable_key=_required_str(section, "stripe", "test_publishable_key"),
        test_webhook_secret=_required_str(section, "stripe", "test_webhook_secret"),
        live_secret_key=_required_str(section, "stripe", "live_secret_key"),
        live_publishable_key=_required_str(section, "stripe", "live_publishable_key"),
        live_webhook_secret=_required_str(section, "stripe", "live_webhook_secret"),
    )


def _load_backups(raw: dict[str, Any]) -> BackupsConfig:
    section = _section(raw, "backups")
    return BackupsConfig(
        database_backups_enabled=_required_bool(section, "backups", "database_backups_enabled"),
        config_backups_enabled=_required_bool(section, "backups", "config_backups_enabled"),
        media_backups_enabled=_required_bool(section, "backups", "media_backups_enabled"),
        s3_bucket=_required_str(section, "backups", "s3_bucket"),
        s3_prefix=_required_str(section, "backups", "s3_prefix"),
        local_backup_dir=Path(_required_str(section, "backups", "local_backup_dir")),
        database_retention_days=_required_int(section, "backups", "database_retention_days"),
        config_retention_days=_required_int(section, "backups", "config_retention_days"),
        media_retention_days=_required_int(section, "backups", "media_retention_days"),
        config_paths=tuple(
            Path(path) for path in _required_str_list(section, "backups", "config_paths")
        ),
    )


def _reject_aws_key_config(raw: dict[str, Any]) -> None:
    if "aws" in raw:
        raise ConfigError("Do not configure an [aws] section; V1 uses the EC2 IAM role")

    forbidden_keys = {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "aws_access_key_id",
        "aws_secret_access_key",
    }
    for section_name, section in raw.items():
        if isinstance(section, dict) and forbidden_keys.intersection(section.keys()):
            raise ConfigError(
                f"Do not configure AWS access keys in [{section_name}]; V1 uses the EC2 IAM role"
            )
