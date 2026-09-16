from pathlib import Path

import pytest

from thephage.config import ConfigError, get_config_path, load_config

FIXTURE_CONFIG = Path("tests/fixtures/thephage.test.toml")


def test_load_config_reads_all_sections() -> None:
    config = load_config(FIXTURE_CONFIG)

    assert config.site.base_url == "http://testserver"
    assert config.site.allowed_hosts == ("testserver", "localhost")
    assert config.site.timezone == "America/Los_Angeles"
    assert config.database.name == "thephage_test"
    assert config.paths.media_root == Path("/tmp/thephage-test/media")
    assert config.paths.reimbursement_receipt_root == Path(
        "/tmp/thephage-test/private/reimbursement-receipts"
    )
    assert config.stripe.test_secret_key == "sk_test_dummy"
    assert config.backups.s3_bucket == "web2-backups-thephage"
    assert config.backups.media_retention_days == 45


def test_config_path_uses_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THEPHAGE_CONFIG", "/tmp/example.toml")

    assert get_config_path() == Path("/tmp/example.toml")


def test_load_config_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="does not exist"):
        load_config(tmp_path / "missing.toml")


def test_load_config_rejects_aws_section(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
[site]
base_url = "http://testserver"
secret_key = "test"
debug = true
allowed_hosts = ["testserver"]
timezone = "America/Los_Angeles"

[database]
host = "localhost"
port = 5432
name = "thephage_test"
user = "thephage"
password = "test"

[paths]
public_root = "/tmp/public"
static_root = "/tmp/static"
media_root = "/tmp/media"
tmp_root = "/tmp/tmp"
reimbursement_receipt_root = "/tmp/private/reimbursement-receipts"

[stripe]
test_secret_key = "sk_test_dummy"
test_publishable_key = "pk_test_dummy"
test_webhook_secret = "whsec_test_dummy"
live_secret_key = "sk_live_dummy"
live_publishable_key = "pk_live_dummy"
live_webhook_secret = "whsec_live_dummy"

[backups]
database_backups_enabled = true
config_backups_enabled = true
media_backups_enabled = true
s3_bucket = "web2-backups-thephage"
s3_prefix = "test"
local_backup_dir = "/tmp/backups"
database_retention_days = 30
config_retention_days = 90
media_retention_days = 45
config_paths = []

[aws]
region = "us-west-2"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="EC2 IAM role"):
        load_config(config_path)


def test_reimbursement_receipt_root_must_be_outside_media(tmp_path: Path) -> None:
    config_text = FIXTURE_CONFIG.read_text(encoding="utf-8").replace(
        'reimbursement_receipt_root = "/tmp/thephage-test/private/reimbursement-receipts"',
        'reimbursement_receipt_root = "/tmp/thephage-test/media/receipts"',
    )
    config_path = tmp_path / "unsafe.toml"
    config_path.write_text(config_text, encoding="utf-8")

    with pytest.raises(ConfigError, match="outside media_root"):
        load_config(config_path)
