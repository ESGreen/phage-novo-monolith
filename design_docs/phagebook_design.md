# Phagebook Design

## Purpose

The Phagebook is a year-scoped member directory for a camp year.

It lets logged-in members see the people who are fully registered for a specific camp year, including their name, profile photo, email address, and bio.

## Goals

- Add a member-only page at `/<year>/phagebook/`, such as `/2026/phagebook/`.
- Show only people who have completed the registration checklist for that camp year.
- Allow any logged-in active member to view the page, even if that viewer is not fully registered.
- Render a long-scroll list of registered members.
- Reuse the same completion rules as the dashboard and taxes flow so registration status does not drift across pages.
- Keep V1 server-rendered with no required JavaScript.

## Non-Goals

- No public Phagebook page.
- No admin-only Phagebook variant in V1.
- No search, filtering, pagination, or export in V1.
- No custom visibility/privacy controls in V1.
- No editing profile details from the Phagebook page.
- No separate `Roster` product terminology or route.

## Terminology

Use `Phagebook` in user-facing copy.

Use `phagebook` for routes, view names, URL names, template names, and tests.

Do not use `roster` for this feature unless referring to discarded design history.

## Routes

| Route | Behavior |
| --- | --- |
| `/phagebook/` | Redirect to the current year Phagebook |
| `/<year>/phagebook/` | Display the Phagebook for a camp year |

The canonical year route includes the trailing slash. For example, use `/2026/phagebook/` in year-specific templates, tests, redirects, and docs.

The default root menu should link to `/phagebook/` so the menu remains valid when the current camp year changes.

The route should return `404` when the camp year does not exist.

## Permissions

The Phagebook is a member page.

Rules:

- Anonymous visitors are redirected to `/login/` with `next` set to the requested Phagebook URL.
- Active logged-in members can view the Phagebook.
- Active admins can view the Phagebook because admins are also members.
- Admin pages remain the only role-restricted pages.
- Viewing the Phagebook does not require the viewer to be fully registered.

## Registration Completion

A member appears in a camp year's Phagebook only when their registration checklist is complete for that camp year.

For V1, complete means:

- First name is present.
- Last name is present.
- Profile photo is present.
- Bio is present.
- The camp survey is complete when the `CampYear` has a configured `camp_survey`.
- Taxes are paid or waived for the `CampYear`.

This profile completion definition should also apply to the dashboard checklist and taxes prerequisite gate. A member should not be able to reach the tax payment page until first name, last name, photo, bio, and the camp survey requirement are complete.

If a camp survey is configured after members were previously complete, those members should no longer appear in the Phagebook until they complete the newly configured camp survey. This matches the dashboard checklist behavior.

## Profile Form Requirements

The profile bio form should require:

- First name.
- Last name.
- Bio.

The photo upload remains a separate profile form and is still required for registration completion.

Existing users with blank first name, blank last name, or blank bio become incomplete until they update their profile.

## Phagebook Entry Display

Each Phagebook entry should display, in this order:

1. Name.
2. Profile picture.
3. Email.
4. Bio.

The display name should be the user's full name from `User.get_full_name()`.

Because first name and last name are required for Phagebook inclusion, the normal case should always have a full name. A defensive fallback to email is acceptable if an inconsistent record is ever rendered.

Profile bio content is stored as Markdown. The Phagebook should render bios through the existing sanitized Markdown renderer rather than outputting raw Markdown or unsafe HTML.

## Ordering

Order entries by:

1. Last name.
2. First name.
3. Email.

This keeps the long-scroll directory predictable.

## Empty State

If no members are fully registered for the camp year, show an empty state such as:

`No one is fully registered for 2026 yet.`

## Data Sources

Use existing models:

- `accounts.User` for name and email.
- `accounts.MemberProfile` for photo and bio.
- `payments.Payment` for paid taxes.
- `camp.TaxOverride` for waived taxes.
- `surveys.SurveyResponse` for camp survey completion.
- `camp.CampYear` for year scoping and optional camp survey configuration.

No new database model is needed for V1.

## Implementation Notes

The implementation avoids duplicating checklist logic in multiple places.

Current structure:

- `camp.services.is_profile_complete()` checks first name, last name, photo, and bio.
- `camp.services.is_camp_survey_complete()` checks the configured Camp survey response.
- `camp.services.are_taxes_complete()` checks paid or waived taxes.
- `camp.services.is_registration_complete()` combines those rules for Phagebook inclusion.
- Dashboard completion, tax gating, and Phagebook inclusion should continue to share these helpers.

The Phagebook query should avoid showing inactive users.

For V1, it is acceptable to build the eligible user list using clear Django queries plus a small amount of Python filtering, since the camp population is expected to be modest. If the member list grows large later, this can be optimized with annotations or subqueries.

## Template

Use `templates/camp/phagebook.html`.

The page should extend `member_base.html` and follow existing member page card patterns.

Suggested page structure:

- Page heading with `{{ camp_year.year }} Phagebook`.
- Short explanatory text.
- One long-scroll list of member cards.
- Each card contains name, photo, email, and rendered bio.
- Empty state when there are no entries.

No menu or dashboard link is required. Maintainers can add links through menus or markdown pages.

## Styling

Keep styling small and consistent with existing member pages.

Suggested classes:

- `.phagebook-list`
- `.phagebook-entry`
- `.phagebook-entry__name`
- `.phagebook-entry__photo`
- `.phagebook-entry__email`
- `.phagebook-entry__bio`

The layout should work as a readable single column on mobile. Desktop can remain a single long-scroll column or use a modest card layout if it preserves readability.

## Tests

Add coverage for:

- `/2026/phagebook/` requires login.
- `/phagebook/` redirects to the current year Phagebook.
- `/2026/phagebook/` returns `404` for an unknown camp year.
- Any logged-in active member can view the page even when that viewer is not fully registered.
- Fully registered paid members appear.
- Fully registered tax-waived members appear.
- Members with missing first name do not appear.
- Members with missing last name do not appear.
- Members with missing profile photo do not appear.
- Members with blank bio do not appear.
- Members missing a required camp survey response do not appear.
- Members with a required camp survey response appear when the rest of the checklist is complete.
- Bio Markdown renders safely and strips or escapes unsafe HTML.
- Dashboard and taxes prerequisite tests cover the updated name requirement.

## Future Ideas

Potential later enhancements:

- Search by name.
- Filtering by camp year participation status.
- Optional contact fields collected by survey.
- Admin export.
- Member-controlled visibility settings.
- Profile detail pages.
