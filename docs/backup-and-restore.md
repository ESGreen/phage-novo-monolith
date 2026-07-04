# Backup And Restore Runbook

## Purpose

This document describes the backup and restore approach for `thephage.org`.

Use this when:

- Preparing for tax season.
- Verifying backups during tax season.
- Making major server or deployment changes.
- Recovering from a broken deployment.
- Recovering from database, media, or configuration loss.

## Bottom Line First

Backups are handled outside the Django web app.

The web app should not know how to back itself up.

V1 backup tooling uses external Python utility scripts:

```text
backup-thephage
restore-thephage
```

Backups are scheduled by the server, preferably with a systemd timer.

V1 runs daily backups. If the site dies during tax collection, manually reconciling a small number of transactions is acceptable.

S3 access is handled through the EC2 instance IAM role.

There is no AWS access key section in:

```text
/etc/thephage/thephage.toml
```

There are two backup layers:

- Full EC2 image backups for major changes.
- Lightweight active-season backups for database, config, and media.

## Backup Philosophy

The backup system should be boring and external.

The Django app should not perform backups because backups need access to:

- PostgreSQL dump commands.
- Deployment config files.
- Media files.
- S3 backup storage.
- Retention cleanup.
- Restore verification.

Those concerns belong to server operations, not request/response web application code.

## Backup Scripts

The backup script should be an external Python utility.

Script name:

```text
backup-thephage
```

The restore script should also be an external Python utility.

Script name:

```text
restore-thephage
```

Expected installed location:

```text
/opt/thephage/scripts/backup-thephage
/opt/thephage/scripts/restore-thephage
```

These are the documented V1 paths. If deployment needs a different path, update this runbook and the systemd units together.

## Backup Scheduling

Backups should run automatically.

Admins should not need to remember to manually create routine backups.

Preferred scheduler:

```text
systemd timer
```

Cron is acceptable if needed, but systemd timers are preferred because they provide clearer status and logs.

Useful commands:

```bash
systemctl status thephage-backup.timer
systemctl status thephage-backup.service
journalctl -u thephage-backup.service
```

For a one-off backup before a risky change:

```bash
sudo systemctl start thephage-backup.service
```

## Backup Types

### Full EC2 Image

Use EC2 images for full-machine recovery.

Create an EC2 image:

- Before tax season.
- Before OS upgrades.
- Before major package upgrades.
- Before major website deployments.
- Before risky server configuration changes.
- After tax season if a final yearly snapshot is wanted.

This is the easiest full rollback path.

### Lightweight Backups

Use lightweight backups while the site is active.

These cover:

- PostgreSQL database.
- Deployment configuration.
- Uploaded media.
- Public static files if changed on the server.

These backups upload to S3.

## S3 Backup Location

Backup S3 location is configured in:

```text
/etc/thephage/thephage.toml
```

Relevant config:

```toml
[backups]
s3_bucket = "web2-backups-thephage"
s3_prefix = "prod"
```

Expected paths:

```text
s3://web2-backups-thephage/prod/database/
s3://web2-backups-thephage/prod/config/
s3://web2-backups-thephage/prod/media/
s3://web2-backups-thephage/prod/media-manifests/
```

The bucket should be:

- Private.
- Encrypted.
- Versioned.
- Restricted to the EC2 instance IAM role.
- Not publicly accessible.

## Database Backups

Database backups should use `pg_dump`.

Recommended format:

```text
pg_dump -Fc
```

The custom format is good because it works well with `pg_restore`.

Suggested filename format:

```text
database/YYYY-MM-DD-HHMM.dump
```

Example:

```text
s3://web2-backups-thephage/prod/database/2026-07-03-0100.dump
```

V1 backup cadence:

```text
daily database backups
```

## Config Backups

Config backups should include files needed to understand or recreate the deployment.

Configured in:

```toml
[backups]
config_paths = [
  "/etc/thephage/thephage.toml",
  "/etc/nginx/sites-available/thephage",
  "/etc/systemd/system/thephage.service",
  "/etc/systemd/system/thephage-backup.service",
  "/etc/systemd/system/thephage-backup.timer",
]
```

Suggested filename format:

```text
config/YYYY-MM-DD-HHMM.tar.gz
```

Example:

```text
s3://web2-backups-thephage/prod/config/2026-07-03-0100.tar.gz
```

Config backups may contain secrets.

Protect them accordingly.

## Media Backups

Media files are uploaded through the website.

Examples:

- Profile pictures.
- Media-admin uploads.
- Images used in Markdown pages.

Media root is configured in:

```toml
[paths]
media_root = "/var/www/thephage/media"
```

Media should not be backed up as repeated full tarballs.

Media backup should use an incremental S3 sync.

Recommended behavior:

```text
media_root -> s3://web2-backups-thephage/prod/media/
```

The backup script should upload new or changed files.

Unchanged files should not be uploaded again.

Media backup should mirror deletes to S3.

If a file is deleted locally, the current S3 object should also be deleted.

The S3 bucket must use versioning so older object versions remain recoverable.

S3 lifecycle rules should expire old non-current media versions.

Default media non-current version retention:

```text
45 days
```

This keeps S3 size under control while still allowing recovery from accidental deletion or overwrite.

## Media Manifests

Each media backup run should write a small manifest.

Suggested path:

```text
s3://web2-backups-thephage/prod/media-manifests/YYYY-MM-DD-HHMM.json
```

The manifest should include at least:

```json
{
  "created_at": "2026-07-03T01:00:00Z",
  "file_count": 1234,
  "total_bytes": 1456789012,
  "media_root": "/var/www/thephage/media",
  "s3_prefix": "prod/media/"
}
```

The manifest helps verify that the media backup ran without downloading all media every night.

## Public Static File Backups

Public pages live under:

```toml
[paths]
public_root = "/var/www/thephage/public"
```

If public files are changed directly on the server, they should be backed up.

If public files are deployed from another source, that source may be the backup.

V1 default: treat public files as deployed static assets. If production public files are edited directly on the server, add `public_root` to the backup plan before doing so.

## Backup Retention

Configured in:

```toml
[backups]
database_retention_days = 30
config_retention_days = 90
media_retention_days = 45
```

Suggested starting point:

- Database backups: 30 days.
- Config backups: 90 days.
- Media non-current object versions: 45 days.

For media, retention means old S3 object versions, not repeated full media snapshots.

## What Not To Back Up Here

Stripe secrets do not need a special backup process beyond config backups.

Stripe configuration can be recreated if needed.

The expected config file format is documented in:

```text
deploy/thephage.toml.example
```

Do not write secrets into git.

## Backup Script Behavior

`backup-thephage` should:

- Read `/etc/thephage/thephage.toml`.
- Verify required backup settings exist.
- Create PostgreSQL dump if database backups are enabled.
- Archive config paths if config backups are enabled.
- Sync media to S3 if media backups are enabled.
- Mirror media deletes to S3.
- Write media manifest.
- Upload backup artifacts to S3.
- Apply retention cleanup.
- Log success or failure clearly.
- Exit non-zero on failure.

The script should not print secrets.

The script should redact sensitive values in logs.

## Restore Script Behavior

`restore-thephage` should be conservative.

Restore is dangerous and should not silently overwrite production.

The restore script should support safe operations such as:

```bash
restore-thephage list database
restore-thephage list config
restore-thephage list media
restore-thephage fetch database 2026-07-03-0100
restore-thephage verify --latest
```

Real restore actions should require explicit confirmation.

The script should:

- List available backups.
- Download selected backups.
- Restore into scratch locations for verification.
- Refuse destructive actions without explicit confirmation.
- Print what it is about to do.
- Avoid overwriting arbitrary filesystem paths.
- Avoid printing secrets.

## Restore Verification

The system should regularly prove that backups are restorable.

Do not test restore by deleting production data.

Instead, restore into scratch locations.

Recommended scheduled verification:

```bash
backup-thephage && restore-thephage verify --latest
```

Verification should use:

```text
scratch database: thephage_restore_check
scratch root: /var/tmp/thephage-restore-check
scratch config dir: /var/tmp/thephage-restore-check/config
scratch media dir: /var/tmp/thephage-restore-check/media
```

The verification step should:

- Restore latest database backup into scratch database.
- Confirm expected tables exist.
- Confirm basic expected rows exist.
- Extract latest config backup into scratch directory.
- Confirm config TOML parses.
- Verify latest media manifest exists.
- Download a small sample of media files.
- Confirm sampled media files match expected size.
- Confirm S3 media prefix is reachable.
- Delete scratch restore data when done.
- Log success or failure clearly.

Because media may be large, nightly restore verification should sample media instead of restoring all media.

## Full Media Restore Drill

Do a full media restore drill occasionally.

Recommended times:

- Before tax season.
- After backup script changes.
- After major deployment changes.

Full media restore drill should:

- Sync all media from S3 into a scratch directory.
- Compare file count to latest manifest.
- Compare total bytes to latest manifest.
- Verify a sample of files loads.
- Delete scratch restore data after verification.

## Backup Verification

Backups are only useful if they can be found and restored.

Regular checks should verify:

- Recent database backup exists.
- Recent config backup exists.
- Recent media manifest exists.
- Media S3 prefix exists.
- Backup files are non-empty.
- Backups are uploaded to S3.
- S3 bucket is reachable from EC2.
- Backup logs show success.
- Backup failures are visible to the admin/operator.

Useful commands:

```bash
aws s3 ls s3://web2-backups-thephage/prod/database/
aws s3 ls s3://web2-backups-thephage/prod/config/
aws s3 ls s3://web2-backups-thephage/prod/media/
aws s3 ls s3://web2-backups-thephage/prod/media-manifests/
```

## Restore Strategy

Pick the restore path based on what broke.

## Full Server Failure

Use EC2 image restore.

Steps:

- Launch instance from latest good EC2 image.
- Attach/restore needed volumes if applicable.
- Verify `/etc/thephage/thephage.toml`.
- Verify PostgreSQL is running.
- Verify app service is running.
- Verify Nginx/TLS.
- Run deployment verification tests.
- Check `/admin/stripe/`.
- Check `/dashboard/`.

## Broken Deployment

If the server is healthy but the app deployment is broken:

- Roll back code/deployment if possible.
- Restore config files from S3 if needed.
- Restart services.
- Run deployment verification tests.

If rollback is not practical, restore from EC2 image.

## Database Loss Or Corruption

Restore from latest known-good database backup.

High-level steps:

- Stop the web app service.
- Create a safety copy of the current broken database if possible.
- Download database backup from S3.
- Restore with `pg_restore`.
- Run migrations if needed.
- Start the web app service.
- Run deployment verification tests.
- Verify payments in `/admin/payments/`.
- Verify Stripe state in Stripe Dashboard if payments were involved.

Example restore outline:

```bash
sudo systemctl stop thephage
aws s3 cp s3://web2-backups-thephage/prod/database/YYYY-MM-DD-HHMM.dump /tmp/thephage.restore.dump
sudo -u postgres pg_dump -Fc --file=/tmp/thephage.pre-restore-safety.dump thephage
sudo -u postgres dropdb --if-exists thephage
sudo -u postgres createdb --owner=thephage thephage
sudo -u postgres pg_restore --dbname=thephage --role=thephage /tmp/thephage.restore.dump
sudo systemctl start thephage
```

These commands assume the V1 single-host PostgreSQL setup from `docs/deployment.md`.

## Config Loss Or Corruption

Restore config archive from S3.

High-level steps:

- Download config backup.
- Extract to a temporary location.
- Compare files.
- Restore needed files.
- Set correct ownership and permissions.
- Restart affected services.
- Run deployment verification tests.

Important config files may include:

- `/etc/thephage/thephage.toml`
- Nginx config.
- Systemd service file.
- Backup timer/service files.

## Media Loss

Restore media from S3.

High-level steps:

- Stop writes if needed.
- Sync media from S3 into `media_root`.
- Set correct ownership and permissions.
- Verify media URLs load.
- Verify profile photos and page images.

If the loss was accidental deletion, S3 versioning may be needed to recover older object versions.

## Payment-Specific Recovery Notes

Stripe is the source of truth for whether money moved.

If database restore affects payment records:

- Check Stripe Dashboard.
- Check recent Stripe webhook events.
- Check payment logs if available.
- Compare restored payment records to Stripe.
- Be careful not to mark someone paid unless Stripe confirms it.

If a payment is uncertain, use `requires_review`.

For V1, resolving payment review can be done directly in the database after confirming the truth in Stripe.

## Manual Restore Test

Periodically test restore on non-production infrastructure.

Suggested cadence:

- Before tax season.
- After major backup script changes.
- After major server/deployment changes.

Test should verify:

- Database backup can restore.
- Config backup can be opened and understood.
- Media backup can be sampled or fully restored.
- App can start with restored data if practical.
- Deployment verification tests pass.

## Settled Backup Details

Backup script path:

```text
/opt/thephage/scripts/backup-thephage
```

Restore script path:

```text
/opt/thephage/scripts/restore-thephage
```

Backup scheduler:

```text
systemd timer
```

Backup cadence:

```text
daily at 09:30 UTC
```

Service and timer names:

```text
thephage-backup.service
thephage-backup.timer
```

Application service name:

```text
thephage.service
```

Nginx config path:

```text
/etc/nginx/sites-available/thephage
```

Backup logs:

```text
journalctl -u thephage-backup.service
```

S3 bucket:

```text
web2-backups-thephage
```

EC2 IAM role:

```text
thephage-web-role
```

Backup failure notification:

```text
manual V1 monitoring through systemd status and journal logs
```

Manual V1 monitoring is acceptable because daily backups are enough for the expected risk. Operators should check backup status before tax season, after deployments, and during operational reviews.

Media manifest format:

```json
{
  "created_at": "2026-07-03T01:00:00Z",
  "file_count": 1234,
  "total_bytes": 1456789012,
  "media_root": "/var/www/thephage/media",
  "s3_prefix": "prod/media/"
}
```

Media sync command shape:

```bash
aws s3 sync "$MEDIA_ROOT/" "s3://$S3_BUCKET/$S3_PREFIX/media/" --delete
```

The Python backup script may use AWS SDK calls instead of shelling out, but behavior should match this command: incremental upload with mirrored deletes.

## Backup Timer Unit

Service path:

```text
/etc/systemd/system/thephage-backup.service
```

Service unit:

```ini
[Unit]
Description=Back up The Phage website
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=oneshot
User=phage
Group=phage
Environment=THEPHAGE_CONFIG=/etc/thephage/thephage.toml
ExecStart=/opt/thephage/scripts/backup-thephage
```

Timer path:

```text
/etc/systemd/system/thephage-backup.timer
```

Timer unit:

```ini
[Unit]
Description=Run The Phage backup daily

[Timer]
OnCalendar=*-*-* 09:30:00
Persistent=true
RandomizedDelaySec=15m

[Install]
WantedBy=timers.target
```

Enable the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now thephage-backup.timer
systemctl list-timers | grep thephage-backup
```
