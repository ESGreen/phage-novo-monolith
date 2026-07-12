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
| `/phagebook/` | Redirects to current year Phagebook |
| `/<year>/` | Redirects or aliases to `/<year>/dashboard/` |
| `/<year>/dashboard/` | Canonical year dashboard |
| `/<year>/phagebook/` | Member Phagebook for a camp year |
| `/<year>/taxes/` | Tax selection/payment page |
| `/<year>/taxes/return/` | Stripe return page |
| `/profile/` | Profile page |
| `/survey/<slug>/` | Member survey page |
| `/survey/<slug>/complete/` | Default survey completion page |
| `/pages/<slug>/` | Member-only content page |
| `/menu/<menu_name>/` | Member-only menu page |

### Admin Routes

| URL | Purpose |
|---|---|
| `/admin/` | Admin home |
| `/admin/users/` | User/profile management |
| `/admin/users/<user_id>/` | Edit one user |
| `/admin/camp/` | Camp years, Dashboard Setup, tiers, add-ons, overrides |
| `/admin/camp/<year>/` | Edit one camp year |
| `/admin/camp/<year>/tax-tier/<tier_id>/` | Edit one tax tier |
| `/admin/camp/<year>/tax-add-on/<add_on_id>/` | Edit one tax add-on |
| `/admin/payments/` | Payment review |
| `/admin/stripe/` | Stripe mode/status/test cleanup |
| `/admin/pages/` | Content pages |
| `/admin/pages/<slug>/` | Edit one content page |
| `/admin/surveys/` | Surveys overview and create form |
| `/admin/surveys/<slug>/` | Edit one survey |
| `/admin/surveys/<slug>/<question_id>/` | Edit one survey question |
| `/admin/surveys/<slug>/responses/` | Review survey responses |
| `/admin/surveys/<slug>/responses.csv` | Export survey responses as CSV |
| `/admin/menus/` | Named menus and menu items |
| `/admin/menus/<menu_name>/` | Edit one menu |
| `/admin/menu-items/<item_id>/` | Edit one menu item |
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

- Members can update name and bio. First name, last name, and bio are required.
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
- Ordered registration checklist.
- Dashboard post-content page, if configured.

Checklist behavior:

- Profile step is complete only when the user has first name, last name, profile photo, and non-empty bio.
- Camp Survey step appears between Profile and Taxes when the camp year has a configured Camp survey.
- Camp Survey step is complete when the user has a response for that survey.
- Taxes step is complete when taxes are paid or waived.
- Paid and waived tax completion display as `Taxes - Paid`.
- Only the first incomplete step is current and actionable.
- Later incomplete steps are locked until earlier steps are complete.
- Completed Profile remains editable from the dashboard.
- Completed Taxes has no action link.
- When all steps are complete, the dashboard shows the fully registered message.

## Phagebook Page

URLs:

| URL | Notes |
|---|---|
| `/<year>/phagebook/` | Canonical year Phagebook |
| `/phagebook/` | Redirects to current year |

Behavior:

- Member-only.
- Any active logged-in member can view it.
- Only fully registered members appear.
- Entries show name, profile photo, email, and sanitized rendered bio.
- Entries are ordered by last name, first name, then email.

## Member Survey Page

URLs:

| URL | Notes |
|---|---|
| `/survey/<slug>/` | Display and submit active survey |
| `/survey/<slug>/complete/` | Default completion page |

Behavior:

- Member-only.
- Active surveys allow the member to create or update their own response.
- Inactive surveys are not available to members.
- Successful submission redirects to the configured internal Redirect after submission URL, or to `/survey/<slug>/complete/` when blank.

## Taxes Page

URL:

- `/<year>/taxes/`

Behavior:

- If user already has a `paid` payment for the year, show paid status and do not allow another payment.
- Direct tax page access redirects back to the dashboard until profile and configured Camp survey prerequisites are complete.
- If no tax tiers are currently available and the user has no override tier, show taxes unavailable.
- If available tiers exist, user selects one tier from tier cards.
- Multiple available tiers are allowed.
- User may enter a tax amount greater than or equal to the chosen tier minimum.
- If user has a reduced-minimum override, show and enforce a synthetic reduced-minimum tier.
- If user has a waived override, show a synthetic `$0.00` waived tier.
- User may select currently available add-ons.
- Waived users may select add-ons at full price and start checkout for add-ons.
- Zero-dollar waived checkout is rejected because no payment is needed.
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
- Link back to member-facing site.

Navigation:

- The `The Phage Admin` title links to `/admin/`.
- The admin nav links to Users, Camp, Payments, Stripe, Pages, Surveys, Menus, Media, and Member site.
- There is no separate Home nav item because the title link already serves that purpose.

## Users Admin

URL:

- `/admin/users/`
- `/admin/users/<user_id>/`

List columns:

| Column |
|---|
| Email |
| First name |
| Last name |
| Active |
| Admin |
| Last login |

Create form fields:

| Field | Notes |
|---|---|
| `account_address` | Required email |
| `first_name` | Optional |
| `last_name` | Optional |
| `is_active` | Boolean |
| `is_admin` | Boolean |
| `initial_secret` | Initial password |

Edit sections:

| Section | Fields |
|---|---|
| User Flags | `is_active`, `is_admin` |
| Email | `new_email` |
| Password | `new_password1`, `new_password2` |
| Photo | `photo` |
| Basic Bio | `first_name`, `last_name`, `bio_markdown` |

Behavior:

- Admins can create users.
- New users get a profile automatically.
- Admins can deactivate users.
- Admins can manually set/reset passwords.
- Admins can replace profile photos and edit profile bio fields.
- The users overview supports browser-side search and sorting as progressive enhancement.
- The create-user form can generate a visible password and copy a rendered intro email.
- Intro email text is rendered from `templates/adminui/emails/new_user_intro.txt`.
- Admins cannot edit their own account through `/admin/users/<user_id>/`.
- No email invitation flow in V1.
- No member impersonation in V1.

## Camp Admin

URL:

- `/admin/camp/`
- `/admin/camp/<year>/`
- `/admin/camp/<year>/tax-tier/<tier_id>/`
- `/admin/camp/<year>/tax-add-on/<add_on_id>/`

`/admin/camp/` is the camp year overview and create page.

`/admin/camp/<year>/` is the camp year edit page for Dashboard Setup, tax tiers, tax add-ons, and tax overrides.

Tax tiers and tax add-ons have separate edit/delete pages because they are year-specific configured objects.

Sections:

| Section |
|---|
| Camp years |
| Dashboard Setup |
| Tax tiers |
| Tax add-ons |
| Tax overrides |

Camp year form:

| Field | Notes |
|---|---|
| `year` | Required unique year |
| `dashboard_pre_page` | Optional content page |
| `dashboard_post_page` | Optional content page |
| `camp_survey` | Optional survey required before taxes |

Tax tier form:

| Field | Notes |
|---|---|
| `name` | Required |
| `description` | Optional |
| `minimum_amount_dollars` | Required dollar input, stored as cents |
| `start_date` | Required date-only input, stored internally as local midnight |
| `expiration_date` | Required date-only input, stored internally as local midnight |

Tax add-on form:

| Field | Notes |
|---|---|
| `name` | Required |
| `description` | Optional |
| `amount_dollars` | Required dollar input, stored as cents |
| `start_date` | Required date-only input, stored internally as local midnight |
| `expiration_date` | Required date-only input, stored internally as local midnight |

Tax override form:

| Field | Notes |
|---|---|
| `user` | Required named-user picker scoped by route |
| `override_type` | `reduced_minimum` or `waived` |
| `reduced_minimum_amount_dollars` | Required only for reduced minimum, stored as cents |
| `note` | Admin-only |

Behavior:

- Camp years are listed newest first with summary counts.
- Tax tiers and add-ons append to the bottom when created.
- Tax tiers and add-ons are reordered with `▲` and `▼` controls.
- `display_order` is not a direct admin form field.
- Dashboard Setup saves pre-page, post-page, and optional Camp survey together.
- Tax overrides are created on the camp year edit page and deleted from the same section.
- The tax override user picker searches by member name and shows email for disambiguation.

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
- `/admin/pages/<slug>/`

Fields:

| Field | Notes |
|---|---|
| `title` | Required |
| `slug` | Required unique slug |
| `body_markdown` | Required |

Behavior:

- `/admin/pages/` lists pages and has a separate create card.
- Existing pages are edited through `/admin/pages/<slug>/`.
- Page edit supports Update and Back, Update and View, and Delete Page.
- Slug changes redirect to the page overview or the new member-facing URL after save.
- Protected pages that are referenced by another object cannot be deleted.
- No published/unpublished state.
- If a page exists, it is live.
- No `year_id`.
- No rendered preview in V1.

## Surveys Admin

URL:

- `/admin/surveys/`
- `/admin/surveys/<slug>/`
- `/admin/surveys/<slug>/<question_id>/`
- `/admin/surveys/<slug>/responses/`
- `/admin/surveys/<slug>/responses.csv`

Behavior:

- `/admin/surveys/` lists active surveys by default and can show inactive surveys with progressive enhancement.
- Create Survey is a separate card on the overview page.
- `/admin/surveys/<slug>/` edits survey details, questions, choices, ordering, and protected survey deletion.
- Survey details include active status and optional internal Redirect after submission URL.
- `/admin/surveys/<slug>/<question_id>/` edits one question and its conditional display rules.
- `/admin/surveys/<slug>/responses/` shows member name, member email, and one column per current question.
- `/admin/surveys/<slug>/responses.csv` exports the same response matrix.
- Member survey routes stay singular at `/survey/<slug>/` and `/survey/<slug>/complete/`.

## Menus Admin

URL:

- `/admin/menus/`
- `/admin/menus/<menu_name>/`
- `/admin/menu-items/<item_id>/`

Menu fields:

| Field | Notes |
|---|---|
| `menu_name` | Required unique internal slug |

Menu item fields:

| Field | Notes |
|---|---|
| `label` | Required user-facing text |
| `url` | Required |

Behavior:

- `/admin/menus/` lists menus and has a separate create card.
- `/admin/menus/<menu_name>/` lists items for one menu, creates new items for that menu, reorders items, and deletes non-root menus.
- `/admin/menu-items/<item_id>/` updates or deletes one item.
- The `root` menu is required and should not be deleted.
- The `root` menu is shown as the top member menu.
- New systems seed `root` with Dashboard, Phage Book, and Profile in that order.
- Non-root menus are available at `/menu/<menu_name>/`.
- Menu item URLs may point to internal paths, external URLs, or menu pages.
- The menu relationship is route-scoped and is not edited through the menu item form.
- `display_order` is not typed directly; it is controlled with `▲` and `▼` buttons.
- The menu item URL field has progressive-enhancement suggestions but remains free-form without JavaScript.
- There is no link type field.
- There is no published/unpublished state.
- Items sort by admin-managed order.

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
