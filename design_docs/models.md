# Models

## Purpose

This document defines the V1 Django database model contract for `thephage.org`.

The goal is to keep the schema small, explicit, and easy to maintain.

## Global Conventions

- Database is PostgreSQL.
- Primary keys use Django `BigAutoField` unless otherwise noted.
- Text fields support Unicode.
- Money is stored as integer cents.
- Currency is not stored in V1 because all payments are USD.
- Timestamps are stored in UTC.
- Admin-entered tax dates are entered and displayed in `America/Los_Angeles`.
- Markdown fields are rendered through the shared Markdown sanitizer.
- Uploaded media is image-only in V1.
- Most admin-managed records include `created_at`, `updated_at`, `created_by`, and `updated_by` where practical.

## User

Custom Django user model.

Use email for login. Do not use usernames.

| Field | Type | Notes |
|---|---|---|
| `email` | `EmailField(unique=True)` | Login identifier, stored lowercase |
| `password` | Django password hash | From `AbstractBaseUser` |
| `first_name` | `CharField(max_length=150, blank=True)` |  |
| `last_name` | `CharField(max_length=150, blank=True)` |  |
| `is_active` | `BooleanField(default=True)` | Controls login |
| `is_admin` | `BooleanField(default=False)` | Controls site admin access |
| `date_joined` | `DateTimeField(default=timezone.now)` | UTC |
| `last_login` | `DateTimeField(null=True, blank=True)` | UTC |
| `updated_at` | `DateTimeField(auto_now=True)` | UTC |

Rules:

- `USERNAME_FIELD = "email"`.
- Email normalization uses `.lower()`.
- Login compares normalized lowercase email.
- No username.
- No product-level `is_staff`.
- No product-level `is_superuser`.
- Admin access checks use `is_admin`.
- Inactive users cannot log in.
- Inactive users cannot access member pages.
- Inactive users cannot pay taxes.

Constraints and indexes:

- Unique `email`.
- Optional defensive PostgreSQL unique constraint on `Lower("email")`.

## MemberProfile

Each user has exactly one profile.

| Field | Type | Notes |
|---|---|---|
| `user` | One-to-one `User` | `CASCADE` |
| `photo` | FK `MediaItem`, nullable | `SET_NULL` |
| `bio_markdown` | `TextField(blank=True)` | Markdown |
| `created_at` | `DateTimeField(auto_now_add=True)` | UTC |
| `updated_at` | `DateTimeField(auto_now=True)` | UTC |

Rules:

- Profile is created when user is created.
- Members can edit their bio.
- Members can replace their profile photo.
- Members cannot self-delete their profile photo in V1.
- Bio is Markdown and sanitized on display.
- Admins can manage profile data from user admin.
- Registration profile completion requires first name, last name, profile photo, and bio.

## SiteSettings

Singleton row for database-backed operational settings.

| Field | Type | Notes |
|---|---|---|
| `id` | `SmallIntegerField(primary_key=True)` | Always `1` |
| `stripe_mode` | `CharField` | `test` or `live` |
| `updated_at` | `DateTimeField(auto_now=True)` | UTC |
| `updated_by` | FK `User`, nullable | `SET_NULL` |

Rules:

- Exactly one row.
- Default Stripe mode is `test`.
- Stripe credentials stay in `/etc/thephage/thephage.toml`.
- `/admin/stripe/` changes `stripe_mode`.
- This setting controls future Stripe Checkout payments only. Individual payment records store their actual source in `Payment.mode`.

## CampYear

Represents one camp year.

| Field | Type | Notes |
|---|---|---|
| `year` | `PositiveSmallIntegerField(unique=True)` | Example: `2026` |
| `dashboard_pre_page` | FK `ContentPage`, nullable | `PROTECT` |
| `dashboard_post_page` | FK `ContentPage`, nullable | `PROTECT` |
| `camp_survey` | FK `Survey`, nullable | `PROTECT` |
| `created_at` | `DateTimeField(auto_now_add=True)` | UTC |
| `updated_at` | `DateTimeField(auto_now=True)` | UTC |
| `created_by` | FK `User`, nullable | `SET_NULL` |
| `updated_by` | FK `User`, nullable | `SET_NULL` |

Rules:

- Current year is inferred from the max configured `year`.
- Do not store `is_current`.
- Dashboard content references member-only content pages.
- `dashboard_pre_page` appears above the dashboard checklist.
- `dashboard_post_page` appears below the dashboard checklist.
- Referenced dashboard pages use `PROTECT` so admins cannot accidentally delete content used by a camp year dashboard.
- Referenced Camp surveys use `PROTECT` so admins cannot accidentally delete a survey required by a camp year.

## TaxTier

Minimum payment option for a camp year.

| Field | Type | Notes |
|---|---|---|
| `camp_year` | FK `CampYear` | `CASCADE` |
| `name` | `CharField(max_length=120)` | Display name |
| `description` | `TextField(blank=True)` | Member-facing help text |
| `minimum_amount_cents` | `PositiveIntegerField` | Minimum payment |
| `start_date` | `DateTimeField` | Stored UTC |
| `expiration_date` | `DateTimeField` | Stored UTC |
| `display_order` | `PositiveIntegerField(default=0)` | Sort order |
| `created_at` | `DateTimeField(auto_now_add=True)` | UTC |
| `updated_at` | `DateTimeField(auto_now=True)` | UTC |
| `created_by` | FK `User`, nullable | `SET_NULL` |
| `updated_by` | FK `User`, nullable | `SET_NULL` |

Rules:

- There is no separate tax window model.
- A tier is available when `start_date <= now < expiration_date`.
- Multiple tiers may be available at the same time.
- The member chooses one available tier.
- Multiple available tiers are intentional. They let members who can pay more choose a higher minimum tier to help offset costs for people who need a lower tier.
- Members may pay more than the chosen tier minimum.
- There is no `is_active`; if a tier should not be offered, delete it or change its dates.

Constraints and indexes:

- `expiration_date > start_date`.
- `minimum_amount_cents > 0`.
- Index `camp_year`, `start_date`, `expiration_date`.
- Index `camp_year`, `display_order`.

## TaxAddOn

Optional add-on during payment.

| Field | Type | Notes |
|---|---|---|
| `camp_year` | FK `CampYear` | `CASCADE` |
| `name` | `CharField(max_length=120)` | Display name |
| `description` | `TextField(blank=True)` | Member-facing help text |
| `amount_cents` | `PositiveIntegerField` | Fixed amount |
| `start_date` | `DateTimeField` | Stored UTC |
| `expiration_date` | `DateTimeField` | Stored UTC |
| `display_order` | `PositiveIntegerField(default=0)` | Sort order |
| `created_at` | `DateTimeField(auto_now_add=True)` | UTC |
| `updated_at` | `DateTimeField(auto_now=True)` | UTC |
| `created_by` | FK `User`, nullable | `SET_NULL` |
| `updated_by` | FK `User`, nullable | `SET_NULL` |

Rules:

- An add-on is available when `start_date <= now < expiration_date`.
- There is no `is_active`; if an add-on should not be offered, delete it or change its dates.

Constraints and indexes:

- `expiration_date > start_date`.
- `amount_cents > 0`.
- Index `camp_year`, `start_date`, `expiration_date`.
- Index `camp_year`, `display_order`.

## TaxOverride

Per-user tax exception for a camp year.

| Field | Type | Notes |
|---|---|---|
| `user` | FK `User` | `PROTECT` |
| `camp_year` | FK `CampYear` | `CASCADE` |
| `override_type` | `CharField` | `reduced_minimum` or `waived` |
| `reduced_minimum_amount_cents` | `PositiveIntegerField(null=True, blank=True)` | Required for reduced minimum |
| `note` | `TextField(blank=True)` | Admin-only |
| `created_at` | `DateTimeField(auto_now_add=True)` | UTC |
| `updated_at` | `DateTimeField(auto_now=True)` | UTC |
| `created_by` | FK `User`, nullable | `SET_NULL` |
| `updated_by` | FK `User`, nullable | `SET_NULL` |

Rules:

- A user may have at most one tax override per camp year.
- `waived` means the tax step is complete without payment.
- `reduced_minimum` lowers the allowed minimum payment.
- Overrides do not create payment records.

Constraints:

- Unique `user`, `camp_year`.
- `reduced_minimum` requires `reduced_minimum_amount_cents`.
- `waived` requires `reduced_minimum_amount_cents IS NULL`.

## ContentPage

Member-only Markdown page.

| Field | Type | Notes |
|---|---|---|
| `title` | `CharField(max_length=200)` | Display title |
| `slug` | `SlugField(unique=True)` | URL slug |
| `body_markdown` | `TextField(blank=True)` | Markdown source |
| `created_at` | `DateTimeField(auto_now_add=True)` | UTC |
| `updated_at` | `DateTimeField(auto_now=True)` | UTC |

Rules:

- Member-only in V1.
- No published/unpublished state.
- If a page exists, it is live.
- No `year_id`.
- Markdown is sanitized on output.

## Menu

Named member navigation menu.

| Field | Type | Notes |
|---|---|---|
| `menu_name` | `SlugField(unique=True)` | Internal name, not user-facing |
| `created_at` | `DateTimeField(auto_now_add=True)` | UTC |
| `updated_at` | `DateTimeField(auto_now=True)` | UTC |

Rules:

- A `root` menu always exists.
- The `root` menu is the top-level member menu shown on logged-in pages.
- Non-root menus render at `/menu/<menu_name>/`.
- `menu_name` is a stable internal slug, not the visible menu heading.
- The visible text users see comes from the `MenuItem.label` that links to the menu page.

## MenuItem

Navigation item inside a named menu.

| Field | Type | Notes |
|---|---|---|
| `menu` | FK `Menu` | `CASCADE` |
| `label` | `CharField(max_length=200)` | Display text |
| `url` | `CharField(max_length=500)` | Internal path, external URL, or `/menu/<menu_name>/` |
| `display_order` | `IntegerField(default=0)` | Sort order |
| `created_at` | `DateTimeField(auto_now_add=True)` | UTC |
| `updated_at` | `DateTimeField(auto_now=True)` | UTC |

Rules:

- No link type field.
- No published/unpublished state.
- If a menu item exists, it is live.
- URLs can be internal paths, full external URLs, or menu-page URLs such as `/menu/camp-info/`.
- Menu pages are normal member-only pages that list the items for that menu.
- V1 does not use hover menus.
- A later progressive enhancement may render root links to `/menu/<menu_name>/` as click/tap dropdown panels while keeping the page URL as the fallback.

Indexes:

- `menu`, `display_order`, `label`.

## MediaItem

Image upload record.

| Field | Type | Notes |
|---|---|---|
| `original_filename` | `CharField(max_length=255)` | Original upload name |
| `file_path` | `CharField(max_length=255, unique=True)` | Relative to `media_root` |
| `content_type` | `CharField(max_length=100)` | Image MIME type |
| `size_bytes` | `PositiveBigIntegerField` | File size |
| `title` | `CharField(max_length=200, blank=True)` | Admin display title |
| `created_at` | `DateTimeField(auto_now_add=True)` | UTC |
| `updated_at` | `DateTimeField(auto_now=True)` | UTC |

Rules:

- V1 media is image-only.
- V1 uses one flat media folder.
- Do not store image width or height in V1.
- `file_path` includes database ID and safe original filename.
- Example stored filename: `481-phage-map-2026.png`.
- Deleting a media item deletes the database record and file.
- Profile photos reference `MediaItem`.
- Content pages may reference media URLs in Markdown.

## Survey Models

The detailed survey contract lives in `design_docs/survey_design.md`. Current survey tables are:

- `Survey`: name, slug, description Markdown, active flag, optional internal redirect after submission.
- `SurveyQuestion`: question text/configuration, type, render hint, required flag, optional other-answer support, display order.
- `SurveyChoice`: choice label/value and display order.
- `SurveyQuestionCondition`: simple conditional visibility based on a controlling choice.
- `SurveyResponse`: one response per survey/user.
- `SurveyAnswer`: JSON text answer values plus question/choice snapshots.

Rules:

- Surveys are generic and member-facing at `/survey/<slug>/`.
- `Survey.is_active` controls member submission/editing.
- `Survey.redirect_after_submission_url` must be blank or an internal path starting with `/`.
- Deleted questions preserve old answers through nullable question references and snapshots.
- Camp years can reference one optional Camp survey through `CampYear.camp_survey`.

## Payment

Local payment attempt and final payment state for Stripe Checkout payments and admin-created manual payments.

| Field | Type | Notes |
|---|---|---|
| `user` | FK `User` | `PROTECT` |
| `camp_year` | FK `CampYear` | `PROTECT` |
| `status` | `CharField` | See statuses |
| `mode` | `CharField` | `stripe_test`, `stripe_live`, or `manual` |
| `tax_amount_cents` | `PositiveIntegerField` | Member-selected tax amount |
| `add_on_amount_cents` | `PositiveIntegerField(default=0)` | Sum of add-ons |
| `total_amount_cents` | `PositiveIntegerField` | Total payment amount |
| `tax_tier_name_snapshot` | `CharField(max_length=120)` | Historical chosen tier |
| `tax_tier_minimum_cents_snapshot` | `PositiveIntegerField` | Historical minimum |
| `stripe_checkout_session_id` | `CharField(max_length=255, unique=True, null=True, blank=True)` | Stripe Checkout session, blank for manual payments |
| `stripe_payment_intent_id` | `CharField(max_length=255, unique=True, null=True, blank=True)` | Stripe payment intent, blank for manual payments |
| `checkout_created_at` | `DateTimeField(null=True, blank=True)` | UTC |
| `checkout_expires_at` | `DateTimeField(null=True, blank=True)` | UTC |
| `paid_at` | `DateTimeField(null=True, blank=True)` | UTC |
| `note` | `TextField(blank=True)` | Optional admin note/reference, primarily for manual payments |
| `created_by` | FK `User`, nullable | Paying member for Stripe payments; admin for manual payments; `SET_NULL` |
| `created_at` | `DateTimeField(auto_now_add=True)` | UTC |
| `updated_at` | `DateTimeField(auto_now=True)` | UTC |

Statuses:

- `created`
- `paid`
- `failed`
- `cancelled`
- `refunded`
- `requires_review`

Rules:

- The member chooses one currently available tax tier.
- Payment stores a snapshot of the chosen tier.
- Tax amount must be at least the chosen tier minimum or applicable reduced override minimum.
- Checkout return page does not mark payment paid.
- Stripe webhook is the source of truth for Stripe Checkout payments becoming `paid`.
- Stripe Checkout payments use `mode = "stripe_test"` or `mode = "stripe_live"`, mapped from `SiteSettings.stripe_mode` at checkout creation time.
- Stripe Checkout payments set `created_by` to the paying member.
- Manual payments use `mode = "manual"`, `status = "paid"`, `paid_at` set at creation, and `created_by` set to the admin who created the record.
- Manual payments may include an admin note/reference in `note` and should create the same tax tier and add-on snapshots as Stripe payments.
- Manual payments do not have Stripe Checkout Session IDs, Stripe Payment Intent IDs, or checkout expiration timestamps.
- Only one `paid` payment is allowed per user per camp year.
- Do not create a second Checkout Session for the same user/year while an existing local `created` payment is unexpired.
- Failed, cancelled, refunded, and `requires_review` payments do not count as paid.
- Test payments can be deleted through `/admin/stripe/` by matching `mode = "stripe_test"`.
- Manual payments must not be deleted by test payment cleanup.
- Live payments should not be deleted through normal admin workflows.

Constraints and indexes:

- Partial unique constraint for one `paid` payment per `user`, `camp_year`.
- `total_amount_cents = tax_amount_cents + add_on_amount_cents`.
- Amounts must be non-negative.
- `paid_at` is required when status is `paid`.
- `checkout_expires_at` should be set for Checkout-created payments.
- Index `user`, `camp_year`.
- Index `status`.
- Index `mode`, `status`.

Migration stance before launch:

- Use a normal Django migration for the change from `stripe_mode` to `mode`, adding `manual`, `note`, and `created_by`.
- Migrate existing payment values from `test` to `stripe_test` and `live` to `stripe_live`.
- Backfill existing Stripe payment `created_by` to the payment user when practical.
- This service is not released yet, so migrations can be squashed or rebuilt before launch if the test database is intentionally recreated. Until then, normal migrations keep local, CI, and the test system aligned.

## PaymentAddOn

Snapshot of selected add-ons for a payment.

| Field | Type | Notes |
|---|---|---|
| `payment` | FK `Payment` | `CASCADE` |
| `tax_add_on` | FK `TaxAddOn`, nullable | `SET_NULL` |
| `name_snapshot` | `CharField(max_length=120)` | Historical name |
| `amount_cents_snapshot` | `PositiveIntegerField` | Historical amount |
| `created_at` | `DateTimeField(auto_now_add=True)` | UTC |

Rules:

- Do not store `display_order_snapshot`.
- Snapshots preserve payment history if add-ons are renamed or deleted later.
- Deleting a test payment deletes related add-on snapshots.

## PaymentLog

Redacted Stripe/payment troubleshooting log.

| Field | Type | Notes |
|---|---|---|
| `payment` | FK `Payment`, nullable | `SET_NULL` |
| `level` | `CharField(max_length=20)` | `info`, `warning`, or `error` |
| `event_type` | `CharField(max_length=120)` | App-defined |
| `mode` | `CharField(max_length=20, blank=True)` | `stripe_test`, `stripe_live`, `manual`, or blank when unknown |
| `stripe_event_id` | `CharField(max_length=255, blank=True)` | Webhook event ID |
| `message` | `TextField(blank=True)` | Human-readable summary |
| `redacted_payload` | `JSONField(null=True, blank=True)` | No secrets or card data |
| `created_at` | `DateTimeField(auto_now_add=True)` | UTC |

Rules:

- Logs never store Stripe secret keys.
- Logs never store webhook secrets.
- Logs never store card data.
- Logs are for troubleshooting only.
- Logs do not drive payment state.
- Manual payment creation logs use `mode = "manual"` and an event type such as `manual_payment.create`.

Indexes:

- `created_at`.
- `payment`, `created_at`.
- `stripe_event_id`.

## Excluded From V1 Models

- Tax window model.
- Job/shift tables.
- Generic roster/report tables beyond the current Phagebook.
- Email confirmation tables.
- Password reset email tables.
- Multi-currency payment tables.
- Complex role/permission tables.
- Width/height media metadata.
- Soft-delete framework.
