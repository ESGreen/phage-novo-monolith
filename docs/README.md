# Operational Docs

This directory contains maintainer runbooks for `thephage.org`.

Start here when preparing, deploying, testing, or recovering the production site.

## Core Runbooks

- `yearly-rollover.md`: yearly setup before opening taxes.
- `pre-launch-checklist.md`: manual smoke test before opening taxes or after major changes.
- `stripe.md`: Stripe test/live mode, payment verification, and troubleshooting.
- `backup-and-restore.md`: backup strategy, restore procedure, and restore verification.
- `deployment.md`: EC2, S3, IAM, and deployed config notes.

## Important Paths

- Real deployed config: `/etc/thephage/thephage.toml`.
- Committed config example: `deploy/thephage.toml.example`.
- Public static pages: `/public/`.
- Member/admin site: Django.

## Maintenance Rules

- Do not commit real secrets.
- Use Stripe test mode for annual payment-flow verification.
- Do not announce taxes until the final live admin payment succeeds.
- Use EC2 IAM role access for S3 backups in V1.
- Keep backup and restore tooling outside the Django web app.
