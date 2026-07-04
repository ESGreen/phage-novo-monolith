#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON="${PROJECT_ROOT}/.venv/bin/python"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Expected virtualenv Python at: ${PYTHON}" >&2
  echo "Create/install the project virtualenv first." >&2
  exit 1
fi

RUNTIME_ROOT="${THEPHAGE_TEST_SERVER_ROOT:-/tmp/thephage-test-server}"
HOST="${THEPHAGE_TEST_SERVER_HOST:-127.0.0.1}"
PORT="${THEPHAGE_TEST_SERVER_PORT:-8000}"
LINK_HOST="127.0.0.1"

CONFIG_PATH="${RUNTIME_ROOT}/thephage.toml"
SQLITE_PATH="${RUNTIME_ROOT}/thephage.sqlite3"
PUBLIC_ROOT="${RUNTIME_ROOT}/public"
STATIC_ROOT="${RUNTIME_ROOT}/static"
MEDIA_ROOT="${RUNTIME_ROOT}/media"
TMP_ROOT="${RUNTIME_ROOT}/tmp"
BACKUP_ROOT="${RUNTIME_ROOT}/backups"

mkdir -p "${PUBLIC_ROOT}" "${STATIC_ROOT}" "${MEDIA_ROOT}" "${TMP_ROOT}" "${BACKUP_ROOT}"

cat > "${CONFIG_PATH}" <<EOF
[site]
base_url = "http://${LINK_HOST}:${PORT}"
secret_key = "test-server-secret-key-not-for-production"
debug = true
allowed_hosts = ["127.0.0.1", "localhost", "testserver"]
timezone = "America/Los_Angeles"

[database]
host = "localhost"
port = 5432
name = "unused_sqlite_test_server"
user = "unused"
password = "unused"

[paths]
public_root = "${PUBLIC_ROOT}"
static_root = "${STATIC_ROOT}"
media_root = "${MEDIA_ROOT}"
tmp_root = "${TMP_ROOT}"

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
s3_prefix = "local-test"
local_backup_dir = "${BACKUP_ROOT}"
database_retention_days = 30
config_retention_days = 90
media_retention_days = 45
config_paths = ["${CONFIG_PATH}"]
EOF

cat > "${PUBLIC_ROOT}/index.html" <<'EOF'
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>The Phage Test Server</title>
  </head>
  <body>
    <h1>The Phage Test Server</h1>
    <p><a href="/login/">Log in</a> with phage@phage.com / 12345.</p>
  </body>
</html>
EOF

export THEPHAGE_CONFIG="${CONFIG_PATH}"
export THEPHAGE_SQLITE_PATH="${SQLITE_PATH}"

"${PYTHON}" "${PROJECT_ROOT}/manage.py" migrate --noinput

"${PYTHON}" "${PROJECT_ROOT}/manage.py" shell <<'PY'
from datetime import timedelta

from django.utils import timezone

from accounts.models import User
from camp.models import CampYear, TaxAddOn, TaxTier
from content.models import ContentPage, Menu, MenuItem

user, _ = User.objects.get_or_create(email="phage@phage.com")
user.first_name = "Phage"
user.last_name = "Phage"
user.is_active = True
user.is_admin = True
user.set_password("12345")
user.save(update_fields=["first_name", "last_name", "is_active", "is_admin", "password", "updated_at"])

dashboard_page, _ = ContentPage.objects.update_or_create(
    slug="test-dashboard-welcome",
    defaults={
        "title": "Test Dashboard Welcome",
        "body_markdown": "# Welcome\n\nThis local test server is seeded with a demo admin account.",
    },
)

camp_year, _ = CampYear.objects.update_or_create(
    year=timezone.now().year,
    defaults={"dashboard_pre_page": dashboard_page},
)

root_menu, _ = Menu.objects.get_or_create(menu_name=Menu.ROOT_MENU_NAME)
for label, url, display_order in [
    ("Dashboard", "/dashboard/", 1),
    ("Profile", "/profile/", 2),
    ("Admin", "/admin/", 3),
]:
    MenuItem.objects.update_or_create(
        menu=root_menu,
        label=label,
        defaults={"url": url, "display_order": display_order},
    )

now = timezone.now()
TaxTier.objects.update_or_create(
    camp_year=camp_year,
    name="Test Standard",
    defaults={
        "description": "Seeded test tier.",
        "minimum_amount_cents": 10000,
        "start_date": now - timedelta(days=1),
        "expiration_date": now + timedelta(days=365),
        "display_order": 1,
    },
)
TaxAddOn.objects.update_or_create(
    camp_year=camp_year,
    name="Test Add-on",
    defaults={
        "description": "Seeded optional add-on.",
        "amount_cents": 2500,
        "start_date": now - timedelta(days=1),
        "expiration_date": now + timedelta(days=365),
        "display_order": 1,
    },
)

print("Seeded phage@phage.com / 12345")
PY

echo
echo "The Phage test server is ready."
echo "URL:      http://${LINK_HOST}:${PORT}/login/"
echo "Admin:    http://${LINK_HOST}:${PORT}/admin/"
echo "Email:    phage@phage.com"
echo "Password: 12345"
echo "SQLite:   ${SQLITE_PATH}"
echo "Config:   ${CONFIG_PATH}"
echo

exec "${PYTHON}" "${PROJECT_ROOT}/manage.py" runserver "${HOST}:${PORT}"
