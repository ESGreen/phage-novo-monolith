# Reimbursements

## Purpose

The reimbursement system lets members record expenses made on behalf of the
camp and submit them for manual reimbursement.

The system should:

- Allow members to create reimbursements only for themselves.
- Support multiple categorized expenses within one reimbursement.
- Support multiple receipts or explanations covering the reimbursement as a
  whole.
- Reuse a member's preferred payout information.
- Preserve the payout information used when a reimbursement was submitted.
- Let administrators review, reject, return, and mark reimbursements paid.
- Keep the current reimbursement state understandable without preserving every
  prior negotiation version.

## Non-Goals

The first version does not include:

- Automated payments.
- A separate approval state.
- ACH payments.
- International check payments.
- Partial reimbursement payments.
- Multiple payments for one reimbursement.
- Payment verification.
- Payment references, check numbers, or transaction IDs.
- Administrators manually creating or submitting reimbursements for other
  members. The Split action may create a system-generated linked draft for the
  original requester.
- Receipt-to-expense matching.
- Expense dates.
- Expense ordering.
- Expense audit timestamps.
- Currency selection; all amounts are USD.

International and unusual payment situations will be handled outside the
website as one-off cases.

## Terminology

| Product Term | Meaning |
|---|---|
| Reimbursement | A member's request to be repaid for camp expenses |
| Expense | One categorized amount within a reimbursement |
| Receipt | An image, PDF, or written explanation supporting the reimbursement |
| Expense Category | A camp-year-specific category managed by administrators |
| Payout Profile | A member's current reusable reimbursement payment information |
| Payout Snapshot | The payout information copied into a reimbursement when submitted |

## Reimbursement

A reimbursement belongs to one member and one camp year.

The feature is implemented as a dedicated Django app named `reimbursements`.
The app owns reimbursement models, member/admin reimbursement views, payout
profiles, receipt storage and serving, reports, and tests. The existing camp
admin page calls into this app for category management.

Suggested fields:

```text
Reimbursement
- id
- reimbursement_number
- camp_year: foreign key to `CampYear`
- requester
- split_from
- status
- requester_notes
- payer_notes
- created_at
- submitted_at
- submitted_by
- paid_at
- paid_by
- rejected_at
- rejected_by
```

### Internal ID

`id` is the normal Django database primary key.

### Human-Readable ID

`reimbursement_number` is an immutable human-readable identifier.

Recommended format:

```text
2026-R-0001
2026-R-0002
2027-R-0001
```

Rules:

- The year comes from `camp_year`.
- `camp_year` is a foreign key to the existing `CampYear` model.
- Numbering is scoped to the camp year.
- The number is calculated when a draft is created by finding the greatest
  existing reimbursement number for that camp year and adding one.
- The number does not change when the reimbursement changes state.
- A database unique constraint on `reimbursement_number` is the final safeguard.
- If a rare concurrent collision occurs, retry calculation once and otherwise
  show a normal creation error.
- Gaps in the sequence are acceptable if a draft is deleted.
- The field is unique.
- Application forms and services never update the number after creation; no
  database-level immutability mechanism is required.

### Requester

`requester` identifies the member asking for reimbursement.

Rules:

- Members may create reimbursements only for themselves.
- Administrators create their own reimbursements through the normal member
  workflow.
- Administrators cannot create or submit a reimbursement on another user's
  behalf.
- The Split action is a narrow exception that allows the system to create a
  linked draft for the original requester. The administrator cannot edit or
  submit that draft as the requester.
- The requester cannot be changed after creation.

## V1 Simplicity Principles

This feature is designed for a community of at most approximately 200 people
who know one another and communicate directly. It is a workflow aid, not a
general accounting, dispute-resolution, or immutable audit system.

The following constraints are intentional:

- Split moves selected expenses into a new draft. Previous expense versions are
  not preserved.
- A reimbursement currently in draft may be deleted even if it was previously
  submitted or rejected.
- Manual payment happens outside the website. A rare payment/state race is
  handled by showing a clear conflict and resolving it through direct
  communication.
- Receipt file operations use safe ordering and best-effort cleanup. A small
  number of orphan files after a crash is acceptable.
- Private receipts must be included in backup, but completing the general
  backup/restore system is outside this feature.
- Direct database correction by an administrator is acceptable for exceptional
  cases that are intentionally not supported by the UI.
- User, camp-year, administrator-account deletion, and immutable historical
  identity edge cases are outside V1 scope.
- Paid amount and category data are read from the current expense records. No
  additional paid-expense snapshots are maintained.

The implementation should remain small unless an actual recurring operational
problem demonstrates that more machinery is needed.

### Split Lineage

`split_from` is a nullable self-referencing foreign key to the reimbursement
from which the new draft's expenses were split.

Rules:

- A normal reimbursement has no `split_from` value.
- A system-generated split draft points to its source reimbursement.
- One source reimbursement may have multiple split reimbursements.
- Split chains are allowed if a resubmitted split reimbursement is split again.
- `split_from` exists for convenient navigation, not permanent audit history.
- Deleting a split draft does not affect its source reimbursement.
- Use a reverse relationship such as `split_reimbursements` so both sides can
  display the lineage.

### Notes

`requester_notes` contains general information from the member.

`payer_notes` contains information from the administrator reviewing or paying
the reimbursement.

Rules:

- Payer notes are visible to the requester.
- Payer notes are not an internal or secret administrator field.
- Receipt explanations belong in receipt records rather than being hidden
  inside general requester notes.

## Reimbursement Status

Supported states:

```text
draft
submitted
paid
rejected
```

### Draft

- Editable by the requester.
- Expenses may be added and deleted.
- Correcting an expense means deleting it and adding a replacement.
- Receipts may be created and deleted.
- Requester notes may be edited.
- The draft may be deleted by the requester.
- A payout snapshot is not yet permanent.

### Submitted

- No longer editable by the requester.
- Waiting for administrator review or payment.
- Contains an immutable payout snapshot.
- Cannot be deleted by the requester.
- Remains submitted until an administrator pays it, rejects it, or returns it
  to draft.

There is no separate approval step. Marking a submitted reimbursement paid is
the administrator's approval and payment action.

### Paid

- The reimbursement has been manually paid.
- `paid_at` and `paid_by` are populated.
- The state is terminal in the normal workflow.
- Expenses, receipts, requester notes, and payout information remain unchanged.
- Payer notes may be corrected if needed.

### Rejected

- Rejected by an administrator.
- `rejected_at` and `rejected_by` are populated.
- Remains visible to the requester.
- Remains uneditable by the requester.
- May be moved back to `submitted` or returned to `draft` by an administrator.

## Status Transitions

Member-controlled transition:

```text
draft -> submitted
submitted -> draft through Unsubmit
```

Administrator-controlled transitions:

```text
submitted -> paid
submitted -> rejected
submitted -> draft

rejected -> submitted
rejected -> draft
```

Normal transitions out of `paid` are not supported.

If a paid reimbursement is recorded incorrectly, a future explicit correction
or reversal workflow should preserve the original history rather than silently
returning it to draft.

## Expenses

One reimbursement contains one or more expenses.

Suggested fields:

```text
ReimbursementExpense
- id
- reimbursement
- category
- description: required, maximum 2,000 characters
- amount_cents: PositiveBigIntegerField
```

The expense deliberately does not contain:

- Expense date.
- Display order.
- Created timestamp.
- Updated timestamp.
- Receipt relationship.

### Expense Rules

- At least one expense is required before submission.
- `category` is required.
- `description` is required and may not be blank or whitespace-only.
- `amount_cents` is required.
- Amounts are stored as integer cents.
- Amounts must be greater than zero.
- An individual expense may not exceed $1,000,000.00.
- Negative adjustments and credits are not supported in V1.
- The expense category must belong to the same camp year as the reimbursement.
- Expenses may be added and deleted only while the reimbursement is a draft.
- Members cannot change expenses while submitted, paid, or rejected.
- An administrator may move selected submitted expenses into a new draft
  through Split.

### Reimbursement Total

The total is derived from the expenses:

```text
total_amount_cents = sum(expense.amount_cents)
```

The reimbursement does not need a separately entered total.

The calculated total reflects the reimbursement's current expense rows. A Split
intentionally lowers the submitted source reimbursement total by moving selected
expenses into a new draft.

## Expense Categories

Expense categories are configured independently for each camp year.

Suggested fields:

```text
ReimbursementExpenseCategory
- id
- camp_year: foreign key to `CampYear`
- name: maximum 120 characters
```

Rules:

- Categories are managed by administrators.
- Category names are unique within a camp year, ignoring case and surrounding
  whitespace.
- Categories display alphabetically by name, ignoring case.
- No display-order field is needed.
- Categories are not renamed after creation.
- Members cannot create categories.
- An expense may use only a category from its reimbursement's camp year.
- A category cannot be deleted while any expense references it.
- Categories are independent between camp years.

### New Camp Years

Reimbursement categories are not copied when a camp year is created. Every camp
year begins with no reimbursement categories. Administrators create the
categories needed for that year from the camp-year edit page.

## Receipts And Explanations

Receipts belong to the reimbursement as a whole.

They do not belong to individual expenses because one receipt may contain
purchases allocated across multiple expense categories.

A reimbursement may have multiple receipt records.

Suggested fields:

```text
ReimbursementReceipt
- id
- reimbursement
- receipt_type
- original_filename
- file_path
- content_type
- size_bytes
- explanation
```

`original_filename` has a maximum stored length of 255 characters. Longer names
are deterministically truncated while preserving the validated extension.

Receipt explanations have a maximum length of 10,000 characters.

Supported receipt types:

```text
image
pdf
explanation
```

### File Receipts

For `image` or `pdf`:

- A file is required.
- `original_filename` is populated.
- `file_path` is populated.
- `content_type` is populated.
- `size_bytes` is populated.
- `explanation` is optional and contains notes or a description of the receipt.

### Explanation Receipts

For `explanation`:

- A meaningful explanation is required.
- No file is stored.
- File metadata fields are blank.

The server can require a non-empty explanation, but administrators remain
responsible for deciding whether the explanation is sufficient.

Every receipt therefore has an explanation field. It is optional when a file is
present and required when no file is present.

### Submission Requirement

A reimbursement must contain at least one receipt record before submission.

That receipt may be:

- An image.
- A PDF.
- A written explanation describing why no normal receipt is available and how
  the expense information was established.

## Receipt File Types

Accepted file types for V1:

```text
JPEG
PNG
WebP
PDF
```

Not accepted:

```text
SVG
HTML
ZIP
Office documents
Executables
Arbitrary renamed files
```

HEIC is not included in V1 unless specifically added later.

Images are validated with Pillow rather than trusting only the extension or
browser-provided MIME type.

For V1, a file whose sanitized filename ends in `.pdf`, ignoring case, is
accepted as a PDF after the normal file-size check. V1 does not parse, scan, or
inspect PDF contents. More sophisticated PDF validation may be added if an
actual problem occurs.

## Receipt File Limits

Recommended limits:

```text
Maximum file size: 15 MB
Maximum files per reimbursement: 20
Maximum total file size per reimbursement: 100 MB
```

These limits must be enforced by the application. Production Nginx
configuration must allow individual files up to the accepted application limit.

Written explanation receipts do not count toward the file count or byte limit.

## Private Receipt Storage

Receipt files must not be stored under the existing public media root.

Recommended production root:

```text
/var/lib/thephage/private/reimbursement-receipts/
```

Receipt files must not be stored under:

```text
/var/www/thephage/media/
```

The existing media path is served directly by Nginx and is unsuitable for
private financial documents.

### File Layout

Recommended layout:

```text
/var/lib/thephage/private/reimbursement-receipts/
  2026/
    2026-R-0001/
      4ff98266-91bd-4d0f-bf80-9886718c17e6.pdf
      5929d3fa-47e8-41c2-89ef-095ee7f6f21d.jpg
```

Rules:

- Store only a relative file path in the database.
- Generate an opaque UUID filename.
- Preserve a validated extension.
- Store the original filename in the database for display and download.
- Do not trust the original filename as a storage path.
- Do not expose filesystem paths to users.

### Filesystem Permissions

Recommended production ownership and modes:

```text
receipt root: phage:phage mode 0700
receipt files: phage:phage mode 0600
```

Only the Django application process should have access.

Nginx should not have direct filesystem access to receipt files.

The underlying production volume should use encryption at rest.

## Receipt Access

Receipt files should be served through an authenticated Django view.

Example route:

```text
/<year>/reimbursements/<reimbursement_number>/receipts/<receipt_id>/
```

Access is allowed only when the logged-in user is:

- The reimbursement requester.
- An administrator.

The receipt must belong to the reimbursement identified by the route, and the
reimbursement must belong to the camp year identified by the route.

Recommended response headers:

```text
X-Content-Type-Options: nosniff
Cache-Control: private, no-store
```

Images may be displayed inline.

PDFs should initially be served as downloads rather than embedded as
same-origin active content.

Django `FileResponse` is sufficient for the expected V1 traffic. An
authenticated Nginx internal redirect may be considered later if receipt
traffic becomes significant.

## Receipt Editing And Deletion

- Members may add and delete receipts while the reimbursement is a draft.
- Members cannot alter receipts after submission.
- Returning the reimbursement to draft restores receipt editing.
- Deleting a draft reimbursement deletes its stored receipt files.
- Submitted, rejected, and paid receipt evidence is retained.
- File deletion uses best-effort cleanup after the database change succeeds.
- A crash or filesystem error may leave an unreferenced private file. This is an
  accepted V1 tradeoff and does not require a cleanup subsystem.

## Receipt Backups

Private receipts should be backed up separately from public media.

Recommended S3 prefix:

```text
s3://web2-backups-thephage/prod/private/reimbursement-receipts/
```

The backup location must be:

- Private.
- Encrypted.
- Versioned.
- Restricted to the EC2 IAM role.
- Included in the existing scheduled backup operation.

Completing the repository's general restore workflow is outside this feature.
The known backup/restore gaps remain documented in
`design_docs/ReviewNotes_9_13_26.md`.

## Payout Methods

Supported methods in V1:

```text
paper_check
zelle
```

Not supported:

```text
ach
international_check
```

International and unusual payments will be handled manually outside the normal
website workflow.

Payment methods are code-defined choices, not administrator-created records. A
future payment method requires deliberate fields, validation, forms, and
display behavior.

## User Payout Profile

A member enters their preferred reimbursement payment information once through
the normal profile area.

The payout information should use a separate one-to-one model rather than
adding unrelated nullable fields directly to `MemberProfile`.

Suggested fields:

```text
ReimbursementPayoutProfile
- id
- user
- method
- zelle_email: maximum 254 characters
- check_payee_name: maximum 200 characters
- check_address_line_1: maximum 200 characters
- check_address_line_2: maximum 200 characters
- check_city: maximum 200 characters
- check_state: 2 characters
- check_postal_code: maximum 10 characters
```

There is no verification state or verification workflow.

### Zelle Profile

When `method = zelle`:

- `zelle_email` is required.
- The value is trimmed, lowercased, and validated as an email address.
- Check fields are blank.

The complete Zelle email is stored in the normal database and displayed to the
requester and administrator where needed.

It does not need to be masked on the reimbursement detail page. General
overview pages should show only the payment method because the complete email
is unnecessary there.

### Paper Check Profile

When `method = paper_check`:

- `check_payee_name` is required.
- `check_address_line_1` is required.
- `check_address_line_2` is optional.
- `check_city` is required.
- `check_state` is required.
- `check_postal_code` is required.
- `zelle_email` is blank.

Only United States mailing addresses are supported.

All check text fields are trimmed. State is stored as an uppercase two-letter
US state or territory code. ZIP code accepts either `12345` or `12345-6789`.
PO boxes, military addresses, and US territories are allowed. The website does
not verify that a mailing address actually exists.

The UI should explain that overseas or unusual reimbursements must be
coordinated separately outside the website.

A country field is unnecessary in V1 because the address is always a United
States address.

### Profile Permissions

- Users may create and update only their own payout profile.
- Administrators cannot create or edit another member's payout profile.
- Administrators update their own payout profile through the normal member UI.
- Changing methods clears fields belonging to the prior method.
- A payout profile is not required for normal login or registration.
- A valid payout profile is required to submit a reimbursement.

Profile saves and reimbursement submission should each validate a complete
payout profile. Rare overlapping edits from multiple browser tabs do not
require profile revisioning or a dedicated locking protocol in V1.

## Reimbursement Payout Snapshot

When a reimbursement is submitted, the current payout profile is copied into
an immutable one-to-one snapshot.

Suggested fields:

```text
ReimbursementPayoutSnapshot
- id
- reimbursement
- method
- zelle_email
- check_payee_name
- check_address_line_1
- check_address_line_2
- check_city
- check_state
- check_postal_code
```

Snapshot fields use the same maximum lengths and normalization rules as the
payout profile.

Rules:

- The snapshot belongs to exactly one reimbursement.
- The snapshot is created during submission.
- The snapshot is not directly editable.
- Its method-specific validation matches the payout-profile validation.
- Its information remains unchanged if the member later updates their profile.
- The complete email or mailing address is visible on the reimbursement detail
  page.
- Full payout information should not appear in broad overview tables, logs, or
  CSV exports.

## Returning A Reimbursement To Draft

When an administrator returns a reimbursement to draft or a member unsubmits
their own reimbursement:

- The existing payout snapshot is removed.
- The member may update their payout profile.
- The member may edit expenses, receipts, and requester notes.
- `submitted_at` is cleared.
- Resubmission copies the then-current payout profile into a new snapshot.
- A successful resubmission sets a new `submitted_at` value.

## Submitting A Reimbursement

Submission should occur in one database transaction.

The application must:

1. Confirm that the logged-in user owns the reimbursement.
2. Confirm that its current status is `draft`.
3. Confirm that at least one expense exists.
4. Validate every expense.
5. Confirm that every category belongs to the reimbursement's camp year.
6. Confirm that at least one receipt or explanation exists.
7. Validate all receipt records.
8. Confirm that the user has a valid payout profile.
9. Copy the payout profile into a payout snapshot.
10. Set `submitted_at`.
11. Change status to `submitted`.

If validation fails, the reimbursement remains a draft and no partial snapshot
or status change is saved.

If another action changes the reimbursement before submission completes, the
request makes no change and displays the current state with a clear conflict
message.

## Administrator Review

Administrators may review:

- Requester.
- Camp year.
- Human-readable reimbursement number.
- Expenses.
- Calculated total.
- Receipt images.
- Receipt PDFs.
- Receipt explanations.
- Requester notes.
- Payout snapshot.
- Current status.

Administrators may:

- Mark a submitted reimbursement paid.
- Reject a submitted reimbursement.
- Move a rejected reimbursement back to submitted.
- Return a submitted or rejected reimbursement to draft.
- Add or update payer notes.
- Manage camp-year expense categories.
- Add and delete expenses and receipt evidence on draft reimbursements.
- Submit a draft reimbursement for its requester when the requester already has
  valid payout information.

Administrators may not edit the member's expenses, receipts, requester notes, or
payout profile while the reimbursement is submitted, paid, or rejected.

On a draft reimbursement, admins may manage expenses and receipt evidence but
may not change the requester, requester notes, or payout profile. Admin
submission snapshots the requester's payout profile and records the admin in
`submitted_by`. Member submission records the requester in `submitted_by`.
Returning to draft clears `submitted_by`.

## Recording Payment

Payments are completed manually outside the website.

Because V1 supports exactly one full manual payment per reimbursement and does
not store a payment reference, a separate payment table is unnecessary.

Payment fields remain on `Reimbursement`:

```text
- status
- payer_notes
- paid_at
- paid_by
```

### Marking Paid

When an administrator marks a reimbursement paid, the application must:

1. Confirm the reimbursement is currently `submitted`.
2. Require the administrator to affirm that the displayed reimbursement has
   already been paid to the displayed requester using the displayed total and
   payout method.
3. Confirm an immutable payout snapshot exists.
4. Confirm at least one expense exists.
5. Recalculate the reimbursement total.
6. Confirm the total is greater than zero.
7. Set `status = paid`.
8. Set `paid_at` to the current time.
9. Set `paid_by` to the administrator.
10. Save payer notes, if supplied.

These changes occur in one transaction.

Manual payment occurs outside the website. If the reimbursement changes after
the administrator sends money but before Mark Paid succeeds, the website does
not attempt automatic reconciliation. It displays the current state and tells
the administrator and member to resolve the rare discrepancy directly.

There is no:

- Separate approval action.
- Payment reference.
- Check number.
- Zelle transaction ID.
- Verification record.
- Partial payment.
- Multiple-payment workflow.
- ACH account information.

## Payout Display

A Zelle reimbursement detail may show:

```text
Payment method: Zelle
Zelle email: person@example.com
```

A paper-check reimbursement detail may show:

```text
Payment method: Paper check
Payable to: Alice Smith
Address:
123 Example Street
Apartment 4
Seattle, WA 98101
```

The paper-check form should note that only United States addresses are
supported. Overseas reimbursement must be coordinated separately.

An administrator overview needs only summary information:

```text
2026-R-0001 | Alice Smith | $142.18 | Submitted | Zelle
```

Complete payout information belongs on the reimbursement detail page.

## Permissions Summary

### Member

A member may:

- Manage their own payout profile.
- Create their own reimbursement drafts.
- Edit and delete their own drafts.
- Manage expenses and receipts on their own drafts.
- Submit their own drafts.
- View their own reimbursements in every state.
- View payer notes on their reimbursements.

A member may not:

- Create a reimbursement for another user.
- Edit a reimbursement after submission.
- Change reimbursement status directly.
- View another member's reimbursements.
- Mark a reimbursement paid.

### Administrator

An administrator may:

- View all reimbursements.
- Review expenses, receipts, notes, and payout snapshots.
- Mark submitted reimbursements paid.
- Split selected expenses from a submitted reimbursement into a linked draft.
- Reject, move rejected reimbursements back to submitted, or return
  reimbursements to draft.
- Manage camp-year expense categories.
- Submit personal reimbursements through the normal member workflow.

An administrator may not:

- Submit a reimbursement for another member.
- Edit or submit a system-generated split draft as another member.
- Edit another member's payout profile.
- Edit another member's submitted expense data as if they were that member.

## Data Integrity Rules

The implementation should enforce:

- Unique human-readable reimbursement numbers.
- One requester and camp year per reimbursement.
- A split reimbursement has the same requester and camp year as its source.
- A source reimbursement is protected from deletion while split reimbursements
  reference it.
- At least one expense before submission.
- Positive expense amounts.
- Expense category and reimbursement camp-year agreement.
- At least one file receipt or explanation receipt before submission.
- Exactly one valid representation per receipt record.
- Exactly one payout snapshot for a submitted, paid, or rejected reimbursement.
- No payout snapshot for a draft reimbursement.
- Payout profile and snapshot fields consistent with their method.
- Only United States addresses for paper checks.
- Immutable member-controlled data after submission.
- `paid_at` and `paid_by` required when status is `paid`.
- `paid_at` and `paid_by` blank before payment.
- `rejected_at` and `rejected_by` required when status is `rejected`.
- `rejected_at` and `rejected_by` blank for all other statuses.
- Only submitted reimbursements may transition to paid.
- Only a reimbursement whose current status is draft may be deleted through the
  member UI.
- A draft may be deleted even if it was submitted or rejected previously.

## Future Extensions

Possible future additions include:

- Additional manual payout methods.
- International payment handling.
- Partial payments.
- Payment correction or reversal history.
- Dedicated financial audit events.
- Budget reporting by category.
- Receipt thumbnails or previews.
- Receipt retention policies.
- Reimbursement CSV/accounting exports.

These should be added only when needed rather than building a generic payment
or accounting platform in V1.

## Member Reimbursement UI

The member reimbursement interface has two primary pages:

```text
/<year>/reimbursements/
/<year>/reimbursements/<reimbursement_number>/
```

Example URLs:

```text
/2026/reimbursements/
/2026/reimbursements/2026-R-0001/
```

Both pages require an authenticated active member.

All reimbursement member and admin routes are owned by the dedicated
`reimbursements` Django app and included once from the project URL
configuration. The existing camp-year admin route remains in the custom admin
UI and calls reimbursement forms/services for category management.

Members may view and manage only their own reimbursements. Attempting to access
another member's reimbursement should return `404` rather than revealing that
it exists.

Navigation links are intentionally deferred until the feature is implemented
and can be evaluated with the rest of the member and admin navigation.

## Reimbursement Overview UI

URL:

```text
/<year>/reimbursements/
```

Example:

```text
/2026/reimbursements/
```

The page heading should include the camp year:

```text
2026 Reimbursements
```

The page begins with a table containing the logged-in member's reimbursements
for that camp year.

Recommended columns:

| Column | Content |
|---|---|
| Reimbursement | Human-readable reimbursement ID |
| Created | Date the draft was created |
| Submitted | Most recent submission date, or blank |
| Amount | Calculated total of all expenses |
| Status | Draft, Submitted, Paid, or Rejected |
| Action | Available member action |

The reimbursement ID links to the reimbursement detail page.

Rows should be ordered newest first by creation date, with the reimbursement
number as a deterministic secondary order.

### Overview Actions

For `draft` reimbursements:

```text
Edit
```

For `submitted` reimbursements:

```text
View
Unsubmit
```

For `paid` reimbursements:

```text
View
```

For `rejected` reimbursements:

```text
View
```

`Unsubmit` is a POST action and requires confirmation.

### Empty State

If the member has no reimbursements for the year, show:

```text
You do not have any reimbursements for 2026.
```

### Create Reimbursement

Below the reimbursement table, show a button:

```text
Create Reimbursement
```

Creation must use a CSRF-protected POST request rather than creating a draft
through a GET request.

The action should:

1. Confirm the camp year exists.
2. Create a draft for the logged-in member.
3. Allocate the next concurrency-safe human-readable ID.
4. Redirect to the new reimbursement detail page.

Example redirect:

```text
/2026/reimbursements/2026-R-0001/
```

## Reimbursement Detail UI

URL:

```text
/<year>/reimbursements/<reimbursement_number>/
```

Example:

```text
/2026/reimbursements/2026-R-0001/
```

The route must confirm:

- The camp year exists.
- The reimbursement number exists.
- The reimbursement belongs to that camp year.
- The reimbursement belongs to the logged-in member.

The page should use the existing member layout and card patterns.

Recommended section order:

1. Reimbursement summary.
2. Payment method.
3. Receipts and explanations.
4. Expenses.
5. Requester notes.
6. Submit or Unsubmit action.
7. Delete danger area for drafts only.

## Reimbursement Summary UI

The summary should show:

- Reimbursement number.
- Camp year.
- Current status.
- Created date.
- Submitted date when present.
- Paid date when present.
- Calculated total.
- Payer notes when present.

Example:

```text
Reimbursement: 2026-R-0001
Status: Draft
Created: September 13, 2026
Total: $142.18
```

Status should be visually clear without relying only on color.

## Editable And Read-Only States

A reimbursement is member-editable only when its status is:

```text
draft
```

Draft members may:

- Update their payment method.
- Add or delete receipt files.
- Add or delete receipt explanations.
- Add or delete expenses.
- Edit requester notes.
- Submit the reimbursement.
- Delete the reimbursement.

Submitted, paid, and rejected reimbursements are read-only to the member.

A submitted reimbursement may be unsubmitted by the member.

A rejected reimbursement remains read-only unless an administrator returns it
to draft.

A paid reimbursement remains read-only and cannot be unsubmitted or deleted.

## Payment Method UI

### Draft Display

For a draft reimbursement, the payment section shows an editable payout-profile
form.

If the member already has a payout profile, populate the form from that profile.

If no payout profile exists, show an empty form and require the member to
complete it before submission.

Supported choices:

```text
Zelle
Paper check
```

The section should explain:

> Your payment method will be remembered for future reimbursements.

Saving this form updates the member's reusable payout profile. It does not
create the immutable reimbursement payout snapshot until the reimbursement is
submitted.

### Zelle Form

Fields:

```text
Payment method: Zelle
Zelle email
```

The Zelle email is required and must be a valid email address.

### Paper Check Form

Fields:

```text
Payment method: Paper check
Payable to
Address line 1
Address line 2
City
State
ZIP code
```

Address line 2 is optional. All other fields are required.

The form should state:

> Paper checks can be mailed only to United States addresses. Contact the camp
> directly to arrange an overseas or unusual reimbursement.

### Read-Only Display

For submitted, paid, and rejected reimbursements, display the immutable payout
snapshot rather than the current profile.

Zelle example:

```text
Payment method: Zelle
Zelle email: person@example.com
```

Paper-check example:

```text
Payment method: Paper check
Payable to: Alice Smith
123 Example Street
Apartment 4
Seattle, WA 98101
```

The member cannot edit the payout snapshot directly.

## Receipts And Explanations UI

The section begins with the existing receipt evidence.

The section should explain:

> Receipts are best, and please upload any receipts you have. If some expenses
> were made and there are no receipts, please provide as much information as you
> can in an explanation.

Recommended columns or list fields:

| Field | Content |
|---|---|
| Type | Image, PDF, or Explanation |
| File | Original filename or blank |
| Notes / Explanation | Optional file notes or required no-file explanation |
| Action | View, Download, or Delete |

Images should link to the protected receipt view.

PDFs should use a protected download action.

Explanations should display as normal wrapped text.

### Draft Receipt Actions

Draft reimbursements show two separate creation forms.

Upload form:

```text
Upload Receipt
- File
- Notes / description, optional
- Upload Receipt
```

Explanation form:

```text
Add Explanation Without a File
- Explanation
- Add Explanation
```

Existing receipt records include a Delete action while the reimbursement is a
draft.

After adding or deleting receipt evidence, redirect using POST/redirect/GET:

```text
/2026/reimbursements/2026-R-0001/#receipts
```

### Read-Only Receipt Display

Submitted, paid, and rejected reimbursements show the same evidence without
upload, explanation-creation, or deletion controls.

## Expenses UI

The expenses section begins with a table.

The section should explain:

> A reimbursement is made up of categorized expenses. Please break out the
> total reimbursement into the appropriate categories so we can better track
> camp spending.

Recommended columns:

| Column | Content |
|---|---|
| Category | Camp-year reimbursement category |
| Description | Required expense description |
| Amount | Formatted USD amount |
| Action | Delete for drafts only |

Expenses should use a deterministic database order such as ascending expense
ID. There is no member-controlled display order.

The table footer displays the calculated total:

```text
Total: $142.18
```

### Draft Expenses

Draft reimbursements include a Delete action for each expense.

There is no expense-edit workflow in V1. To correct an expense, the member
deletes it and adds a replacement.

Below the table, show:

```text
Add Expense
- Name
- Category
- Description
- Amount
- Add Expense
```

The category selector includes only reimbursement categories belonging to the
reimbursement's camp year.

Category, description, and amount are required. The amount
must be greater than zero.

After adding or deleting an expense, redirect using:

```text
/2026/reimbursements/2026-R-0001/#expenses
```

This returns the browser with the expense table at the top of the viewport.

### Read-Only Expenses

Submitted, paid, and rejected reimbursements show the expense table and total
without:

- Delete actions.
- Add Expense form.
- Editable fields.

If a submitted expense must be corrected, the member first unsubmits the
reimbursement, then deletes and re-adds the expense.

## Requester Notes UI

Draft reimbursements show an editable requester-notes form.

Submitted, paid, and rejected reimbursements show requester notes as read-only
text.

Requester notes provide general context. A missing receipt should be
represented with a dedicated explanation receipt.

After saving notes, redirect to:

```text
/2026/reimbursements/2026-R-0001/#requester-notes
```

## Submitting A Reimbursement UI

A draft detail page includes:

```text
Submit Reimbursement
```

The action should appear after the editable payment, receipt, expense, and
requester-note sections.

Help text should explain:

> Submitting locks this reimbursement for review. You may unsubmit it until the
> camp marks it paid or rejected.

Submission is a CSRF-protected POST action.

Before submission, validate:

- The reimbursement still belongs to the logged-in member.
- The reimbursement remains a draft.
- At least one expense exists.
- All expenses are valid.
- The total is greater than zero.
- Every category belongs to the reimbursement's camp year.
- At least one image, PDF, or explanation receipt exists.
- The member's payout profile is complete and valid.

On success:

1. Copy the current payout profile into the reimbursement payout snapshot.
2. Set `submitted_at` to the current time.
3. Set status to `submitted`.
4. Redirect back to the read-only detail page.
5. Show a success message.

All submission changes should occur in one database transaction.

If validation fails:

- Keep the reimbursement in draft.
- Do not create a partial payout snapshot.
- Show a validation summary.
- Link validation errors to the relevant page sections.

## Unsubmitting A Reimbursement UI

A submitted reimbursement includes:

```text
Unsubmit Reimbursement
```

The action should be available from:

- The reimbursement overview table.
- The reimbursement detail page.

Unsubmit is a CSRF-protected POST action and requires confirmation.

Help text should explain:

> Unsubmitting returns this reimbursement to draft and removes it from the
> payment queue.

On success:

1. Lock the reimbursement row.
2. Confirm it still belongs to the logged-in member.
3. Confirm its status is still `submitted`.
4. Set status to `draft`.
5. Set `submitted_at` to blank.
6. Delete the immutable payout snapshot.
7. Redirect to the editable detail page.
8. Show a success message.

If an administrator marks the reimbursement paid or rejected before the
unsubmit transaction obtains its lock, unsubmit must fail safely without
changing the new state.

## Deleting A Reimbursement UI

Only a draft reimbursement can be deleted.

The delete action should appear at the bottom of the draft detail page in a
clearly marked danger area.

Submitted, paid, and rejected reimbursements must not show a delete action.

The confirmation should identify the reimbursement and explain that deletion
also removes:

- All expenses.
- All receipt explanations.
- All uploaded receipt files.
- The reimbursement itself.

The confirmation requires the member to type:

```text
delete
```

Deletion is a CSRF-protected POST action.

Before deleting:

1. Lock the reimbursement.
2. Confirm the logged-in member owns it.
3. Confirm it remains a draft.
4. Determine which private receipt files must be removed.

After successful deletion:

```text
redirect to /2026/reimbursements/
```

The page should show a success message.

Database and filesystem cleanup must be failure-aware so deletion does not
leave a live database record pointing to a deliberately deleted file. Failed
best-effort file deletion may leave an unreferenced private file.

## Reimbursement Form And Redirect Behavior

All state-changing actions use POST requests with CSRF protection.

Successful form submissions use POST/redirect/GET.

Recommended fragments:

```text
#payment-method
#receipts
#expenses
#requester-notes
#submit-reimbursement
#delete-reimbursement
```

Validation failures render the same page with:

- Field-level errors next to their fields.
- Non-field errors above the relevant form.
- A page-level summary when submission fails because multiple sections are
  incomplete.

## Reimbursement Responsive Behavior

The overview and expense tables may use horizontal scrolling on narrow screens.

Buttons and form controls should remain large enough for touch use.

Payment, receipt, expense, notes, submission, and deletion sections should
remain in the same logical order on desktop and mobile.

JavaScript may improve file selection or confirmation behavior, but all
reimbursement creation, editing, submission, unsubmission, and deletion
workflows must work without JavaScript.

## Reimbursement Categories Admin UI

Reimbursement expense categories are managed from the existing camp-year edit
page.

URL:

```text
/admin/camp/<year>/
```

Example:

```text
/admin/camp/2026/
```

The page should include a card named:

```text
Reimbursement Categories
```

Recommended card order:

1. Dashboard Setup.
2. Reimbursement Categories.
3. Tax Tiers.
4. Tax Add-ons.
5. Tax Overrides.

The card should use this fragment:

```text
#reimbursement-categories
```

Create and delete actions should return to this fragment.

### Category Table

The card begins with a table of categories for the selected camp year.

Recommended columns:

| Category | Usage | Action |
|---|---:|---|
| Food | 4 reimbursements | In use |
| Fuel | 0 reimbursements | Delete |
| Supplies | 2 reimbursements | In use |

Rules:

- Categories are always sorted alphabetically by name, ignoring case.
- Database ID is the deterministic secondary ordering value.
- Usage is the number of distinct reimbursements containing an expense in the
  category.
- A category is considered used when any `ReimbursementExpense` references it,
  including an expense on a draft reimbursement.
- The table has no edit or rename action.
- An unused misspelled category is corrected by deleting it and creating a new
  category.
- A category that has already been used retains its original spelling as part
  of the reimbursement history.

If no categories exist, show:

```text
No reimbursement categories are configured for 2026.
```

### Delete Category

An unused category has a Delete action in its table row.

A used category does not have an active Delete action and instead displays:

```text
In use
```

Delete is a CSRF-protected POST action.

The server must:

1. Confirm that the category belongs to the camp year in the route.
2. Confirm that no reimbursement expense references the category.
3. Delete the category.
4. Redirect to the category-card fragment.
5. Show a success message.

The expense-to-category relationship should use database protection as the
final concurrency safeguard. If an expense begins using the category between
the initial page render and the delete request, deletion must fail with a normal
admin error rather than a server error.

Example redirect:

```text
/admin/camp/2026/#reimbursement-categories
```

### Add Category

Below the table, show a small create form:

```text
Add Reimbursement Category

Category name
[                         ]

Add Category
```

The form contains only the category name. Category descriptions, edit forms,
and ordering controls are not part of V1.

Validation rules:

- Trim leading and trailing whitespace.
- Reject an empty name.
- Limit the name to 120 characters.
- Support Unicode.
- Require the name to be unique within the camp year, ignoring case.
- Treat `Food`, `food`, and ` food ` as the same category name.
- Allow the same category name in different camp years.

On success, the server should:

1. Create the category for the camp year in the route.
2. Redirect to the category-card fragment.
3. Show a success message.

On validation failure, render the same camp-year edit page with field-level
errors and return the browser to `#reimbursement-categories`.

### Category Permissions

- The card and all category actions require an authenticated active admin.
- Members cannot access category administration.
- Category IDs submitted by the form must be scoped to the camp year in the
  route.
- A category from another camp year cannot be deleted through the current
  camp-year page.

### Category Progressive Enhancement

Category administration must work without JavaScript.

No client-side sorting, drag-and-drop ordering, inline rename behavior, or
modal-only workflow is needed.

### Category Admin Tests

Tests should cover:

- Anonymous access redirects to login.
- An active non-admin receives `403`.
- An admin can load the reimbursement category card.
- Categories from the selected year are shown.
- Categories from other years are not shown.
- Categories are sorted alphabetically without regard to case.
- The empty state is shown when no categories exist.
- An admin can create a valid category.
- Names are trimmed before saving.
- Blank names are rejected.
- Names longer than 120 characters are rejected.
- Case-insensitive duplicates within one year are rejected.
- The same category name can be used in different years.
- An unused category can be deleted.
- A category used by a draft expense cannot be deleted.
- A category used by a submitted, paid, or rejected reimbursement cannot be
  deleted.
- A category from another year cannot be deleted through the current route.
- A concurrent protected-delete failure produces a useful admin error.
- Create and delete success redirects include `#reimbursement-categories`.
- The card does not expose category descriptions, rename controls, or ordering
  controls.

## Annual Reimbursements Admin UI

The annual reimbursements admin page combines category reporting, payment
preparation, and submitted, paid, and rejected reimbursement records for one
camp year.

Routes:

```text
/admin/reimbursements/
/admin/<year>/reimbursements/
```

Examples:

```text
/admin/reimbursements/
/admin/2026/reimbursements/
```

Both routes require an authenticated active admin.

### Current-Year Redirect

`/admin/reimbursements/` redirects to the maximum configured camp year.

Example:

```text
/admin/reimbursements/
-> /admin/2026/reimbursements/
```

When a valid `year` query parameter is supplied, the redirect route sends the
admin to that year's canonical page instead:

```text
/admin/reimbursements/?year=2025
-> /admin/2025/reimbursements/
```

Exactly one four-digit configured camp-year value is accepted. Missing uses the
latest year; duplicate, malformed, signed, nonnumeric, or unknown supplied
values return `404`. If no camp year exists, the redirect route shows a clear
no-year state rather than failing.

## Annual Reimbursements Header

The page title includes the selected year:

```text
Reimbursements 2026
```

The year selector appears to the right of the title on wide screens and wraps
below the title on small screens.

### Year Selector

The year selector is a normal GET form:

```text
[ 2026 v ] [ View Year ]
```

The select lists every configured camp year, newest first, and marks the
current page's year as selected.

The form submits to `/admin/reimbursements/` with a `year` query parameter. It
therefore works without JavaScript.

JavaScript may progressively submit the form as soon as the selection changes.
Without JavaScript, the administrator selects a year and clicks `View Year`.
A separate no-JavaScript list of year links is unnecessary because the select
and button remain fully functional.

## Expenses By Category Card

The first card is named:

```text
Expenses by Category
```

The table reports dollar totals rather than itemized expense lists.

Recommended columns:

| Category | Submitted | Paid |
|---|---:|---:|
| Food | $425.18 | $1,842.57 |
| Fuel | $0.00 | $318.44 |
| Supplies | $122.13 | $957.22 |
| Total | $547.31 | $3,118.23 |

Rules:

- Each normal row represents one reimbursement expense category.
- Submitted is the sum of expense amounts in `submitted` reimbursements.
- Paid is the sum of expense amounts in `paid` reimbursements.
- Draft and rejected reimbursements are excluded.
- Show a category when either its submitted or paid total is greater than zero.
- Categories are sorted alphabetically by name, ignoring case.
- Include a final row containing the submitted and paid grand totals.
- All amounts are calculated from `ReimbursementExpense.amount_cents`.
- If no submitted or paid expenses exist, show a clear empty state.

## Paid Expenses By Person Card

The second card is named:

```text
Paid Expenses by Person
```

Recommended table:

| Member | Category | Amount Paid |
|---|---|---:|
| Alice Smith | Food | $324.18 |
| Alice Smith | Supplies | $82.15 |
| Bob Jones | Fuel | $122.35 |

Rules:

- Include only expenses belonging to `paid` reimbursements.
- Each row represents one requester and category combination.
- Sum amounts across all paid reimbursements for that requester and category.
- Order by requester last name, first name, email, and then category name.
- Use the requester's email as a deterministic tie-breaker and for defensive
  disambiguation when needed.
- Display the requester's full name when nonblank and otherwise display email.
- Include a final grand-total row.
- If no paid expenses exist, show a clear empty state.

### Copy Paid Expenses To Clipboard

Below the table, show:

```text
Copy to Clipboard
```

Copying directly to the clipboard requires JavaScript and a secure browser
context such as HTTPS or localhost.

The button should write both clipboard formats:

```text
text/html
text/plain
```

`text/html` contains the table as HTML. `text/plain` contains tab-separated
columns with newline-separated rows. Providing both formats allows reliable
pasting into common spreadsheet applications while retaining a plain-text
fallback.

Rules:

- Clipboard writing occurs only from the administrator's button click.
- Show a success message after copying.
- Show a useful error if clipboard access is unavailable or denied.
- Neutralize spreadsheet formula prefixes in every text cell copied to the
  clipboard.
- The visible table remains fully usable without JavaScript.

Safe spreadsheet text uses one rule for HTML clipboard text, TSV, and CSV:
prefix a single apostrophe when a text cell's first non-whitespace/control
character is `=`, `+`, `-`, or `@`.

Because automatic clipboard access is impossible without JavaScript, provide a
normal CSV download as the no-JavaScript fallback:

```text
/admin/2026/reimbursements/paid-expenses.csv
```

Recommended controls when JavaScript is available:

```text
[ Copy to Clipboard ] [ Download CSV ]
```

The CSV contains the same columns, rows, ordering, and totals as the visible
table. It must apply the same spreadsheet formula neutralization.

The final total row is represented consistently in all formats:

```text
Member: Total
Category: blank
Amount Paid: grand total
```

## Submitted Reimbursements Admin Card

The third card is named:

```text
Submitted Reimbursements
```

Recommended table:

| Submitted | Member | Total | Action |
|---|---|---:|---|
| September 10, 2026 | Alice Smith | $142.18 | View |
| September 12, 2026 | Bob Jones | $87.42 | View |

Rules:

- Include only `submitted` reimbursements for the selected camp year.
- Order by `submitted_at` ascending so the oldest request appears first.
- Use reimbursement number as a deterministic secondary ordering value.
- Display the requester's name and email when needed for disambiguation.
- Calculate total from the reimbursement's expense rows.
- The View action opens the annual admin reimbursement detail page.
- Show a clear empty state when no reimbursements are awaiting payment.

Example View target:

```text
/admin/2026/reimbursements/2026-R-0001/
```

## Paid Reimbursements Admin Card

The fourth card, between Submitted Reimbursements and Rejected Reimbursements,
is named:

```text
Paid Reimbursements
```

Recommended table:

| Paid | Member | Total | Method | Action |
|---|---|---:|---|---|
| September 8, 2026 | Alice Smith | $142.18 | Zelle | View |

Rules:

- Include only `paid` reimbursements for the selected camp year.
- Order by `paid_at` descending, with reimbursement number as a deterministic
  secondary ordering value.
- Calculate total from expense rows.
- Display the payout method from the immutable reimbursement payout snapshot.
- Do not display the full Zelle email or mailing address in this overview.
- The View action opens the annual admin reimbursement detail page.
- Show a clear empty state when no paid reimbursements exist.

Example View target:

```text
/admin/2026/reimbursements/2026-R-0001/
```

## Rejected Reimbursements Admin Card

The fifth card is named:

```text
Rejected Reimbursements
```

Recommended table:

| Submitted | Member | Total | Rejected | Actions |
|---|---|---:|---|---|
| September 5, 2026 | Alice Smith | $42.18 | September 8, 2026 | View, Move to Submitted, Move to Draft |

Rules:

- Include only `rejected` reimbursements for the selected camp year.
- Order by `rejected_at` descending, with reimbursement number as a
  deterministic secondary ordering value.
- Preserve and display the reimbursement's original `submitted_at`.
- Display the requester's name and email when needed for disambiguation.
- Calculate total from expense rows.
- Include View, Move to Submitted, and Move to Draft actions.
- Show a clear empty state when no rejected reimbursements exist.

### View Rejected Reimbursement

The View action opens:

```text
/admin/2026/reimbursements/2026-R-0001/
```

### Move Rejected To Submitted

Move to Submitted is a CSRF-protected POST action.

The server must:

1. Lock the reimbursement row.
2. Confirm it belongs to the camp year in the route.
3. Confirm its status is still `rejected`.
4. Set status to `submitted`.
5. Preserve the original `submitted_at`.
6. Preserve the immutable payout snapshot.
7. Set `rejected_at` to blank.
8. Set `rejected_by` to blank.
9. Redirect back to the selected year's annual admin page.
10. Show a success message.

This action represents undoing a rejection without returning the reimbursement
to member editing.

### Move Rejected To Draft

Move to Draft is a CSRF-protected POST action and requires confirmation because
it restores member editing and removes the submitted payout snapshot.

The server must:

1. Lock the reimbursement row.
2. Confirm it belongs to the camp year in the route.
3. Confirm its status is still `rejected`.
4. Set status to `draft`.
5. Set `submitted_at` to blank.
6. Set `rejected_at` to blank.
7. Set `rejected_by` to blank.
8. Delete the immutable payout snapshot.
9. Redirect back to the selected year's annual admin page.
10. Show a success message.

The member can then edit and resubmit the reimbursement through the normal
member workflow.

## Rejection Metadata

The annual admin page requires these reimbursement fields:

```text
Reimbursement
- rejected_at
- rejected_by
```

When an administrator rejects a submitted reimbursement, the application must
atomically:

1. Confirm the reimbursement is still `submitted`.
2. Set status to `rejected`.
3. Set `rejected_at` to the current time.
4. Set `rejected_by` to the administrator.
5. Preserve `submitted_at`.
6. Preserve the payout snapshot.
7. Save payer notes, if supplied.

When a reimbursement leaves the rejected state, both rejection fields are
cleared. V1 preserves only the current rejection metadata, not a complete state
history.

## Annual Reimbursements Admin Responsive Behavior

- The page title and year selector wrap cleanly on small screens.
- Reporting and reimbursement tables may scroll horizontally on narrow
  screens.
- State-changing controls remain normal buttons with accessible labels.
- The year selector and CSV download work without JavaScript.
- Reporting totals and all state transitions are calculated and enforced by the
  server.
- JavaScript is required only for automatic year selection and clipboard
  convenience.

## Annual Reimbursements Admin Tests

Tests should cover:

- Anonymous users are redirected to login.
- Active non-admin members receive `403`.
- Admins can load the annual reimbursements page.
- `/admin/reimbursements/` redirects to the maximum configured camp year.
- A valid `year` query parameter redirects to that year's canonical page.
- Unknown years return `404`.
- The no-year state renders without failing.
- The year selector lists all configured years newest first.
- The year selector works through a normal GET without JavaScript.
- Category reporting includes submitted and paid amounts only.
- Draft and rejected expenses are excluded from category reporting.
- Zero-total category rows are omitted.
- Category rows are alphabetical and include correct grand totals.
- Paid-by-person rows group by requester and category.
- Paid-by-person rows exclude non-paid reimbursements.
- Paid-by-person ordering and totals are correct.
- Clipboard source data contains equivalent HTML and TSV representations.
- Spreadsheet formula prefixes are neutralized.
- CSV output matches the visible paid-by-person report.
- Submitted reimbursements are ordered oldest first.
- Submitted totals and View links are correct.
- Paid reimbursements appear between submitted and rejected cards.
- Paid reimbursements show method but not complete payout details.
- Paid reimbursements are ordered by newest payment first.
- Rejected reimbursements show submitted and rejected dates.
- Rejected reimbursements provide View, Move to Submitted, and Move to Draft.
- Moving rejected to submitted preserves submission date and payout snapshot.
- Moving rejected to submitted clears rejection metadata.
- Moving rejected to draft clears submission and rejection dates.
- Moving rejected to draft deletes the payout snapshot and restores member
  editing.
- State actions reject wrong-year reimbursement IDs.
- Concurrent state changes are serialized and fail safely.
- Rejection sets `rejected_at` and `rejected_by` atomically.
- All reporting and state-changing behavior works without JavaScript except the
  clipboard action.

## Reimbursement Admin Detail UI

The admin reimbursement detail page displays one reimbursement and provides
the actions available for its current state.

URL:

```text
/admin/<year>/reimbursements/<reimbursement_number>/
```

Example:

```text
/admin/2026/reimbursements/2026-R-0001/
```

The route must confirm:

- The camp year exists.
- The reimbursement exists.
- The reimbursement belongs to the camp year in the route.
- The logged-in user is an authenticated active admin.

An unknown year, reimbursement number, or mismatched year/reimbursement pair
returns `404`.

## Reimbursement Admin Detail Title

For a submitted reimbursement, the title is:

```text
2026 Reimbursement to Fred Smith
```

Use the requester's full name. If the account lacks a usable full name, use the
requester's email as a defensive fallback.

The submitted-state page uses this card order:

1. Summary.
2. Notes.
3. Receipts and Explanations.
4. Split Expenses.
5. Payment Method.
6. Actions.

Other states use the same read-only information cards but change the Split
Expenses and Actions cards as described below.

## Reimbursement Admin Summary Card

The first card shows four lines:

```text
Submitted: September 10, 2026
Status: Submitted
Total: $142.18
Categories: Food, Fuel, Supplies
```

Rules:

- Display `submitted_at` in the configured local timezone.
- Display the current reimbursement status.
- Calculate total from all current expense rows.
- Display each distinct expense category once.
- Sort category names alphabetically, ignoring case.
- Use a comma-separated text list for categories.
- Do not trust a posted total or category list.

State-specific dates are shown as follows:

- Draft: created date.
- Submitted: submitted date.
- Paid: submitted date and paid date.
- Rejected: submitted date and rejected date.

## Reimbursement Admin Notes Card

The second card shows:

- Requester notes as read-only text.
- Payer/admin notes in an editable textarea.
- A `Save Notes` button.

Payer notes remain visible to the requester.

Saving notes uses a CSRF-protected POST and POST/redirect/GET back to the same
page:

```text
/admin/2026/reimbursements/2026-R-0001/#notes
```

This technically refreshes through a same-page redirect but does not navigate
the administrator away from the reimbursement. It prevents accidental form
resubmission and does not require JavaScript.

### Shared Notes And Action Form

The payer-notes textarea may belong to one form whose buttons appear in
different cards using the HTML `form` attribute.

Supported submitted-state actions for that form are:

```text
Save Notes
Pay
Reject
```

This allows Pay and Reject to save the current textarea value without requiring
the administrator to click Save Notes first. It also allows rejection to
validate the currently entered notes instead of only previously stored notes.

## Reimbursement Admin Receipts And Explanations Card

The third card lists every receipt and explanation attached to the
reimbursement.

File receipt links display the original uploaded filename even though the
private stored filename is UUID-based.

Examples:

```text
costco-receipt.pdf
gas-station.jpg
```

Rules:

- Image links use the protected authenticated receipt route.
- PDF links use the protected authenticated download route.
- Explanations display directly as wrapped text.
- UUID storage names and filesystem paths do not appear in the UI.
- Receipt access remains restricted to the requester and active admins.
- The admin detail page does not edit or delete submitted receipt evidence.

## Split Expenses Card

The Split Expenses card appears only when the reimbursement is `submitted`.

It does not appear for draft, paid, or rejected reimbursements.

Recommended table:

| Select | Category | Description | Amount |
|---|---|---|---:|
| checkbox | Food | Dinner supplies | $82.14 |
| checkbox | Fuel | Truck refill | $60.04 |

Below the table, show:

```text
Notes
[                                                     ]

Split
```

The notes field contains the administrator's reason that the selected expenses
need more information. Notes are required.

### Split Validation

The server must confirm:

- The source reimbursement is still `submitted`.
- At least one expense is selected.
- At least one expense remains on the source reimbursement.
- Every selected expense belongs to the source reimbursement.
- Split notes are non-empty.
- The source reimbursement still has a payout snapshot.

If every expense needs more information, the administrator should use Move to
Draft rather than Split.

### Split Transaction

The split operation must:

1. Lock the source reimbursement.
2. Revalidate its status and selected expense IDs.
3. Allocate a new concurrency-safe human-readable reimbursement number.
4. Create a new draft for the same requester and camp year.
5. Set the new reimbursement's `split_from` value to the source reimbursement.
6. Move the selected expense rows to the new draft.
7. Copy the source reimbursement's requester notes to the new draft.
8. Set the new draft's payer notes exactly to the required split rationale. Do
   not copy the source reimbursement's payer notes.
9. Copy every receipt explanation to the new draft.
10. Copy every receipt file to an independent private file with a new UUID
    storage name.
11. Preserve every original receipt and explanation on the source
    reimbursement.
12. Leave the source reimbursement in `submitted` state.
13. Recalculate the source reimbursement total from its remaining expenses.
14. Remain on the source reimbursement detail page.
15. Show a success message linking to the new draft.

Example success message:

```text
Selected expenses were moved to draft reimbursement 2026-R-0002.
```

The source page should also display links to reimbursements created by prior
splits. A split draft should display a link back to its source reimbursement.

### Split Draft State

The newly created reimbursement has:

```text
status = draft
created_at = now
submitted_at = blank
paid_at = blank
paid_by = blank
rejected_at = blank
rejected_by = blank
payout snapshot = none
split_from = source reimbursement
```

The split action is a narrow system-generated-draft exception. The admin does
not edit or submit the new reimbursement as the requester. The requester must
review, edit, and submit it through the normal member workflow.

### Copied Receipt Evidence

Copied receipt records retain:

- Original filename.
- Receipt type.
- Content type.
- File size.
- Explanation text, when applicable.

Each copied file receives an independent UUID storage path. Do not share one
physical file between reimbursement records. Independent copies avoid
reference-counting and deletion ambiguity.

Database changes must be atomic. Receipt files are copied before the related
database changes commit, and normal failures attempt best-effort cleanup. A
process crash may leave unreferenced copied files; this is acceptable in V1.

## Reimbursement Admin Payment Method Card

For submitted, paid, and rejected reimbursements, show the immutable payout
snapshot.

Zelle example:

```text
Payment method: Zelle
Zelle email: fred@example.com
```

Paper-check example:

```text
Payment method: Paper check
Payable to: Fred Smith
123 Example Street
Seattle, WA 98101
```

The administrator cannot edit the payout snapshot.

A draft reimbursement has no payout snapshot. Its admin page does not display
the member's current payout profile. It shows:

```text
No payout snapshot exists. Payment information will be captured when the member
submits this reimbursement.
```

## Reimbursement Admin Actions Card

For a submitted reimbursement, the final card contains:

```text
[ Pay ] [ Move to Draft ] [ Reject ]
```

Recommended visual treatment:

- Pay uses the primary or success action style.
- Move to Draft uses secondary action styling.
- Reject uses the existing red danger-action styling.

Every action is a CSRF-protected POST. Each action locks the reimbursement and
rechecks its current status before making changes.

If another action already changed the reimbursement, the losing action makes no
changes and displays the current state. Rare real-world payment discrepancies
are resolved directly by the people involved.

After Pay, Move to Draft, or Reject succeeds, redirect to:

```text
/admin/2026/reimbursements/#SubmittedReimbursements
```

The `SubmittedReimbursements` fragment must be present on the annual page.

### Pay Confirmation

The Actions card contains a confirmation box before the Pay button.

Zelle example:

```text
Confirm Payment

Payee: Fred Smith
Total: $142.18
Method: Zelle
Zelle email: fred@example.com

[ ] I confirm that this reimbursement has been paid.

[ Mark Paid ]
```

Paper-check example:

```text
Confirm Payment

Payee: Fred Smith
Total: $142.18
Method: Paper check
Mail to:
Fred Smith
123 Example Street
Seattle, WA 98101

[ ] I confirm that this reimbursement has been paid.

[ Mark Paid ]
```

The server must reload the payout snapshot and recalculate the total. It must
not trust displayed, hidden, or posted payment details.

On success, the same transaction saves any submitted payer notes, sets status
to `paid`, sets `paid_at`, and records `paid_by`.

### Move Submitted To Draft

Move to Draft must:

1. Lock the reimbursement.
2. Confirm it remains `submitted`.
3. Set status to `draft`.
4. Set `submitted_at` to blank.
5. Delete the payout snapshot.
6. Preserve expenses, receipts, requester notes, and payer notes.
7. Restore member editing.

### Reject Submitted Reimbursement

Payer notes are optional when rejecting. On success, one transaction must:

1. Confirm the reimbursement remains `submitted`.
2. Save the submitted payer notes, including blank notes.
3. Set status to `rejected`.
4. Set `rejected_at` to the current time.
5. Set `rejected_by` to the administrator.
6. Preserve `submitted_at`.
7. Preserve the payout snapshot, expenses, and receipts.

## Admin Detail Actions By State

| State | Split Expenses | Available Actions |
|---|---|---|
| Draft | Hidden | None |
| Submitted | Shown | Pay, Move to Draft, Reject |
| Paid | Hidden | None |
| Rejected | Hidden | Move to Submitted, Move to Draft |

### Move Rejected To Submitted From Detail

The rejected detail page includes Move to Submitted as well as Move to Draft.

Move to Submitted must:

- Preserve `submitted_at`.
- Preserve the payout snapshot.
- Preserve expenses, receipts, requester notes, and payer notes.
- Clear `rejected_at`.
- Clear `rejected_by`.
- Set status to `submitted`.
- Redirect to the annual page's `#SubmittedReimbursements` fragment.

### Move Rejected To Draft From Detail

Move to Draft must:

- Set status to `draft`.
- Clear `submitted_at`.
- Clear `rejected_at`.
- Clear `rejected_by`.
- Delete the payout snapshot.
- Preserve expenses, receipts, requester notes, and payer notes.
- Restore member editing.

## Reimbursement Admin Detail Responsive Behavior

- Cards retain the same logical order on desktop and mobile.
- Expense and receipt tables may scroll horizontally on narrow screens.
- Confirmation information remains adjacent to the action it confirms.
- Action buttons remain visually distinct and keyboard accessible.
- Notes saving, splitting, payment, rejection, and state changes work without
  JavaScript.
- JavaScript may improve confirmation or feedback but is not authoritative.

## Reimbursement Admin Detail Tests

Tests should cover:

- Anonymous access redirects to login.
- Active non-admin members receive `403`.
- Unknown years and reimbursement numbers return `404`.
- A reimbursement from another year is not accessible through the route.
- The title uses the requester's full name with email fallback.
- Summary values, distinct category names, ordering, and total are correct.
- Requester notes are read-only.
- Payer notes can be saved with a same-page redirect to `#notes`.
- Receipt links display original filenames rather than UUID storage names.
- Receipt links remain protected by requester/admin authorization.
- Explanation receipts display as text.
- Split Expenses appears only for submitted reimbursements.
- Split requires at least one selected expense and non-empty notes.
- Split rejects expense IDs belonging to another reimbursement.
- Split refuses to move every expense from the source.
- Split allocates a new human-readable number safely.
- Split creates a draft for the same requester and camp year.
- Split sets `split_from` to the source reimbursement.
- Split moves only the selected expenses.
- Split copies requester notes and stores the rationale in payer notes.
- Split copies every explanation receipt.
- Split creates independent copies of every private receipt file.
- Split leaves the source submitted with its original receipt evidence.
- Split remains on the source page and links to the new draft.
- Split failures leave database and private file state unchanged or cleaned up.
- Source reimbursement deletion is protected while split children exist.
- Payment Method displays the immutable payout snapshot.
- Pay is an explicit admin action and does not require a separate confirmation
  checkbox.
- Pay recalculates total and reloads payout information server-side.
- Pay saves payer notes and sets status, `paid_at`, and `paid_by` atomically.
- Move to Draft clears submission date and payout snapshot.
- Reject allows empty payer notes.
- Reject saves notes and rejection metadata atomically.
- Draft and paid reimbursements show no Split or Actions card.
- Rejected reimbursements show Move to Submitted and Move to Draft only.
- Moving rejected to submitted preserves the original submission date and
  payout snapshot.
- Moving rejected to draft clears dates and deletes the payout snapshot.
- Concurrent split, pay, reject, unsubmit, and move-to-draft actions fail safely
  after one operation changes the locked status.

## Focused Reimbursement Test Plan

The test suite should protect normal user workflows, private receipt access,
money calculations, and state changes. It should not attempt to turn this small
community workflow into a general accounting or audit system.

Recommended organization:

```text
reimbursements/tests/
  test_models.py
  test_forms.py
  test_member_views.py
  test_admin_views.py
  test_receipts.py
  test_reports.py
  test_services.py
```

Use the existing pytest and pytest-django conventions. Use `tmp_path` for every
receipt-file test. A small PostgreSQL-only test module may be added for
human-readable number allocation and competing state transitions if the chosen
implementation depends on row locking.

The following risks are explicitly accepted and do not require additional
models or exhaustive tests:

- External manual payment cannot be atomic with website state.
- Split does not preserve previous expense versions.
- Draft deletion can erase a previous submission negotiation.
- A crash may leave unreferenced private receipt files.
- Exceptional corrections may be made directly in the database.
- The reimbursement feature includes receipts in backup but does not complete
  the repository's restore system.

## Reimbursement Model Tests

Test:

- New reimbursement defaults to `draft`.
- Requester and camp year are required.
- Status choices are exactly draft, submitted, paid, and rejected.
- Human-readable number is unique and immutable.
- Number format is `YYYY-R-NNNN`.
- Sequence is scoped by camp year.
- Derived total sums all expense cents.
- No posted or stored total overrides the calculated total.
- Paid requires `paid_at` and `paid_by`.
- Non-paid states require paid fields to be blank.
- Rejected requires `rejected_at` and `rejected_by`.
- Non-rejected states require rejection fields to be blank.
- Draft has no payout snapshot.
- Submitted, paid, and rejected have one payout snapshot.
- Only a current draft can be deleted through the member UI.

## Split Link Tests

Test that a split child references its source, uses the same requester and camp
year, and displays navigation links in both directions while both records
exist. The link is for convenience, not permanent audit history.

## Expense Model And Form Tests

Test:

- Category, name, and amount are required.
- Description is optional.
- Name is trimmed and not whitespace-only.
- Amount is stored as integer cents.
- Amount must be greater than zero.
- Negative, zero, malformed, non-finite, overprecision, and values above
  $1,000,000.00 fail.
- Category must belong to the reimbursement year.
- Category deletion is protected.
- Expenses order deterministically by ID.
- There is no expense edit workflow, date, display order, receipt relation, or
  audit timestamp.
- Dollar values such as `0.01` convert exactly to integer cents.
- Category choices contain only categories for the reimbursement year.

## Category Model Tests

Test:

- Name is required, trimmed, Unicode-capable, and at most 120 characters.
- Names are unique per year after normalization.
- `Food`, `food`, and ` food ` conflict.
- The same normalized name is allowed in different years.
- Categories sort case-insensitively by name and then ID.
- Category has no description or display order.
- Category cannot be renamed through the supported service.
- Used categories are protected in every reimbursement state.
- Database uniqueness is tested directly as well as through the form.

## Receipt Model Tests

Test each valid representation:

| Type | Required | Must Be Blank |
|---|---|---|
| Image | File metadata | Explanation |
| PDF | File metadata | Explanation |
| Explanation | Explanation text | All file metadata |

Also test:

- Mixed file and explanation representation fails.
- File type without a file fails.
- Explanation type with blank or whitespace explanation fails.
- Unsupported receipt type fails.
- Receipt belongs to a reimbursement, not an expense.
- Explanation records do not count toward file-byte totals.
- Explanations longer than 10,000 characters are rejected.

## Payout Profile Tests

Test:

- Profile is optional until reimbursement submission.
- At most one profile exists per user.
- Method choices are Zelle and paper check only.
- Zelle requires a valid trimmed email.
- Zelle requires all check fields to be blank.
- Paper check requires payee, address line 1, city, two-letter US state or
  territory code, and ZIP or ZIP+4.
- Address line 2 is optional.
- Paper check requires the Zelle field to be blank.
- No country, ACH, verification, or international fields exist.
- Switching methods clears irrelevant fields.
- A user can edit only their own profile.
- Posted user IDs cannot redirect a profile update to another user.

## Payout Snapshot Tests

Test:

- Submission copies every normalized payout value.
- Snapshot is one-to-one with reimbursement.
- Snapshot validation matches payout-profile validation.
- Later profile changes do not alter the snapshot.
- Snapshot cannot be directly edited through supported services.
- Returning to draft deletes the snapshot.
- Resubmission copies the latest profile.
- Full payout details do not appear in broad reports, logs, or CSV.

## Human-Readable Number Tests

Fast tests:

- First number is `2026-R-0001`.
- Subsequent numbers increment.
- Different years begin independently.
- Deleted drafts leave acceptable gaps.
- Split and normal creation use the same allocator.
- The database uniqueness constraint prevents duplicate numbers.

Test the calculation from the greatest existing number for the year. If a rare
database uniqueness collision is simulated, creation retries once or returns a
normal creation error.

## New Camp Year Category Tests

Test that creating a camp year does not copy reimbursement categories and that
the new year begins with an empty category list.

## Receipt Validation Tests

Accepted content:

- JPEG.
- PNG.
- WebP.
- Valid PDF.

Rejected content:

- SVG.
- HTML.
- ZIP.
- Office-like files.
- Executable bytes.
- HEIC.
- Corrupt or truncated files.
- Images that Pillow cannot verify.

PDF rule:

- Any size-valid file whose sanitized filename ends in `.pdf`, ignoring case,
  is accepted as a PDF without content parsing, regardless of its contents.

Limits:

- Exactly 15 MB is accepted.
- More than 15 MB is rejected.
- The twentieth file is accepted.
- The twenty-first file is rejected.
- Exactly 100 MB aggregate is accepted.
- More than 100 MB aggregate is rejected.
- Explanations do not count as files.

Filename handling:

- Original filename is retained for display.
- Storage path uses a UUID plus validated extension.
- Path separators are removed.
- Control characters are removed.
- Long names are safely bounded.
- Non-ASCII names are safely displayed and encoded in download headers.
- Duplicate original names do not collide.

## Private Receipt Storage Tests

Every storage test uses a unique temporary receipt root.

Test:

- Files are stored outside `MEDIA_ROOT`.
- Files use `<year>/<reimbursement number>/<uuid>.<extension>`.
- Database stores only a relative path.
- Absolute and traversal paths are rejected.
- Symlink escapes are rejected.
- Stored bytes match validated upload bytes.
- File permissions are restrictive where supported.
- UUID paths and private roots never appear in pages, logs, CSV, or errors.
- Deleting one copied receipt does not delete another reimbursement's copy.
- Missing underlying files fail safely.
- Draft deletion makes a best-effort attempt to remove receipt files.
- A file-write failure does not create a receipt row.
- A database failure after a file write makes a best-effort attempt to remove
  the unreferenced file.

## Receipt Access Tests

Test:

- Anonymous user redirects to login.
- Inactive user cannot access receipts.
- Requester can access their receipt.
- Active admin can access receipts.
- Another member receives `404`.
- Wrong reimbursement and receipt pairing receives `404`.
- Explanation records cannot be used as file downloads.
- Image response uses the detected image type.
- PDF response uses attachment disposition.
- Original filename is safely represented in `Content-Disposition`.
- Response includes `X-Content-Type-Options: nosniff`.
- Response includes `Cache-Control: private, no-store`.
- Missing files fail without exposing paths.
- Receipt content cannot be reached through `/media/`, `/static/`, or
  `/public/`.

## Submission Tests

Validation failures:

- Wrong owner.
- Non-draft status.
- No expenses.
- Zero total.
- Invalid expense.
- Category from another year.
- No receipt or explanation.
- Malformed receipt record.
- Missing payout profile.
- Invalid payout profile.

Successful submission:

- Rechecks that the reimbursement remains draft.
- Creates one snapshot.
- Sets `submitted_at`.
- Sets status to submitted.
- Preserves expenses, receipts, and requester notes.
- Performs all database writes atomically.

Rollback behavior:

- Any failure leaves status draft.
- No snapshot remains.
- Submission date remains blank.
- No child record is partially changed.

Resubmission behavior:

- Unsubmit clears `submitted_at`.
- Unsubmit deletes the old snapshot.
- Updated payout profile is captured on resubmission.
- New `submitted_at` uses the resubmission time.

## Reimbursement State Transition Tests

Complete actor-aware transition matrix:

| Transition | Actor | Allowed |
|---|---|---|
| Draft to Submitted | Owner | Yes |
| Submitted to Draft | Owner | Yes |
| Submitted to Paid | Admin | Yes |
| Submitted to Rejected | Admin | Yes |
| Submitted to Draft | Admin | Yes |
| Rejected to Submitted | Admin | Yes |
| Rejected to Draft | Admin | Yes |
| Paid to any state | Anyone | No |

For every transition, assert:

- Correct source-state requirement.
- Correct actor requirement.
- Correct timestamp and actor fields.
- Correct fields cleared.
- Correct fields preserved.
- Snapshot is created, retained, or deleted correctly.
- A stale POST makes no change and shows the current state clearly.
- Redirect and message are correct.

## Member Reimbursement Overview Tests

Route:

```text
/<year>/reimbursements/
```

Test:

- Authentication and active-user requirement.
- Unknown year returns `404`.
- Only the logged-in member's reimbursements appear.
- Other years are excluded.
- Heading and empty state.
- Created and submitted dates.
- Submitted date is blank after unsubmit.
- Totals are derived from expenses.
- Newest-created ordering with deterministic tie-breaker.
- Draft shows Edit.
- Submitted shows View and Unsubmit.
- Paid and rejected show View only.
- Full payout details are absent.
- GET does not create a draft.
- POST creates only for the logged-in member.
- Create redirects to the canonical human-readable URL.

## Member Reimbursement Detail Tests

Test:

- Unknown year or number returns `404`.
- Wrong-year reimbursement returns `404`.
- Another member's reimbursement returns `404`.
- Summary fields and total are correct.
- Section order matches the design.
- Draft shows editable payout, receipts, expenses, notes, submit, and delete.
- Submitted, paid, and rejected are read-only.
- Submitted alone shows Unsubmit.
- Only draft shows Delete.
- Expense correction is delete-and-re-add only.
- Category choices are restricted to the reimbursement year.
- Payer notes are visible.
- Split lineage links display where applicable.
- Every mutation requires POST and CSRF.
- Success redirects to the correct fragment.
- Validation errors preserve attempted values and do not partially write data.

## Draft Reimbursement Deletion Tests

Test:

- Owner can delete their draft with correct confirmation.
- Incorrect or missing confirmation fails.
- Submitted, paid, and rejected cannot be deleted.
- Another member cannot delete the draft.
- Admin cannot use the member endpoint as the requester.
- Expenses and explanation records are deleted.
- Private files receive best-effort cleanup.
- A previously submitted or rejected reimbursement can be deleted after its
  current status returns to draft.

## Reimbursement Category Admin Tests

Route:

```text
/admin/camp/<year>/
```

Test:

- Anonymous access redirects to login.
- Non-admin receives `403`.
- Card appears in the intended position.
- Only selected-year categories appear.
- Alphabetical case-insensitive sorting.
- Usage counts distinct reimbursements rather than expenses.
- Usage includes draft, submitted, paid, and rejected records.
- Empty state.
- Valid creation.
- Trimming and length validation.
- Case-insensitive duplicate rejection.
- Same name in another year.
- Unused deletion.
- Used category has no active Delete action.
- A protected deletion failure gives a useful error rather than a server error.
- Wrong-year category ID is rejected.
- Success redirects to `#reimbursement-categories`.
- No descriptions, rename controls, or ordering controls appear.

## Annual Reimbursements Admin Tests

Routes:

```text
/admin/reimbursements/
/admin/<year>/reimbursements/
```

Test:

- Admin-only access.
- Latest-year redirect.
- Explicit valid year query redirect.
- Unknown year.
- No-year state.
- Year selector lists all years newest first.
- GET selector works without JavaScript.
- Card order is correct.
- Full payout details are absent from overview reports.

### Expenses By Category Report

Test:

- Submitted and paid totals are separate.
- Draft and rejected expenses are excluded.
- Multiple expense rows are not double-counted.
- Categories with both totals zero are omitted.
- Alphabetical ordering.
- Correct submitted, paid, and grand totals.
- Empty state.

### Paid Expenses By Person Report

Test:

- Only paid reimbursements are included.
- Group by requester and category.
- Aggregate across multiple reimbursements.
- Sort by last name, first name, email, and category.
- Members with duplicate names remain separate.
- Missing names display defensively.
- Correct grand total.
- Empty state.

### Submitted Reimbursements Report

Test:

- Submitted status only.
- Selected year only.
- Oldest `submitted_at` first.
- Reimbursement number tie-breaker.
- Derived total.
- Correct detail link.
- Empty state.

### Paid Reimbursements Report

Test:

- Paid status only.
- Newest `paid_at` first.
- Method comes from payout snapshot.
- Full payout details remain hidden.
- Correct detail link.
- Empty state.

### Rejected Reimbursements Report

Test:

- Rejected status only.
- Submitted and rejected dates display.
- Newest rejected first.
- View, Move to Submitted, and Move to Draft appear.
- Correct total and detail link.
- Empty state.

## CSV And Clipboard Tests

Shared report-builder tests:

- HTML table, TSV source, and CSV use identical logical rows.
- Ordering and totals match.
- No payout email, address, private path, or unrelated-year data appears.
- HTML values are escaped.
- Tabs, newlines, quotes, commas, carriage returns, and Unicode are handled.
- Formula-leading cells are neutralized after leading whitespace/control
  analysis.
- Values beginning with `=`, `+`, `-`, and `@` cannot execute as formulas.

CSV response tests:

- Admin authorization.
- Correct year scoping.
- Correct content type and safe filename.
- UTF-8 behavior.
- Correct columns and line endings.
- `Cache-Control: private, no-store`.
- `X-Content-Type-Options: nosniff`.

Clipboard contract tests:

- Template includes Copy button, CSV fallback, and status region.
- JavaScript is progressively loaded.
- Copy writes `text/html` and `text/plain`.
- Plain text is TSV.
- Success and failure are announced accessibly.
- CSV remains usable when clipboard access is unavailable.

Because the repository has no browser test framework, use:

- Python tests for report data and rendered clipboard source.
- `node --check` for JavaScript syntax.
- One manual browser acceptance test for Clipboard API behavior.

## Reimbursement Admin Detail Tests

Route:

```text
/admin/<year>/reimbursements/<reimbursement_number>/
```

Test:

- Admin-only access.
- Unknown and wrong-year records return `404`.
- Title uses full name with email fallback.
- Summary total and distinct category list are correct.
- Categories are sorted alphabetically.
- Requester notes are read-only.
- Payer notes save to `#notes`.
- Original receipt filenames display instead of UUID names.
- Explanations display as text.
- Receipt links remain protected.
- Payout snapshot is read-only.
- Draft admin page does not expose an unsubmitted payout snapshot.

### Admin Notes Tests

Test:

- Save Notes works without JavaScript.
- Pay and Reject save the currently submitted textarea.
- Rejection permits blank payer notes.

### Admin Pay Tests

Test:

- Submitted status is required.
- Confirmation checkbox is required.
- Payout snapshot and at least one expense are required.
- Total is recalculated server-side.
- Posted total and payout data are ignored.
- Paid status, time, actor, and notes save atomically.
- Duplicate Pay does not change `paid_at` or `paid_by`.
- If another action changed state first, Pay makes no change and shows a clear
  conflict.

### Admin Reject Tests

Test:

- Submitted status is required.
- Rejection metadata and notes save atomically.
- Submission date and payout snapshot remain.
- Duplicate Reject does not rewrite rejection metadata.

### Admin Move To Draft Tests

Test:

- Submitted or rejected source state is required as appropriate.
- Submission and rejection metadata are cleared.
- Payout snapshot is deleted.
- Expenses, receipts, requester notes, and payer notes remain.
- Member editing is restored.

### Admin Move Rejected To Submitted Tests

Test:

- Rejected status is required.
- Original submission date remains.
- Payout snapshot remains.
- Rejection metadata is cleared.
- Redirect targets `#SubmittedReimbursements`.

## Split Reimbursement Tests

Validation tests:

- Submitted source is required.
- At least one expense must be selected.
- At least one expense must remain.
- Nonblank rationale is required.
- Foreign expense IDs are rejected.
- Duplicate IDs are handled deterministically.

Successful split tests:

- Source and selected children are locked.
- A new number is allocated through the shared allocator.
- New draft has the same requester and camp year.
- `split_from` points to the source.
- Only selected expenses move.
- Requester notes are copied.
- Rationale becomes child payer notes.
- Every explanation is copied.
- Every receipt file receives an independent physical copy.
- Original receipts remain unchanged.
- Source payout snapshot remains unchanged.
- Child has no payout snapshot or state timestamps.
- Source remains submitted with a reduced total.
- Response remains on the source detail page.
- Success message links to the child.
- Annual report totals immediately reflect the moved expenses.

- Child editing or deletion does not change the source reimbursement's remaining
  expenses or original receipt files.

## Reimbursement Configuration Tests

Test:

- Private receipt root is required.
- Root is absolute.
- Root is not inside the public media root.
- Settings expose no public receipt URL.
- Test and example TOML files include the setting.
- The reimbursement app is installed and routed.
- Missing or unsafe receipt configuration fails clearly.
- Secrets and private paths are not printed unnecessarily.

## Reimbursement Backup Tests

Test:

- Private receipts use a dedicated S3 prefix.
- Backup does not report success when receipt backup fails.
- The private receipt root is included in the existing scheduled backup.
- Receipt files remain private in S3.

Completing restore support remains outside this feature.

## Deployment And Update Preparation

Production starts through a stable repository-owned wrapper:

```text
/opt/thephage/app/deploy/scripts/start-thephage
```

The systemd service should execute that wrapper rather than invoke Gunicorn
directly. The wrapper prepares and validates the deployment once, then replaces
itself with Gunicorn.

Startup sequence:

```text
standalone preflight
-> create or repair application-owned directories
-> manage.py migrate --noinput
-> manage.py collectstatic --noinput
-> Django and deployment checks
-> exec Gunicorn
```

The wrapper must not use `AppConfig.ready()` for deployment preparation because
that code would run once per Gunicorn worker and during unrelated management
commands.

### Automatic Startup Changes

The startup wrapper should automatically perform safe, idempotent changes that
the application account owns:

- Create the configured private receipt directory when its parent is writable.
- Set application-owned private receipt directories to mode `0700`.
- Set application-owned receipt files to mode `0600` where practical.
- Create required temporary directories.
- Apply committed database migrations with `migrate --noinput`.
- Run `collectstatic --noinput`.
- Run Django system checks.
- Confirm no migrations remain unapplied.
- Confirm the private receipt root exists, is writable, and is outside public
  media.
- Confirm reimbursement backup configuration includes the private receipt root.

The wrapper never generates migrations.

### Changes Startup Must Not Make

The application must not automatically modify:

- `/etc/thephage/thephage.toml`.
- Nginx configuration.
- Systemd unit files.
- IAM roles or policies.
- S3 bucket settings.
- OS packages.
- Root-owned directories that the application account cannot safely manage.
- Source code.

### Startup Blocker Output

When a required change cannot be made automatically, startup must print:

- What is wrong.
- The exact file or path requiring modification.
- The exact configuration text or shell commands to use.
- Why the change is required.
- Which service reload or restart is needed.

It then exits nonzero without starting Gunicorn. Under systemd, the same output
is available through:

```bash
journalctl -u thephage.service
```

Example missing configuration output:

```text
STARTUP BLOCKED: reimbursement receipt storage is not configured.

File:
  /etc/thephage/thephage.toml

Required change under [paths]:
  reimbursement_receipt_root = "/var/lib/thephage/private/reimbursement-receipts"

Why:
  Reimbursement receipts cannot be stored under publicly served media.
```

Example directory output:

```text
STARTUP BLOCKED: the private receipt directory cannot be created by user phage.

Required command:
  sudo install -d -o phage -g phage -m 0700 \
    /var/lib/thephage/private/reimbursement-receipts

After making the change:
  sudo systemctl restart thephage.service
```

Example Nginx output:

```text
STARTUP BLOCKED: Nginx rejects valid reimbursement receipt uploads.

File:
  /etc/nginx/sites-available/thephage

Required change:
  client_max_body_size 20M;

After making the change:
  sudo nginx -t
  sudo systemctl reload nginx
  sudo systemctl restart thephage.service
```

Missing or unsafe local configuration is a startup blocker. A temporary S3 or
network outage during an ordinary restart should produce a warning rather than
prevent the web application from starting; the scheduled backup service still
fails until backup storage is reachable.

## Reimbursement Deployment Tests

Verify on the installed host:

- Receipt root is
  `/var/lib/thephage/private/reimbursement-receipts/`.
- Root owner and group are correct.
- Directory mode is `0700`.
- File mode is `0600`.
- Application user can read and write.
- Nginx cannot traverse or serve the directory.
- Direct guessed public receipt paths fail.
- Authenticated Django receipt access succeeds.
- Nginx accepts the configured upload limit plus multipart overhead.
- EBS or storage encryption is enabled.
- S3 prefix is private, encrypted, and versioned.
- Backup configuration includes receipts.
- Reimbursement migrations are applied.
- The stable startup wrapper runs migrations and collectstatic before Gunicorn.
- Startup creates application-owned receipt directories when possible.
- Missing root-owned configuration prints exact remediation and prevents
  Gunicorn from starting.
- A temporary S3 reachability failure warns but does not block web startup.

## Reimbursement Manual Acceptance Plan

Run complete member workflows for both Zelle and paper check:

1. Create a reimbursement.
2. Save payment information.
3. Add several categorized expenses.
4. Upload image and PDF receipts.
5. Add an explanation.
6. Save requester notes.
7. Submit.
8. Unsubmit.
9. Change payment information.
10. Resubmit.
11. Verify the new payout snapshot.
12. Delete a separate draft.

Run complete admin workflows:

1. Review annual reports.
2. Copy Paid Expenses by Person into the target spreadsheet.
3. Download the CSV without JavaScript.
4. Open receipt images and PDFs.
5. Save payer notes.
6. Split selected expenses.
7. Verify copied files and notes.
8. Pay the remaining original reimbursement.
9. Reject another reimbursement with notes.
10. Move a rejected reimbursement to submitted.
11. Move a rejected reimbursement to draft.
12. Verify state-specific controls appear and disappear correctly.

Run privacy and accessibility checks:

- Another member cannot access reimbursement or receipt URLs.
- Payout details never appear in overview reports or CSV.
- Private paths never appear in responses.
- All workflows function without JavaScript except clipboard copying.
- Tables work on mobile.
- Focus and keyboard navigation work.
- Status does not rely only on color.
- Clipboard denial produces a useful fallback.

## Reimbursement Test Definition Of Done

The feature is test-complete when:

1. The full default SQLite suite passes.
2. Every state transition has success, authorization, stale-state, and rollback
   coverage.
3. Human-readable number allocation cannot create duplicate numbers.
4. Every receipt test uses an isolated private root.
5. Accepted and rejected file types and limits are covered.
6. Member and admin routes enforce ownership, year scoping, CSRF, and POST-only
   mutations.
7. Split moves only the selected expenses and copies the specified notes and
   receipt evidence.
8. Reports, clipboard data, and CSV produce the intended totals.
9. Payout details and private paths do not leak.
10. Private receipts are included in scheduled backup.
11. Django checks, migration drift checks, Ruff, JavaScript syntax checks, and
    all tests pass.
12. Manual spreadsheet clipboard acceptance succeeds on HTTPS or localhost.
