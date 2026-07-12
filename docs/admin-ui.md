# Admin UI Guide

## Purpose

This guide describes the current maintainer UI under `/admin/`.

Use this when making yearly content, user, survey, menu, media, tax, payment, or Stripe changes.

## Access And Navigation

- Admin pages require a logged-in active user with `is_admin = true`.
- Logged-in non-admin members receive `403` for admin pages.
- The header title `The Phage Admin` links to `/admin/`.
- The admin nav links directly to Users, Camp, Payments, Stripe, Pages, Surveys, Menus, Media, and Member site.
- There is no separate `Home` nav item because the title link already goes to the admin home page.
- The Member site link opens `/dashboard/` so admins can check what members see.

## Shared UI Pattern

Most admin sections use the same workflow:

- Overview pages show tables with clear edit links.
- Create forms are separate cards on the overview or object page.
- Records with larger editable content have object-specific edit pages.
- Destructive actions live on the object edit page or in a clearly marked danger area.
- Ordering is changed with `Move up` and `Move down` buttons, shown as `▲` and `▼`.
- Internal implementation fields such as `display_order` are not typed directly by admins.

## Admin Home

URL:

```text
/admin/
```

The home page shows current Stripe mode, current camp year, and a guide table explaining each admin section.

## Users

Overview URL:

```text
/admin/users/
```

The users page has a create-user card and an existing-users table.

Create user supports:

- Email.
- First and last name.
- Active flag.
- Admin flag.
- Initial password.
- Password generation.
- Copying a rendered intro email.

The intro email text is rendered from:

```text
templates/adminui/emails/new_user_intro.txt
```

Existing users can be searched and sorted in the browser. This JavaScript is only a convenience; normal page rendering still provides the full table.

User edit URL:

```text
/admin/users/<user_id>/
```

The user edit page has separate cards for flags, email, password, photo, and basic bio. Admins cannot edit their own user through this page.

## Camp Years And Taxes

Overview URL:

```text
/admin/camp/
```

The camp overview lists years newest first and summarizes people, paid members, waived members, overrides, tax tiers, add-ons, tax open date, and tax close date.

Create camp year is a separate card on the overview page.

Camp year edit URL:

```text
/admin/camp/<year>/
```

The camp year edit page contains:

- Dashboard Setup.
- Tax Tiers.
- Tax Add-ons.
- Tax Overrides.

Dashboard Setup selects the pre-checklist and post-checklist content pages used on the member dashboard. It also selects the optional Camp survey. If a Camp survey is selected, members must complete that survey before they can pay taxes.

Tax tiers and tax add-ons are created on the camp year edit page. Amounts are entered in dollars. Start and end values are date-only inputs and are saved internally as local-midnight datetimes.

Tax tiers and add-ons append to the bottom when created. Use `▲` and `▼` to change order.

Tax tier edit URL:

```text
/admin/camp/<year>/tax-tier/<tier_id>/
```

Tax add-on edit URL:

```text
/admin/camp/<year>/tax-add-on/<add_on_id>/
```

The tax tier and tax add-on edit pages handle updates and deletion.

Tax overrides are created directly on the camp year edit page. The user picker searches by member name and displays email for disambiguation. Each user may have at most one override per camp year.

## Pages

Overview URL:

```text
/admin/pages/
```

The pages overview lists existing member Markdown pages and has a separate create-page card.

Page edit URL:

```text
/admin/pages/<slug>/
```

The page edit screen supports updating title, slug, and Markdown body. `Update and Back` returns to `/admin/pages/`. `Update and View` saves and opens the member-facing page.

Page deletion is available from the page edit screen. A page that is referenced by another record, such as a camp year dashboard slot, cannot be deleted until that reference is removed.

## Surveys

Overview URL:

```text
/admin/surveys/
```

The surveys overview lists active surveys by default, with a checkbox to show inactive surveys too. Create Survey accepts name, slug, and Markdown description. New surveys are active by default.

Survey edit URL:

```text
/admin/surveys/<slug>/
```

The survey edit page manages survey details, question order, question updates, choice creation/editing/reordering/deletion, add-question workflow, and protected survey deletion.

Survey details include an optional Redirect after submission URL. Leave it blank to use `/survey/<slug>/complete/`. Use an internal path such as `/2026/dashboard/` when a camp survey should return members to the dashboard after submission.

The surveys overview also shows response counts and a View Responses action.

Survey responses URL:

```text
/admin/surveys/<slug>/responses/
```

The responses page shows one row per response, with member name, member email, and one column per current survey question. The Export CSV button downloads the same table as `/admin/surveys/<slug>/responses.csv`.

Question detail URL:

```text
/admin/surveys/<slug>/<question_id>/
```

The question detail page manages the same question fields, conditional display rules, and protected question deletion.

Member survey URL:

```text
/survey/<slug>/
```

Members can submit or revise their own response while the survey is active. Successful submission redirects to `/survey/<slug>/complete/`.

## Menus

Overview URL:

```text
/admin/menus/
```

The menus overview lists named menus and a short summary of each menu's items. Create menu is a separate card.

The required top-level member menu is named `root`. It cannot be deleted.

Menu edit URL:

```text
/admin/menus/<menu_name>/
```

The menu edit page lists items for that menu, provides item ordering controls, creates new items for that menu, and deletes non-root menus.

Menu item edit URL:

```text
/admin/menu-items/<item_id>/
```

Menu items expose only label and URL in the form. The menu relationship is controlled by the route where the item is created. Ordering is controlled by the `▲` and `▼` buttons.

Menu item URLs are free-form. They may be internal paths such as `/dashboard/`, `/pages/<slug>/`, `/menu/<menu_name>/`, `/<year>/taxes/`, or external URLs.

The URL field has a progressive-enhancement suggestion picker. Suggestions include common app routes, current-year dashboard and taxes routes, content pages, and menu pages. The field still works as a normal text input without JavaScript.

## Payments

URL:

```text
/admin/payments/
```

Use this page to review payment records and recent payment logs. Payment records are not edited through the normal admin UI in V1.

## Stripe

URL:

```text
/admin/stripe/
```

Use this page to see and switch Stripe test/live mode, inspect payment logs, and delete local test payments before going live.

## Media

URL:

```text
/admin/media/
```

Use this page to upload image media for Markdown pages and profiles. Uploaded media shows its site URL. Deleting media removes the database record and stored file.
