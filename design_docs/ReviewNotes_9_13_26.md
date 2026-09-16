# Code Review Notes - September 13, 2026

## Purpose

This document preserves the project-understanding and static code-review notes
gathered on September 13, 2026. It is a working review record, not a claim that
the listed issues have already been fixed.

The findings should be revalidated against the current code before each fix,
especially if implementation continues after this review date.

## Review Scope

Reviewed:

- All tracked code in the current Django application.
- Application models, forms, services, views, URLs, migrations, templates, and
  JavaScript.
- Automated tests.
- Deployment configuration, backup, and restore tooling.
- Current operational docs and design docs as statements of intended behavior.

Excluded:

- `old_website/`, including the ignored WordPress and legacy CGI code.
- `.venv/`, `.pytest_cache/`, `.ruff_cache/`, and other generated dependencies
  or caches.
- `var/`, which contains generated/private backup data.
- Untracked legacy and design image assets, except for noting their existence.

This was a static review. Tests and linters were not run during the review
because the session was in read-only plan mode.

## Project Summary

This is a custom Django replacement for `thephage.org`. It provides a static
public site and a private member site for:

- Email/password login.
- Member profile completion.
- Yearly registration dashboards.
- Configurable member surveys.
- A year-scoped Phagebook.
- Camp tax selection and Stripe Checkout.
- Manual off-site payment records.
- Custom product administration.
- Server deployment, backup, and restore operations.

The intended implementation style is intentionally small and conventional:

- Server-rendered Django templates.
- Minimal progressive JavaScript.
- PostgreSQL in production.
- TOML deployment configuration.
- Custom product admin under `/admin/`.
- Stripe-hosted card collection.
- External backup tooling rather than backup logic in Django requests.

## Operating Model

### Startup

```text
TOML configuration
-> thephage.config
-> Django settings
-> root URL dispatcher
-> application routes
```

`thephage/settings.py` eagerly loads the configured TOML file. The deployed
default is `/etc/thephage/thephage.toml`; tests point to
`tests/fixtures/thephage.test.toml`.

### Member Registration

```text
Login
-> /dashboard/
-> maximum configured CampYear
-> profile completion
-> optional Camp survey completion
-> taxes paid or waived
-> fully registered
-> eligible for Phagebook display
```

Profile completion currently requires first name, last name, profile photo,
and non-empty bio. Survey completion is based on the existence of a response
for the configured survey. Taxes are complete when a paid payment exists or a
waived override applies.

### Stripe Payment

```text
Tax form
-> server-side tier/add-on validation
-> local Payment(status=created)
-> Stripe Checkout Session
-> Stripe webhook
-> local payment transition
-> dashboard registration status
```

The browser return page never marks a payment paid. Stripe webhooks are intended
to be the source of truth.

### Administration

```text
/admin/
-> accounts.permissions.admin_required
-> users
-> camp years and taxes
-> payments and Stripe mode
-> pages and media
-> surveys
-> menus
```

The admin is custom product UI, not Django's built-in admin. An active user with
`is_admin = true` has access to all admin workflows.

### Production

```text
browser
-> Nginx
-> Gunicorn over Unix socket
-> Django
-> local PostgreSQL
```

Nginx serves public files, static assets, and uploaded media directly. Backups
are run by repo-owned scripts, normally from a systemd timer, and upload to S3
through the EC2 instance IAM role.

## Subsystem Map

### Project Configuration

- `manage.py`: Django command-line entry point.
- `pyproject.toml`: package metadata, dependencies, pytest settings, and Ruff
  settings.
- `requirements.txt`: duplicate runtime dependency list for deployment.
- `thephage/config.py`: TOML parsing and structural validation.
- `thephage/settings.py`: Django settings, database selection, security, paths,
  templates, and installed apps.
- `thephage/urls.py`: root route composition and debug file serving.
- `thephage/asgi.py`: ASGI entry point.
- `thephage/wsgi.py`: WSGI/Gunicorn entry point.

### Accounts

- `accounts/models.py`: custom lowercase-email user, user manager, and one-to-one
  member profile.
- `accounts/forms.py`: login, profile photo, profile bio, and email-change forms.
- `accounts/password_validation.py`: two-character-class password validator.
- `accounts/permissions.py`: member and admin access decorators.
- `accounts/views.py`: login, logout, and profile editing.
- `accounts/management/commands/create_admin.py`: initial admin creation.
- `accounts/tests/`: account model and member-flow tests.
- `templates/accounts/`: login and profile pages.

### Core

- `core/models.py`: singleton-like `SiteSettings`, currently storing Stripe
  test/live mode.
- `core/views.py`: `/` to `/public/` redirect.
- `core/management/commands/check_config.py`: deployment configuration check.
- `core/management/commands/check_stripe.py`: local Stripe configuration check.
- `core/tests/`: initial data and command tests.

### Content And Media

- `content/models.py`: content pages, media items, menus, and menu items.
- `content/forms.py`: media upload form.
- `content/markdown.py`: escaped Markdown rendering and Bleach sanitization.
- `content/media.py`: image validation, safe storage naming, and profile
  derivatives.
- `content/context_processors.py`: database-backed root member menu.
- `content/views.py`: member pages, menu pages, and derived-media serving.
- `content/tests/`: Markdown, media, menu, and view tests.
- `templates/content/`: member page and menu rendering.

### Camp And Registration

- `camp/models.py`: camp years, tax tiers, add-ons, and per-user overrides.
- `camp/forms.py`: tax choices, dollar input, minimums, add-ons, and totals.
- `camp/services.py`: current year and registration completion policy.
- `camp/taxes.py`: availability windows, overrides, and cent conversion.
- `camp/views.py`: dashboard, Phagebook, taxes, and Stripe return page.
- `camp/templatetags/money.py`: USD display formatting.
- `camp/tests/`: dashboard, Phagebook, taxes, and tax-view tests.
- `templates/camp/`: dashboard, no-year, Phagebook, taxes, and return templates.
- `static/js/taxes.js`: progressive tax-card and total behavior.

### Surveys

- `surveys/question_types.py`: question types, render hints, and compatibility.
- `surveys/models.py`: surveys, questions, choices, conditions, responses,
  answers, and snapshots.
- `surveys/forms.py`: survey-builder forms and condition replacement.
- `surveys/services.py`: ordering, condition graphs, answer parsing, visibility,
  validation, and transactional submission.
- `surveys/views.py`: member survey and completion pages.
- `surveys/tests/`: survey model and member submission tests.
- `templates/surveys/`: member survey and completion templates.
- `static/js/surveys.js`: conditional-question and Other-field enhancement.

### Payments

- `payments/models.py`: payment attempts, add-on snapshots, payment logs,
  statuses, modes, and database constraints.
- `payments/checkout.py`: payment admission checks, local attempt creation,
  line items, metadata, and Checkout Session creation.
- `payments/stripe_client.py`: Stripe credentials and SDK call.
- `payments/webhooks.py`: signature verification, event routing, state changes,
  refunds, and logs.
- `payments/views.py`: public POST-only webhook endpoint.
- `payments/tests/`: checkout and webhook tests.

### Custom Admin

- `adminui/forms.py`: all account, camp, tax, payment, content, menu, and media
  forms.
- `adminui/views.py`: all custom admin workflows and cross-app orchestration.
- `adminui/urls.py`: admin route map.
- `adminui/tests/test_admin.py`: broad admin integration suite.
- `adminui/tests/test_surveys_admin.py`: survey-builder and response tests.
- `templates/adminui/`: all admin screens and intro-email template.
- `static/js/admin-users.js`: password generation, intro email, user filtering,
  and sorting.
- `static/js/admin-camp.js`: named-user comboboxes.
- `static/js/admin-menus.js`: menu URL suggestions.
- `static/js/admin-surveys.js`: survey filtering, collapsible question cards,
  and condition-choice rebuilding.

### Shared Frontend

- `templates/base.html`: global HTML shell and message rendering.
- `templates/public_base.html`: public Django-page header.
- `templates/member_base.html`: member navigation and logout.
- `templates/admin_base.html`: admin navigation.
- `static/css/site.css`: shared responsive styling.
- `public/index.html`: current static public-site placeholder.
- `static/img/header_icon.png`: shared header icon.
- `static/img/favicon.ico`: favicon asset, not explicitly linked in templates.

### Deployment And Recovery

- `deploy/thephage.toml.example`: production configuration example.
- `deploy/scripts/checkDeployment.sh`: local deployment checks.
- `deploy/scripts/runTestServer.sh`: disposable SQLite development server.
- `deploy/scripts/backup-thephage`: backup CLI wrapper.
- `deploy/scripts/restore-thephage`: restore CLI wrapper.
- `deploy_tools/backup.py`: database/config/media S3 backups and support bundles.
- `deploy_tools/restore.py`: support-bundle extraction and local database restore.
- `tests/test_deploy_tools.py`: backup and restore unit tests.
- `tests/test_config.py`: TOML loader tests.

## Ranked Findings

Priority definitions:

- P0 Critical: credible secret exposure, destructive data loss, or duplicate
  real charges.
- P1 High: payment, security, or recovery failures likely to affect production.
- P2 Medium: meaningful correctness, privacy, operational, or maintainability
  defects.
- P3 Low: localized defects and code smells.

## P0 Critical

### P0-1: A successful charge in `requires_review` does not block another payment

Locations:

- `payments/webhooks.py:109-121`
- `payments/checkout.py:27-41`
- `camp/views.py:204-220`
- `adminui/forms.py:484-500`

A webhook mismatch changes the payment to `requires_review`, even though Stripe
may have charged it successfully. Only `paid` and unexpired `created` records
block another checkout or manual payment. The member can therefore be charged
again before an administrator resolves the first transaction.

Suggested direction: treat `requires_review` as payment-blocking and centralize
the blocking policy for both member checkout and manual payment creation.

### P0-2: Payment state transitions can reverse refunds and review decisions

Locations:

- `payments/webhooks.py:98-145`
- `payments/webhooks.py:213-251`

A replayed completion event can move `refunded`, `cancelled`, `failed`, or
`requires_review` back to `paid`. A duplicate full-refund event can move
`refunded` to `requires_review`.

Suggested direction: implement an explicit transition table. Normally only
`created -> paid` should happen automatically. Refunded and review states should
not be cleared by a replayed completion event.

### P0-3: Nginx is granted read access to application secrets

Locations:

- `docs/deployment.md:126-155`
- `docs/deployment.md:606`

The deployment runbook adds `www-data` to group `phage`, then stores the TOML
configuration as `root:phage` mode `0640`. Nginx can therefore read the Django
secret, database password, and live Stripe credentials.

Suggested direction: use a separate socket-access group. Nginx must not belong
to the group that can read application configuration.

### P0-4: Restore can recursively delete an arbitrary supplied directory

Locations:

- `deploy_tools/restore.py:74-91`
- `deploy_tools/restore.py:119-127`

`--restore-root` is passed to `shutil.rmtree()` before the archive is validated.
A typo can delete unrelated data, and a bad archive destroys a previous good
extraction before replacement.

Suggested direction: constrain restore roots to a dedicated base and validate a
new temporary extraction before replacing an existing extraction.

## P1 High

### P1-1: Concurrent requests can create multiple chargeable Checkout Sessions

Locations:

- `payments/checkout.py:44-97`
- `payments/models.py:58-72`
- `adminui/forms.py:474-500`

Existing-payment checks do not lock a shared user/year record. Concurrent
requests can create different local payments and Stripe idempotency keys, so
multiple real charges remain possible even though the database prevents two
local `paid` rows.

Suggested direction: serialize all payment admission for a user/year and repeat
the checks under the same lock.

### P1-2: Admin cancellation leaves the Stripe Session payable

Locations:

- `adminui/views.py:557-592`
- `payments/checkout.py:35-41`
- `payments/webhooks.py:98-145`

Cancellation changes local status only. It unblocks replacement checkout while
the original Stripe Session may still be paid.

Suggested direction: expire the remote Session before unblocking, or retain a
blocking/review state when remote expiration is uncertain.

### P1-3: Failed card events may unblock a still-active Checkout Session

Locations:

- `payments/webhooks.py:186-210`
- `payments/checkout.py:35-41`

`payment_intent.payment_failed` marks the local payment failed even though
hosted Checkout may still permit another card attempt in the same Session. The
member can use that Session and create a replacement.

Suggested direction: track Checkout Session lifecycle separately from an
individual failed card attempt.

### P1-4: Some webhook handlers can overwrite a concurrent completion

Locations:

- `payments/webhooks.py:84-145`
- `payments/webhooks.py:186-251`

Completion uses a transaction and row lock, but failure, expiration, and refund
handlers do not. A stale handler can overwrite a newly paid record.

Suggested direction: lock and re-evaluate every payment transition inside a
transaction and commit its result log atomically.

### P1-5: Non-completion webhooks do not fully verify mode and object identity

Location:

- `payments/webhooks.py:186-267`

Expiration, failure, and refund events can locate a payment by metadata ID
without confirming test/live mode or matching the local Checkout Session or
Payment Intent.

Suggested direction: verify mode and the applicable Stripe object ID before any
state mutation.

### P1-6: Stripe creation failure leaves a blocking local payment

Locations:

- `payments/checkout.py:61-124`
- `camp/views.py:210-218`

The local `created` payment commits before Stripe is called. Network or API
failure returns a server error, writes no failure log, and blocks retry for
approximately one hour.

Suggested direction: classify and log failures, preserve the same payment and
idempotency key for ambiguous retries, and provide an explicit retryable state.

### P1-7: Stripe credentials are process-global

Location:

- `payments/stripe_client.py:36-53`

The code assigns `stripe.api_key` globally. Overlapping test and live requests
can potentially use the wrong credential.

Suggested direction: use a request-scoped Stripe client or request options.

### P1-8: Admin can persist an invalid Stripe mode

Locations:

- `adminui/views.py:672-684`
- `core/models.py:12-20`
- `payments/models.py:77-91`

The mode is copied directly from POST data. Model field choices are not enforced
automatically by `save()`. An invalid value breaks checkout and can break both
webhook-secret verification attempts.

Suggested direction: use a validated `ChoiceField` and database check
constraint.

### P1-9: Admin mark-paid does not verify Stripe

Locations:

- `adminui/forms.py:552-566`
- `adminui/views.py:539-543`
- `adminui/views.py:595-661`

An admin-provided reference can mark `created`, `failed`, `cancelled`, or
`requires_review` payments paid without checking Stripe amount, currency, mode,
status, or metadata.

Suggested direction: restrict the action to intended review cases and verify the
referenced Stripe transaction. Keep any true manual override separately named
and strongly audited.

### P1-10: Conflicting Stripe references can produce a false audit trail

Location:

- `adminui/views.py:625-660`

If a payment already stores one Checkout Session ID, a different submitted ID
may be logged without being validated or stored.

Suggested direction: require equality for existing identifiers and log only
validated references.

### P1-11: Deployment checks accept example placeholders and debug mode

Locations:

- `core/management/commands/check_config.py:21-25`
- `core/management/commands/check_stripe.py:13-23`
- `deploy/thephage.toml.example:38-43`
- `deploy/thephage.toml.example:189-251`
- `deploy/scripts/checkDeployment.sh:85-91`

The checker looks for `change-me`, while the example uses `CHANGE_ME`. Stripe
checks require only non-empty strings, and the deployment script does not reject
`DEBUG=true` or run Django's deployment checks.

Suggested direction: reject normalized placeholder values, validate key
prefixes and secret strength, require production debug off, and run
`manage.py check --deploy`.

### P1-12: Scheduled backups cannot be restored by the restore CLI

Locations:

- `deploy_tools/backup.py:185-256`
- `deploy_tools/restore.py:44-94`

Normal backups produce separate database, config, media, and manifest objects.
Restore only accepts a support-bundle tarball containing `database.dump`.

Suggested direction: add and test list, fetch, verify, and scratch-restore
support for normal scheduled backup artifacts.

### P1-13: Restore database safety can be bypassed by connection configuration

Location:

- `deploy_tools/restore.py:10-41`

`pg_restore --dbname` accepts connection strings, while the safety check treats
the value as a simple name. Ambient libpq variables can also redirect the
operation.

Suggested direction: require a simple scratch identifier, force loopback
connection settings, clear unsafe ambient settings, and verify the target before
destructive restore.

### P1-14: Profile originals are placed under public `/media/`

Locations:

- `content/media.py:58-72`
- `content/models.py:45-47`
- `templates/accounts/profile.html:11-15`
- `docs/deployment.md:329-337`

Original uploads, including EXIF/GPS metadata, are served anonymously by Nginx
if the URL is known. This conflicts with the member-only Phagebook model.

Suggested direction: re-encode profile photos, strip metadata, and serve them
through authenticated or otherwise private storage.

### P1-15: High-pixel compressed images can exhaust application workers

Locations:

- `content/media.py:24-44`
- `content/media.py:96-125`

Validation limits bytes but not width, height, or total pixels. Derivative
generation fully decodes the image during a Phagebook request.

Suggested direction: reject excessive dimensions/pixel counts and handle Pillow
decompression-bomb exceptions.

### P1-16: Menu URLs permit executable schemes

Locations:

- `content/models.py:80-89`
- `adminui/forms.py:136-140`
- `templates/member_base.html:11-18`
- `templates/content/menu_detail.html:8-13`

Values such as `javascript:` and `data:` are rendered directly into member links.

Suggested direction: allow root-relative paths and an explicit set of external
schemes only.

### P1-17: Creating a future year publishes it immediately

Locations:

- `camp/services.py:10-11`
- `adminui/views.py:211-220`

Current year is always the maximum configured number. A future year cannot be
configured privately before `/dashboard/` and `/phagebook/` redirect to it.

Suggested direction: add explicit draft/current/open state and an activation
workflow.

### P1-18: Tax overrides bypass tax opening and closing

Locations:

- `camp/forms.py:131-169`
- `camp/taxes.py:11-26`

Reduced and waived override options are created before requiring any active
normal tax tier. Overridden users can pay before opening, after closing, or with
no normal tier configured.

Suggested direction: separate whether taxes are open from calculation of the
member's effective minimum.

### P1-19: Survey CSV export permits spreadsheet formula injection

Location:

- `adminui/views.py:1091-1131`

Member-controlled cells beginning with spreadsheet formula characters can be
evaluated when an administrator opens the CSV.

Suggested direction: neutralize dangerous leading characters in every exported
cell while retaining original database values.

## P2 Medium

### P2-1: Test payments remain registration truth after switching live

Locations:

- `adminui/views.py:672-690`
- `payments/checkout.py:27-41`
- `camp/services.py:30-38`

Paid lookup ignores payment mode. A forgotten test payment can keep a member
registered and prevent their live payment. This is currently managed only by
the operational cleanup checklist.

### P2-2: Reusing a survey across years reuses completion state

Locations:

- `camp/models.py:25-31`
- `surveys/models.py:158-168`
- `camp/services.py:24-27`

Responses are unique by survey/user, not camp year. Selecting last year's survey
for a new year immediately completes it for prior respondents.

### P2-3: Survey structural changes do not invalidate prior completion

Locations:

- `camp/services.py:24-28`
- `surveys/services.py:254-292`

Adding a new required question leaves all existing response rows considered
complete.

### P2-4: Impossible survey dates can produce a server error

Location:

- `surveys/services.py:369-382`

An ISO-shaped but impossible date such as `2026-02-31` can raise `ValueError`
instead of producing a validation error.

### P2-5: Single-choice questions can store multiple values

Location:

- `surveys/services.py:303-398`

A crafted POST can submit one normal choice plus Other or repeated choice IDs.
Multi-choice answers can also retain duplicates.

### P2-6: Multiple controlling questions can exist for one dependent question

Locations:

- `surveys/models.py:116-155`
- `surveys/services.py:404-437`
- `surveys/views.py:89-95`

Normal forms produce one parent, but the schema permits several. Runtime chooses
the first without deterministic semantics.

### P2-7: Conditional graph updates can race into a cycle

Location:

- `surveys/services.py:66-148`

Graph validation occurs before condition replacement without locking the survey
graph.

### P2-8: JavaScript condition visibility can disagree with the server

Location:

- `static/js/surveys.js:12-24`
- `static/js/surveys.js:46-72`

A late controlling question can leave a dependent hidden for one update cycle,
while server validation considers it visible and required.

### P2-9: Media replacement/deletion leaves old files or derivatives

Locations:

- `accounts/forms.py:64-68`
- `content/models.py:49-54`
- `content/media.py:76-125`
- `content/views.py:36-47`

Replacing a profile photo leaves the previous media item. Deleting media removes
only the original and leaves generated derivatives accessible to members.

### P2-10: Media creation is not failure-atomic

Location:

- `content/media.py:47-72`

Storage or database failures can leave provisional rows or orphan files. Long
filenames can also exceed path limits after the media ID prefix is added.

### P2-11: Member bios permit remote tracking images

Locations:

- `content/markdown.py:37-48`
- `templates/camp/phagebook.html:23-26`

A member can embed a remote HTTPS image that receives every Phagebook viewer's
IP address and request metadata.

### P2-12: Tax end dates close at the start of the selected day

Locations:

- `adminui/forms.py:151-159`
- `camp/taxes.py:11-26`

Both start and end dates become local midnight and expiration is exclusive. An
end date of March 1 means unavailable throughout March 1.

### P2-13: Any configured year can accept payments

Locations:

- `camp/urls.py:8-14`
- `camp/views.py:198-235`

Historical and future year tax routes remain financially active whenever their
tier dates permit it. There is no explicit year-level payment-open state.

### P2-14: Manual paid records are difficult to correct safely

Locations:

- `adminui/forms.py:418-533`
- `adminui/views.py:477-517`

Submission immediately creates a paid record. The reference is optional, there
is no confirmation summary, and paid manual records cannot be voided through the
admin UI.

### P2-15: Initial passwords remain reusable indefinitely

Locations:

- `adminui/views.py:107-135`
- `templates/adminui/users.html:42-53`
- `templates/adminui/emails/new_user_intro.txt:3-9`

Passwords are visible, returned as JSON, copied to the clipboard, and emailed.
There is no forced first-login rotation, and password-bearing responses lack an
explicit `Cache-Control: no-store` policy.

### P2-16: Login lacks throttling and whitespace counts as a password class

Locations:

- `accounts/views.py:27-45`
- `accounts/password_validation.py:8-26`

The public login endpoint permits unlimited attempts. The custom password
validator counts whitespace as the fourth class, so letters plus spaces satisfy
the two-class policy.

### P2-17: Alternate hostnames can lose the session after Stripe return

Locations:

- `deploy/thephage.toml.example:28-35`
- `payments/checkout.py:174-180`
- `thephage/settings.py:115-121`

Nginx accepts bare and `www` hosts, but Stripe returns to one configured
`base_url`. Host-only session cookies do not cross between those hosts.

### P2-18: Deleting a CampYear-referenced survey returns an unhandled error

Locations:

- `adminui/views.py:908-920`
- `camp/models.py:25-30`

The database correctly protects the survey, but the view does not catch
`ProtectedError` and explain which camp year references it.

### P2-19: Failed survey slug validation can render actions for another survey

Locations:

- `adminui/views.py:792-805`
- `adminui/views.py:922-938`

A bound `ModelForm` mutates its instance before uniqueness validation. Posting
another survey's slug can cause rerendered action URLs to target the wrong slug.

### P2-20: Choice creation can partially save unrelated survey edits

Locations:

- `adminui/views.py:827-874`
- `adminui/views.py:955-985`

Question and options edits may commit before choice validation. The operation can
display a failure while some submitted edits have succeeded.

### P2-21: Test-payment cleanup is effectively one-click and unaudited

Locations:

- `templates/adminui/stripe.html:9-13`
- `adminui/views.py:685-691`

The hidden form supplies its own confirmation. Logs and payments are deleted in
separate operations and no surviving audit event records the cleanup.

### P2-22: Backup retention settings are not implemented

Locations:

- `thephage/config.py:195-210`
- `deploy_tools/backup.py:185-256`

Retention periods are parsed and documented but never applied.

### P2-23: Missing config backup paths are silently skipped

Location:

- `deploy_tools/backup.py:177-183`

A backup can report success after omitting a missing TOML, Nginx, or systemd
file.

### P2-24: Backup names collide within the same minute

Location:

- `deploy_tools/backup.py:31-33`

Concurrent or repeated runs can write the same local and S3 paths.

### P2-25: Sensitive local backup permissions depend on process umask

Locations:

- `deploy_tools/backup.py:57-78`
- `deploy_tools/backup.py:138-187`

Database dumps, media, and secret-bearing config archives do not explicitly
enforce private modes.

### P2-26: S3 backup safety controls are not verified

Location:

- `deploy_tools/backup.py:192-256`

Encryption, private access, versioning, and lifecycle are documented but not
checked. `sync --delete` is dangerous when versioning is missing or the media
root is unexpectedly empty.

### P2-27: Deployment verification is narrower than its success message

Location:

- `deploy/scripts/checkDeployment.sh:67-120`

It does not verify file permissions, free space, service state, HTTP/TLS,
collected assets, real Stripe connectivity, S3 access, or a real backup/restore
round trip.

### P2-28: Backup artifacts are not a coherent point-in-time snapshot

Location:

- `deploy_tools/backup.py:150-256`

Database, config, media, and manifests are collected sequentially. Partial S3
sets remain after failure and there is no completion marker or checksum set.

### P2-29: Restore can leave a partially restored database

Locations:

- `deploy_tools/restore.py:33-41`
- `deploy_tools/restore.py:87-94`

`pg_restore` does not use an explicit exit-on-error/single-transaction strategy,
and the target is not necessarily a newly created scratch database.

## P3 Low And Code Smells

### P3-1: `SurveyResponse.updated_at` is stale after revisions

Locations:

- `surveys/models.py:158-168`
- `surveys/services.py:274-292`

Answer rows are updated, but the existing parent response is not saved.

### P3-2: Number questions accept non-finite Decimal values

Location:

- `surveys/services.py:378-382`

`NaN`, `Infinity`, and `-Infinity` pass `Decimal()` parsing.

### P3-3: Bulk deletion bypasses model-level protections

Locations:

- `content/models.py:49-54`
- `content/models.py:74-77`
- `surveys/models.py:106-113`

Queryset deletion bypasses instance `delete()` methods used for media cleanup,
root-menu protection, and condition-referenced choice protection.

### P3-4: Configuration integer validation accepts booleans

Location:

- `thephage/config.py:137-141`

Python treats `bool` as a subclass of `int`, allowing invalid TOML values such as
`port = true`.

### P3-5: Admin overview pages are unbounded

Locations:

- `adminui/views.py:86-104`
- `adminui/views.py:398-407`
- `adminui/views.py:1108-1125`

Users, payments, media, surveys, and response matrices lack server-side
pagination.

### P3-6: Admin modules are cross-domain monoliths

Locations:

- `adminui/views.py:1-1460`
- `adminui/forms.py:1-566`

Account, camp, survey, payment, content, and media behavior is concentrated in
two large modules. This increases coupling and makes financial and survey logic
harder to isolate.

### P3-7: Important invariants rely on `clean()` or instance `delete()`

Django does not automatically call `full_clean()` during `save()`, and queryset
deletion bypasses instance `delete()`. Several protections therefore depend on
all callers using a particular form or service path.

### P3-8: Payment and ordering policies are duplicated

Payment blockers are implemented independently in checkout, manual-payment, and
resolution code. Display-order allocation and date conversion are also repeated.
This has allowed pending/review behavior to diverge across workflows.

### P3-9: Operational documentation has drifted

Locations:

- `docs/stripe.md:119-165`
- `docs/stripe.md:391-415`
- `docs/yearly-rollover.md:492-505`

Documentation says Stripe mode lives in TOML and `requires_review` resolution
happens directly in the database. Mode is actually database-backed, and the
admin includes a web resolution action.

### P3-10: Deployment checks require an unused external `tar`

Location:

- `deploy_tools/backup.py:259-265`

Archive creation uses Python's `tarfile`, but tool verification requires an
external `tar` executable.

### P3-11: The public site is still a placeholder

Location:

- `public/index.html:1-12`

Deploying the tracked public tree as-is does not produce a finished public site.

### P3-12: Local test server can be exposed with known credentials

Locations:

- `deploy/scripts/runTestServer.sh:35-38`
- `deploy/scripts/runTestServer.sh:120-135`
- `deploy/scripts/runTestServer.sh:186-199`

The script permits a non-loopback bind while using debug mode, a fixed secret,
and a known administrator password.

## Positive Observations

- The codebase follows a conventional Django structure.
- The product scope is explicit and appropriately small for V1.
- Member and admin authorization is centralized in clear decorators.
- No missing `admin_required` decorator or obvious member-to-admin authorization
  bypass was found in the reviewed routes.
- Markdown is escaped before rendering and sanitized through a shared helper.
- Image uploads validate extension, reported MIME type, and Pillow format.
- Money is stored and calculated in integer cents.
- Payment totals and paid-record uniqueness have database constraints.
- Stripe Checkout, not the application, handles card data.
- The browser return URL does not mark payments paid.
- Checkout metadata is present on both Session and Payment Intent.
- Successful completion currently uses a transaction and row lock.
- Member survey answers are scoped to the logged-in user.
- Server-side survey validation remains authoritative without JavaScript.
- Survey answer snapshots preserve historical context after edits/deletions.
- Admin object IDs are generally scoped to their route parent.
- The test suite is substantial and business-rule focused.
- Runbooks cover yearly rollover, Stripe testing, deployment, and recovery.

## Test Assessment

Strong existing coverage includes:

- Email authentication and profile workflows.
- Member/admin access distinctions.
- Dashboard checklist progression.
- Tax calculations, add-ons, and ordinary override cases.
- Survey models, member submission, conditions, and admin builder workflows.
- Normal Stripe checkout and common webhook happy paths.
- Custom admin CRUD and route scoping.
- Basic backup/restore command construction.

Highest-value missing coverage:

- Concurrent checkout, manual-payment, and webhook operations.
- Full payment state-transition permutations.
- Checkout Session behavior after cancellation and card failure.
- Test/live webhook isolation for every event type.
- Stripe API, network, malformed response, and post-Stripe database failures.
- `requires_review` followed by another checkout/manual payment.
- Duplicate refunds and completion replay after refund.
- Normal scheduled-backup to scratch-restore round trip.
- Restore-root containment and remote-database safety.
- Deployment shell script behavior and production security checks.
- Anonymous access to profile originals.
- Excessive image dimensions and decompression-bomb handling.
- Spreadsheet formula prefixes in CSV exports.
- Impossible dates, repeated choices, and non-finite survey numbers.
- JavaScript runtime behavior for nested survey conditions and tax calculations.
- CSRF-enforced clients and malformed admin action IDs.
- Exact tax date boundaries and Pacific daylight-saving transitions.

## Suggested Remediation Order

When work resumes, use this order:

1. Fix production group/config permissions.
2. Define and enforce the payment state machine.
3. Make every potentially charged/review payment block another payment.
4. Serialize checkout and manual-payment admission by user/year.
5. Integrate remote Checkout Session expiration with cancellation/retry policy.
6. Lock and verify every webhook transition.
7. Harden Stripe mode validation and remove global API-key mutation.
8. Make scheduled backups demonstrably restorable.
9. Constrain destructive restore paths and database targets.
10. Protect profile media and bound image processing.
11. Add explicit camp-year activation and payment-open state.
12. Fix survey malformed-input and data-shape bugs.
13. Harden menu URLs and CSV exports.
14. Address backup retention, permissions, and S3 checks.
15. Reconcile runbooks with actual behavior.
16. Refactor duplicated business policies only after correctness is covered by
    focused tests.

## Current Readiness Assessment

The project has a strong functional foundation and substantially more test
coverage than an early prototype. The major concerns are concentrated in the
most consequential boundaries: Stripe state transitions, duplicate-payment
prevention, deployment secret permissions, restore safety, backup
restorability, and private media handling.

The application should not yet be considered ready for real payment collection
or backup-dependent production recovery until the P0 findings and the core P1
payment/deployment/recovery findings are addressed and verified with tests.

## Reimbursement Design Review Decisions

The reimbursement design was reviewed separately after this general code
review. The product is intentionally optimized for a trusted community of at
most approximately 200 people and a very small annual reimbursement volume.

The following decisions are intentional and should not be reopened without a
real operational need:

- Split moves selected expenses into a new draft and does not preserve prior
  expense versions.
- Members may unsubmit their own submitted reimbursements.
- Rare races between external manual payment and website state are handled with
  clear conflict messages and direct communication, not a payment-processing
  state.
- Draft expenses are corrected by delete-and-re-add; there is no expense edit
  workflow.
- Any reimbursement whose current state is draft may be deleted, even if it was
  submitted or rejected previously.
- Exceptional corrections may be performed directly in the database.
- Paid amount and category snapshots are unnecessary because normal UI paths do
  not edit paid expenses or used category names.
- User, camp-year, and administrator-account deletion edge cases are outside
  the reimbursement V1 scope.
- Private receipt operations use safe ordering and best-effort file cleanup;
  occasional orphan files are acceptable.
- Private receipts must be included in backup, but completing the repository's
  overall restore system is outside the reimbursement feature.
- Production startup uses a stable wrapper that automatically applies committed
  migrations, runs collectstatic, prepares application-owned directories, and
  refuses to start Gunicorn when required local configuration is incomplete.
- Startup diagnostics identify the exact file, change, command, and reason for
  every root-owned change that the application cannot perform itself.
- Reimbursements are implemented in a dedicated Django app and use foreign keys
  to the existing `CampYear` model.
- Human-readable reimbursement numbers are calculated from the greatest
  existing number in the year, protected by a database unique constraint; no
  dedicated sequence model is required.
- New camp years begin with no reimbursement categories; categories are not
  copied from prior years.
- V1 accepts a size-valid `.pdf` upload based on its filename extension without
  parsing PDF contents.
- Rejection notes are optional.
- The receipt route is year-scoped under the member reimbursement route.
- Spreadsheet text uses a leading apostrophe for formula-like cells.
- Reimbursement navigation is deferred until implementation is complete.
- Expense descriptions are required and use 2,000 characters; notes and receipt
  explanations use 10,000 characters, original filenames 255 characters, and
  individual expenses are capped at $1,000,000.00.
- Zelle emails are trimmed and lowercased. Paper-check states use uppercase
  two-letter state/territory codes and ZIP supports five digits or ZIP+4.
- Draft admin pages do not expose current payout-profile details before a
  submitted snapshot exists.
- Draft deletion requires typing `delete`; Pay is a direct admin action without
  a separate confirmation checkbox; rejection notes remain optional.
- The feature should remain small rather than adding generalized audit,
  reconciliation, cleanup, or accounting subsystems for hypothetical cases.

The reimbursement implementation should still protect ordinary access,
validate positive integer-cent amounts, keep receipts outside public media,
scope every member/admin action correctly, recheck state before transitions,
and include receipt files in scheduled backup.
