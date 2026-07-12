# Storage And Database Design

## Purpose

This document describes how the site stores its data.

It covers:

- Database schema.
- Media/file storage.
- Static public files.
- Stripe configuration, test/live Stripe payment records, and manual payment records.
- Backup and recovery assumptions.

The first focus is the database schema. Other storage details are included afterward.

## Database

The application should use PostgreSQL.

Django should own the application schema through migrations.

All text/string fields should support Unicode.

Most admin-edited records should include audit fields:

- Created at.
- Updated at.
- Created by, where practical.
- Updated by, where practical.

These fields are primarily for troubleshooting. They are not expected to be part of normal day-to-day workflows.

## Schema Overview

V1 database areas:

- Users and profiles.
- Camp years.
- Member content pages.
- Menus.
- Media records.
- Tax configuration.
- Payments.

Future database areas:

- Surveys.
- Survey reports.
- Jobs/shifts.
- Payment requirements.

## Users

The user table stores login and account information.

Email is the primary login identifier. Usernames are not needed.

Likely fields:

- ID.
- Email.
- Password hash.
- First name.
- Last name.
- Is active.
- Is admin.
- Created at.
- Updated at.
- Last login.

`is_active` controls whether the user can log in.

`is_admin` controls whether the user can access admin pages.

The site does not need separate `is_staff` or `is_superuser` product concepts.

If Django requires internal staff/superuser behavior for framework compatibility, that should be handled as an implementation detail and not exposed as product-level account state.

## Member Profiles

Each user has exactly one member profile.

Because the relationship is 1:1, user and profile data should be presented together in the admin UI.

Likely fields:

- ID.
- User.
- Profile photo media item, optional.
- Bio text.
- Created at.
- Updated at.
- Created by, where practical.
- Updated by, where practical.

The profile should not store contact details, yearly participation status, payment status, or survey answers.

Registration profile completion uses first name and last name from `User`, plus profile photo and bio from `MemberProfile`.

Members can replace their profile photo through the profile page. Members do not need a self-service profile photo delete action in V1.

## Camp Years

The camp year table is intentionally small.

Likely fields:

- ID.
- Year.
- Created at.
- Updated at.
- Created by, where practical.
- Updated by, where practical.

The current year can be inferred from the maximum configured year or from context.

Tax tiers, add-ons, payments, and the optional Camp survey point to a camp year. Future jobs may also point to a camp year.

## Content Pages

Content pages are member-facing Markdown pages managed in the admin.

Public pages are not stored here. Public pages are static files under `/public/`.

Likely fields:

- ID.
- Title.
- Slug.
- Body Markdown.
- Created at.
- Updated at.
- Created by, where practical.
- Updated by, where practical.

There is no published/unpublished state.

If a page exists, it is live.

If an admin wants a draft, they can keep it outside the site until ready. This avoids extra state and avoids questions like whether drafts appear in menus, whether direct URLs work, and who can preview unpublished content.

Year-specific content should be handled through the title and slug, for example:

- `2026-arrival-info`

There is no `year_id` on content pages.

## Menus

Menus store named lists of navigation items.

The top-level member menu is the `root` menu.

A menu has an internal name. A menu item belongs to a menu and is just a visible label, URL, and display order.

Likely menu fields:

- ID.
- Menu name.
- Created at.
- Updated at.
- Created by, where practical.
- Updated by, where practical.

Likely menu item fields:

- ID.
- Menu.
- Label.
- URL.
- Display order.
- Created at.
- Updated at.
- Created by, where practical.
- Updated by, where practical.

There is no published/unpublished state.

If a menu item exists, it is live.

URLs may be internal paths or full external URLs.

URLs may also point to another member-only menu page.

Examples:

- `/dashboard/`
- `/phagebook/`
- `/2026/taxes/`
- `/profile/`
- `/pages/camp-info/`
- `/menu/camp-info/`
- `https://youtube.com/...`

The app should not need special menu link types for content pages, application pages, menu pages, or external URLs. These are all real endpoints, so the menu can link to them directly.

Menu items should be sorted by display order, then label.

If an endpoint changes, the menu can be updated.

## Media Records

Media records track uploaded files.

Files are stored on disk. The database stores metadata and the path/name needed to find the file.

Likely fields:

- ID.
- Original filename.
- Stored filename.
- File path.
- Media type.
- Title.
- Uploaded by.
- Created at.
- Updated at.
- Created by, where practical.
- Updated by, where practical.

Stored filenames should include the database ID and a safe version of the original filename.

Example:

- `481-phage-map-2026.png`

This makes files easier to identify if someone is browsing the filesystem during troubleshooting.

For V1, media uses one flat folder with no subfolders.

Later, media may gain a folder structure that reflects how files are stored on disk.

When media is deleted, delete the database record and the file from disk.

Full system backups and the S3 media backup are expected to cover recovery. Media backup should be an incremental S3 sync with mirrored deletes and S3 bucket versioning.

## Tax Tiers

Tax tiers define suggested/minimum payment levels for a camp year.

Each tax tier has a start date and expiration date. A tier is available when `start_date <= now < expiration_date`.

Multiple tax tiers may be available at the same time. The member chooses one available tier.

Likely fields:

- ID.
- Camp year.
- Name.
- Description.
- Minimum amount in cents.
- Start date.
- Expiration date.
- Display order.
- Created at.
- Updated at.
- Created by, where practical.
- Updated by, where practical.

A tax tier is a minimum, not a fixed required amount.

Members may enter a higher amount.

There is no `is_active` field. If a tier should not be offered, delete it or change its dates.

## Tax Add-Ons

Tax add-ons define optional items that can be added to a tax payment.

Add-ons are year-specific.

Likely fields:

- ID.
- Camp year.
- Name.
- Description.
- Amount in cents.
- Start date.
- Expiration date.
- Display order.
- Created at.
- Updated at.
- Created by, where practical.
- Updated by, where practical.

There is no `is_active` field. If an add-on should not be offered, delete it or change its dates.

## Tax Overrides

Tax overrides define per-user exceptions for a camp year.

Most users do not have a tax override.

There are two override types:

- Reduced minimum amount.
- Tax waived.

Likely fields:

- ID.
- User.
- Camp year.
- Override type.
- Minimum amount in cents, required for reduced minimum overrides.
- Created at.
- Updated at.
- Created by, where practical.
- Updated by, where practical.

There should be at most one tax override per user per camp year.

A reduced minimum override changes the minimum amount the member may pay.

A tax waived override means the member does not need to pay taxes for that camp year and should not create a payment record by itself.

If an override is no longer needed, delete it.

## Payments

Payments store local records of Stripe payment activity and admin-created manual payment activity.

The site should not store card details.

Currency is always USD. If that ever changes, the system can be modified. Currency does not need to be a database field in V1.

Likely fields:

- ID.
- User.
- Camp year.
- Amount in cents.
- Status.
- Mode.
- Stripe Checkout Session ID, blank for manual payments.
- Stripe Payment Intent ID, blank for manual payments.
- Checkout expiration timestamp, blank for manual payments.
- Note, optional.
- Created at.
- Updated at.
- Paid at.
- Created by.
- Updated by, where practical.

Initial payment statuses:

- `created`
- `paid`
- `failed`
- `cancelled`
- `refunded`
- `requires_review`

Payment mode values:

- `stripe_test`
- `stripe_live`
- `manual`

Payment mode is stored for correctness, review, and troubleshooting. Test/live Stripe configuration is exposed through `/admin/stripe/`; manual payments are created from the payments admin.

V1 accepts credit cards only through Stripe Checkout.

Manual payments represent off-site tax payments entered by an admin. They are created as paid records, store `created_by` as the admin user, can include an optional note/reference, and do not have Stripe IDs.

Stripe Checkout payments store `created_by` as the paying member.

A member is considered paid for a camp year if they have at least one `paid` payment for that year.

If a Stripe webhook or payment event does not match expected local payment data, the payment should be marked `requires_review`. For V1, these cases can be resolved directly in the database by an admin if needed. No custom web workflow is required.

Test payments can be deleted from `/admin/stripe/` by matching `mode = "stripe_test"`. Deleting a test payment deletes the local database records. Stripe test references do not need to be preserved locally. Manual payments are not test payments and must not be deleted by this cleanup path.

## Payment Logs

Payment logs store Stripe-related request, response, webhook activity, and manual payment audit activity for troubleshooting.

The site should log useful traffic between the website and Stripe, including checkout creation, Stripe responses, webhook receipt, webhook validation, and webhook processing results.

Logs should avoid storing secrets and should not include card data. If a payload contains sensitive values, those values should be redacted before storage.

Likely fields:

- ID.
- Payment, optional.
- Direction.
- Event type.
- Mode.
- Stripe event ID, optional.
- Stripe Checkout Session ID, optional.
- Stripe Payment Intent ID, optional.
- Status/result.
- Message.
- Payload, redacted where needed.
- Created at.

Possible directions:

- `to_stripe`
- `from_stripe`
- `webhook`
- `internal`

Payment logs are expected to be useful for debugging rare payment issues. They are not intended to drive normal payment state by themselves.

## Payment Add-Ons

Payment add-ons store the add-ons selected as part of a payment.

Likely fields:

- ID.
- Payment.
- Tax add-on.
- Add-on name snapshot.
- Amount in cents snapshot.
- Created at.
- Updated at.

The name and amount are snapshotted at payment time so old payment records remain understandable if the original add-on changes later.

## Future Payment Requirements

Payment requirements are a future concept.

They may eventually track what a user must complete before paying taxes for a camp year.

Possible future requirements:

- Complete survey.
- Sign up for jobs/shifts.
- Acknowledge information.
- Manual admin approval.

This does not need to be implemented in the first database pass unless the feature is active.

## Survey Tables

The current app includes survey tables for:

- Surveys.
- Survey questions.
- Survey choices.
- Survey question conditions.
- Survey responses.
- Survey answers.

Surveys are generic and accessed at `/survey/<slug>/`. A camp year may optionally select one survey as its Camp survey.

Survey answers are not stored directly on users.

## Future Job/Shift Tables

Future job/shift tables are out of V1 scope.

The design should leave room for a future jobs section, but this document will not define that schema until the feature becomes active.

## File Storage

Media files should be stored on disk.

For V1, use one flat media folder.

Example:

- `media/uploads/`

Stored filenames should include the media database ID and a safe original filename.

Example:

- `481-phage-map-2026.png`

If media is deleted through the admin, both the file and database record should be deleted.

Full system backups and the S3 media backup are expected to provide recovery. Media backup should be an incremental S3 sync with mirrored deletes, backed by S3 bucket versioning. The default lifecycle rule should keep non-current media object versions for 45 days.

## Public Static Files

Public pages are static files under `/public/`.

Examples:

- `/public/index.html`
- `/public/about.html`
- `/public/assets/...`

The web root `/` redirects to `/public/`.

Public static files are not Django content pages and are not stored in the database.

Deployment should make it easy to upload or replace public static files.

## Stripe Configuration Storage

Stripe configuration is stored in the deployed TOML config file:

```text
/etc/thephage/thephage.toml
```

The committed example is:

```text
deploy/thephage.toml.example
```

The admin UI does not need to edit raw Stripe secret values.

The `/admin/stripe/` page should show:

- Whether Stripe configuration appears valid.
- Whether the site is in test or live mode.
- Which mode future payments will use.
- Whether webhook/configuration checks are healthy.
- Recent Stripe/payment log entries.
- Test and live payment activity needed for troubleshooting.

Test mode must be obvious.

Live mode must be obvious.

Admins should be able to switch the site between Stripe test mode and Stripe live mode. Production may run in test mode when admins are verifying the yearly payment flow.

The member-facing payment workflow should be the same in test mode and live mode. Test/live state should only be exposed in the Stripe admin area.

## Backups And Recovery

The system is expected to run somewhere where full system backups are easy, such as EC2.

Backups should cover:

- Database.
- Media files.
- Public static files.
- Application configuration needed to restore the site.
- Stripe configuration location, without exposing secrets in documentation.

Because full system backups exist, deleted media and deleted test payment records do not need soft-delete behavior.

Lightweight active-season backups should be handled by external server utilities, not by Django request/response code. The expected utilities are `backup-thephage` and `restore-thephage`.

## Related Design Documents

More detailed implementation guidance now lives in:

- `design_docs/models.md`.
- `design_docs/admin_and_pages.md`.
- `design_docs/content_media_security.md`.
- `design_docs/implementation_plan.md`.
- `design_docs/stripe_implementation.md`.

Operational backup and deployment details live in:

- `docs/backup-and-restore.md`.
- `docs/deployment.md`.
