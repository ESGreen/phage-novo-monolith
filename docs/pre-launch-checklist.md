# Pre-Launch Checklist

## Purpose

Run this before opening taxes for a camp year and after major deployment or server changes.

This verifies the site end-to-end from public, member, admin, Stripe, and backup perspectives.

## Public Site

- Visit `/`.
- Confirm it redirects to `/public/`.
- Confirm `/public/` loads the public landing page.
- Confirm public assets load.
- Confirm `/login/` loads.

## Login And Profile

- Log in as a normal member.
- Confirm login redirects to `/dashboard/`.
- Confirm `/dashboard/` redirects to the current year dashboard.
- Visit `/profile/`.
- Update first name, last name, and bio.
- Replace profile photo.
- Change email with confirmation.
- Log out.
- Confirm old email no longer works.
- Confirm new email works.

## Member Access

- Confirm member can access the year dashboard.
- Confirm member can access `/phagebook/`.
- Confirm member can access member content pages.
- Confirm member cannot access `/admin/`.
- Confirm member receives `403` for admin pages.

## Admin Access

- Log in as admin.
- Confirm `/admin/` loads.
- Confirm the `The Phage Admin` title links back to `/admin/`.
- Confirm the admin nav does not duplicate the title link with a separate Home item.
- Confirm `/admin/users/` loads.
- Confirm `/admin/camp/` loads.
- Confirm `/admin/payments/` loads.
- Confirm `/admin/stripe/` loads.
- Confirm `/admin/pages/` loads.
- Confirm `/admin/surveys/` loads.
- Confirm `/admin/menus/` loads.
- Confirm `/admin/media/` loads.

## Camp Setup

- Confirm current camp year exists.
- Open the current year edit page from `/admin/camp/`.
- Confirm Dashboard Setup pages are set or intentionally blank.
- Confirm Camp survey is selected or intentionally blank.
- If Camp survey is selected, confirm its Redirect after submission URL sends members back to the dashboard or another intended internal path.
- Confirm tax tiers are configured.
- Confirm add-ons are configured.
- Confirm tax tier and add-on order is correct.
- Confirm tax tier and add-on edit pages load.
- Confirm dashboard pre-checklist content appears.
- Confirm dashboard post-checklist content appears.
- Confirm menus look correct.

## Pages And Menus

- Confirm `/admin/pages/` lists content pages and shows the Create Page card.
- Open an existing page edit screen at `/admin/pages/<slug>/`.
- Confirm Update and Back works for a harmless wording change or no-op save.
- Confirm Update and View opens the member-facing page.
- Confirm `/admin/menus/` lists menus and shows the Create Menu card.
- Open `/admin/menus/root/`.
- Confirm root menu items include Dashboard, Phage Book, and Profile in the intended order.
- Confirm menu item order controls are present where needed.
- Open an existing menu item edit screen.
- Confirm the menu item form only asks for label and URL.
- Confirm URL suggestions appear when JavaScript is enabled, while free-form URLs are still accepted.

## Stripe Test Mode

- Go to `/admin/stripe/`.
- Switch site to Stripe test mode.
- Confirm test mode is obvious in `/admin/stripe/`.
- Log in as test member.
- Confirm the test member has first name, last name, profile photo, and bio.
- If the current camp year has a Camp survey, complete it before taxes.
- Go to the year dashboard.
- Go to the taxes page.
- Select a tax amount and add-ons.
- Complete Stripe Checkout using `4242 4242 4242 4242`.
- Confirm return to site works.
- Confirm webhook marks payment paid.
- Confirm dashboard shows tax step complete.
- Confirm payment appears in admin.
- Confirm add-ons appear in admin.
- Confirm Stripe/payment logs exist.
- Delete test payment from `/admin/stripe/`.
- Confirm test member can repeat the test payment flow.

## Stripe Live Mode

- Return to `/admin/stripe/`.
- Switch site to live mode.
- Confirm live mode is obvious in `/admin/stripe/`.
- Confirm member-facing payment flow still looks normal.

## Final Live Payment Test

This test uses real money and should be performed intentionally.

- Confirm `/admin/stripe/` is in live mode.
- Admin logs in through the normal member flow.
- Confirm the admin member profile has first name, last name, profile photo, and bio.
- If the current camp year has a Camp survey, complete it before taxes.
- Admin goes to the current year dashboard.
- Admin goes to the taxes page.
- Admin pays their actual taxes with a real payment method.
- Admin confirms the site returns to the dashboard.
- Admin confirms the dashboard shows the tax step complete.
- Admin confirms the payment appears in `/admin/payments/`.
- Admin confirms the payment appears in the Stripe Dashboard.
- Admin confirms Stripe shows the expected amount and successful status.
- Admin confirms the payment is live, not test.

## Backups

- Confirm active-season backup schedule is enabled.
- Confirm recent database backup exists.
- Confirm recent config backup exists.
- Confirm media sync has run or media backup status is known.
- Confirm backup files are non-empty.
- Confirm backup upload target is reachable.
- Confirm restore procedure is documented in `docs/backup-and-restore.md`.

## Final Checks

- Confirm debug mode is off.
- Confirm HTTPS works.
- Confirm secure cookies are enabled.
- Confirm public pages and media still load.
- Confirm `/dashboard/` redirects to the correct year.
- Confirm `/phagebook/` redirects to the correct year.
- Confirm taxes are not announced until the final live payment test succeeds.
