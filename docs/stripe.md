# Stripe Runbook

## Bottom Line First

The Stripe test/live switch is in:

```text
/admin/stripe/
```

Use this page to:

- See whether the site is in Stripe test mode or live mode.
- Switch between test and live mode.
- Check Stripe configuration health.
- Review recent Stripe/payment logs.
- Delete test payments.

Common Stripe test card:

```text
4242 4242 4242 4242
```

Use any valid future expiration date and CVC supported by Stripe test mode.

Production may run in Stripe test mode when admins are verifying the yearly payment flow. The member-facing workflow should be the same in test mode and live mode.

The deployed Stripe secrets and mode defaults live in `/etc/thephage/thephage.toml`. The committed example format is `deploy/thephage.toml.example`.

## Purpose

This document describes how Stripe is used by `thephage.org`.

Use this when:

- Configuring Stripe.
- Testing yearly payments.
- Switching between test and live mode.
- Investigating payment problems.
- Reviewing webhook behavior.
- Cleaning up test payments.

## Core Rules

- Stripe Checkout is used for payment collection.
- V1 accepts credit cards only.
- The website never stores card details.
- Stripe webhooks are the source of truth for successful payments.
- The same member-facing payment flow is used in test mode and live mode.
- Test/live mode is controlled from `/admin/stripe/`.
- Test/live mode should not appear as a special workflow on member-facing pages.
- Production may run in Stripe test mode when admins are testing the yearly payment flow.
- Only one successful payment is allowed per user per camp year.
- Extra or unusual payments are handled outside the website.

## Admin Pages

Stripe-related admin work happens primarily in:

```text
/admin/stripe/
```

Payment review happens in:

```text
/admin/payments/
```

## Stripe Modes

The site has two Stripe modes:

- `test`
- `live`

Test mode uses Stripe test credentials.

Live mode uses Stripe live credentials.

The current mode must be obvious on `/admin/stripe/`.

## When To Use Test Mode

Use test mode:

- During yearly rollover.
- Before opening taxes.
- After major deployment changes.
- After OS/server/package upgrades.
- When investigating payment workflow problems.
- Before switching back to live mode after changes.

Test mode is allowed in production so admins can test the real deployed workflow.

## When To Use Live Mode

Use live mode only when the site is ready to accept real payments.

Before switching to live mode, verify:

- Tax tier start/expiration dates are correct.
- Tax tiers are correct.
- Add-ons are correct.
- Tax overrides are correct.
- Dashboard content is correct.
- Stripe test payment flow succeeds.
- Test payments have been deleted.
- Backups are running.

## Stripe Configuration

Stripe secrets are stored in the deployed TOML config file:

```text
/etc/thephage/thephage.toml
```

The committed example format is:

```text
deploy/thephage.toml.example
```

The website admin does not need to edit raw Stripe secret values.

The expected Stripe configuration should include:

```text
mode
test_secret_key
test_publishable_key
test_webhook_secret
live_secret_key
live_publishable_key
live_webhook_secret
```

Secrets should not be committed to the repository.

Secrets should not be shown in admin pages.

Secrets should not be written to payment logs.

## Stripe Admin Health

`/admin/stripe/` should show:

- Current Stripe mode.
- Whether test configuration appears valid.
- Whether live configuration appears valid.
- Whether webhook configuration appears valid.
- Recent Stripe/payment log entries.
- Test and live payment activity needed for troubleshooting.
- Test payment cleanup controls.

The page should make it very obvious whether the site is in test mode or live mode.

## Switching To Test Mode

Go to:

```text
/admin/stripe/
```

Switch mode to:

```text
test
```

Verify:

- Test mode is obvious.
- Stripe test configuration appears healthy.
- Webhook configuration appears healthy.
- Member-facing payment workflow still looks normal.

Then run the normal member payment flow using a Stripe test card.

## Test Payment Flow

Use this flow during yearly rollover or deployment testing.

Steps:

- Go to `/admin/stripe/`.
- Switch site to test mode.
- Log in as a test member.
- Go to `/dashboard/`.
- Go to the current year dashboard.
- Go to taxes.
- Select a valid tax amount.
- Select any add-ons that need testing.
- Start Stripe Checkout.
- Use a Stripe test card.
- Complete checkout.
- Return to the site.
- Confirm dashboard shows tax step complete.
- Confirm payment appears in `/admin/payments/`.
- Confirm selected add-ons are recorded.
- Confirm payment logs were created.
- Confirm Stripe Dashboard shows the test payment.

Common Stripe test card:

```text
4242 4242 4242 4242
```

Use any valid future expiration date and CVC supported by Stripe test mode.

## Deleting Test Payments

Test payments should be deletable from:

```text
/admin/stripe/
```

Deleting test payments should delete:

- Local test payment records.
- Related local test payment add-ons.
- Related local test payment logs, as appropriate.

Deleting test payments should not delete live payments.

After deleting test payments, the test user should be able to repeat the test payment flow.

## Switching To Live Mode

Go to:

```text
/admin/stripe/
```

Switch mode to:

```text
live
```

Verify:

- Live mode is obvious.
- Live configuration appears healthy.
- Webhook configuration appears healthy.
- Member-facing payment workflow still looks normal.
- Test payments have been deleted.

Do not announce taxes until the final live payment test succeeds.

## Final Live Payment Test

This is a manual test using real money.

The admin should pay their own taxes through the normal member flow.

Steps:

- Confirm `/admin/stripe/` is in live mode.
- Admin logs in as a normal member.
- Admin goes to `/dashboard/`.
- Admin goes to the current year dashboard.
- Admin goes to taxes.
- Admin pays taxes with a real payment method.
- Admin confirms the site returns to the dashboard.
- Admin confirms dashboard shows tax step complete.
- Admin confirms payment appears in `/admin/payments/`.
- Admin confirms payment appears in the Stripe Dashboard.
- Admin confirms Stripe shows the expected amount.
- Admin confirms Stripe marks the payment successful.
- Admin confirms the payment is live, not test.

## Payment Records

Each checkout attempt creates a local payment record.

Checkout-created payment records store a Checkout expiration timestamp so the site can avoid creating duplicate open checkout sessions for the same user/year.

Payment statuses:

- `created`
- `paid`
- `failed`
- `cancelled`
- `refunded`
- `requires_review`

A member is considered paid for a camp year only if they have a `paid` payment for that year.

Failed, cancelled, and `requires_review` payments do not count as paid.

Refunded payments do not count as paid unless explicitly changed later.

## Payment Add-Ons

Selected add-ons are stored with the payment.

Add-on records should include snapshots of:

- Add-on name.
- Add-on amount.

This makes old payment records understandable even if the add-on is renamed or changed later.

## Payment Logs

The site should log useful Stripe-related traffic, including:

- Checkout creation.
- Stripe responses.
- Webhook receipt.
- Webhook signature validation.
- Webhook processing result.
- Internal payment state changes.

Logs should not store:

- Stripe secret keys.
- Webhook secrets.
- Card data.
- Sensitive fields that Stripe may send unexpectedly.

If a payload contains sensitive values, redact them before storage.

Payment logs are for troubleshooting. They should not drive payment state by themselves.

## Webhooks

Stripe webhooks are the source of truth for marking payments paid.

The webhook handler should:

- Verify the webhook signature.
- Log receipt of the webhook.
- Validate required metadata.
- Find the matching local payment.
- Confirm amount matches.
- Confirm Stripe mode matches.
- Confirm user/camp year metadata matches.
- Mark payment as `paid` only if the data matches.
- Set `paid_at`.
- Avoid duplicate records if the same webhook arrives more than once.

Webhook handling must be idempotent.

## Required Metadata

Stripe Checkout sessions should include enough metadata to match a webhook to a local payment.

Recommended metadata:

```text
payment_id
user_id
camp_year
stripe_mode
```

If required metadata is missing, the payment should not be marked paid.

## Requires Review

Use `requires_review` when a webhook or payment event does not match expected local data.

Examples:

- Amount mismatch.
- Unknown payment ID.
- Missing metadata.
- Wrong Stripe mode.
- User mismatch.
- Camp year mismatch.

For V1, there is no custom web workflow for resolving `requires_review`.

If this rare case happens, an admin can inspect:

- `/admin/payments/`
- `/admin/stripe/`
- Payment logs.
- Stripe Dashboard.
- Stripe webhook events.
- Database records.

After confirming the truth in Stripe, an admin can resolve the issue directly in the database if needed.

## Common Troubleshooting

### Member Says They Paid But Dashboard Does Not Show Paid

Check:

- `/admin/payments/`
- `/admin/stripe/`
- Payment logs.
- Stripe Dashboard.
- Stripe webhook events.

Look for:

- Payment status.
- Stripe mode.
- Amount.
- User.
- Camp year.
- Webhook delivery status.
- `requires_review`.

### Stripe Payment Exists But Site Did Not Update

Check:

- Webhook endpoint is configured.
- Webhook secret is correct.
- Webhook delivery succeeded in Stripe.
- Webhook logs exist locally.
- Payment metadata matches local payment.
- Payment is not marked `requires_review`.

### Test Payment Accidentally Left In System

Go to:

```text
/admin/stripe/
```

Delete test payments.

Confirm:

- Test payments are gone.
- Live payments remain.
- Test user can pay again if needed.

### Wrong Stripe Mode

Go to:

```text
/admin/stripe/
```

Confirm current mode.

If wrong:

- Stop.
- Switch to the correct mode.
- Review recent payment activity.
- Confirm no live payment was made in error.
- Confirm no test payment is being treated as live.

## Annual Stripe Checklist

Before opening taxes:

- Switch to test mode.
- Complete test payment flow.
- Confirm webhook works.
- Confirm add-ons are recorded.
- Confirm payment logs exist.
- Delete test payments.
- Switch to live mode.
- Complete final live admin payment.
- Verify payment in Stripe Dashboard.
- Announce taxes only after live payment succeeds.

## Things Not Handled By Website

The website does not handle:

- Arbitrary extra payments.
- Donations outside camp taxes.
- Multiple successful payments per user/year.
- Complex refund workflows.
- Dispute management.

Handle those directly in Stripe or manually as needed.
