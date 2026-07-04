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
- Update name or bio.
- Replace profile photo.
- Change email with confirmation.
- Log out.
- Confirm old email no longer works.
- Confirm new email works.

## Member Access

- Confirm member can access the year dashboard.
- Confirm member can access member content pages.
- Confirm member cannot access `/admin/`.
- Confirm member receives `403` for admin pages.

## Admin Access

- Log in as admin.
- Confirm `/admin/` loads.
- Confirm `/admin/users/` loads.
- Confirm `/admin/camp/` loads.
- Confirm `/admin/payments/` loads.
- Confirm `/admin/stripe/` loads.
- Confirm `/admin/pages/` loads.
- Confirm `/admin/menus/` loads.
- Confirm `/admin/media/` loads.

## Camp Setup

- Confirm current camp year exists.
- Confirm tax tiers are configured.
- Confirm add-ons are configured.
- Confirm dashboard pre-checklist content appears.
- Confirm dashboard post-checklist content appears.
- Confirm menus look correct.

## Stripe Test Mode

- Go to `/admin/stripe/`.
- Switch site to Stripe test mode.
- Confirm test mode is obvious in `/admin/stripe/`.
- Log in as test member.
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
- Confirm taxes are not announced until the final live payment test succeeds.
