# Yearly Rollover Runbook

## Purpose

This document describes how to prepare `thephage.org` for a new camp year.

Use this before opening taxes each year.

The goal is to make the yearly update predictable and boring.

## When To Use This

Use this runbook:

- Before opening taxes for a new camp year.
- Before announcing that members can log in and pay.
- After major tax/page/menu changes for the year.

## Assumptions

- Public pages live under `/public/`.
- Member pages are managed through the website admin.
- The current year is inferred from the maximum configured camp year.
- `/dashboard/` redirects to the current year dashboard.
- `/<year>/dashboard/` is the canonical year dashboard.
- Stripe test/live mode is managed through `/admin/stripe/`.

## Admin Sections Used

- `/admin/users/`
- `/admin/camp/`
- `/admin/payments/`
- `/admin/stripe/`
- `/admin/pages/`
- `/admin/menus/`
- `/admin/media/`

## High-Level Checklist

- Create a full EC2 image before major changes.
- Create or verify the new camp year.
- Update year dashboard content.
- Update member content pages.
- Update public static pages if needed.
- Update menus.
- Configure tax tiers.
- Configure tax add-ons.
- Add tax overrides if needed.
- Review users.
- Test Stripe in test mode.
- Delete test payments.
- Switch Stripe to live mode.
- Run final live payment test.
- Confirm backups are running.
- Open taxes.

## 1. Create A System Backup

Before making major yearly changes, create an EC2 image.

This gives a full-machine rollback point before changing tax settings, pages, menus, or deployment configuration.

Record:

- Backup date.
- EC2 image ID.
- Reason for backup.
- Person who created it.

## 2. Create Or Verify Camp Year

Go to `/admin/camp/`.

Create the new camp year if it does not already exist.

Example:

```text
2026
```

The current year is inferred from the maximum configured camp year, so creating a new year changes where `/dashboard/` points.

Verify:

- The new year exists.
- Old years still exist.
- `/dashboard/` points to the new year dashboard after the new year is ready.

Do not create the new camp year until you are ready for it to become the current year.

## 3. Configure Year Dashboard Content

Go to `/admin/camp/`.

Configure the year dashboard text.

The dashboard has two Markdown content areas:

- Pre-checklist content.
- Post-checklist content.

Use the pre-checklist content for the most important yearly information.

Use the post-checklist content for supporting details, reminders, links, or longer explanatory text.

Verify:

- `/<year>/dashboard/` loads.
- The pre-checklist content appears.
- The post-checklist content appears.
- The dashboard makes the next required action obvious.

## 4. Update Member Content Pages

Go to `/admin/pages/`.

Review existing member pages.

Update evergreen pages in place.

Create a new page only when the old page should remain available or when the page is specifically year-based.

For year-specific content, include the year in the slug.

Example:

```text
2026-arrival-info
```

Verify:

- Page titles are clear.
- Slugs are correct.
- Markdown renders correctly.
- Images load.
- Links work.
- Member-only pages require login.

## 5. Update Public Static Pages

Public pages are static files under `/public/`.

Update these files outside Django and upload them to the public directory.

Common files:

```text
/public/index.html
/public/about.html
/public/assets/...
```

Verify:

- `/` redirects to `/public/`.
- `/public/` loads.
- Public assets load.
- Public pages do not show member navigation.
- Public pages link to `/login/` where appropriate.

## 6. Update Media

Go to `/admin/media/`.

Upload any new media needed for member content pages.

For V1, media is stored in one flat folder.

If an image needs resizing, resize it offline and upload the resized file.

Verify:

- Uploaded media appears in `/admin/media/`.
- Media files load from the site.
- Markdown pages can reference uploaded media.

## 7. Update Menus

Go to `/admin/menus/`.

Review the member menu.

The top-level member menu is the `root` menu.

Menu items are labels plus URLs inside a named menu.

Menu items can link to member-only menu pages such as `/menu/camp-info/` to keep the top-level menu short.

Common menu targets:

```text
/dashboard/
/profile/
/<year>/taxes/
/pages/<slug>/
/menu/<menu_name>/
https://external.example.com
```

Verify:

- Menu order is correct by display order, then label.
- Labels are clear.
- Internal URLs work.
- Menu page URLs work.
- External URLs work.
- Logout is available from the member menu.
- Public pages do not show the member menu.

## 8. Configure Tax Tiers

Go to `/admin/camp/`.

Create tax tiers for the new year.

Each tax tier is a minimum amount, not a fixed required payment.

Members may pay more than the tier minimum.

Each tax tier has a start timestamp and an expiration timestamp.

At least one available tax tier is required before members can pay.

Verify:

- Tier names are clear.
- Descriptions are clear.
- Minimum amounts are correct.
- Start timestamps are correct.
- Expiration timestamps are correct.
- Expiration timestamps are after start timestamps.
- Display order is correct.

## 9. Configure Tax Add-Ons

Go to `/admin/camp/`.

Create any optional add-ons for the new year.

Examples:

```text
Hoodie
Porta contribution
Supplies
```

Each add-on has its own start timestamp and expiration timestamp.

Verify:

- Add-on names are clear.
- Descriptions are clear.
- Amounts are correct.
- Start timestamps are correct.
- Expiration timestamps are correct.
- Expiration timestamps are after start timestamps.
- Display order is correct.

## 10. Configure Tax Overrides

Go to `/admin/camp/`.

Most members do not need tax overrides.

Create an override only for a special case.

Override types:

- Reduced minimum amount.
- Tax waived.

Use reduced minimum amount when a person should be allowed to pay a lower minimum.

Use tax waived when a person should not owe taxes for the year.

Verify:

- Override applies to the correct user.
- Override applies to the correct camp year.
- Reduced minimum amount is correct.
- Tax waived users see the tax step as complete.
- No user has more than one override for the same camp year.

## 11. Review Users

Go to `/admin/users/`.

Review users before opening taxes.

Verify:

- Admin users are correct.
- Member users are correct.
- Inactive users should remain inactive.
- Users who should not access the site are inactive.
- Users have correct email addresses.
- User/profile data looks reasonable.

## 12. Run Stripe Test Mode

Go to `/admin/stripe/`.

Switch the site to Stripe test mode.

Verify:

- Test mode is obvious in `/admin/stripe/`.
- Test Stripe configuration is healthy.
- Webhook configuration is healthy.

Log in as a test member.

Run the normal member payment flow:

- Go to `/dashboard/`.
- Go to the current year dashboard.
- Go to the taxes page.
- Select tax amount.
- Select add-ons.
- Start Stripe Checkout.
- Complete checkout using a Stripe test card.
- Return to the site.
- Confirm dashboard shows tax step complete.
- Confirm payment appears in admin.
- Confirm add-ons appear in admin.
- Confirm Stripe/payment logs exist.

## 13. Delete Test Payments

Go to `/admin/stripe/`.

Delete test payments created during testing.

Verify:

- Test payments are deleted.
- Related local test add-ons are deleted.
- Related local test logs are deleted as appropriate.
- Live payments are not deleted.
- The test member can repeat the test flow if needed.

## 14. Switch Stripe To Live Mode

Go to `/admin/stripe/`.

Switch the site to live mode.

Verify:

- Live mode is obvious in `/admin/stripe/`.
- Live Stripe configuration is healthy.
- Webhook configuration is healthy.
- Member-facing workflow looks the same as test mode.

## 15. Run Final Live Payment Test

This is a manual test and uses real money.

The admin should pay their actual taxes through the normal member flow.

Steps:

- Confirm `/admin/stripe/` is in live mode.
- Admin logs in as a normal member.
- Admin goes to `/dashboard/`.
- Admin goes to the current year dashboard.
- Admin goes to the taxes page.
- Admin pays taxes with a real payment method.
- Admin confirms the site returns to the dashboard.
- Admin confirms the dashboard shows the tax step complete.
- Admin confirms the payment appears in `/admin/payments/`.
- Admin confirms the payment appears in the Stripe Dashboard.
- Admin confirms Stripe shows the expected amount and successful status.
- Admin confirms the payment is live, not test.

## 16. Verify Backups

Before announcing taxes, verify active-season backups.

Check:

- Recent database backup exists.
- Backup file is non-empty.
- Backup uploaded to S3.
- Deployment/config backup exists.
- Backup process reports success.
- EC2 image exists if one was created for the rollover.

Daily database backups are acceptable for V1.

## 17. Open Taxes

After the live payment test succeeds, taxes can be announced.

Before announcement, verify:

- `/dashboard/` redirects to the correct year.
- Current year dashboard is correct.
- Tax page is available.
- Tax tiers are correct.
- Add-ons are correct.
- Stripe is in live mode.
- Backups are running.
- Admin has successfully made a live payment.

## 18. Monitor After Opening

After taxes open, periodically check:

- `/admin/payments/`
- `/admin/stripe/`
- Stripe Dashboard
- Backup status
- Error logs

Look for:

- Failed payments.
- `requires_review` payments.
- Stripe webhook errors.
- Members reporting login issues.
- Members reporting tax amount issues.

## 19. Closing Taxes

When taxes are done:

- Confirm all tax tiers and add-ons have expired or are no longer needed.
- Confirm no unexpected available add-ons remain.
- Confirm final payments are visible.
- Confirm database backup completed.
- Consider taking a final EC2 image.
- Keep records for the year.

## Troubleshooting Notes

If a payment is marked `requires_review`, inspect:

- Payment record.
- Payment logs.
- Stripe Dashboard.
- Stripe webhook events.

For V1, there is no custom web workflow for resolving `requires_review` payments.

If needed, an admin can resolve the issue directly in the database after confirming the truth in Stripe.

If Stripe test/live mode is confusing, stop and verify `/admin/stripe/` before continuing.

If a member cannot pay, check:

- User is active.
- Correct camp year exists.
- At least one valid tax tier exists.
- Required steps are complete.
- Tax override is correct.
- Member has not already paid.
