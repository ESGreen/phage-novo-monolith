# Testing Design

## Purpose

This document describes the testing strategy for the `thephage.org` Django website.

The goal is not to test every line of code. The goal is to make the dangerous parts boring:

- Login and access control.
- Admin-only pages.
- Year dashboard routing.
- Tax minimum calculations.
- Tax overrides.
- Add-on selection.
- Stripe Checkout creation.
- Stripe webhook handling.
- Test/live payment separation.
- Payment status display.
- Deployment health.

Most pages are simple server-rendered Django views. These do not need heavy browser automation unless behavior becomes complex.

Tests should focus on:

- Business rules.
- Permissions.
- Payment safety.
- Data integrity.
- Regression protection for yearly setup.
- Verifying that the deployed site is reachable and correctly configured.

Prefer small, clear tests over elaborate test frameworks.

Manual smoke testing is still important before launch, especially for Stripe test/live behavior and deployment verification.

## Tooling And Test Environment

The test setup should use `pytest` with `pytest-django`.

This is preferred because it keeps tests readable and maintainable:

- Tests can be simple functions.
- Fixtures can create users, camp years, tax tiers, and payments.
- Plain `assert` statements are easy to read.
- Django's test client and database support are still available.

Recommended tools:

- `pytest`
- `pytest-django`
- Django test client
- PostgreSQL for integration tests where database behavior matters
- Temporary media directory for upload/media tests
- Mocked Stripe client for automated tests
- Stripe test mode for manual end-to-end payment tests

Automated tests should not hit live Stripe.

Automated tests should not create real payments.

The project should support at least these test commands:

- Run the full automated test suite.
- Run only fast/unit tests.
- Run deployment verification checks.
- Run a manual smoke-test checklist before launch.

Test data should be small and explicit.

Useful test fixtures:

- Active member user.
- Admin user.
- Inactive user.
- Current camp year.
- Old camp year.
- Tax tiers.
- Tax add-ons.
- Reduced minimum tax override.
- Tax waived override.
- Paid test payment.
- Failed/cancelled test payment.

Where practical, tests should create their own data instead of relying on shared seed data.

## User, Account, And Profile Tests

These tests verify account behavior, email login, profile linkage, and profile editing.

Automated tests should cover:

- Users log in with email, not username.
- Email matching is case-insensitive using simple normalization such as Python `lower()`.
- Email uniqueness is enforced after normalization.
- Unicode names are accepted and displayed correctly.
- Profile bio supports Unicode text.
- Active users can log in.
- Inactive users cannot log in.
- Admin users are identified by `is_admin`.
- Non-admin users are not treated as admins.
- Each user has exactly one profile.
- A profile belongs to exactly one user.
- Profile photo can point to a media record.

### Email Change Tests

Because email is the login identifier and users can change it from `/profile/`, tests should explicitly cover that flow.

Automated tests should verify:

- A logged-in user can change their email.
- The email change requires an on-page confirmation step, not an email confirmation message.
- Changing email does not log the user out unexpectedly.
- The existing session remains valid after the email changes.
- After logout, the old email no longer works.
- After logout, the new email works.
- A user cannot change their email to one already used by another account, ignoring case.

Suggested flow test:

1. Create user with `old@example.com`.
2. Log in as `old@example.com`.
3. Visit `/profile/`.
4. Change email to `new@example.com` and confirm.
5. Verify user is still logged in.
6. Log out.
7. Verify `old@example.com` login fails.
8. Verify `new@example.com` login succeeds.

For Unicode/case, use simple practical behavior:

```text
normalize_email = email.lower()
```

The site does not need to solve every Unicode/email edge case.

## Access Control And Redirect Tests

These tests verify that public, member, and admin pages are protected correctly.

Automated tests should cover:

- Anonymous users can access `/public/`.
- Anonymous users can access `/login/`.
- Anonymous users visiting `/dashboard/` are redirected to `/login/`.
- Anonymous users visiting `/<year>/dashboard/` are redirected to `/login/`.
- Anonymous users visiting `/<year>/taxes/` are redirected to `/login/`.
- Anonymous users visiting `/profile/` are redirected to `/login/`.
- Anonymous users visiting `/admin/` are redirected to `/login/` or otherwise blocked before admin access.
- Logged-in members can access `/dashboard/`.
- Logged-in members can access `/<year>/dashboard/`.
- Logged-in members can access `/profile/`.
- Logged-in members cannot access `/admin/`.
- Logged-in non-admin users visiting `/admin/` receive `403 Forbidden`.
- Logged-in non-admin users visiting `/admin/users/` receive `403 Forbidden`.
- Logged-in non-admin users visiting `/admin/camp/` receive `403 Forbidden`.
- Logged-in non-admin users visiting `/admin/payments/` receive `403 Forbidden`.
- Logged-in non-admin users visiting `/admin/stripe/` receive `403 Forbidden`.
- Logged-in non-admin users visiting `/admin/pages/` receive `403 Forbidden`.
- Logged-in non-admin users visiting `/admin/menus/` receive `403 Forbidden`.
- Logged-in non-admin users visiting `/admin/media/` receive `403 Forbidden`.
- Admin users can access `/admin/`.
- Admin users can access all admin section pages.
- Inactive users cannot log in.
- Inactive users cannot access authenticated pages.
- Already logged-in users visiting `/login/` are redirected to `/dashboard/`.
- `/dashboard/` redirects to the current year dashboard.
- `/<year>/` redirects to or aliases `/<year>/dashboard/`.

## Public Static Page Tests

These tests verify that the static public site is wired correctly.

Automated or deployment tests should cover:

- `/` redirects to `/public/`.
- `/public/` serves `/public/index.html`.
- `/public/index.html` loads successfully.
- Public static assets under `/public/` load successfully.
- Public pages do not require login.
- Public pages do not show the member menu.
- Public pages can link to `/login/`.
- A public page link to a member-only URL still triggers login protection when followed.

This section can be partly automated in Django/local tests and partly covered by deployment verification, depending on whether `/public/` is served by Django in development or by the web server in production.

## Camp Year And Dashboard Tests

These tests verify that year-specific routing and dashboard behavior work correctly.

Automated tests should cover:

- The current camp year is inferred from the maximum configured camp year.
- `/dashboard/` redirects to the current year dashboard.
- `/<year>/dashboard/` loads for an existing camp year.
- `/<year>/` redirects to or aliases `/<year>/dashboard/`.
- Old year dashboards can still load, such as `/2025/dashboard/`.
- Unknown years return `404`.
- Dashboard shows the correct year.
- Dashboard renders pre-checklist Markdown content when configured.
- Dashboard renders post-checklist Markdown content when configured.
- Dashboard shows required steps/checklist items.
- Dashboard shows whether each required step is complete.
- Dashboard shows payment status for the member/year.
- Dashboard shows a taxes link when payment is available.
- Dashboard does not show a payment action when payment is blocked or already complete.

If no camp year exists, `/dashboard/` should not crash.

Acceptable behavior:

- Show a simple "No camp year is configured" page.
- Or return `404`.

Preferred behavior:

- `/dashboard/` shows "No camp year is configured."
- `/<year>/dashboard/` for an unknown year returns `404`.

## Content Pages, Menus, Media, And Markdown Tests

These tests verify admin-managed member content, navigation, uploaded media, and Markdown safety.

Automated tests should cover:

- A content page exists at `/pages/<slug>/`.
- Member content pages require login.
- A logged-in member can view a content page.
- Unknown content page slugs return `404`.
- Content pages do not have published/unpublished state.
- If a content page exists, it is live.

Markdown tests should cover:

- Markdown headings render.
- Markdown lists render.
- Markdown links render.
- Markdown images render.
- Uploaded media URLs can be used in Markdown.
- Offsite image URLs can be used in Markdown.
- Raw HTML is escaped or stripped.
- Script tags do not render.
- Event-handler attributes do not render.
- Arbitrary inline styles do not render.

Image behavior:

- Uploaded files are stored as-is.
- The site CSS should make content images responsive.
- If an image needs resizing, it should be resized offline and uploaded again.
- No custom Markdown image resizing is required in V1.

Menu tests should cover:

- The `root` menu appears as the top member menu.
- Menu items are ordered by display order, then label.
- Menu items can link to internal paths.
- Menu items can link to external URLs.
- Menu items can link to menu pages such as `/menu/camp-info/`.
- Menu pages render the items for the requested menu.
- Unknown menu pages return `404`.
- The member menu appears on logged-in member pages.
- The member menu does not appear on public static pages.
- The member menu includes a logout button.

Media tests should cover:

- Admin can upload a media file.
- Media files are stored in the configured flat media folder.
- Stored filenames include the media record ID and safe original filename.
- Media metadata is stored in the database.
- Uploaded media can be referenced from Markdown content.
- Deleting media deletes both the database record and file from disk.

Implementation note:

```markdown
Markdown rendering should use a safe renderer plus an HTML sanitizer allowlist. Raw HTML should not be trusted.
```

## Tax Configuration Logic Tests

These tests verify tax tiers, add-ons, minimum amounts, and availability rules.

All tax-related open, close, and expiration values are timestamps.

For entry and display, timestamps are defined in Pacific time.

Under the covers, the system may store timezone-aware values in UTC, but admin forms and user-facing displays should treat them as Pacific time.

Automated tests should cover:

- Tax tiers are available when the current timestamp is inside their start/expiration range.
- Tax tiers are not available before their start timestamp.
- Expired tax tiers are not available.
- Tax tiers are ordered by display order.
- If multiple tax tiers are available, the member can choose one.
- The chosen tier determines the member's minimum payment.
- A member can enter an amount greater than the chosen tier minimum.
- A member cannot enter an amount below the chosen tier minimum.
- Add-ons are available inside their start/expiration timestamp range.
- Add-ons are not available before their start timestamp.
- Add-ons are not available after their expiration timestamp.
- Selected add-ons are added to the final payment amount.
- If no tax tier is available, the user cannot start payment.

Timezone tests should cover:

- Admin-entered Pacific timestamps are interpreted as Pacific time.
- Stored timestamps compare correctly even if represented internally as UTC.
- Daylight saving time boundaries do not break tier or add-on availability checks.

Implementation note:

```markdown
Use timezone-aware datetimes. Use `America/Los_Angeles` for admin entry/display and safe timezone-aware comparisons internally.
```

## Tax Override Tests

These tests verify per-user tax exceptions.

Automated tests should cover:

- A user without a tax override uses the normal minimum from available tax tiers.
- A reduced minimum override changes the user's minimum amount for that camp year.
- A reduced minimum override applies only to the matching user.
- A reduced minimum override applies only to the matching camp year.
- A reduced minimum override can be lower than the normal minimum.
- A user with a reduced minimum override can enter an amount greater than the override minimum.
- A user with a reduced minimum override cannot enter an amount below the override minimum.
- Add-ons still add to the final payment amount when a reduced minimum override exists.
- A tax waived override marks the tax step complete for that user/year.
- A tax waived override does not create a payment record by itself.
- A user with a tax waived override should not be required to start Stripe Checkout.
- A user with a tax waived override should see the dashboard tax step as complete.
- A tax waived override applies only to the matching user.
- A tax waived override applies only to the matching camp year.
- There can be at most one tax override per user per camp year.
- Deleting a tax override returns the user to the normal tax rules.
- Tax overrides do not make payment available when no tax tier is available unless explicitly changed later.

## Stripe Checkout Creation Tests

Automated tests should mock Stripe. Automated tests should not call live Stripe.

Automated tests should cover:

- A logged-in member can start checkout when at least one tax tier is available.
- A logged-in member cannot start checkout before any tax tier starts.
- A logged-in member cannot start checkout after all tax tiers expire.
- A logged-in member cannot start checkout if no valid tax tier exists.
- A logged-in member cannot start checkout for an amount below their minimum.
- A logged-in member can start checkout for an amount above their minimum.
- Selected add-ons are included in the final amount.
- Unavailable add-ons cannot be selected.
- Expired tax tiers cannot be used.
- A reduced minimum tax override is honored.
- A tax waived override blocks checkout because no payment is required.
- A member who has already paid for that camp year cannot start another checkout.
- A member with an unexpired `created` payment for the same year cannot start another checkout.
- A member with only expired `created` payments can start a new checkout.
- Checkout creates a local payment attempt record.
- Checkout stores Stripe mode, test or live, on the local payment record.
- Checkout stores the Stripe Checkout Session ID when Stripe returns it.
- Checkout stores `checkout_expires_at`.
- Checkout passes useful metadata to Stripe, including user ID, camp year, payment ID, and Stripe mode.
- Checkout uses credit cards only.
- Checkout success URL points back to `/<year>/taxes/return/`.
- Checkout cancel URL points back to `/<year>/taxes/`.

Only one successful payment per user per camp year is allowed. Extra or unusual payments are handled outside the website.

## Stripe Webhook Handling Tests

Stripe webhooks are the source of truth for successful payment completion.

Automated tests should mock webhook payloads and signature verification. Automated tests should not call live Stripe.

Automated tests should cover:

- Valid webhook signatures are accepted.
- Invalid webhook signatures are rejected.
- Webhook receipt is logged.
- Webhook validation result is logged.
- Webhook processing result is logged.
- A completed checkout session marks the matching local payment as `paid`.
- A paid webhook sets `paid_at`.
- A paid webhook does not create a second successful payment for the same user/year.
- Duplicate webhook events are safe and do not duplicate records.
- Webhook handling is idempotent.
- Duplicate webhook information is logged without relying on a unique log-field constraint.
- Webhook metadata is used to find the local payment record.
- Webhook events with missing required metadata fail safely.
- Webhook events for unknown payment IDs fail safely.
- Webhook events for the wrong Stripe mode mark the payment `requires_review` or fail safely.
- Webhook amount must match the local payment amount.
- Webhook user/year metadata must match the local payment.
- Mismatched webhook data marks the payment `requires_review`.
- Failed/cancelled/expired payment events update the local payment status where applicable.
- Refund events update the local payment status to `refunded` if refund support is enabled.
- Webhook logs do not store secrets or card data.

Safety rule:

```markdown
If a webhook payload does not match the expected local payment record, the site should not mark the payment as paid. It should mark the local payment `requires_review` where possible.
```

V1 admin handling:

```markdown
Payments marked `requires_review` should be visible to admins, but V1 does not need a custom workflow for resolving them. If this rare case occurs, an admin can resolve it directly in the database.
```

## Payment Records And Add-Ons Tests

Automated tests should cover:

- Starting checkout creates a payment record.
- Payment records store user.
- Payment records store camp year.
- Payment records store amount in cents.
- Payment records store status.
- Payment records store Stripe mode.
- Payment records store Stripe Checkout Session ID when available.
- Payment records store Stripe Payment Intent ID when available.
- Payment records store Checkout expiration when available.
- Payment records store `paid_at` after successful webhook.
- Currency is not stored because V1 is USD-only.
- A successful payment makes the member paid for that camp year.
- A failed payment does not make the member paid.
- A cancelled payment does not make the member paid.
- A refunded payment does not make the member paid unless later changed explicitly.
- A `requires_review` payment does not make the member paid.
- Only one successful paid payment is allowed per user per camp year.
- Multiple failed/cancelled attempts may exist before one successful payment.
- Failed/cancelled attempts are kept. No cleanup behavior is needed in V1.

## Payment Add-On Tests

Automated tests should cover:

- Selected add-ons create payment add-on records.
- Payment add-on records point to the payment.
- Payment add-on records point to the original tax add-on.
- Add-on name is snapshotted at payment time.
- Add-on amount is snapshotted at payment time.
- Editing a tax add-on later does not change old payment add-on snapshots.
- Payment amount includes selected add-ons.
- Unselected add-ons are not recorded on the payment.

## Test Vs Live Stripe Mode Tests

These tests verify that Stripe test and live modes are clearly separated while still using the same website workflow.

Production can be switched into Stripe test mode. Admins will use test mode in production to verify the full real workflow each year, then switch the site back to live mode after testing.

Automated tests should cover:

- The site has an explicit Stripe mode: `test` or `live`.
- Admins can switch the configured Stripe mode.
- Stripe mode is stored on every payment record.
- Stripe mode is stored on relevant payment log records.
- Test mode uses test Stripe configuration.
- Live mode uses live Stripe configuration.
- Checkout creation uses the currently configured Stripe mode.
- Webhook handling verifies that the webhook mode matches the payment mode.
- A test webhook cannot mark a live payment as paid.
- A live webhook cannot mark a test payment as paid.
- Mode mismatches mark the payment `requires_review` or fail safely.
- `/admin/stripe/` clearly shows whether the site is in test mode or live mode.
- `/admin/stripe/` shows recent Stripe/payment activity needed to debug test and live payments.
- `/admin/stripe/` allows deleting test payments.
- Deleting test payments deletes related local payment add-ons and payment logs as appropriate.
- Live payments cannot be deleted through the test-payment cleanup path.
- Member-facing pages do not expose special test/live UI.
- The member tax payment workflow is the same in test mode and live mode.

## Admin Workflow Tests

These tests verify the main admin sections, yearly setup tasks, and expected validation failures.

### Admin Access

Automated tests should cover:

- Non-admin users receive `403` for all admin pages.
- Admin users can access `/admin/`.
- Admin users can access `/admin/users/`.
- Admin users can access `/admin/camp/`.
- Admin users can access `/admin/payments/`.
- Admin users can access `/admin/stripe/`.
- Admin users can access `/admin/pages/`.
- Admin users can access `/admin/menus/`.
- Admin users can access `/admin/media/`.

### Users Admin

Happy-path tests should cover:

- Admin can create a member.
- Admin can create another admin.
- Admin can deactivate a user.
- Admin can reset or set a password.
- User and profile data are presented together.

Validation/error tests should cover:

- Duplicate email is rejected, ignoring case.
- Invalid email is rejected.
- Missing required name/email fields are rejected.
- Inactive user cannot log in after deactivation.
- Non-admin user cannot grant themselves admin access.

### Camp Admin

Happy-path tests should cover:

- Admin can create a camp year.
- Admin can configure dashboard pre-checklist content page.
- Admin can configure dashboard post-checklist content page.
- Admin can create tax tiers.
- Admin can create tax add-ons.
- Admin can create reduced tax overrides.
- Admin can create tax waived overrides.

Validation/error tests should cover:

- Duplicate camp year is rejected.
- Invalid year values are rejected.
- Tax tier minimum amount must be greater than or equal to zero.
- Tax tier expiration timestamp must be after start timestamp.
- Tax add-on amount must be greater than or equal to zero.
- Tax add-on expiration timestamp must be after start timestamp.
- Tax override can only exist once per user per camp year.
- Reduced tax override requires a minimum amount.
- Tax waived override does not require a minimum amount.
- Invalid Pacific-time timestamp input is rejected clearly.

### Stripe Admin

Happy-path tests should cover:

- Admin can see current Stripe mode.
- Admin can switch Stripe mode.
- Admin can see Stripe configuration health.
- Admin can see recent payment/Stripe logs.
- Admin can delete test payments.
- Admin can use test mode in production without changing the member-facing workflow.

Validation/error tests should cover:

- Invalid Stripe configuration reports unhealthy status.
- Switching to live mode fails or warns clearly if live configuration is missing.
- Switching to test mode fails or warns clearly if test configuration is missing.
- Deleting test payments does not delete live payments.
- Non-admin users cannot switch Stripe mode.
- Non-admin users cannot delete test payments.

### Payments Admin

Happy-path tests should cover:

- Admin can view successful payments.
- Admin can view failed/cancelled/refunded payments.
- Admin can view `requires_review` payments.
- Admin can view selected add-ons.
- Admin can view related Stripe/payment logs.

Validation/error tests should cover:

- Payment records cannot be edited into invalid amounts.
- Payment status must be one of the allowed statuses.
- Payment cannot be marked paid without enough Stripe/local data unless changed directly in database outside normal UI.
- `requires_review` payments are visible but do not require a custom resolution workflow in V1.

### Pages Admin

Happy-path tests should cover:

- Admin can create a Markdown content page.
- Admin can edit a Markdown content page.
- Admin can delete a content page.

Validation/error tests should cover:

- Duplicate slug is rejected.
- Invalid slug is rejected.
- Empty title is rejected.
- Unsafe Markdown/HTML is sanitized or rejected.

### Menus Admin

Happy-path tests should cover:

- Admin can create a menu.
- Admin can create a menu item.
- Admin can edit menu item label, URL, menu, and display order.
- Admin can delete a menu item.
- Internal URLs work as menu targets.
- External URLs work as menu targets.
- Menu-page URLs work as menu targets.

Validation/error tests should cover:

- Duplicate menu name is rejected.
- Empty label is rejected.
- Empty URL is rejected.
- Bad URL values are rejected.
- Duplicate display order is handled by sorting alphabetically by label.

### Media Admin

Happy-path tests should cover:

- Admin can upload media.
- Admin can browse media.
- Admin can delete media.
- Uploaded files are stored as-is.
- Stored filenames include database ID and safe original filename.

Validation/error tests should cover:

- Missing upload file is rejected.
- Unsafe filenames are sanitized.
- Deleting media removes both database record and file from disk.
- Non-admin users cannot upload media.

## Profile Management Tests

These tests verify that members can manage their own account/profile data safely.

Automated tests should cover:

- Logged-in member can access `/profile/`.
- Anonymous users are redirected to `/login/`.
- Member can update first name.
- Member can update last name.
- Member can update bio.
- Member can replace profile photo.
- Member does not have a self-service profile photo delete action in V1.
- Member can change password.
- Member can change email with confirmation.
- Changing email does not break the current session.
- After email change and logout, old email no longer works.
- After email change and logout, new email works.
- Member cannot change their email to an email already used by another user, ignoring case.
- Member cannot edit another user's profile.
- Unicode names and bio text save and display correctly.

## Security And Secret Handling Tests

V1 does not require two-factor authentication.

Accounts should require strongish passwords:

- Minimum length of 10 characters.
- Unicode characters are allowed.
- Password must include at least two character classes.

Character classes:

- Letters.
- Numbers.
- Punctuation.
- Other Unicode characters.

Automated tests should cover:

- Passwords shorter than 10 characters are rejected.
- Passwords with only one character class are rejected.
- Passwords with two or more character classes are accepted.
- Unicode passwords are accepted.
- Anonymous users cannot access member pages.
- Non-admin users receive `403` for admin pages.
- Inactive users cannot log in.
- Passwords are stored as hashes, not plaintext.
- Stripe secret keys are not stored in the database.
- Stripe secret keys are not exposed in admin pages.
- Stripe secret keys are not written to payment logs.
- Webhook secrets are not exposed in admin pages.
- Webhook secrets are not written to payment logs.
- Payment logs redact sensitive fields.
- Markdown rendering strips or escapes unsafe HTML.
- Uploaded media filenames are sanitized.
- Path traversal filenames are rejected or sanitized.
- User-uploaded media cannot overwrite arbitrary server files.
- CSRF protection applies to forms that mutate data.
- Admin-only mutations require admin access.
- Profile updates can only affect the logged-in user's profile.
- Email change confirmation prevents accidental one-field edits.

Deployment/security checks should later cover:

- HTTPS is enabled in production.
- Secure cookies are enabled in production.
- Debug mode is off in production.
- Allowed hosts are configured.
- Static public file serving does not expose private project files.

## Deployment Verification Tests

Deployment verification checks confirm that the deployed website is reachable and configured correctly.

These tests should run from the command line against a deployed environment. They are intended for occasional use after major OS, server, dependency, or website updates.

Deployment tests should be safe to run against production.

The command should accept a base URL.

Example:

```bash
pytest -m deployment --base-url https://thephage.org
```

Some checks may require credentials. Credentials can be supplied on the command line or through environment variables.

Example:

```bash
pytest -m deployment --base-url https://thephage.org --admin-email admin@example.com --admin-password ...
```

Authenticated deployment checks should only run when credentials are provided.

Deployment tests should cover:

- `https://thephage.org/` redirects to `/public/`.
- `/public/` returns the public landing page.
- `/login/` loads.
- `/dashboard/` redirects unauthenticated users to `/login/`.
- A known member-only page redirects unauthenticated users to `/login/`.
- `/admin/` redirects anonymous users to `/login/` or blocks access.
- Static public assets load.
- Uploaded media files load, if a known test media URL is configured.
- Database connection is healthy, if a health endpoint or admin check is available.
- Application migrations have been applied, if exposed through an admin/health check.
- Debug mode is off.
- HTTPS is working.
- Secure cookies are enabled.
- Allowed hosts are configured correctly.
- Stripe admin status page reports expected mode and configuration health when admin credentials are provided.
- Current Stripe mode is obvious on `/admin/stripe/` when admin credentials are provided.
- Admin pages reject non-admin users when member credentials are provided.
- Admin pages load for admin users when admin credentials are provided.

Recommendation for implementation:

- Use `pytest` with a `deployment` marker.
- Deployment tests should use `requests` or a browserless HTTP client.
- Do not run deployment tests by default with normal local tests.
- Do not create live payments.
- Authenticated checks should be skipped if credentials are not supplied.

## Backups And Recovery Checks

The backup strategy has two levels.

### Heavy System Backups

Before the season and before major system changes, create an EC2 image.

This is the full-machine recovery path.

Use before:

- OS upgrades.
- Major package upgrades.
- Major website deployments.
- Start of tax season.

### Lightweight Active-Season Backups

During active tax collection, the system should back up the database and deployment configuration without requiring a full EC2 image.

Recommended approach:

- Use `pg_dump` for PostgreSQL.
- Compress the dump.
- Upload the backup to S3.
- Back up deployment configuration files to S3.
- Back up uploaded media files to S3 with incremental sync.

Suggested cadence:

- Hourly database backups while taxes are open.
- Daily database backups outside tax season.
- Config backup after any deployment/config change.
- Media backup daily if media changes during the season.

Backups should cover:

- PostgreSQL database.
- Deployment configuration.
- Backup scripts.
- Web server/service configuration.
- Public static files if changed on the server.
- Uploaded media files.

Do not create a special Stripe backup outside normal config backups. The deployed Stripe configuration lives in `/etc/thephage/thephage.toml`; the committed example format is `deploy/thephage.toml.example`.

Backup checks should verify:

- Recent database backup exists.
- Recent config backup exists.
- Backup upload target is reachable.
- Backup files are non-empty.
- Backup process reports success/failure clearly.
- Restore procedure is documented.
- Occasional manual restore test is performed on non-production infrastructure.

## Manual Pre-Launch Smoke Test

The manual smoke test should be run before opening taxes for the year and after major deployment/server changes.

This test verifies the site works end-to-end from an admin/member perspective.

This checklist is also maintained as the operational runbook `docs/pre-launch-checklist.md`.

### Public Site

- Visit `/`.
- Confirm it redirects to `/public/`.
- Confirm `/public/` loads the public landing page.
- Confirm public assets load.
- Confirm `/login/` loads.

### Login And Profile

- Log in as a normal member.
- Confirm login redirects to `/dashboard/`.
- Confirm `/dashboard/` redirects to the current year dashboard.
- Visit `/profile/`.
- Update name or bio.
- Replace profile photo.
- Change email with confirmation.
- Log out.
- Confirm old email no longer works.
- Confirm new email works.

### Member Access

- Confirm member can access year dashboard.
- Confirm member can access member content pages.
- Confirm member cannot access `/admin/`.
- Confirm member receives `403` for admin pages.

### Admin Access

- Log in as admin.
- Confirm `/admin/` loads.
- Confirm `/admin/users/` loads.
- Confirm `/admin/camp/` loads.
- Confirm `/admin/payments/` loads.
- Confirm `/admin/stripe/` loads.
- Confirm `/admin/pages/` loads.
- Confirm `/admin/menus/` loads.
- Confirm `/admin/media/` loads.

### Camp Setup

- Confirm current camp year exists.
- Confirm tax tiers are configured.
- Confirm add-ons are configured.
- Confirm dashboard pre-checklist content appears.
- Confirm dashboard post-checklist content appears.
- Confirm menus look correct.

### Stripe Test Mode

- Go to `/admin/stripe/`.
- Switch site to Stripe test mode.
- Confirm test mode is obvious in `/admin/stripe/`.
- Log in as test member.
- Go to year dashboard.
- Go to taxes page.
- Select a tax amount and add-ons.
- Complete Stripe Checkout using a Stripe test card.
- Confirm return to site works.
- Confirm webhook marks payment paid.
- Confirm dashboard shows tax step complete.
- Confirm payment appears in admin.
- Confirm add-ons appear in admin.
- Confirm Stripe/payment logs exist.
- Delete test payment from `/admin/stripe/`.
- Confirm test member can repeat the test payment flow.

### Stripe Live Mode

- Return to `/admin/stripe/`.
- Switch site to live mode.
- Confirm live mode is obvious in `/admin/stripe/`.
- Confirm member-facing payment flow still looks normal.

### Final Live Payment Test

This is a manual test and should be performed intentionally with real money.

- Confirm `/admin/stripe/` is in live mode.
- Admin logs in through the normal member flow.
- Admin goes to the current year dashboard.
- Admin goes to the taxes page.
- Admin pays their actual taxes with a real payment method.
- Admin confirms the site returns to the dashboard.
- Admin confirms the dashboard shows the tax step complete.
- Admin confirms the payment appears in `/admin/payments/`.
- Admin confirms the payment appears in the Stripe Dashboard.
- Admin confirms Stripe shows the expected amount and successful status.
- Admin confirms the payment is live, not test.

### Final Checks

- Confirm debug mode is off.
- Confirm HTTPS works.
- Confirm secure cookies are enabled.
- Confirm backups are running.
- Confirm latest database backup exists.
- Confirm public pages and media still load.

## What Not To Test In V1

The V1 test suite should avoid testing features that do not exist yet.

Do not add automated tests for:

- Survey behavior.
- Survey reports.
- Directory/roster pages.
- Job/shift signup.
- Job/shift payment requirements.
- Complex public page editing.
- Rich CMS behavior.
- Email delivery.
- Password reset by email.
- Two-factor authentication.
- Multi-currency payments.
- Arbitrary donation/extra-payment flows.
- Browser screenshot comparisons.
- Detailed visual design.

These areas should be tested when they become real features.

V1 tests should stay focused on:

- Login.
- Access control.
- Admin-only behavior.
- Profile editing.
- Year dashboard behavior.
- Tax calculation.
- Tax overrides.
- Stripe checkout.
- Stripe webhooks.
- Payment records.
- Test/live Stripe mode.
- Deployment verification.

## Operational Docs

This design document describes the testing strategy. Operational checklists live under `docs/`.

Current operational docs:

- `docs/pre-launch-checklist.md`
- `docs/backup-and-restore.md`
- `docs/yearly-rollover.md`
- `docs/stripe.md`
