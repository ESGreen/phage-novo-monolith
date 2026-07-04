# The Phage Website Design

## Purpose

This document describes the target structure for the new `thephage.org` website.

The goal is to define the main information captured, expected pages, proposed URLs, navigation model, access rules, and broad layout structure.

This is not a visual design document. Colors, graphics, logos, typography, and detailed visual treatment will be decided later.

## Site Concept

The site has two main areas:

- Static public site.
- Logged-in member site.

The public site is served from `/public/` as static HTML. Public pages are created outside Django and uploaded as files.

The logged-in member site is handled by Django. It includes yearly dashboards, tax payment, profile management, member-only pages, and admin tools.

The public site should not expose the full member menu. Public static pages may link to login or member-only URLs, but member-only URLs require authentication.

## Main Information Captured

### User Account

Used for login, authentication, and broad account access.

The site should use email as the primary login identifier. Usernames are not needed.

All string/text fields must support Unicode.

Likely fields:

- Email address.
- Password.
- First name.
- Last name.
- Active/inactive status.
- Admin access flag.
- Date joined.
- Last login.

`is_active` controls whether the user can log in.

`is_admin` controls whether the user can access admin pages.

These account access flags should not be used for yearly camp status, payment status, survey status, or roster status.

The product model does not need separate `is_staff` or `is_superuser` concepts. If Django needs internal staff/superuser behavior for framework compatibility, that should be treated as an implementation detail and not exposed as normal product account state.

V1 does not require two-factor authentication. Accounts should require strongish passwords:

- Minimum length of 10 characters.
- Unicode characters are allowed.
- Password must include at least two character classes.

Character classes:

- Letters.
- Numbers.
- Punctuation.
- Other Unicode characters.

### Member Profile

Stores durable member/person information that is not part of authentication.

The member profile should represent the person across years. It should not store yearly camp participation, tax status, survey answers, emergency contact data, phone numbers, or other contact details that are better collected through a yearly survey if needed.

Likely fields:

- Linked user account.
- Photo.
- Bio text.

The user account remains the source for:

- Email address.
- First name.
- Last name.
- Active/inactive status.
- Admin access status.

Display name should be derived from the user account name fields. If someone wants to be known by something other than their legal name, they can set that name in their user account.

Playa names, camp names, personal descriptions, or other self-identifying text can go in the bio.

### Camp Year

Represents a specific camp year.

The camp year should stay intentionally small. It is mainly an anchor for year-specific configuration and records.

Likely fields:

- Year.

The current year does not need to be stored manually. It can be inferred from the maximum configured year or from the system date, depending on the page/context.

Tax dates, tax tiers, and add-ons should not live directly on the camp year record. They belong in the tax configuration for that year.

### Content Pages

Stores mostly-static website content that admins can update without editing Django templates.

Most content pages are evergreen and should be updated in place as needed. One page is expected to be year-specific and will usually be copied from the previous year with dates and details modified. That year-specific page can include the year or date in its slug.

Likely fields:

- Title.
- Slug.
- Body text.

Public pages are static HTML under `/public/`, not Django-managed content pages in V1.

Django-managed content pages are member-only in V1.

Body text should use Markdown.

Markdown should support:

- Headings.
- Paragraphs.
- Lists.
- Links.
- Uploaded site images.
- Offsite image URLs.

The site should provide a way for admins to upload images that can be embedded into Markdown content pages.

### Menu Configuration

Stores navigation separately from page content.

The menu should be configurable by admins.

The menu system has two records:

- Menu.
- Menu item.

A menu has an internal `menu_name`. The required top-level menu is named `root`.

A menu item belongs to a menu and has a visible label, URL, and display order.

Content pages are admin-created Markdown pages, usually available at `/pages/<slug>/`.

Application pages are fixed pages provided by the Django app, such as:

- Year dashboard.
- Pay taxes.
- Profile.
- Future survey pages.
- Future job pages.

Menu item URLs may point to content pages, application pages, external websites, or another menu page.

Menu page URLs use this pattern:

- `/menu/<menu_name>/`

This gives admins a simple way to keep the top member menu short. For example, the `root` menu can contain a `Camp Info` item pointing to `/menu/camp-info/`, and the `camp-info` menu can contain links to arrival info, packing lists, maps, or policies.

Likely menu fields:

- Internal menu name.

Likely menu item fields:

- Label.
- Menu.
- URL.
- Display order.

Menu items are sorted by display order, then label. If two items have the same display order, alphabetical order by label is sufficient. No further tie-breaking behavior is needed.

V1 should render menu pages as normal member-only pages. A later progressive enhancement may render root links to `/menu/<menu_name>/` as click/tap dropdown panels while preserving the normal page URL as the fallback. Do not use hover-only menus in V1.

The menu system should not prevent admins from adding a Pay Taxes link if that makes sense for the year.

### Tax Configuration

Stores yearly tax setup.

Tax configuration belongs to a specific camp year. Tax settings can change year to year.

The tax system has three main pieces:

- Tax tiers.
- Tax add-ons.

#### Tax Tier

Defines suggested/minimum payment levels available for a year.

Each tier has a start date and expiration date. A tier is available when `start_date <= now < expiration_date`.

Multiple tax tiers may be available at the same time. The member chooses one available tier. This lets members who can pay more choose a higher minimum tier to help offset costs for people who need a lower tier.

A tax tier should be treated as a minimum amount, not a fixed required amount. The payment UI should allow a member to enter a higher amount of their choosing.

Likely fields:

- Camp year.
- Name.
- Description.
- Minimum amount.
- Start date.
- Expiration date.
- Display order.

There is no active/inactive status for tax tiers. If a tier should not be offered, delete it or change its dates.

#### Tax Add-On

Defines optional extra items members can add to their tax payment.

Add-ons are year-specific. Add-ons may represent different things each year, such as hoodies, portas, supplies, or other camp-specific items.

Add-ons have their own start date and expiration date. An add-on is available when `start_date <= now < expiration_date`.

Likely fields:

- Camp year.
- Name.
- Description.
- Amount.
- Start date.
- Expiration date.
- Display order.

There is no active/inactive status for add-ons. If an add-on should not be offered, delete it or change its dates.

### Tax Override

Stores per-member exceptions to the normal tax rules for a specific camp year.

Most members do not need a tax override. If no override exists, the member uses the normal active tax tiers and add-ons for the year.

Tax overrides exist for special cases where a specific person should be allowed to pay a different minimum amount, usually less than the standard minimum, or where a specific person should not owe taxes for that year.

Initial override types:

- Reduced minimum amount.
- Tax waived.

Likely fields:

- User account.
- Camp year.
- Override type.
- Minimum amount, required for reduced minimum overrides.

A reduced minimum override should only affect the minimum amount that member is allowed to pay.

A tax waived override means the member does not need to pay taxes for that camp year. The dashboard should treat the tax step as complete without creating a payment record.

Tax overrides should not replace payment records and should not directly create payment records.

If a tax override is no longer needed, it can be deleted.

If a person should not be allowed to pay taxes or access the site, their account should be deactivated.

### Payment

Stores local records of Stripe payment activity.

Payments are used to show member payment status, support admin reconciliation, and preserve a local record of what happened. The site should not store card details.

Likely fields:

- User account.
- Camp year.
- Amount.
- Status.
- Stripe mode.
- Stripe Checkout Session ID.
- Stripe Payment Intent ID.
- Checkout expiration timestamp.
- Created at.
- Paid at.

Payment status should be an enum/string, not a boolean.

Initial status values:

- `created`
- `paid`
- `failed`
- `cancelled`
- `refunded`
- `requires_review`

Stripe webhooks should be the source of truth for marking a payment as paid. The browser success page is only a user experience convenience.

V1 accepts credit cards only through Stripe Checkout.

A user may have more than one payment attempt. A member should be considered paid for a camp year if they have at least one successful paid payment for that year.

The payment amount should include the selected tax amount plus any selected add-ons.

Stripe mode should be stored on payments for correctness, review, and troubleshooting. Test/live mode is exposed through `/admin/stripe/`, not as a separate member-facing workflow.

Payment and Stripe communication should be logged for troubleshooting. This includes Stripe checkout creation, webhook receipt, webhook validation, and relevant Stripe responses. Logs should avoid storing secrets and should not include card data.

If a Stripe webhook or payment record does not match expected local data, the payment should be marked `requires_review` rather than silently failing or being marked paid. For V1, these cases can be handled by an admin directly in the database if they ever occur; no custom web workflow is required.

### Payment Add-On

Stores the add-ons selected as part of a payment.

There will usually only be a small number of add-ons, roughly three to five. They should still be tracked explicitly so admins can report on who purchased or selected each add-on.

Likely fields:

- Payment.
- Tax add-on.
- Add-on name snapshot.
- Amount snapshot.

The name and amount should be snapshotted at payment time so old payment records remain understandable even if the add-on is edited later.

### Payment Requirements

Stores the list of things a member must complete before paying taxes for a camp year.

Payment requirements should be year-specific and configurable. The survey may be one requirement, and some form of job/shift signup has historically been part of the requirements and is expected to be part of the flow again in the future.

Possible requirements:

- Complete yearly survey.
- Sign up for required jobs/shifts.
- Acknowledge important information.
- Manual admin approval.

If no payment requirements are configured for a year, active members can proceed directly to taxes.

Payment requirements should control whether the payment button is available. They should not replace tax records or payment records.

### Future Survey Data

The survey is planned for a future version.

The survey should collect yearly member information and should be configurable through the admin. Survey questions may stay mostly the same year to year, but admins should be able to add, remove, or modify questions as needed.

Survey data should be year-specific.

Likely future concepts:

- Survey.
- Survey question.
- Survey response.
- Survey answer.

The survey should eventually support generating:

- A photo/name directory.
- A tabular roster.
- A summary page with tabulated results.

Survey answers should not be stored directly on the user account. They should remain tied to the survey and camp year.

A completed survey may be one of several requirements before a member is allowed to pay taxes.

### Future Job/Shift Data

Job and shift signup is expected to be added in a future version.

This document will not define the job system in detail yet. The site should leave room for a future jobs section, but the design will be worked out when that feature becomes active.

## Proposed URL Structure

The site should use simple current-purpose URLs for member pages, with year-specific dashboards and tax pages.

Examples:

- `/dashboard/`
- `/<year>/dashboard/`
- `/<year>/taxes/`
- `/pages/<slug>/`
- `/profile/`

Most content pages are evergreen and should not be archived by year. The one year-specific content page can include the year or date in its slug.

Year-specific content page example:

- `/pages/2026-arrival-info/`

The site should not create year-based page archives by default.

## Public Pages

Public pages are static HTML files served from `/public/`.

The Django app does not manage public page content in V1. Public pages can be created offline and uploaded to the public directory.

URL behavior:

- `/` redirects to `/public/`.
- `/public/` serves `/public/index.html`.
- `/public/<path>` serves static public files.
- `/login/` remains the Django login page.

Public static pages may link to Django application pages such as `/login/`, `/dashboard/`, or `/<year>/dashboard/`.

If a visitor follows a member-only link while logged out, Django redirects them to `/login/`.

## Logged-In Member Pages

Logged-in pages should share the member menu and a consistent page structure.

### Year Dashboard

Canonical URL pattern:

- `/<year>/dashboard/`

Example:

- `/2026/dashboard/`

Optional alias:

- `/<year>/`

Example:

- `/2026/`

The short year URL may redirect to or render the same page as the canonical dashboard URL.

The year dashboard should be the default destination after important member actions, including:

- Login.
- Paying taxes.
- Completing a survey.
- Completing future requirements.
- Returning from Stripe Checkout.

The year dashboard should show what the member needs to know and do for that camp year.

The year dashboard should include:

- Basic information about the camp year.
- Required steps for the member.
- Whether each step is complete.
- Whether the member is allowed to pay taxes yet.
- A link to the tax payment page when payment is available.
- Links to relevant member-only content pages.

Old year dashboards may remain accessible through their year-specific dashboard URL, such as `/2025/dashboard/`.

The year dashboard should support linked Markdown content before and after the checklist:

- Pre-checklist content.
- Post-checklist content.

### Dashboard Redirect

URL:

- `/dashboard/`

Purpose:

- Redirect to the current year dashboard.

Example:

- `/dashboard/` redirects to `/2026/dashboard/`.

### Pay Taxes

URL pattern:

- `/<year>/taxes/`

Example:

- `/2026/taxes/`

Purpose:

- Show available tax tiers.
- Show available add-ons.
- Allow the member to enter a payment amount at or above their minimum.
- Let the member start Stripe Checkout.
- If already paid, show payment status instead of the payment action.

### Payment Return

URL pattern:

- `/<year>/taxes/return/`

Purpose:

- Stripe return page after checkout.
- Explain that payment confirmation is finalized by Stripe webhook.
- Link back to the year dashboard.

If checkout is cancelled, Stripe returns the member to `/<year>/taxes/`.

### Private Content Page

URL:

- `/pages/<slug>/`

Purpose:

- Display admin-managed member information pages.

### Member Profile Page

URL:

- `/profile/`

Purpose:

- Let a logged-in member manage their own account/profile information.

Members should be able to update:

- Email address.
- First name.
- Last name.
- Password.
- Profile photo.
- Profile bio.

Members can change their own email. The page should include a confirmation step before saving an email change to prevent accidental edits.

Members can replace their profile photo. Members do not need a self-service profile photo delete action in V1.

### Payment History

A dedicated member-facing payment history page is not needed for V1.

If payment questions come up, they can be handled manually by an admin checking Stripe or the payments admin area.

## Login And Logout

### Login Page

URL:

- `/login/`

Purpose:

- Let members log in using email and password.
- Link back to the public site.
- Avoid showing member navigation before authentication.

If an already logged-in user visits `/login/`, they should be redirected to `/dashboard/`.

### Logout

A logout button should be available from the member menu.

After logout, the user should return to a public or logged-out page.

V1 does not require two-factor authentication. Passwords should follow the site password policy: at least 10 characters and at least two character classes, with Unicode characters allowed.

## Admin Pages

Admin pages can be implemented as conceptual sections inside Django admin or as custom admin pages, depending on which approach keeps the code simpler and easier to understand.

Only users with `is_admin = true` may access admin pages.

Admin pages should include clear navigation back to the member-facing site and to the other admin sections.

### Admin Home

URL:

- `/admin/`

Purpose:

- Main landing page for admins.
- Provide links to each admin section.
- Provide a clear path back to the member-facing site.

Admin sections:

- Users: `/admin/users/`
- Camp: `/admin/camp/`
- Payments: `/admin/payments/`
- Stripe: `/admin/stripe/`
- Pages: `/admin/pages/`
- Menus: `/admin/menus/`
- Media: `/admin/media/`

### Users Admin

URL:

- `/admin/users/`

Purpose:

- Manage accounts and profile data together.

Because every account has exactly one profile, account and profile information should be presented together.

This area should include:

- Email/login.
- First name.
- Last name.
- Active/inactive status.
- Admin access status.
- Manual password setting/reset.
- Profile photo.
- Profile bio.

### Camp Admin

URL:

- `/admin/camp/`

Purpose:

- Manage camp years and yearly tax setup.

This area should include:

- Camp years.
- Tax tiers.
- Tax add-ons.
- Tax overrides.
- Year dashboard pre-checklist content page reference.
- Year dashboard post-checklist content page reference.

Tax overrides belong here because they are exceptions to the yearly tax rules.

### Payments Admin

URL:

- `/admin/payments/`

Purpose:

- Review payment activity and answer payment questions.

This area should show:

- Successful payments.
- Failed payments.
- Cancelled payment attempts.
- Refunded payments, if any.
- Payment amount.
- Camp year.
- User.
- Stripe identifiers.
- Selected add-ons.
- Related Stripe/payment log entries.

Payments marked `requires_review` should be visible here. For V1, there does not need to be a custom workflow for resolving them in the web app.

### Stripe Admin

URL:

- `/admin/stripe/`

Purpose:

- Show Stripe integration status and payment mode.

This area should show:

- Whether the site has a valid Stripe connection.
- Whether the site is in test mode or live mode.
- Which Stripe mode future payments will use.
- Basic webhook/configuration health.
- Recent Stripe/payment log entries.
- Test and live payment activity needed for troubleshooting.

The site must make it very obvious when it is in test mode versus live mode.

Admins should be able to switch the site between Stripe test mode and Stripe live mode from this section. Production may run in test mode when admins are verifying the yearly payment flow.

The member-facing payment workflow should be the same in test mode and live mode. Test/live state should only be exposed in the Stripe admin area.

Stripe secret values are stored in `/etc/thephage/thephage.toml`, with `deploy/thephage.toml.example` as the committed example format. Secrets are not edited directly in the website, but this page should still show whether the current configuration appears valid.

Test payments should be easy to delete from this area so the payment flow can be tested repeatedly.

### Pages Admin

URL:

- `/admin/pages/`

Purpose:

- Manage admin-editable member website content.

This area should include:

- Content pages.
- Page title.
- Slug.
- Markdown body.
- Optional year-specific page slug, such as `2026-arrival-info`.

### Menus Admin

URL:

- `/admin/menus/`

Purpose:

- Manage navigation separately from page content.

This area should include:

- Menus.
- Menu internal name.
- Menu items.
- Menu item label.
- Menu item URL.
- Menu item display order.
- The required `root` menu.
- Links to menu pages such as `/menu/camp-info/`.

### Media Admin

URL:

- `/admin/media/`

Purpose:

- Upload, browse, and organize media used by the site.

For V1, media should use one flat folder with no subfolders. Later, media may gain a folder structure that reflects how files are stored on disk.

Media uploaded here should be usable from Markdown content pages. Markdown should also allow offsite image URLs.

System-generated storage filenames are acceptable. A future database/storage design document should address how admins find media when the site or database has problems.

## Future Survey Section

The survey is planned for a future version.

The survey should eventually be part of the yearly dashboard flow. If enabled for a camp year, the year dashboard should show whether the member has completed the survey.

Future URLs may include:

- `/<year>/survey/`
- `/<year>/survey/complete/`
- `/<year>/directory/`
- `/<year>/roster/`
- `/<year>/survey/results/`

The survey may be one of the requirements before a member is allowed to pay taxes.

The survey should support:

- Admin-configured questions.
- Mostly reused questions year to year.
- New questions when needed.
- Member response editing at any time.
- No survey edit cutoff date.
- Year-specific responses.
- Reports generated from survey answers.

Future survey output pages:

- Photo/name directory.
- Tabular roster.
- Tabulated survey results.

## Future Job/Shift Section

Job and shift signup is expected to be added in a future version.

This document will not define the job system in detail yet. The site should leave room for a future jobs section, but the design will be worked out when that feature becomes active.

## Navigation Model

The site has three navigation modes:

- Public navigation.
- Member navigation.
- Admin navigation.

### Public Navigation

Public pages should not show the full member menu.

The public landing page should show:

- Site identity.
- Main public content.
- Login link.

### Member Navigation

Logged-in members should see a configurable top member menu.

The top member menu is the `root` menu. The menu should be managed separately from content pages. A menu item belongs to a named menu and has a visible label, target URL, and display order. URLs may point to member content pages, application pages, external websites, or menu pages such as `/menu/camp-info/`.

Application pages are fixed endpoints provided by the Django app.

The menu should include a logout button.

### Admin Navigation

Admins should have access to the admin area.

Admin users should see:

- Link to admin home.
- Link back to member-facing site.
- Links between admin sections.

## Layout Styles

This section describes page structure only. Final visual design, colors, graphics, and typography will be decided later.

The site should assume that many members will use it on mobile. The layout should avoid large differences between desktop and mobile where possible.

### Public Landing Layout

Purpose:

- Simple public entry point.
- Avoid exposing private site structure.

Structure:

- Site identity area.
- Main public text section.
- Login link or button.
- Optional footer.

Notes:

- No member menu.
- No admin menu.
- No private links except login.

### Login Layout

Purpose:

- Focused authentication page.

Structure:

- Site identity area.
- Login form.
- Link back to public site.

Notes:

- Users log in with email and password.
- No member menu before authentication.

### Member Layout

Purpose:

- Consistent structure for logged-in pages.

Structure:

- Top member menu.
- Main content area.
- Page title.
- Primary content section.
- Optional secondary/help text section.

Notes:

- Use top navigation rather than side navigation.
- Keep desktop and mobile layouts as similar as practical.
- Menu may link to content pages, application pages, external URLs, or member-only menu pages.
- Avoid hover-only menus. Menu links to `/menu/<menu_name>/` should work as normal pages in V1.
- The current year dashboard is the main member destination.

### Year Dashboard Layout

Purpose:

- Show what the member needs to know and do for a camp year.

Structure:

- Top member menu.
- Year title/summary.
- Pre-checklist Markdown content.
- Required steps section.
- Completion/status indicators.
- Payment status section.
- Links to relevant actions and information pages.
- Post-checklist Markdown content.

Notes:

- The dashboard should be the default destination after login and after completing major actions.
- It should make the next required action obvious.

### Tax Payment Layout

Purpose:

- Let members understand and pay taxes.

Structure:

- Top member menu.
- Explanation text.
- Available tax tiers.
- Add-on selection.
- Custom payment amount input.
- Payment action.
- Existing payment status, if already paid.

Notes:

- Tax tiers are minimums.
- Members may enter a higher amount.
- Stripe Checkout handles card/payment collection.

### Content Page Layout

Purpose:

- Render admin-written Markdown content clearly.

Structure:

- Top member menu.
- Page title.
- Markdown-rendered body.
- Optional last-updated date.

Notes:

- Content pages may include uploaded site images.
- Content pages may include offsite image URLs.

### Profile Layout

Purpose:

- Let members manage their own account/profile information.

Structure:

- Top member menu.
- Account fields.
- Profile photo section.
- Bio section.
- Password change section.

Notes:

- Members can replace their profile photo.
- Members do not need a self-service profile photo delete action in V1.

### Admin Layout

Purpose:

- Help admins reach management sections quickly.

Structure:

- Admin home.
- Links to admin sections.
- Link back to member-facing site.
- Section-specific management pages.

## Access Rules

Access should be simple and explicit.

### Anonymous Visitors

Anonymous visitors can access:

- Static public pages under `/public/`.
- Login page.

Anonymous visitors cannot access:

- Year dashboard.
- Tax pages.
- Profile page.
- Member-only content pages.
- Admin pages.

### Logged-In Members

Logged-in members can access:

- Current and allowed year dashboards.
- Tax pages for allowed years.
- Their own profile page.
- Member-only content pages.
- Application pages linked from the member menu.

Logged-in members cannot access:

- Admin pages.
- Other users' account/profile editing pages.
- Payment records for other users.

### Admins

Admins can access:

- Member-facing pages.
- Admin home.
- Users admin.
- Camp admin.
- Payments admin.
- Stripe admin.
- Pages admin.
- Menus admin.
- Media admin.

Admins should be able to return from admin pages to the member-facing site.

Admins should not have member impersonation in the first version.

### Deactivated Accounts

Deactivated accounts should not be able to log in.

If a person should not be allowed to pay taxes or access private information, their account should be deactivated.

## Resolved Design Questions

- `/dashboard/` redirects to `/<year>/dashboard/`.
- `/<year>/` may redirect to or alias `/<year>/dashboard/`.
- `/login/` redirects already logged-in users to `/dashboard/`.
- Members can change their own email, with a confirmation step before saving.
- Media starts as one flat folder with no subfolders.
- Media may later gain a folder structure that reflects disk storage.
- Media storage filenames may be system-generated.
- Test payment deletion belongs in `/admin/stripe/`.
- Stripe test/live mode is visible and controlled in `/admin/stripe/`.
- Production may be switched to Stripe test mode for yearly payment-flow testing.
- Public pages are static files under `/public/`, not Django-managed content pages.
- `/` redirects to `/public/`.
- Member pages use a top menu.
- The top member menu is named `root`.
- Additional named menus render as member-only pages at `/menu/<menu_name>/`.
- Menu pages may later be progressively enhanced into click/tap dropdown panels, but V1 should not use hover-only menus.
- Admin pages are only accessible to admins.
- Member impersonation is not part of V1.
- Year dashboard content uses linked Markdown pages/content for pre-checklist and post-checklist text.

## Related Design Documents

More detailed implementation guidance now lives in:

- `design_docs/models.md`.
- `design_docs/storage.md`.
- `design_docs/admin_and_pages.md`.
- `design_docs/stripe_implementation.md`.
- `design_docs/content_media_security.md`.
- `design_docs/implementation_plan.md`.
- `design_docs/testing_implementation.md`.
- `design_docs/ui_baseline.md`.
