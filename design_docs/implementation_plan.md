# Implementation Plan

## Purpose

This document defines how to build the V1 Django app.

The goal is to turn the design docs into a concrete, small implementation plan before writing application code.

## Build Strategy

Build the app in thin vertical slices.

Recommended sequence:

1. Project skeleton and config loading.
2. Custom user model and authentication.
3. Member layout, login/logout, profile page.
4. Content pages, Markdown rendering, media uploads.
5. Menus and `/menu/<menu_name>/` pages.
6. Camp years and dashboard.
7. Tax tiers, add-ons, overrides, and tax page.
8. Stripe Checkout and webhooks.
9. Admin pages.
10. Deployment checks and operational polish.

Avoid building all admin pages before the member flow exists. Each feature should include model, admin UI, member UI if needed, and tests close together.

Tests should be written alongside the relevant implementation work. The codebase should stay in a continuous state of testing rather than accumulating untested features to cover later.

## Project Layout

Recommended Django project structure:

```text
thephage/
  manage.py
  pyproject.toml
  README.md

  thephage/
    __init__.py
    asgi.py
    settings.py
    urls.py
    wsgi.py
    config.py

  accounts/
    models.py
    forms.py
    views.py
    urls.py
    tests/

  core/
    models.py
    views.py
    urls.py
    middleware.py
    templatetags/
    tests/

  content/
    models.py
    forms.py
    views.py
    urls.py
    markdown.py
    tests/

  camp/
    models.py
    forms.py
    views.py
    urls.py
    tests/

  payments/
    models.py
    forms.py
    views.py
    urls.py
    stripe_client.py
    webhooks.py
    tests/

  adminui/
    views.py
    urls.py
    forms.py
    tests/

  templates/
    base.html
    public_base.html
    member_base.html
    admin_base.html

  static/
    css/
    js/

  public/
    index.html
```

## Django Apps

### `accounts`

Owns:

- `User`.
- `MemberProfile`.
- Login/logout.
- Profile editing.
- Password change.
- Account/admin user forms.

### `core`

Owns:

- Shared utilities.
- `SiteSettings`.
- Root redirects.
- Dashboard redirect helper.
- Shared template context.
- Health/config checks if needed.

### `content`

Owns:

- `ContentPage`.
- `Menu`.
- `MenuItem`.
- `MediaItem`.
- Markdown rendering/sanitization.
- Media upload helpers.
- `/pages/<slug>/`.
- `/menu/<menu_name>/`.

### `camp`

Owns:

- `CampYear`.
- `TaxTier`.
- `TaxAddOn`.
- `TaxOverride`.
- Dashboard page.
- Taxes page before Stripe handoff.
- Tax availability/minimum calculation.

### `payments`

Owns:

- `Payment`.
- `PaymentAddOn`.
- `PaymentLog`.
- Stripe Checkout creation.
- Stripe webhook handling.
- Test payment cleanup logic.

### `adminui`

Owns product admin views under `/admin/`.

This is intentionally separate from Django's built-in admin.

Admin sections:

- `/admin/`.
- `/admin/users/`.
- `/admin/camp/`.
- `/admin/payments/`.
- `/admin/stripe/`.
- `/admin/pages/`.
- `/admin/menus/`.
- `/admin/media/`.

## Dependencies

Recommended dependencies:

```text
Django
psycopg[binary]
stripe
tomli; python_version < "3.11"
markdown
bleach
Pillow
gunicorn
pytest
pytest-django
freezegun
requests
```

Optional local/dev helpers:

```text
ruff
django-debug-toolbar
```

Keep dependencies boring and common.

## Configuration Loading

Real deployed config:

```text
/etc/thephage/thephage.toml
```

Committed example:

```text
deploy/thephage.toml.example
```

Config loader:

```text
thephage/config.py
```

Behavior:

- Load TOML config once at startup.
- Validate required sections.
- Validate required production settings.
- Provide typed accessors or a small config object.
- Never log secret values.

Required sections:

```text
[site]
[database]
[paths]
[stripe]
[backups]
```

Settings read from TOML:

- `SECRET_KEY`.
- `DEBUG`.
- `ALLOWED_HOSTS`.
- Timezone.
- Database config.
- Public/static/media/tmp paths.
- Stripe credentials.
- Backup config used by external scripts.

## Local Development Config

Use one of these approaches:

Option A:

```text
THEPHAGE_CONFIG=/path/to/local/thephage.toml
```

Option B:

```text
config/local.thephage.toml
```

Recommended:

- Use `THEPHAGE_CONFIG` for local override.
- Default to `/etc/thephage/thephage.toml` when env var is absent.
- Do not commit real local secrets.
- Commit only example config.

## Settings Rules

Production:

- `DEBUG = false`.
- Secure cookies enabled.
- HTTPS expected.
- PostgreSQL only.
- Real media/static/public paths.
- Stripe test/live credentials configured.

Development:

- `DEBUG = true` allowed.
- Local PostgreSQL preferred.
- Local media/static/public paths allowed.
- Stripe test credentials only.

## URL Layout

Project URL includes:

```text
/
/login/
/logout/
/dashboard/
/<year>/
/<year>/dashboard/
/<year>/taxes/
/<year>/taxes/return/
/profile/
/pages/<slug>/
/menu/<menu_name>/
/stripe/webhook/
/admin/
```

Static handling:

- `/public/` serves hand-written public pages.
- `/static/` serves collected Django static assets.
- `/media/` serves uploaded media.

## Authentication

Use custom `User` from the first migration.

Rules:

- Email login.
- No username.
- Normalize email with `.lower()`.
- `is_active` controls login.
- `is_admin` controls product admin access.
- Members can change password from `/profile/`.
- Admins can manually set/reset passwords from `/admin/users/`.

Password policy:

- Minimum 10 characters.
- Unicode allowed.
- At least two character classes:
  - Letters.
  - Numbers.
  - Punctuation.
  - Other Unicode.

## Permissions

Implement decorators or mixins:

```text
member_required
admin_required
```

Rules:

- Anonymous users redirect to `/login/`.
- Non-admin authenticated users receive `403` for admin pages.
- Inactive users cannot log in.
- Admins can access member pages.

## Management Commands

Required commands:

```text
create_admin
check_config
check_stripe
```

### `create_admin`

Purpose:

- Create first admin account from command line.
- Useful before any admin users exist.

Inputs:

```text
--email
--first-name
--last-name
--password
```

Behavior:

- Creates active user.
- Sets `is_admin = true`.
- Creates member profile.
- Refuses duplicate email.

### `check_config`

Purpose:

- Validate TOML config and deployment-critical settings.

Checks:

- Config file exists.
- Required sections exist.
- Required secrets are non-empty.
- Database settings present.
- Path settings present.
- Stripe settings present.
- No AWS key settings required for V1.
- Production safety checks if `debug = false`.

### `check_stripe`

Purpose:

- Validate Stripe mode/config can be loaded.

Checks:

- Test keys present.
- Live keys present.
- Webhook secrets present.
- Current `SiteSettings.stripe_mode` is valid.
- Does not print secrets.
- Does not create payments.

Optional later command:

```text
create_camp_year
```

## Shared Services

Keep logic out of views where it improves clarity.

Recommended service modules:

```text
content/markdown.py
content/media.py
camp/taxes.py
payments/stripe_client.py
payments/webhooks.py
```

### `camp/taxes.py`

Owns:

- Current year lookup.
- Available tier lookup.
- Available add-on lookup.
- Effective minimum calculation.
- Paid/waived status calculation.

### `payments/stripe_client.py`

Owns:

- Stripe client setup by mode.
- Checkout Session creation.
- Idempotency key creation.
- Line item creation.
- Metadata creation.

### `payments/webhooks.py`

Owns:

- Signature verification.
- Event routing.
- Payment verification.
- Idempotent state transitions.
- Payment logging.

## Templates

Base templates:

```text
base.html
public_base.html
member_base.html
admin_base.html
```

Rules:

- Public pages do not show member menu.
- Member pages show `root` menu.
- Admin pages show admin navigation and link back to member site.
- Forms render field errors clearly.
- Flash messages show success/error states.

## Static, Public, And Media Files

Public files:

```text
/public/
```

Django static assets:

```text
/static/
```

Uploaded media:

```text
/media/
```

Rules:

- Do not mix public static pages with Django static assets.
- Do not mix uploaded media with public static pages.
- Media file paths are relative to `media_root`.
- V1 media folder is flat.

## Initial Data

Required initial data:

- `SiteSettings` singleton row.
- `root` menu.
- First admin user.
- At least one camp year before member dashboard works.

Creation approach:

- Migrations may create `SiteSettings` and `root` menu.
- `create_admin` creates first admin user.
- Admin UI creates camp year and content.

## Error Handling

Use simple, explicit behavior:

- `404` for missing pages, menus, years.
- `403` for non-admin admin access.
- Friendly form errors for validation.
- Payment mismatches become `requires_review`.
- Stripe webhook signature failures return `400`.

## What Not To Build In V1

- Email sending.
- Email password reset.
- Email confirmation.
- Public registration.
- Two-factor auth.
- Member impersonation.
- Rich CMS.
- Nested menu trees.
- Hover-only dropdown menus.
- Survey/jobs/roster models.
- Multi-currency payments.
- Non-card Stripe payment methods.
- Image resizing.
