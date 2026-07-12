# Deployment Runbook

## Purpose

This document describes the V1 production deployment target for `thephage.org`.

V1 is a single-machine EC2 deployment. Future containerization should remain possible, but containers are intentionally out of scope for the first deployment because they add operational complexity that is not needed yet.

## Deployment Summary

Settled V1 choices:

- OS: Ubuntu 24.04 LTS.
- Runtime: host install, not containerized.
- App user/group: `phage:phage`.
- Python: host Python 3.12 with a virtualenv.
- Database: PostgreSQL on the same EC2 instance.
- Web app service: Gunicorn managed by systemd.
- Reverse proxy/static serving: Nginx on host.
- TLS: Let's Encrypt with certbot.
- Backups: external Python scripts scheduled by systemd timer.
- S3 access: EC2 IAM role only, no AWS keys in TOML.

## Important Paths

Application paths:

```text
/opt/thephage/app
/opt/thephage/venv
/opt/thephage/scripts
```

Configuration:

```text
/etc/thephage/thephage.toml
```

Web file roots:

```text
/var/www/thephage/public
/var/www/thephage/static
/var/www/thephage/media
```

The application checkout under `/opt/thephage/app` is not the web root. Nginx serves only selected file roots under `/var/www/thephage`:

- `/opt/thephage/app/public/` is source content copied to `/var/www/thephage/public/`.
- `/opt/thephage/app/static/` is source content collected by Django into `/var/www/thephage/static/`.
- Uploaded files are written directly to `/var/www/thephage/media/` through Django's media storage.

Runtime and backup paths:

```text
/run/thephage
/var/tmp/thephage
/var/backups/thephage
```

## Ubuntu Packages

Install these packages on Ubuntu 24.04 LTS:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip postgresql postgresql-contrib nginx certbot python3-certbot-nginx awscli rsync
```

Optional operational packages:

```bash
sudo apt install git curl vim
```

## System User And Directories

Create the app user and group:

```bash
sudo addgroup --system phage
sudo adduser --system --ingroup phage --home /opt/thephage --shell /usr/sbin/nologin phage
sudo usermod --append --groups phage www-data
```

Adding `www-data` to the `phage` group lets Nginx connect to the Gunicorn Unix socket.

Create directories:

```bash
sudo mkdir -p /opt/thephage/app /opt/thephage/scripts /etc/thephage /var/www/thephage/public /var/www/thephage/static /var/www/thephage/media /var/tmp/thephage /var/backups/thephage
```

Set ownership:

```bash
sudo chown -R phage:phage /opt/thephage /var/www/thephage /var/tmp/thephage /var/backups/thephage
sudo chown root:phage /etc/thephage
sudo chmod 0750 /etc/thephage
```

The config file should be readable only by `root` and `phage`:

```bash
sudo chown root:phage /etc/thephage/thephage.toml
sudo chmod 0640 /etc/thephage/thephage.toml
```

## Python Virtualenv

Create the virtualenv:

```bash
sudo -u phage python3 -m venv /opt/thephage/venv
```

Install app dependencies after code is deployed:

```bash
sudo -u phage /opt/thephage/venv/bin/pip install --upgrade pip
sudo -u phage /opt/thephage/venv/bin/pip install -r /opt/thephage/app/requirements.txt
```

If the project uses `pyproject.toml` instead of `requirements.txt`, install from the app checkout:

```bash
sudo -u phage /opt/thephage/venv/bin/pip install /opt/thephage/app
```

## PostgreSQL

PostgreSQL runs on the same EC2 instance in V1.

Database settings:

```text
database name: thephage
database user: thephage
host: localhost
port: 5432
```

Create the database and user:

```bash
sudo -u postgres createuser --pwprompt thephage
sudo -u postgres createdb --owner=thephage thephage
```

Store the same database password in:

```text
/etc/thephage/thephage.toml
```

PostgreSQL should only listen locally unless a future deployment explicitly changes that.

## Config File

The deployed config file is:

```text
/etc/thephage/thephage.toml
```

The committed example file is:

```text
deploy/thephage.toml.example
```

The real config file contains:

- Django secret key.
- Database password.
- Stripe keys.
- Backup bucket and prefix.
- Local filesystem paths.

The real config file does not contain AWS access keys in V1.

## systemd App Service

Service path:

```text
/etc/systemd/system/thephage.service
```

Unit contents:

```ini
[Unit]
Description=The Phage Django application
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=phage
Group=phage
WorkingDirectory=/opt/thephage/app
Environment=THEPHAGE_CONFIG=/etc/thephage/thephage.toml
RuntimeDirectory=thephage
RuntimeDirectoryMode=0755
ExecStart=/opt/thephage/venv/bin/gunicorn thephage.wsgi:application --bind unix:/run/thephage/gunicorn.sock --umask 007 --workers 3 --timeout 60 --access-logfile - --error-logfile -
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

Useful commands:

```bash
sudo systemctl daemon-reload
sudo systemctl enable thephage.service
sudo systemctl start thephage.service
sudo systemctl status thephage.service
journalctl -u thephage.service
```

## Nginx

Nginx site config path:

```text
/etc/nginx/sites-available/thephage
```

Initial HTTP config before certbot:

```nginx
upstream thephage_app {
    server unix:/run/thephage/gunicorn.sock fail_timeout=0;
}

server {
    listen 80;
    listen [::]:80;
    server_name thephage.org www.thephage.org;

    client_max_body_size 10M;

    location = / {
        return 302 /public/;
    }

    location = /public {
        return 301 /public/;
    }

    location /public/ {
        alias /var/www/thephage/public/;
        try_files $uri $uri/ =404;
    }

    location /static/ {
        alias /var/www/thephage/static/;
        try_files $uri =404;
    }

    location /media/ {
        alias /var/www/thephage/media/;
        try_files $uri =404;
    }

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_pass http://thephage_app;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/thephage /etc/nginx/sites-enabled/thephage
sudo nginx -t
sudo systemctl reload nginx
```

If the default Nginx site is enabled and conflicts, disable it:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

## TLS With Let's Encrypt

Use certbot's Nginx integration:

```bash
sudo certbot --nginx -d thephage.org -d www.thephage.org
```

Verify renewal:

```bash
sudo certbot renew --dry-run
```

Certbot should install or use a systemd timer for renewals on Ubuntu 24.04.

Check renewal timer:

```bash
systemctl list-timers | grep certbot
```

## EC2 And S3 Backup Access

For V1, the website runs on an EC2 instance and accesses the S3 backup bucket through the EC2 instance IAM role.

There is no `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or `[aws]` section in `/etc/thephage/thephage.toml`.

If, in the future, backups need to write to S3 using explicit AWS access keys, that path must be designed and documented separately.

## S3 Backup Bucket

Create a private encrypted S3 bucket for backups:

```text
web2-backups-thephage
```

Recommended settings:

- Block all public access.
- Enable default server-side encryption.
- Enable bucket versioning.
- Restrict access to the EC2 instance IAM role.
- Use lifecycle rules for backup retention.
- Expire non-current media object versions after 45 days by default.

Expected backup paths:

```text
s3://web2-backups-thephage/prod/database/
s3://web2-backups-thephage/prod/config/
s3://web2-backups-thephage/prod/media/
s3://web2-backups-thephage/prod/media-manifests/
```

These correspond to:

```toml
[backups]
s3_bucket = "web2-backups-thephage"
s3_prefix = "prod"
```

## EC2 IAM Role

Create an IAM role for the EC2 instance:

```text
thephage-web-role
```

Attach this role to the EC2 instance that runs the website.

The role should allow only the S3 actions needed for backups.

Minimum useful permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListBackupBucket",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:ListBucketVersions"
      ],
      "Resource": "arn:aws:s3:::web2-backups-thephage",
      "Condition": {
        "StringLike": {
          "s3:prefix": [
            "prod/*"
          ]
        }
      }
    },
    {
      "Sid": "ReadWriteBackupObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::web2-backups-thephage/prod/*"
    }
  ]
}
```

If backups later use multipart uploads, add the required multipart permissions.

Media backups should use incremental S3 sync rather than repeated full media archives. Deletes should be mirrored to S3, with bucket versioning and lifecycle rules providing the recovery window for accidental deletes or overwrites.

## Verify S3 Access From EC2

After attaching the IAM role, verify from the EC2 instance that S3 access works without AWS keys in the config file.

Check instance identity:

```bash
aws sts get-caller-identity
```

List the backup prefix:

```bash
aws s3 ls s3://web2-backups-thephage/prod/
```

Test write/delete access under the backup prefix:

```bash
sudo -u phage touch /var/backups/thephage/test.txt
aws s3 cp /var/backups/thephage/test.txt s3://web2-backups-thephage/prod/test.txt
aws s3 rm s3://web2-backups-thephage/prod/test.txt
sudo rm -f /var/backups/thephage/test.txt
```

The instance should not be able to write outside the configured backup prefix.

## Backup Timer

Daily backups are acceptable for V1.

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

The server should use UTC time. `09:30 UTC` is overnight in Pacific time.

Enable the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now thephage-backup.timer
systemctl list-timers | grep thephage-backup
```

Manual V1 backup failure monitoring is acceptable. Operators should check backup status before tax season, after deployments, and during normal operational reviews:

```bash
systemctl status thephage-backup.timer
systemctl status thephage-backup.service
journalctl -u thephage-backup.service
```

## File Ownership And Permissions

Recommended ownership:

```text
/opt/thephage              phage:phage
/opt/thephage/app          phage:phage
/opt/thephage/venv         phage:phage
/opt/thephage/scripts      phage:phage
/var/www/thephage/public   phage:phage
/var/www/thephage/static   phage:phage
/var/www/thephage/media    phage:phage
/var/tmp/thephage          phage:phage
/var/backups/thephage      phage:phage
/etc/thephage              root:phage
/etc/thephage/thephage.toml root:phage mode 0640
```

Recommended directory modes:

```text
/opt/thephage/app        0755
/opt/thephage/venv       0755
/opt/thephage/scripts    0755
/var/www/thephage/public 0755
/var/www/thephage/static 0755
/var/www/thephage/media  0755
/var/tmp/thephage        0750
/var/backups/thephage    0750
/etc/thephage            0750
```

Nginx needs read access to public/static/media files. It does not need read access to `/etc/thephage/thephage.toml`.

## Deployment Command Sequence

High-level deployment sequence:

1. Create/update EC2 instance with Ubuntu 24.04 LTS.
2. Attach IAM role `thephage-web-role`.
3. Install Ubuntu packages.
4. Create `phage` user/group and directories.
5. Create PostgreSQL user/database.
6. Copy `/etc/thephage/thephage.toml` from `deploy/thephage.toml.example` and fill secrets.
7. Deploy code to `/opt/thephage/app`.
8. Create/update virtualenv and install dependencies.
9. Run Django checks and migrations.
10. Sync public files.
11. Collect Django static files.
12. Create first admin if needed.
13. Install/update `thephage.service`.
14. Install/update Nginx site config.
15. Start/restart the app service.
16. Reload Nginx.
17. Run certbot for TLS if this is the first deployment.
18. Install/update backup scripts and timer.
19. Run deployment verification checks.

Representative commands after code is deployed:

```bash
sudo -u phage /opt/thephage/venv/bin/pip install -r /opt/thephage/app/requirements.txt
sudo -u phage THEPHAGE_CONFIG=/etc/thephage/thephage.toml /opt/thephage/venv/bin/python /opt/thephage/app/manage.py check
sudo -u phage THEPHAGE_CONFIG=/etc/thephage/thephage.toml /opt/thephage/venv/bin/python /opt/thephage/app/manage.py migrate
sudo -u phage rsync -a --delete /opt/thephage/app/public/ /var/www/thephage/public/
sudo -u phage THEPHAGE_CONFIG=/etc/thephage/thephage.toml /opt/thephage/venv/bin/python /opt/thephage/app/manage.py collectstatic --noinput
sudo systemctl restart thephage.service
sudo nginx -t
sudo systemctl reload nginx
```

## Logs

Primary app logs:

```bash
journalctl -u thephage.service
```

Backup logs:

```bash
journalctl -u thephage-backup.service
```

Nginx logs:

```text
/var/log/nginx/
```

## Future Containerization Note

The V1 deployment intentionally runs directly on the host. Future containerization should be possible if operational needs change.

If containerization is added later, prefer containerizing the Django/Gunicorn app first while keeping Nginx, certbot, PostgreSQL, media files, and backup timers on the host unless there is a clear reason to move them too.
