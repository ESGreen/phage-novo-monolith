# Testing Implementation

## Purpose

This document defines how tests should be written while implementing the V1 Django app.

The goal is to keep the codebase continuously testable as features are added.

## Core Rule

Tests should be written alongside the relevant implementation code.

Do not build large untested areas and backfill tests later.

Each feature slice should include:

- Model tests where model behavior matters.
- Form tests for validation.
- View tests for permissions, redirects, and successful rendering.
- Service tests for business logic.
- Integration tests for important end-to-end flows.
- Regression tests for bugs as they are found.

## Test Stack

Use:

```text
pytest
pytest-django
freezegun
requests
```

Recommended optional helpers:

```text
pytest-mock
responses
```

Do not call real Stripe from automated tests.

## Test Layout

Each app should own its tests:

```text
accounts/tests/
core/tests/
content/tests/
camp/tests/
payments/tests/
adminui/tests/
```

Recommended structure:

```text
tests/
  test_models.py
  test_forms.py
  test_views.py
  test_services.py
```

Use app-local tests when possible. Use cross-app integration tests only when a flow truly crosses app boundaries.

## Pytest Markers

Recommended markers:

```text
unit
integration
stripe
slow
```

Rules:

- Default test run excludes `deployment`.
- Stripe tests use mocks/fakes.
- Deployment tests run only when explicitly requested.

## Fixtures

Provide small, explicit fixtures:

- Active member user.
- Admin user.
- Inactive user.
- Current camp year.
- Old camp year.
- Content page.
- Root menu.
- Non-root menu.
- Tax tier.
- Tax add-on.
- Reduced minimum override.
- Tax waived override.
- Created payment.
- Paid payment.
- Failed/cancelled payment.
- Temporary media directory.
- Stripe settings.

Fixtures should avoid hidden global assumptions.

Prefer creating data inside the test when that makes the test clearer.

## Continuous Testing Workflow

When implementing a feature:

1. Add or update model tests.
2. Add form validation tests.
3. Add service/business-logic tests.
4. Add view/permission tests.
5. Add one integration test if the feature has a meaningful user flow.
6. Run the relevant app tests.
7. Run the full test suite before considering the feature done.

Definition of done for a feature:

- Relevant tests exist.
- Relevant tests pass.
- No unrelated test failures.
- New behavior is covered at the level where bugs are most likely.

## Accounts Tests

Cover:

- User can log in with email.
- Username is not required.
- Email is normalized lowercase.
- Duplicate email is rejected.
- Inactive user cannot log in.
- `is_admin` controls admin access.
- Profile is created for each user.
- Member can edit name and bio.
- Member bio Markdown renders safely.
- Member can replace profile photo.
- Member cannot self-delete photo in V1.
- Member can change password with old password and new password twice.
- Wrong old password rejects password change.
- Weak password rejects password change.
- Email change requires on-page confirmation.

## Permission Tests

Cover:

- Anonymous member-page access redirects to `/login/`.
- Anonymous admin-page access redirects to `/login/`.
- Active member can access member pages.
- Active member receives `403` for admin pages.
- Active admin can access admin pages.
- Inactive users cannot log in.
- Admins can access member pages.

## Content And Markdown Tests

Cover:

- Admin can create/edit/delete content pages.
- Content page slug uniqueness.
- Missing content page returns `404`.
- Content page requires login.
- Markdown renders headings, lists, links, images, code, and pipe tables.
- Raw unsafe HTML is neutralized.
- `javascript:` links are blocked.
- Event attributes are stripped.
- Raw HTML tables are not trusted as an authoring feature.
- Sanitized output is the only HTML marked safe.

## Media Tests

Cover:

- Valid JPEG upload accepted.
- Valid PNG upload accepted.
- Valid GIF upload accepted.
- Valid WebP upload accepted.
- SVG rejected.
- Non-image rejected.
- Oversized image rejected.
- Stored filename includes media ID and safe original filename.
- File is stored in flat media folder.
- Media URL uses `/media/<stored_filename>`.
- Deleting media deletes database row and file.
- Profile photo upload uses same validation rules.

## Menu Tests

Cover:

- `root` menu is used for top member navigation.
- Non-root menu renders at `/menu/<menu_name>/`.
- Missing menu returns `404`.
- Menu pages require login.
- Menu items sort by `display_order`, then `label`.
- Menu items can link to internal URLs.
- Menu items can link to external URLs.
- Menu items can link to `/menu/<menu_name>/`.
- Admin can create/edit/delete menus and menu items.
- `root` menu cannot be deleted.

## Camp And Tax Tests

Cover:

- Current year is max configured camp year.
- `/dashboard/` redirects to current year dashboard.
- `/<year>/dashboard/` loads.
- Dashboard renders pre/post content pages.
- Dashboard shows paid status.
- Dashboard shows waived status.
- Tax tiers are available inside start/expiration dates.
- Tax tiers unavailable before start.
- Tax tiers unavailable after expiration.
- Multiple available tiers are selectable.
- Chosen tier determines minimum.
- Member can pay above chosen minimum.
- Member cannot pay below chosen minimum.
- Add-ons available inside start/expiration dates.
- Add-ons unavailable outside dates.
- Reduced-minimum override changes minimum.
- Tax-waived override marks tax step complete.
- Tax-waived users cannot start checkout.

## Payment And Stripe Checkout Tests

Use mocked Stripe client.

Cover:

- Checkout requires login.
- Checkout requires active user.
- Checkout blocked when already paid.
- Checkout blocked when unexpired `created` payment exists.
- Checkout allowed when only expired `created` payments exist.
- Checkout creates local payment.
- Checkout stores `checkout_expires_at`.
- Checkout stores Stripe mode.
- Checkout creates add-on snapshots.
- Checkout passes required metadata.
- Checkout uses `payment_method_types = ["card"]`.
- Checkout success URL is `/<year>/taxes/return/`.
- Checkout cancel URL is `/<year>/taxes/`.
- Checkout return page never marks payment paid.

## Stripe Webhook Tests

Use mocked payloads and mocked signature verification.

Cover:

- Invalid signature returns `400`.
- Test webhook secret verifies test event.
- Live webhook secret verifies live event.
- Delayed events still verify after mode switch.
- `checkout.session.completed` marks payment `paid` after full verification.
- Amount mismatch marks `requires_review`.
- Currency mismatch marks `requires_review`.
- User mismatch marks `requires_review`.
- Camp year mismatch marks `requires_review`.
- Wrong Stripe mode marks `requires_review`.
- Missing metadata fails safely.
- Unknown payment ID fails safely.
- Duplicate webhook information is logged.
- Duplicate events do not apply state changes twice.
- `checkout.session.expired` marks created payment `cancelled`.
- `payment_intent.payment_failed` marks created payment `failed`.
- Full refund marks payment `refunded`.
- Partial refund marks `requires_review`.
- Webhook logs do not store secrets or card data.

## Admin UI Tests

Cover each admin section:

- `/admin/`.
- `/admin/users/`.
- `/admin/camp/`.
- `/admin/payments/`.
- `/admin/stripe/`.
- `/admin/pages/`.
- `/admin/menus/`.
- `/admin/media/`.

For each section:

- Anonymous redirects to login.
- Non-admin gets `403`.
- Admin can load page.
- Admin can perform expected create/edit/delete actions.
- Validation errors are shown clearly.

## Management Command Tests

Cover:

- `create_admin` creates active admin user.
- `create_admin` creates profile.
- `create_admin` refuses duplicate email.
- `check_config` validates required TOML sections.
- `check_config` does not print secrets.
- `check_stripe` validates configured keys exist.
- `check_stripe` does not call live payment APIs.
- `check_stripe` does not print secrets.

## Deployment Tests

Deployment tests are not part of the default suite.

Use marker:

```text
deployment
```

Run explicitly:

```bash
pytest -m deployment --base-url https://thephage.org
```

Cover:

- `/` redirects to `/public/`.
- `/public/` loads.
- `/login/` loads.
- Anonymous `/dashboard/` redirects to login.
- Static assets load.
- Known media URL loads if configured.
- HTTPS works.
- Debug mode is off.
- Admin pages reject non-admin users.
- Stripe admin reports expected mode when admin credentials are provided.

## What Not To Test In V1

Do not add tests for features that do not exist:

- Email delivery.
- Email password reset.
- Email confirmation.
- Public registration.
- Two-factor auth.
- Member impersonation.
- Survey/jobs/roster behavior.
- Multi-currency payments.
- Non-card Stripe payment methods.
- Image resizing.
- Hover dropdown menus.
