# UI Baseline

## Purpose

This document defines the V1 layout, navigation, form, and responsive behavior baseline.

The goal is not to create a final visual brand. The goal is to make the first implementation usable, consistent, mobile-friendly, and easy to maintain.

## Core Rules

- Server-rendered Django templates.
- Minimal JavaScript.
- Mobile-friendly from the start.
- Keep desktop and mobile structure similar.
- Public pages do not show member navigation.
- Member pages show the `root` menu.
- Admin pages show admin navigation.
- Forms show clear field-level errors.
- Buttons and links should be visually distinguishable.
- Avoid hover-only interactions.
- Avoid deep/nested navigation.

## Template Structure

Base templates:

```text
base.html
public_base.html
member_base.html
admin_base.html
```

### `base.html`

Owns:

- HTML document shell.
- `<head>` metadata.
- CSS includes.
- Main content block.
- Message rendering.
- Basic footer block if needed.

### `public_base.html`

Extends `base.html`.

Used for:

- Login page.
- Any Django-served public utility pages.

Public static pages under `/public/` are plain static files and do not need to extend Django templates.

### `member_base.html`

Extends `base.html`.

Used for:

- Dashboard.
- Taxes.
- Profile.
- Content pages.
- Menu pages.

Includes:

- Site name/header.
- `root` member menu.
- Logout action.
- Main content area.

### `admin_base.html`

Extends `base.html`.

Used for product admin pages.

Includes:

- Admin header.
- Admin section links.
- Link back to member site.
- Current admin section indicator.

## Layout Width

Use a simple centered page layout.

Recommended max width:

```text
max-width: 72rem
```

For text-heavy content pages, use a narrower readable measure:

```text
max-width: 48rem
```

Rules:

- Main content should have comfortable padding.
- Mobile should use full width with side padding.
- Avoid horizontal scrolling.

## Navigation

## Public Navigation

Public pages should show only:

- Site identity.
- Login link where appropriate.
- Public content links if the static public site wants them.

Do not show:

- Member menu.
- Admin menu.
- Private content links except login.

## Member Navigation

The top member navigation renders the `root` menu.

Desktop behavior:

- Show `root` menu items horizontally if they fit.
- Logout appears as a normal top-level action.
- Menu items can link to `/menu/<menu_name>/` pages.

Mobile behavior:

- Use a simple menu button or stacked vertical nav.
- Avoid hover dropdowns.
- `/menu/<menu_name>/` pages remain normal navigable pages.
- If progressive enhancement is added later, click/tap panels must keep the normal page URL as fallback.

Rules:

- No hover-only dropdowns.
- No nested menu tree in V1.
- Menu item ordering is `display_order`, then `label`.
- The current page may be indicated if straightforward.

## Menu Pages

Menu page layout:

- Page title from the menu name or a readable derived heading.
- List of menu items.
- Same member header and root menu as other member pages.

Recommended display:

```text
Camp Info

- Arrival Info
- Packing List
- Camp Map
- Policies
```

## Admin Navigation

Admin pages should show links to:

- Admin home.
- Users.
- Camp.
- Payments.
- Stripe.
- Pages.
- Menus.
- Media.
- Member site.

Rules:

- Admin navigation should be boring and obvious.
- Do not hide important admin links behind hover behavior.
- Highlight or label the current section if easy.

## Messages

Use Django messages for:

- Save success.
- Delete success.
- Validation failures that are not field-specific.
- Stripe mode switched.
- Test payments deleted.
- Password changed.

Message levels:

- Success.
- Info.
- Warning.
- Error.

Messages should appear near the top of the main content.

## Forms

Form rules:

- Labels are always visible.
- Required fields are obvious.
- Field help text appears near the field.
- Field errors appear next to the field.
- Non-field errors appear above the form.
- Use normal POST/redirect/GET after successful form submissions.
- Avoid modal-only forms in V1.

Recommended button labels:

- `Save`.
- `Create`.
- `Delete`.
- `Cancel`.
- `Start Checkout`.
- `Switch To Test Mode`.
- `Switch To Live Mode`.

Destructive actions:

- Require explicit confirmation page or confirmation form.
- Do not rely only on JavaScript confirm dialogs.
- Use clear wording for test payment cleanup and media deletion.

## Tables And Lists

Admin list pages may use simple tables.

Rules:

- Tables should be readable on desktop.
- On mobile, allow horizontal scroll if needed rather than creating complicated responsive table behavior.
- Keep table columns minimal.
- Provide clear links to edit/detail pages.

Use lists/cards instead of tables where data is short.

## Markdown Content Styling

Rendered Markdown should support:

- Headings.
- Paragraphs.
- Lists.
- Links.
- Images.
- Code blocks.
- Blockquotes.
- Pipe tables.

Rules:

- Content images should be responsive.
- Tables may horizontally scroll on small screens.
- Code blocks may horizontally scroll.
- Long links should wrap.
- Markdown body should use readable line length.

## Images

Content images:

```css
max-width: 100%;
height: auto;
```

Profile photos:

- Display as bounded images.
- Do not require cropping in V1.
- Do not add custom resizing UI.

Media admin:

- Show filename.
- Show title.
- Show copyable `/media/...` URL.
- Show upload date if available.

## Dashboard UI

Dashboard should make the next action obvious.

Sections:

- Year heading.
- Pre-content page.
- Status/checklist.
- Payment status.
- Action links.
- Post-content page.

Status examples:

- Profile complete.
- Taxes waived.
- Taxes paid.
- Taxes not paid.
- Payment pending.

## Taxes UI

Taxes page should show:

- Current year.
- Available tax tiers.
- Explanation that tiers are minimums.
- Custom amount input.
- Available add-ons.
- Total amount.
- Start Checkout button.
- Existing payment status if already paid.
- Waived status if waived.

Rules:

- If no tax tiers are available, explain that taxes are not currently available.
- If already paid, do not show checkout form.
- If waived, do not show checkout form.
- If a pending unexpired checkout exists, explain that another checkout cannot be started yet.

## Stripe Admin UI

`/admin/stripe/` should make mode obvious.

Show:

- Current mode.
- Test config health.
- Live config health.
- Webhook health.
- Recent logs.
- Test payment cleanup.

Mode display should be visually prominent.

Switching mode:

- Use explicit buttons.
- Show confirmation or clear post-action message.
- Do not expose secrets.

## Accessibility Baseline

V1 should follow basic accessibility practices:

- Semantic HTML.
- Labels connected to fields.
- Buttons for actions.
- Links for navigation.
- Visible focus states.
- Sufficient color contrast.
- No hover-only controls.
- Forms usable with keyboard.
- Images include useful alt text when shown from Markdown or admin-managed content.

## JavaScript

Use minimal JavaScript.

Allowed V1 uses:

- Mobile menu toggle, if needed.
- Optional progressive enhancement for UI convenience.

Do not require JavaScript for:

- Login.
- Profile updates.
- Tax payment form submission.
- Admin forms.
- Menu page navigation.
- Stripe mode switching.

Stripe Checkout itself may require Stripe's hosted JavaScript after redirect, but local site functionality should remain server-rendered.

## CSS Organization

Recommended files:

```text
static/css/base.css
static/css/member.css
static/css/admin.css
static/css/markdown.css
```

Keep CSS simple.

Avoid:

- CSS frameworks unless deliberately chosen.
- Complex build pipelines.
- Heavy frontend tooling.

## What Not To Design In V1

- Final branding.
- Complex animations.
- Hover dropdown menus.
- Drag-and-drop menu editing.
- Rich text editor.
- Image cropper.
- Modal-heavy admin UI.
- Client-side app shell.
