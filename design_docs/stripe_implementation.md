# Stripe Implementation

## Purpose

This document defines the V1 Stripe Checkout and webhook implementation for `thephage.org`.

The goals are:

- Keep card/payment handling entirely inside Stripe.
- Treat webhooks as the source of truth.
- Keep test/live mode explicit for admins.
- Prevent local state from marking someone paid unless Stripe confirms it.
- Prefer failed/unavailable checkout over duplicate successful payments.
- Keep payment behavior small enough to reason about during tax season.

## Core Rules

- Use Stripe Checkout.
- Accept credit cards only in V1.
- Do not collect or store card details.
- Use one-time payments only.
- Use USD only.
- Store money locally as integer cents.
- Stripe webhooks are the source of truth for `paid`.
- Checkout return pages never mark payments paid.
- Only one `paid` payment is allowed per user per camp year.
- Failed, cancelled, refunded, and `requires_review` payments do not count as paid.
- Production may run in Stripe test mode for annual payment-flow testing.
- Test/live mode is controlled only from `/admin/stripe/`.

## Configuration

Stripe credentials live in:

```text
/etc/thephage/thephage.toml
```

Example format lives in:

```text
deploy/thephage.toml.example
```

Expected Stripe config fields:

```toml
[stripe]
test_secret_key = "..."
test_publishable_key = "..."
test_webhook_secret = "..."

live_secret_key = "..."
live_publishable_key = "..."
live_webhook_secret = "..."
```

Current mode lives in the database:

```text
SiteSettings.stripe_mode
```

Allowed modes:

```text
test
live
```

Rules:

- `/admin/stripe/` changes `SiteSettings.stripe_mode`.
- Secrets are never edited through the web UI.
- Secrets are never displayed in the web UI.
- Secrets are never written to payment logs.

## Checkout Creation Flow

URL:

```text
/<year>/taxes/
```

When the member submits the tax payment form:

1. Confirm user is active.
2. Confirm camp year exists.
3. Confirm user does not already have a `paid` payment for the camp year.
4. Confirm user does not have a `waived` tax override.
5. Confirm user has no unexpired `created` payment for the same camp year.
6. Load currently available tax tiers.
7. Confirm selected tax tier is currently available.
8. Confirm selected add-ons are currently available.
9. Compute effective minimum.
10. Validate entered tax amount.
11. Create local `Payment(status="created")` with `checkout_expires_at`.
12. Create related `PaymentAddOn` snapshot rows.
13. Create Stripe Checkout Session.
14. Store `stripe_checkout_session_id` and `checkout_created_at`.
15. Redirect user to Stripe Checkout.

## Effective Minimum

If the user has no reduced-minimum override:

```text
effective_minimum = selected_tax_tier.minimum_amount_cents
```

If the user has a reduced-minimum override:

```text
effective_minimum = tax_override.reduced_minimum_amount_cents
```

The member may always pay more than the effective minimum.

## Duplicate Open Checkout Sessions

Before creating a Checkout Session, check whether the same user already has an unexpired `created` payment for the same camp year.

If an unexpired `created` payment exists:

- Do not create another Checkout Session.
- Show a message asking the member to return to the existing checkout flow or wait until it expires.
- Prefer failing closed over creating duplicate successful payment risk.

When `checkout_expires_at` has passed:

- The app may allow a new checkout attempt.
- The old local payment can remain `created` until a Stripe expiration webhook marks it `cancelled`.
- If useful, the taxes page may treat expired local `created` attempts as no longer blocking new checkout.

## Checkout Session Expiration

Store the expected expiration timestamp on the local payment:

```text
Payment.checkout_expires_at
```

Use Stripe Checkout's configured expiration if explicitly set. Otherwise, store the expiration returned by Stripe, if available.

If Stripe does not provide an expiration timestamp in the creation response, use a conservative local expiration window that matches the configured Checkout behavior.

## Checkout Payment Methods

Restrict Checkout to credit cards in V1.

Stripe Checkout configuration should set:

```text
payment_method_types = ["card"]
```

If Stripe sends events related to other payment methods anyway, log them and process only if they match the normal verified Checkout flow. Unknown or unexpected payment-method behavior should not mark a payment paid unless all normal verification succeeds.

## Checkout Line Items

Use Stripe Checkout line items that are readable in Stripe receipts and dashboard views.

Line items:

- One tax line item.
- One line item per selected add-on.

Tax line item name example:

```text
2026 Camp Taxes - Sustainer
```

Add-on line item name example:

```text
Hoodie
```

The Stripe total must equal:

```text
Payment.total_amount_cents
```

## Checkout Metadata

Set metadata on both the Checkout Session and Payment Intent.

Required metadata:

```text
payment_id
user_id
camp_year_id
camp_year
stripe_mode
```

Optional helpful metadata:

```text
tax_tier_name
tax_amount_cents
add_on_amount_cents
total_amount_cents
```

Rules:

- Metadata is for matching and verification.
- Metadata does not replace local database state.
- Webhooks must still verify database values and Stripe amounts.

## Checkout URLs

Success URL:

```text
/<year>/taxes/return/?session_id={CHECKOUT_SESSION_ID}
```

Cancel URL:

```text
/<year>/taxes/
```

Rules:

- The return page can show payment pending or payment complete based on local payment state.
- The return page must not mark payment paid.
- If webhook processing has not completed yet, show a pending/retry message.

## Webhook Endpoint

Recommended URL:

```text
/stripe/webhook/
```

Rules:

- Public unauthenticated endpoint.
- POST only.
- CSRF exempt.
- Must verify Stripe signature before parsing or trusting payload.
- Must use the raw request body for verification.
- Must return `2xx` after safely logging handled or review-required events.

## Webhook Signature Verification

Because production may switch between test and live mode, the webhook handler should be able to verify either test or live webhook signatures.

Recommended behavior:

- Try the current mode's webhook secret first.
- If verification fails, try the other mode's webhook secret.
- If exactly one secret verifies, accept the event and assign that `stripe_mode`.
- If no secret verifies, reject with `400`.
- If both somehow verify, reject or mark suspicious.

This allows delayed test/live webhook events to be processed correctly after the admin switches modes.

## Webhook Events

Primary event:

```text
checkout.session.completed
```

Use this to mark payments paid when all verification succeeds.

Also handle:

```text
checkout.session.expired
payment_intent.payment_failed
charge.refunded
```

V1 behavior:

| Event | Local behavior |
|---|---|
| `checkout.session.completed` | Mark `paid` only after full verification |
| `checkout.session.expired` | Mark `cancelled` if still `created` |
| `payment_intent.payment_failed` | Mark `failed` if still `created` |
| `charge.refunded` | Mark `refunded` only for full refunds |
| Unknown event | Log and return success without state change |

Partial refunds:

```text
requires_review
```

## Webhook Verification Checklist

For `checkout.session.completed`, verify:

- Signature is valid.
- Stripe mode is known.
- Metadata includes `payment_id`.
- Metadata includes `user_id`.
- Metadata includes `camp_year_id` or `camp_year`.
- Local payment exists.
- Local payment user matches metadata.
- Local payment camp year matches metadata.
- Local payment Stripe mode matches verified webhook mode.
- Checkout Session ID matches local payment, or local payment session ID is blank and can be safely filled.
- Stripe `payment_status` is `paid`.
- Stripe amount total matches `Payment.total_amount_cents`.
- Stripe currency is `usd`.
- User does not already have another `paid` payment for the same camp year.

If all checks pass:

```text
Payment.status = "paid"
Payment.paid_at = Stripe-confirmed timestamp or current webhook processing time
```

If any important check fails:

```text
Payment.status = "requires_review"
```

Do not mark paid.

## Idempotency

Webhook handling must be idempotent.

Rules:

- Duplicate Stripe events should be logged but should not apply state changes twice.
- Do not make `PaymentLog.stripe_event_id` unique. A unique log field can create avoidable failures when duplicate information needs to be recorded.
- If payment is already `paid`, duplicate success events return success without changes.
- If payment is already terminal, incompatible events should be logged and ignored or marked for review.
- State changes should happen inside a database transaction.
- Lock the `Payment` row while processing a webhook.

## Stripe API Idempotency

When creating Checkout Sessions, use a Stripe idempotency key.

Recommended key:

```text
payment:{payment_id}:checkout:create
```

This helps avoid duplicate sessions if the app retries after a network failure.

The local unexpired `created` payment check is still required. Stripe API idempotency is not a substitute for local duplicate-payment protection.

## Duplicate Successful Payments

Local rule:

- Only one `paid` payment is allowed per user per camp year.

If two Checkout Sessions somehow complete successfully for the same user/year:

- The first verified webhook marks its payment `paid`.
- Later successful webhooks for the same user/year become `requires_review`.
- Admin resolves directly after checking Stripe.

This should be rare because V1 blocks creation of a second checkout while an earlier local `created` payment remains unexpired.

## Payment Status Transitions

Allowed normal transitions:

| From | To | Cause |
|---|---|---|
| `created` | `paid` | Verified `checkout.session.completed` |
| `created` | `cancelled` | `checkout.session.expired` |
| `created` | `failed` | `payment_intent.payment_failed` |
| `paid` | `refunded` | Full refund webhook |
| Any non-paid | `requires_review` | Mismatch or suspicious event |

Rules:

- Do not automatically move `requires_review` to `paid`.
- Do not mark refunded payments as paid.
- Do not let member-facing return URLs change status.

## Payment Logs

Create `PaymentLog` entries for:

- Checkout creation request.
- Checkout creation success.
- Checkout creation failure.
- Webhook received.
- Duplicate webhook or duplicate event information.
- Webhook signature failure.
- Webhook verification failure.
- Webhook state change.
- `requires_review` decision.
- Test payment cleanup.

Logs must not store:

- Stripe secret keys.
- Webhook signing secrets.
- Card data.
- Full unredacted Stripe payloads with sensitive fields.

## Test Payment Cleanup

Admin URL:

```text
/admin/stripe/
```

Behavior:

- Deletes local test-mode payment records.
- Deletes related test `PaymentAddOn` rows.
- Deletes related test `PaymentLog` rows where appropriate.
- Never deletes live payment records.
- Requires confirmation before cleanup.

Rules:

- Match test payments by `Payment.stripe_mode = "test"`.
- Do not call Stripe to delete payments.
- Stripe Dashboard test records remain in Stripe.
- After cleanup, the test user can repeat the payment flow.

## Stripe Admin Health

`/admin/stripe/` should show:

- Current Stripe mode.
- Whether test secret key appears configured.
- Whether test publishable key appears configured.
- Whether test webhook secret appears configured.
- Whether live secret key appears configured.
- Whether live publishable key appears configured.
- Whether live webhook secret appears configured.
- Recent payment logs.
- Recent test payment activity.
- Recent live payment activity.
- Test payment cleanup controls.

Do not show raw secret values.
