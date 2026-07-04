# Deployment Runbook

## EC2 And S3 Backup Access

For V1, the website runs on an EC2 instance and accesses the S3 backup bucket through the EC2 instance IAM role.

There is no `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or `[aws]` section in `/etc/thephage/thephage.toml`.

If, in the future, backups need to write to S3 using explicit AWS access keys, that path must be designed and documented separately.

## S3 Backup Bucket

Create a private encrypted S3 bucket for backups.

Example:

```text
thephage-backups
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
s3://thephage-backups/prod/database/
s3://thephage-backups/prod/config/
s3://thephage-backups/prod/media/
s3://thephage-backups/prod/media-manifests/
```

These correspond to:

```toml
[backups]
s3_bucket = "thephage-backups"
s3_prefix = "prod"
```

## EC2 IAM Role

Create an IAM role for the EC2 instance.

Example role name:

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
      "Resource": "arn:aws:s3:::thephage-backups",
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
      "Resource": "arn:aws:s3:::thephage-backups/prod/*"
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
aws s3 ls s3://thephage-backups/prod/
```

Test write/delete access under the backup prefix:

```bash
aws s3 cp /var/backups/thephage/test.txt s3://thephage-backups/prod/test.txt
aws s3 rm s3://thephage-backups/prod/test.txt
```

The instance should not be able to write outside the configured backup prefix.

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

## Settled Deployment Details

Application service name:

```text
thephage.service
```

Backup service and timer names:

```text
thephage-backup.service
thephage-backup.timer
```

Nginx site config path:

```text
/etc/nginx/sites-available/thephage
```

Primary app logs should be available through:

```bash
journalctl -u thephage.service
```

Backup logs should be available through:

```bash
journalctl -u thephage-backup.service
```

Nginx access/error logs should use the normal Nginx log location unless deployment later changes it:

```text
/var/log/nginx/
```

## Remaining Deployment TODOs

TODO: Exact Linux distribution.

TODO: App user/group name.

TODO: Python install method.

TODO: Exact Gunicorn/systemd service unit contents.

TODO: Exact Nginx config contents.

TODO: TLS certificate setup.

TODO: Exact backup timer schedule and unit contents.

TODO: Exact deployment command sequence.

TODO: Static/public/media file ownership and permissions.
