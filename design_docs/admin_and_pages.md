# Admin And Pages

## Purpose

This document defines the V1 admin approach, route map, page behavior, permissions, redirects, and form contracts.

The goal is to make implementation straightforward without inventing a complex CMS, role system, or navigation tree.

## Admin Approach

Use custom Django views and templates for the product admin pages under `/admin/`.

Do not rely on Django's built-in admin as the primary maintainer interface.

Reasons:

- Product admin access is controlled by `User.is_admin`.
- The product does not expose `is_staff` or `is_superuser` as normal account state.
- The required admin pages are small and workflow-specific.
- Custom pages make the yearly maintenance UI easier to understand.

Django's built-in admin may exist for developer emergency use if needed, but it is not the documented maintainer workflow for V1.

## Permission Rules

| User state | Member pages | Admin pages |
|---|---|---|
| Anonymous | Redirect to `/login/` | Redirect to `/login/` |
| Inactive | Cannot log in | Cannot log in |
| Active member | Allowed | `403` |
| Active admin | Allowed | Allowed |

Rules:

- Admin pages require authentication.
- Admin pages require `is_admin = true`.
- Non-admin logged-in users receive `403` for `/admin/` pages.
- Admins are also members and can use normal member pages.
- No member impersonation in V1.

## Route Map

### Public Routes

| URL | Behavior |
|---|---|
| `/` | Redirects to `/public/` |
| `/public/` | Static public landing page |
| `/public/...` | Static public files |
| `/login/` | Login page |
| `/logout/` | Logout action |

### Member Routes

| URL | Behavior |
|---|---|
| `/dashboard/` | Redirects to current year dashboard |
| `/<year>/` | Redirects or aliases to `/<year>/dashboard/` |
| `/<year>/dashboard/` | Canonical year dashboard |
| `/<year>/taxes/` | Tax selection/payment page |
| `/profile/` | Profile page |
| `/pages/<slug>/` | Member-only content page |
| `/menu/<menu_name>/` | Member-only menu page |

### Admin Routes

| URL | Purpose |
|---|---|
| `/admin/` | Admin home |
| `/admin/users/` | User/profile management |
| `/admin/camp/` | Camp years, dashboard pages, tiers, add-ons, overrides |
| `/admin/payments/` | Payment review |
| `/admin/stripe/` | Stripe mode/status/test cleanup |
| `/admin/pages/` | Content pages |
| `/admin/menus/` | Named menus and menu items |
| `/admin/media/` | Image uploads |

## Login Page

URL:

- `/login/`

Fields:

| Field | Notes |
|---|---|
| `email` | Normalized lowercase |
| `password` | Django password auth |

Behavior:

- Anonymous users can view `/login/`.
- Logged-in users visiting `/login/` redirect to `/dashboard/`.
- Failed login shows a generic error.
- Inactive users cannot log in.
- Login success redirects to `/dashboard/`.

## Logout

URL:

- `/logout/`

Behavior:

- Logs out the current user.
- Redirects to `/public/` or `/login/`.
- Logout is available from the member menu.

## Profile Page

URL:

- `/profile/`

Profile fields:

| Field | Notes |
|---|---|
| `first_name` | From `User` |
| `last_name` | From `User` |
| `bio_markdown` | From `MemberProfile` |
| `photo` | Optional replacement image |
| `new_email` | Optional email change |
| `confirm_new_email` | Must match before saving email |

Password change fields:

| Field | Notes |
|---|---|
| `old_password` | Required for password change |
| `new_password1` | Must satisfy password policy |
| `new_password2` | Must match `new_password1` |

Behavior:

- Members can update name and bio.
- Members can replace profile photo.
- Members cannot self-delete profile photo in V1.
- Email change requires on-page confirmation.
- Email confirmation by email is not part of V1.
- Members can change their own password by entering old password and the new password twice.

## Dashboard Page

URLs:

| URL | Notes |
|---|---|
| `/<year>/dashboard/` | Canonical |
| `/dashboard/` | Redirects to current year |
| `/<year>/` | Redirects or aliases to dashboard |

Content:

- Year heading.
- Dashboard pre-content page, if configured.
- Checklist/status area.
- Dashboard post-content page, if configured.
- Links to taxes, profile, and member content.

Checklist status should include:

- Profile exists.
- Tax status for year.
- Tax waived status if override exists.
- Payment complete if a `paid` payment exists for the year.

## Taxes Page

URL:

- `/<year>/taxes/`

Behavior:

- If user already has a `paid` payment for the year, show paid status and do not allow another payment.
- If user has `waived` override, show tax step complete and do not require payment.
- If no tax tiers are currently available, show taxes unavailable.
- If available tiers exist, user selects one tier.
- Multiple available tiers are allowed.
- User may enter a tax amount greater than or equal to the chosen tier minimum.
- If user has a reduced-minimum override, enforce the lower minimum.
- User may select currently available add-ons.
- Submit creates a local `Payment` and starts Stripe Checkout.

## Content Page

URL:

- `/pages/<slug>/`

Behavior:

- Member-only.
- Renders sanitized Markdown.
- `404` if the slug does not exist.
- No published/unpublished state.
- No preview workflow in V1.

## Menu Page

URL:

- `/menu/<menu_name>/`

Behavior:

- Member-only.
- Renders the items for the named menu.
- `404` if the menu does not exist.
- Items are sorted by `display_order`, then `label`.
- Menu pages use the same member layout and top `root` menu as other member pages.
- Menu pages are the V1 way to provide grouped navigation without hover dropdowns.

Progressive enhancement later:

- Root menu links to `/menu/<menu_name>/` may be rendered as click/tap dropdown panels.
- The normal `/menu/<menu_name>/` page must remain the fallback.
- Do not use hover-only menus.
- Do not use iframes for menu panels.

## Admin Home

URL:

- `/admin/`

Content:

- Links to all admin sections.
- Current Stripe mode.
- Current camp year.
- Basic warnings if config appears incomplete.
- Link back to member-facing site.

## Users Admin

URL:

- `/admin/users/`

List columns:

| Column |
|---|
| Email |
| First name |
| Last name |
| Active |
| Admin |
| Last login |

Form fields:

| Field | Notes |
|---|---|
| `email` | Required |
| `first_name` | Optional |
| `last_name` | Optional |
| `is_active` | Boolean |
| `is_admin` | Boolean |
| `password` | Manual set/reset |
| `bio_markdown` | Profile bio |
| `photo` | Profile photo replacement |

Behavior:

- Admins can create users.
- New users get a profile automatically.
- Admins can deactivate users.
- Admins can manually set/reset passwords.
- No email invitation flow in V1.
- No member impersonation in V1.

## Camp Admin

URL:

- `/admin/camp/`

Keep `/admin/camp/` as one combined admin page for V1. If it becomes too large, split it later.

Sections:

| Section |
|---|
| Camp years |
| Dashboard content page references |
| Tax tiers |
| Tax add-ons |
| Tax overrides |

Camp year form:

| Field | Notes |
|---|---|
| `year` | Required unique year |
| `dashboard_pre_page` | Optional content page |
| `dashboard_post_page` | Optional content page |

Tax tier form:

| Field | Notes |
|---|---|
| `name` | Required |
| `description` | Optional |
| `minimum_amount_cents` | Required |
| `start_date` | Pacific display/input |
| `expiration_date` | Pacific display/input |
| `display_order` | Required |

Tax add-on form:

| Field | Notes |
|---|---|
| `name` | Required |
| `description` | Optional |
| `amount_cents` | Required |
| `start_date` | Pacific display/input |
| `expiration_date` | Pacific display/input |
| `display_order` | Required |

Tax override form:

| Field | Notes |
|---|---|
| `user` | Required |
| `camp_year` | Required |
| `override_type` | `reduced_minimum` or `waived` |
| `reduced_minimum_amount_cents` | Required only for reduced minimum |
| `note` | Admin-only |

## Payments Admin

URL:

- `/admin/payments/`

List columns:

| Column |
|---|
| User |
| Camp year |
| Status |
| Stripe mode |
| Tax amount |
| Add-on amount |
| Total |
| Created |
| Paid at |

Behavior:

- Admins can view payment detail.
- Admins can inspect selected add-ons.
- Admins can inspect payment logs.
- V1 does not need custom UI to resolve `requires_review`.
- Rare `requires_review` resolution may be handled directly in the database after confirming Stripe truth.

## Stripe Admin

URL:

- `/admin/stripe/`

Content:

- Current Stripe mode.
- Test configuration health.
- Live configuration health.
- Webhook configuration health.
- Recent payment/Stripe logs.
- Test payment cleanup controls.

Actions:

- Switch to test mode.
- Switch to live mode.
- Delete test payments.
- Show confirmation before destructive test cleanup.

Rules:

- Test/live state appears only in Stripe admin.
- Member-facing payment workflow should look the same in test and live modes.
- Live payments are never deleted by test cleanup.

## Pages Admin

URL:

- `/admin/pages/`

Fields:

| Field | Notes |
|---|---|
| `title` | Required |
| `slug` | Required unique slug |
| `body_markdown` | Required |

Behavior:

- No published/unpublished state.
- If a page exists, it is live.
- No `year_id`.
- No rendered preview in V1.

## Menus Admin

URL:

- `/admin/menus/`

Menu fields:

| Field | Notes |
|---|---|
| `menu_name` | Required unique internal slug |

Menu item fields:

| Field | Notes |
|---|---|
| `menu` | Required |
| `label` | Required user-facing text |
| `url` | Required |
| `display_order` | Required |

Behavior:

- The `root` menu is required and should not be deleted.
- The `root` menu is shown as the top member menu.
- Non-root menus are available at `/menu/<menu_name>/`.
- Menu item URLs may point to internal paths, external URLs, or menu pages.
- There is no link type field.
- There is no published/unpublished state.
- Items sort by `display_order`, then `label`.
- If two items have the same display order, alphabetical order by label is sufficient.
- No additional equality/tie-break behavior is needed.

## Media Admin

URL:

- `/admin/media/`

Fields:

| Field | Notes |
|---|---|
| `title` | Optional |
| `image` | Required for upload |

Behavior:

- V1 media is image-only.
- Upload validates image type.
- Upload stores file under `media_root`.
- Upload creates `MediaItem`.
- Delete removes database record and file.
- No custom resizing in V1.
- If an image needs resizing, resize offline before upload.
