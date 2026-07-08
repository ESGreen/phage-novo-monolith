# The Phage Website Outline

## Project Summary

The Phage website will be a Django-based website hosted at `thephage.org`.

The purpose of the site is to give camp members one reliable place to handle yearly camp business, especially paying camp taxes, accessing camp information, and eventually completing yearly survey and roster workflows.

The site should be simple to maintain. Most member-site content changes should be possible through the custom product admin without editing Django templates. The site is expected to change lightly, usually once per year.

## Goals

- Provide a private member area for camp members.
- Allow members to pay yearly camp taxes through Stripe.
- Let admins manually create and manage user accounts.
- Store mostly-static camp information in a maintainable way.
- Support a clear yearly rollover process.
- Avoid unnecessary systems such as email delivery, marketing tools, or a full CMS.
- Keep the codebase small, understandable, and boring.

## Non-Goals

- No email system in the first version.
- No custom credit card handling.
- No public self-registration.
- No complex role system unless needed later.
- No full WordPress-style CMS.
- No automatic recurring billing.
- No job/shift signup in the first version.

## Primary Users

- Camp members who need to log in, read information, and pay taxes.
- Camp admins who need to manage users, yearly tax settings, payments, and site content.
- Future maintainers who need to make yearly updates without reverse-engineering fragile legacy code.

## Version 1 Scope

Version 1 should focus on the essential website foundation.

Core features:

- Public landing page.
- A small number of public static/info pages.
- Login/logout.
- Admin-created user accounts.
- Member dashboard after login.
- Admin-editable content pages.
- Yearly camp tax configuration.
- Stripe Checkout payment flow.
- Stripe webhook handling.
- Payment status shown to users.
- Payment status visible to admins.
- Basic yearly structure through a `CampYear` concept.

## Version 1 Member Dashboard

After logging in, a member should see:

- Their current registration/payment status.
- The current camp year.
- Whether they owe taxes.
- The available tax/payment options.
- A button to pay through Stripe.
- Links to relevant member-only information pages.

## Version 1 Admin Needs

Admins should be able to:

- Create and deactivate users.
- Reset passwords manually.
- Create a new camp year.
- Set tax tiers and optional add-ons.
- Set per-user tax overrides when needed.
- See who has paid.
- Edit member content pages and update static public pages outside Django when needed.
- Review Stripe payment records.

## Payment System

Payments should use Stripe Checkout.

The site should not collect or store card details.

The expected flow:

- User chooses a tax amount or tier.
- Django creates a Stripe Checkout Session.
- User pays on Stripe-hosted checkout.
- Stripe redirects the user back to the site.
- Stripe sends a webhook to Django.
- Django records the payment status.

Stripe webhooks should be treated as the source of truth for successful payments.

## Content Pages

The site should support simple content pages managed through the admin.

Each page should have:

- Title.
- Slug.
- Body content.

Public pages are static files under `/public/`. Member content pages are managed in Django. Menu ordering is managed separately from content pages.

Markdown is likely a good fit for content editing because it is simpler than a full rich-text CMS.

## Yearly Rollover

The site should be organized around camp years.

Each year should have its own:

- Tax settings.
- Payment records.
- Future survey.
- Future roster/report configuration.
- Year-specific information as needed.

The yearly rollover should be explicit and admin-driven.

Expected yearly process:

- Create new camp year.
- Configure tax tiers and options.
- Update member content pages and public static pages.
- Create or update user accounts.
- Open payments.
- Review payment status.

## Future Roadmap

Future versions should expand the site without requiring a rewrite.

Likely future modules:

- Yearly member survey.
- Photo/name directory.
- Tabular roster.
- Survey results/statistics pages.
- CSV exports.
- Job/shift signup.
- More detailed admin reporting.

## Future Survey System

The survey should eventually be configurable through the admin rather than hardcoded in templates.

The survey should support questions that can change year to year while preserving old responses.

Likely question types:

- Short text.
- Long text.
- Yes/no.
- Single choice.
- Multiple choice.
- Number.
- Date.
- Image/photo upload.

Survey answers should support future reports such as the member directory, roster table, and aggregate stats.

## Future Roster And Reports

Survey results should eventually feed three main outputs:

- A photo/name directory of camp members.
- A tabular roster with selected fields.
- A summary page with tabulated survey results.

Admins should be able to choose which survey questions appear in the roster or stats pages.

## Future Job Signup

The old site had job and kitchen shift signup behavior. This should not be part of Version 1 unless priorities change.

If added later, it should be a separate module tied to the camp year.

Likely future concepts:

- Job categories.
- Jobs.
- Job slots or dates.
- User assignments.
- Minimum job count rules, if needed.

## Technical Direction

The project should be built as a conventional Django application.

Expected stack:

- Django.
- PostgreSQL.
- Custom product admin views.
- Django authentication.
- Stripe Checkout.
- Server-rendered templates.
- Minimal JavaScript.
- TOML server config file for secrets and deployment settings.
- Static file handling suitable for deployment.

The new site should not copy the old WordPress/CGI architecture.

## Maintenance Principles

- Prefer simple Django models over ad hoc scripts.
- Prefer server-rendered pages over browser-heavy interfaces.
- Keep yearly changes admin-editable where practical.
- Avoid hardcoded year IDs, form IDs, and payment amounts.
- Keep Stripe logic isolated and testable.
- Keep permissions simple and explicit.
- Document the yearly update process.

## Main Risks

- Stripe webhook correctness.
- Manual user/password management without email.
- Yearly rollover mistakes.
- Privacy decisions around member information.
- Future survey/report flexibility becoming too complex.
- Image uploads and storage once member photos are added.
- Importing or referencing old WordPress/Gravity Forms data.

## Guiding Principle

The site should be easy to understand one year later.

The best version is not the most flexible possible system. The best version is a small, reliable Django app that handles taxes and camp information cleanly, while leaving room for survey, roster, and job features to be added later.
