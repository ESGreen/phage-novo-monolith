from __future__ import annotations

from datetime import datetime, time, timedelta
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from camp.models import CampYear, TaxAddOn, TaxOverride, TaxTier
from content.models import ContentPage, MediaItem, Menu, MenuItem
from core.models import SiteSettings
from payments.models import Payment, PaymentLog

pytestmark = pytest.mark.django_db

ADMIN_SECTIONS = [
    "/admin/",
    "/admin/users/",
    "/admin/camp/",
    "/admin/payments/",
    "/admin/stripe/",
    "/admin/pages/",
    "/admin/menus/",
    "/admin/media/",
]


def create_user(
    email: str = "member@example.com",
    is_admin: bool = False,
    first_name: str = "",
    last_name: str = "",
):
    return get_user_model().objects.create_user(
        email=email,
        password="test-password-1",
        first_name=first_name,
        is_admin=is_admin,
        last_name=last_name,
    )


def png_upload(name: str = "image.png") -> SimpleUploadedFile:
    output = BytesIO()
    Image.new("RGB", (1, 1), "red").save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


def local_midnight(year: int, month: int, day: int):
    return timezone.make_aware(
        datetime(year, month, day),
        timezone.get_current_timezone(),
    )


def create_tax_tier(
    camp_year: CampYear,
    *,
    name: str = "Standard",
    display_order: int = 1,
    expiration_date=None,
    minimum_amount_cents: int = 10000,
    start_date=None,
) -> TaxTier:
    now = timezone.now()
    return TaxTier.objects.create(
        camp_year=camp_year,
        name=name,
        minimum_amount_cents=minimum_amount_cents,
        start_date=start_date or now,
        expiration_date=expiration_date or now + timedelta(days=30),
        display_order=display_order,
    )


def create_tax_add_on(
    camp_year: CampYear,
    *,
    amount_cents: int = 2500,
    name: str = "Hoodie",
    display_order: int = 1,
    expiration_date=None,
    start_date=None,
) -> TaxAddOn:
    now = timezone.now()
    return TaxAddOn.objects.create(
        camp_year=camp_year,
        name=name,
        amount_cents=amount_cents,
        start_date=start_date or now,
        expiration_date=expiration_date or now + timedelta(days=30),
        display_order=display_order,
    )


@pytest.mark.parametrize("url", ADMIN_SECTIONS)
def test_admin_sections_require_login(client, url: str) -> None:
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"] == f"/login/?next={url}"


@pytest.mark.parametrize("url", ADMIN_SECTIONS)
def test_admin_sections_reject_non_admin_members(client, url: str) -> None:
    user = create_user()
    client.force_login(user)

    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.parametrize("url", ADMIN_SECTIONS)
def test_admin_sections_load_for_admin(client, url: str) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.get(url)

    assert response.status_code == 200


def test_admin_home_renders_section_guide(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    CampYear.objects.create(year=2026)
    client.force_login(admin)

    response = client.get("/admin/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Current Status" in body
    assert "Stripe mode:" in body
    assert "Current camp year:" in body
    assert 'href="/admin/users/"' in body
    assert "Create member accounts" in body
    assert 'href="/admin/camp/"' in body
    assert "Manage camp years" in body
    assert 'href="/admin/payments/"' in body
    assert "Review payment records" in body
    assert 'href="/admin/stripe/"' in body
    assert "Switch Stripe test/live mode" in body
    assert 'href="/admin/pages/"' in body
    assert "Create and edit member Markdown content pages" in body
    assert 'href="/admin/menus/"' in body
    assert "Manage member navigation menus" in body
    assert 'href="/admin/media/"' in body
    assert "Upload and delete image media" in body
    assert 'href="/dashboard/"' in body
    assert "check what members see" in body


def test_payments_admin_renders_payment_and_log_tables(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com")
    camp_year = CampYear.objects.create(year=2026)
    payment = Payment.objects.create(
        user=member,
        camp_year=camp_year,
        status=Payment.Status.PAID,
        stripe_mode=Payment.StripeMode.TEST,
        tax_amount_cents=30000,
        add_on_amount_cents=2500,
        total_amount_cents=32500,
        tax_tier_name_snapshot="Standard",
        tax_tier_minimum_cents_snapshot=10000,
        paid_at=timezone.now(),
    )
    payment_log = PaymentLog.objects.create(
        payment=payment,
        level=PaymentLog.Level.INFO,
        event_type="checkout.create.success",
        stripe_mode=Payment.StripeMode.TEST,
        message="Stripe Checkout session created.",
    )
    PaymentLog.objects.create(
        payment=None,
        level=PaymentLog.Level.WARNING,
        event_type="webhook.signature.failure",
        message="Webhook signature verification failed.",
    )
    client.force_login(admin)

    response = client.get("/admin/payments/")
    body = response.content.decode()
    log_timestamp = timezone.localtime(payment_log.created_at).strftime("%Y-%m-%d %H:%M:%S")

    assert response.status_code == 200
    assert body.count('<section class="content-card">') == 2
    assert "<h1>Payments</h1>" in body
    assert "<h2>Recent Logs</h2>" in body
    assert "member@example.com" in body
    assert "$300.00" in body
    assert "$25.00" in body
    assert "$325.00" in body
    assert "Timestamp" in body
    assert log_timestamp in body
    assert "checkout.create.success" in body
    assert "Stripe Checkout session created." in body
    assert "webhook.signature.failure" in body
    assert "Webhook signature verification failed." in body
    assert "----" in body


def test_users_admin_renders_client_side_search_and_sort_controls(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    create_user(email="Member@Example.com")
    client.force_login(admin)

    response = client.get("/admin/users/")
    body = response.content.decode()

    assert response.status_code == 200
    assert 'data-user-table-search' in body
    assert 'data-user-table-clear' in body
    assert 'data-user-table-count' in body
    assert 'data-sort-column="0"' in body
    assert 'data-sort-column="5"' in body
    assert 'data-search="member@example.com  "' in body
    assert '<td data-sort="member@example.com">member@example.com</td>' in body
    assert 'src="/static/js/admin-users.js"' in body


def test_users_admin_renders_create_user_form_before_user_table(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.get("/admin/users/")
    body = response.content.decode()

    assert response.status_code == 200
    assert body.index("Create User") < body.index("Existing Users")
    assert 'name="account_address"' in body
    assert 'name="first_name"' in body
    assert 'name="last_name"' in body
    assert 'name="is_admin"' in body
    assert 'name="is_active"' in body
    assert 'name="initial_secret"' in body
    assert 'type="password"' not in body
    assert 'data-generate-password' in body
    assert 'data-copy-intro-email' in body
    assert 'name="bio_markdown"' not in body
    assert 'name="photo"' not in body


def test_users_admin_links_to_edit_for_other_users_but_not_current_user(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com")
    client.force_login(admin)

    response = client.get("/admin/users/")
    body = response.content.decode()

    assert response.status_code == 200
    assert f'href="/admin/users/{member.id}/"' in body
    assert f'href="/admin/users/{admin.id}/"' not in body
    assert "Current user cannot be edited" in body


def test_admin_user_edit_loads_for_other_user(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com")
    member.first_name = "Jane"
    member.last_name = "Smith"
    member.save(update_fields=["first_name", "last_name", "updated_at"])
    client.force_login(admin)

    response = client.get(f"/admin/users/{member.id}/")

    assert response.status_code == 200
    assert b"Edit: Jane Smith" in response.content
    assert b"User Flags" in response.content
    assert b"Update Email" in response.content
    assert b"Update Password" in response.content
    assert b"Load Photo" in response.content
    assert b"Basic Bio" in response.content


def test_admin_user_edit_blocks_current_user(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.get(f"/admin/users/{admin.id}/")

    assert response.status_code == 403


def test_admin_can_update_other_user_flags(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com")
    client.force_login(admin)

    response = client.post(
        f"/admin/users/{member.id}/",
        {"action": "flags", "is_admin": "on"},
    )

    assert response.status_code == 302
    member.refresh_from_db()
    assert member.is_active is False
    assert member.is_admin is True


def test_admin_can_update_other_user_email(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com")
    client.force_login(admin)

    response = client.post(
        f"/admin/users/{member.id}/",
        {"action": "email", "new_email": "NewEmail@example.com"},
    )

    assert response.status_code == 302
    member.refresh_from_db()
    assert member.email == "newemail@example.com"


def test_admin_user_edit_rejects_duplicate_email(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com")
    create_user(email="taken@example.com")
    client.force_login(admin)

    response = client.post(
        f"/admin/users/{member.id}/",
        {"action": "email", "new_email": "taken@example.com"},
    )

    assert response.status_code == 200
    assert b"Another account already uses this email address." in response.content
    member.refresh_from_db()
    assert member.email == "member@example.com"


def test_admin_can_update_other_user_password_without_old_password(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com")
    client.force_login(admin)

    response = client.post(
        f"/admin/users/{member.id}/",
        {
            "action": "password",
            "new_password1": "better-password-1",
            "new_password2": "better-password-1",
        },
    )

    assert response.status_code == 302
    member.refresh_from_db()
    assert member.check_password("better-password-1")


def test_admin_can_update_other_user_photo(client, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com")
    client.force_login(admin)

    response = client.post(
        f"/admin/users/{member.id}/",
        {"action": "photo", "photo": png_upload("avatar.png")},
    )

    assert response.status_code == 302
    member.profile.refresh_from_db()
    assert member.profile.photo is not None
    assert member.profile.photo.file_path.startswith(f"{member.profile.photo.id}-avatar")


def test_admin_can_update_other_user_bio(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com")
    client.force_login(admin)

    response = client.post(
        f"/admin/users/{member.id}/",
        {
            "action": "bio",
            "first_name": "Jane",
            "last_name": "Smith",
            "bio_markdown": "Admin updated bio",
        },
    )

    assert response.status_code == 302
    member.refresh_from_db()
    assert member.first_name == "Jane"
    assert member.last_name == "Smith"
    assert member.profile.bio_markdown == "Admin updated bio"


def test_admin_can_create_user(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.post(
        "/admin/users/",
        {
            "account_address": "NewMember@example.com",
            "first_name": "New",
            "last_name": "Member",
            "is_admin": "on",
            "is_active": "on",
            "initial_secret": "test-password-1",
        },
    )

    assert response.status_code == 302
    user = get_user_model().objects.get(email="newmember@example.com")
    assert user.first_name == "New"
    assert user.last_name == "Member"
    assert user.is_active is True
    assert user.is_admin is True
    assert user.check_password("test-password-1")
    assert user.profile.bio_markdown == ""


def test_admin_new_user_intro_email_renders_template_without_creating_user(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.post(
        "/admin/users/intro-email/",
        {
            "account_address": "NewMember@example.com",
            "first_name": "New",
            "last_name": "Member",
            "is_active": "on",
            "initial_secret": "test-password-1",
        },
    )

    assert response.status_code == 200
    body = response.json()["body"]
    assert "Hi New Member," in body
    assert "Username: newmember@example.com" in body
    assert "Password: test-password-1" in body
    assert "Login page: http://testserver/login/" in body
    assert not get_user_model().objects.filter(email="newmember@example.com").exists()


def test_admin_new_user_intro_email_rejects_duplicate_email(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    create_user(email="taken@example.com")
    client.force_login(admin)

    response = client.post(
        "/admin/users/intro-email/",
        {
            "account_address": "taken@example.com",
            "first_name": "Taken",
            "last_name": "Member",
            "is_active": "on",
            "initial_secret": "test-password-1",
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["message"] == "Email: A user with this email already exists."
    assert "account_address" in data["errors"]


def test_admin_create_user_failure_renders_inline_status_message(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    create_user(email="taken@example.com")
    client.force_login(admin)

    response = client.post(
        "/admin/users/",
        {
            "account_address": "taken@example.com",
            "first_name": "Taken",
            "last_name": "Member",
            "is_active": "on",
            "initial_secret": "test-password-1",
        },
    )
    body = response.content.decode()

    assert response.status_code == 200
    assert '<p class="help-text" data-intro-email-status data-status-type="error"' in body
    assert "Email: A user with this email already exists." in body


def test_admin_new_user_intro_email_requires_admin(client) -> None:
    member = create_user(email="member@example.com")
    client.force_login(member)

    response = client.post(
        "/admin/users/intro-email/",
        {
            "account_address": "new@example.com",
            "initial_secret": "test-password-1",
        },
    )

    assert response.status_code == 403


def test_admin_can_create_camp_year(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.post(
        "/admin/camp/",
        {"action": "camp_year", "year": "2026"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/camp/2026/#dashboard-pages"
    camp_year = CampYear.objects.get(year=2026)
    assert camp_year.created_by == admin
    assert camp_year.updated_by == admin


def test_camp_admin_lists_years_descending_with_summary_counts(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    paid_member = create_user(email="paid@example.com")
    waived_member = create_user(email="waived@example.com")
    reduced_member = create_user(email="reduced@example.com")
    current_year = CampYear.objects.create(year=2027)
    older_year = CampYear.objects.create(year=2026)
    opens_at = timezone.now() - timedelta(days=1)
    closes_at = timezone.now() + timedelta(days=30)
    TaxTier.objects.create(
        camp_year=current_year,
        name="Standard",
        minimum_amount_cents=10000,
        start_date=opens_at,
        expiration_date=closes_at,
    )
    TaxAddOn.objects.create(
        camp_year=current_year,
        name="Hoodie",
        amount_cents=2500,
        start_date=opens_at,
        expiration_date=closes_at,
    )
    Payment.objects.create(
        user=paid_member,
        camp_year=current_year,
        status=Payment.Status.PAID,
        stripe_mode=Payment.StripeMode.TEST,
        tax_amount_cents=10000,
        add_on_amount_cents=0,
        total_amount_cents=10000,
        tax_tier_name_snapshot="Standard",
        tax_tier_minimum_cents_snapshot=10000,
        paid_at=timezone.now(),
    )
    TaxOverride.objects.create(
        user=waived_member,
        camp_year=current_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )
    TaxOverride.objects.create(
        user=reduced_member,
        camp_year=current_year,
        override_type=TaxOverride.OverrideType.REDUCED_MINIMUM,
        reduced_minimum_amount_cents=5000,
    )
    client.force_login(admin)

    response = client.get("/admin/camp/")
    body = response.content.decode()
    camp_years = list(response.context["camp_years"])

    assert response.status_code == 200
    assert body.index("Edit 2027") < body.index("Edit 2026")
    assert camp_years[0] == current_year
    assert camp_years[1] == older_year
    assert camp_years[0].people_count == 3
    assert camp_years[0].paid_count == 1
    assert camp_years[0].waived_count == 1
    assert camp_years[0].override_count == 2
    assert camp_years[0].tax_tier_count == 1
    assert camp_years[0].tax_add_on_count == 1
    assert camp_years[0].tax_opens_at == opens_at
    assert camp_years[0].tax_closes_at == closes_at


def test_camp_admin_create_year_form_defaults_to_current_year_and_blank_pages(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.get("/admin/camp/")
    body = response.content.decode()

    assert response.status_code == 200
    assert response.context["camp_year_form"]["year"].value() == timezone.localdate().year
    assert ">----</option>" in body


def test_admin_camp_year_edit_page_loads_year_scoped_sections(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    CampYear.objects.create(year=2026)
    create_user(email="named@example.com", first_name="Jane", last_name="Member")
    create_user(email="unnamed@example.com")
    client.force_login(admin)

    response = client.get("/admin/camp/2026/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Edit Camp Year: 2026" in body
    assert "Dashboard Pages" in body
    assert "Tax Tiers" in body
    assert "Tax Add-ons" in body
    assert "Tax Overrides" in body
    assert 'id="dashboard-pages"' in body
    assert 'id="tax-tiers"' in body
    assert 'id="tax-add-ons"' in body
    assert 'id="tax-overrides"' in body
    assert 'action="/admin/camp/2026/#tax-tiers"' in body
    assert 'src="/static/js/admin-camp.js"' in body
    assert 'data-user-combobox' in body
    assert "Jane Member - named@example.com" in body
    assert 'data-name-search="jane member member jane"' in body
    assert 'data-name-search="jane member member jane named@example.com"' not in body
    assert "unnamed@example.com" not in body
    assert 'name="camp_year"' not in body
    assert 'name="display_order"' not in body
    assert "Display order" not in body
    assert 'type="date"' in body
    assert 'type="datetime-local"' not in body


def test_admin_can_update_camp_year_dashboard_pages(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    pre_page = ContentPage.objects.create(title="Pre", slug="pre", body_markdown="Pre")
    post_page = ContentPage.objects.create(title="Post", slug="post", body_markdown="Post")
    camp_year = CampYear.objects.create(year=2026)
    client.force_login(admin)

    response = client.post(
        "/admin/camp/2026/",
        {
            "action": "pages",
            "dashboard_pre_page": str(pre_page.id),
            "dashboard_post_page": str(post_page.id),
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/camp/2026/#dashboard-pages"
    camp_year.refresh_from_db()
    assert camp_year.dashboard_pre_page == pre_page
    assert camp_year.dashboard_post_page == post_page
    assert camp_year.updated_by == admin


def test_admin_can_create_year_scoped_tax_tier_with_dollar_amount(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    create_tax_tier(camp_year, name="Early", display_order=1)
    client.force_login(admin)

    response = client.post(
        "/admin/camp/2026/",
        {
            "action": "tax_tier",
            "name": "Standard",
            "description": "Standard taxes",
            "minimum_amount_dollars": "125.50",
            "start_date": "2026-01-01",
            "expiration_date": "2026-03-01",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/camp/2026/#tax-tiers"
    tax_tier = TaxTier.objects.get(camp_year=camp_year, name="Standard")
    assert tax_tier.minimum_amount_cents == 12550
    assert timezone.localtime(tax_tier.start_date).date().isoformat() == "2026-01-01"
    assert timezone.localtime(tax_tier.start_date).time() == time.min
    assert timezone.localtime(tax_tier.expiration_date).date().isoformat() == "2026-03-01"
    assert timezone.localtime(tax_tier.expiration_date).time() == time.min
    assert tax_tier.display_order == 2
    assert tax_tier.created_by == admin
    assert tax_tier.updated_by == admin


def test_admin_tax_tier_edit_loads_prepopulated_form(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    tax_tier = create_tax_tier(
        camp_year,
        name="Standard",
        minimum_amount_cents=12550,
        start_date=local_midnight(2026, 1, 1),
        expiration_date=local_midnight(2026, 3, 1),
    )
    tax_tier.description = "Standard taxes"
    tax_tier.save(update_fields=["description", "updated_at"])
    client.force_login(admin)

    response = client.get(f"/admin/camp/2026/tax-tier/{tax_tier.id}/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Edit Tax Tier: Standard" in body
    assert 'value="Standard"' in body
    assert 'value="125.50"' in body
    assert 'value="2026-01-01"' in body
    assert 'value="2026-03-01"' in body
    assert "Standard taxes" in body
    assert "display_order" not in body
    assert 'href="/admin/camp/2026/#tax-tiers"' in body
    assert "Delete Tax Tier" in body
    assert 'class="danger-button"' in body


def test_admin_can_update_tax_tier(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    creator = create_user(email="creator@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    tax_tier = TaxTier.objects.create(
        camp_year=camp_year,
        name="Standard",
        description="Old description",
        minimum_amount_cents=10000,
        start_date=local_midnight(2026, 1, 1),
        expiration_date=local_midnight(2026, 3, 1),
        display_order=4,
        created_by=creator,
    )
    client.force_login(admin)

    response = client.post(
        f"/admin/camp/2026/tax-tier/{tax_tier.id}/",
        {
            "name": "Updated Standard",
            "description": "Updated description",
            "minimum_amount_dollars": "150.25",
            "start_date": "2026-02-01",
            "expiration_date": "2026-04-01",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/camp/2026/#tax-tiers"
    tax_tier.refresh_from_db()
    assert tax_tier.name == "Updated Standard"
    assert tax_tier.description == "Updated description"
    assert tax_tier.minimum_amount_cents == 15025
    assert timezone.localtime(tax_tier.start_date).date().isoformat() == "2026-02-01"
    assert timezone.localtime(tax_tier.expiration_date).date().isoformat() == "2026-04-01"
    assert tax_tier.display_order == 4
    assert tax_tier.created_by == creator
    assert tax_tier.updated_by == admin


def test_admin_cannot_edit_tax_tier_from_another_year(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    CampYear.objects.create(year=2026)
    other_year = CampYear.objects.create(year=2027)
    tax_tier = create_tax_tier(other_year)
    client.force_login(admin)

    response = client.get(f"/admin/camp/2026/tax-tier/{tax_tier.id}/")

    assert response.status_code == 404


def test_admin_can_delete_tax_tier(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    tax_tier = create_tax_tier(camp_year)
    client.force_login(admin)

    response = client.post(
        f"/admin/camp/2026/tax-tier/{tax_tier.id}/",
        {"action": "delete"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/camp/2026/#tax-tiers"
    assert not TaxTier.objects.filter(pk=tax_tier.pk).exists()


def test_admin_cannot_delete_tax_tier_from_another_year(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    CampYear.objects.create(year=2026)
    other_year = CampYear.objects.create(year=2027)
    tax_tier = create_tax_tier(other_year)
    client.force_login(admin)

    response = client.post(
        f"/admin/camp/2026/tax-tier/{tax_tier.id}/",
        {"action": "delete"},
    )

    assert response.status_code == 404
    assert TaxTier.objects.filter(pk=tax_tier.pk).exists()


def test_admin_can_create_year_scoped_tax_add_on_with_dollar_amount(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    create_tax_add_on(camp_year, name="Sticker", display_order=1)
    client.force_login(admin)

    response = client.post(
        "/admin/camp/2026/",
        {
            "action": "tax_add_on",
            "name": "Hoodie",
            "description": "Camp hoodie",
            "amount_dollars": "25.50",
            "start_date": "2026-01-01",
            "expiration_date": "2026-03-01",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/camp/2026/#tax-add-ons"
    tax_add_on = TaxAddOn.objects.get(camp_year=camp_year, name="Hoodie")
    assert tax_add_on.amount_cents == 2550
    assert timezone.localtime(tax_add_on.start_date).date().isoformat() == "2026-01-01"
    assert timezone.localtime(tax_add_on.start_date).time() == time.min
    assert timezone.localtime(tax_add_on.expiration_date).date().isoformat() == "2026-03-01"
    assert timezone.localtime(tax_add_on.expiration_date).time() == time.min
    assert tax_add_on.display_order == 2
    assert tax_add_on.created_by == admin
    assert tax_add_on.updated_by == admin


def test_admin_tax_add_on_edit_loads_prepopulated_form(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    tax_add_on = create_tax_add_on(
        camp_year,
        name="Hoodie",
        amount_cents=2550,
        start_date=local_midnight(2026, 1, 1),
        expiration_date=local_midnight(2026, 3, 1),
    )
    tax_add_on.description = "Camp hoodie"
    tax_add_on.save(update_fields=["description", "updated_at"])
    client.force_login(admin)

    response = client.get(f"/admin/camp/2026/tax-add-on/{tax_add_on.id}/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Edit Tax Add-on: Hoodie" in body
    assert 'value="Hoodie"' in body
    assert 'value="25.50"' in body
    assert 'value="2026-01-01"' in body
    assert 'value="2026-03-01"' in body
    assert "Camp hoodie" in body
    assert "display_order" not in body
    assert 'href="/admin/camp/2026/#tax-add-ons"' in body
    assert "Delete Tax Add-on" in body
    assert 'class="danger-button"' in body


def test_admin_can_update_tax_add_on(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    creator = create_user(email="creator@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    tax_add_on = TaxAddOn.objects.create(
        camp_year=camp_year,
        name="Hoodie",
        description="Old description",
        amount_cents=2500,
        start_date=local_midnight(2026, 1, 1),
        expiration_date=local_midnight(2026, 3, 1),
        display_order=4,
        created_by=creator,
    )
    client.force_login(admin)

    response = client.post(
        f"/admin/camp/2026/tax-add-on/{tax_add_on.id}/",
        {
            "name": "Updated Hoodie",
            "description": "Updated description",
            "amount_dollars": "30.25",
            "start_date": "2026-02-01",
            "expiration_date": "2026-04-01",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/camp/2026/#tax-add-ons"
    tax_add_on.refresh_from_db()
    assert tax_add_on.name == "Updated Hoodie"
    assert tax_add_on.description == "Updated description"
    assert tax_add_on.amount_cents == 3025
    assert timezone.localtime(tax_add_on.start_date).date().isoformat() == "2026-02-01"
    assert timezone.localtime(tax_add_on.expiration_date).date().isoformat() == "2026-04-01"
    assert tax_add_on.display_order == 4
    assert tax_add_on.created_by == creator
    assert tax_add_on.updated_by == admin


def test_admin_cannot_edit_tax_add_on_from_another_year(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    CampYear.objects.create(year=2026)
    other_year = CampYear.objects.create(year=2027)
    tax_add_on = create_tax_add_on(other_year)
    client.force_login(admin)

    response = client.get(f"/admin/camp/2026/tax-add-on/{tax_add_on.id}/")

    assert response.status_code == 404


def test_admin_can_delete_tax_add_on(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    tax_add_on = create_tax_add_on(camp_year)
    client.force_login(admin)

    response = client.post(
        f"/admin/camp/2026/tax-add-on/{tax_add_on.id}/",
        {"action": "delete"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/camp/2026/#tax-add-ons"
    assert not TaxAddOn.objects.filter(pk=tax_add_on.pk).exists()


def test_admin_cannot_delete_tax_add_on_from_another_year(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    CampYear.objects.create(year=2026)
    other_year = CampYear.objects.create(year=2027)
    tax_add_on = create_tax_add_on(other_year)
    client.force_login(admin)

    response = client.post(
        f"/admin/camp/2026/tax-add-on/{tax_add_on.id}/",
        {"action": "delete"},
    )

    assert response.status_code == 404
    assert TaxAddOn.objects.filter(pk=tax_add_on.pk).exists()


def test_admin_camp_year_edit_renders_tax_tier_move_buttons_at_boundaries(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    create_tax_tier(camp_year, name="Early", display_order=1)
    second = create_tax_tier(camp_year, name="Late", display_order=2)
    client.force_login(admin)

    response = client.get("/admin/camp/2026/")
    body = response.content.decode()

    assert response.status_code == 200
    assert body.count('value="tax_tier_move_up"') == 1
    assert body.count('value="tax_tier_move_down"') == 1
    assert f'href="/admin/camp/2026/tax-tier/{second.id}/"' in body
    assert "Edit: Late" in body


def test_admin_can_move_tax_tier_up(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    first = create_tax_tier(camp_year, name="Early", display_order=1)
    second = create_tax_tier(camp_year, name="Late", display_order=2)
    client.force_login(admin)

    response = client.post(
        "/admin/camp/2026/",
        {"action": "tax_tier_move_up", "item_id": str(second.id)},
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/camp/2026/#tax-tiers"
    first.refresh_from_db()
    second.refresh_from_db()
    assert second.display_order == 1
    assert first.display_order == 2


def test_admin_cannot_move_tax_tier_from_another_year(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    CampYear.objects.create(year=2026)
    other_year = CampYear.objects.create(year=2027)
    other_tier = create_tax_tier(other_year)
    client.force_login(admin)

    response = client.post(
        "/admin/camp/2026/",
        {"action": "tax_tier_move_up", "item_id": str(other_tier.id)},
    )

    assert response.status_code == 404


def test_admin_camp_year_edit_renders_tax_add_on_move_buttons_at_boundaries(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    create_tax_add_on(camp_year, name="Sticker", display_order=1)
    second = create_tax_add_on(camp_year, name="Hoodie", display_order=2)
    client.force_login(admin)

    response = client.get("/admin/camp/2026/")
    body = response.content.decode()

    assert response.status_code == 200
    assert body.count('value="tax_add_on_move_up"') == 1
    assert body.count('value="tax_add_on_move_down"') == 1
    assert f'href="/admin/camp/2026/tax-add-on/{second.id}/"' in body
    assert "Edit: Hoodie" in body


def test_admin_can_move_tax_add_on_down(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    first = create_tax_add_on(camp_year, name="Sticker", display_order=1)
    second = create_tax_add_on(camp_year, name="Hoodie", display_order=2)
    client.force_login(admin)

    response = client.post(
        "/admin/camp/2026/",
        {"action": "tax_add_on_move_down", "item_id": str(first.id)},
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/camp/2026/#tax-add-ons"
    first.refresh_from_db()
    second.refresh_from_db()
    assert second.display_order == 1
    assert first.display_order == 2


def test_admin_can_create_year_scoped_tax_override_with_dollar_amount(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com", first_name="Jane", last_name="Member")
    camp_year = CampYear.objects.create(year=2026)
    client.force_login(admin)

    response = client.post(
        "/admin/camp/2026/",
        {
            "action": "tax_override",
            "user": str(member.id),
            "override_type": TaxOverride.OverrideType.REDUCED_MINIMUM,
            "reduced_minimum_amount_dollars": "50.00",
            "note": "Approved",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/camp/2026/#tax-overrides"
    tax_override = TaxOverride.objects.get(camp_year=camp_year, user=member)
    assert tax_override.reduced_minimum_amount_cents == 5000
    assert tax_override.created_by == admin
    assert tax_override.updated_by == admin


def test_admin_tax_override_rejects_duplicate_user_for_year(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com", first_name="Jane", last_name="Member")
    camp_year = CampYear.objects.create(year=2026)
    TaxOverride.objects.create(
        user=member,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )
    client.force_login(admin)

    response = client.post(
        "/admin/camp/2026/",
        {
            "action": "tax_override",
            "user": str(member.id),
            "override_type": TaxOverride.OverrideType.WAIVED,
            "reduced_minimum_amount_dollars": "",
            "note": "Duplicate",
        },
    )

    assert response.status_code == 200
    assert b"This user already has a tax override for this camp year." in response.content


def test_admin_tax_override_rejects_unnamed_user(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    unnamed_member = create_user(email="member@example.com")
    CampYear.objects.create(year=2026)
    client.force_login(admin)

    response = client.post(
        "/admin/camp/2026/",
        {
            "action": "tax_override",
            "user": str(unnamed_member.id),
            "override_type": TaxOverride.OverrideType.WAIVED,
            "reduced_minimum_amount_dollars": "",
            "note": "No name",
        },
    )

    assert response.status_code == 200
    assert b"Select a valid choice" in response.content
    assert not TaxOverride.objects.filter(user=unnamed_member).exists()


def test_admin_can_delete_tax_override(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com", first_name="Jane", last_name="Member")
    camp_year = CampYear.objects.create(year=2026)
    tax_override = TaxOverride.objects.create(
        user=member,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )
    client.force_login(admin)

    page_response = client.get("/admin/camp/2026/")
    assert 'value="tax_override_delete"' in page_response.content.decode()
    assert 'class="danger-button"' in page_response.content.decode()

    response = client.post(
        "/admin/camp/2026/",
        {"action": "tax_override_delete", "override_id": str(tax_override.id)},
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/camp/2026/#tax-overrides"
    assert not TaxOverride.objects.filter(pk=tax_override.pk).exists()


def test_admin_cannot_delete_tax_override_from_another_year(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com", first_name="Jane", last_name="Member")
    CampYear.objects.create(year=2026)
    other_year = CampYear.objects.create(year=2027)
    tax_override = TaxOverride.objects.create(
        user=member,
        camp_year=other_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )
    client.force_login(admin)

    response = client.post(
        "/admin/camp/2026/",
        {"action": "tax_override_delete", "override_id": str(tax_override.id)},
    )

    assert response.status_code == 404
    assert TaxOverride.objects.filter(pk=tax_override.pk).exists()


def test_pages_admin_lists_pages_in_table_and_separate_create_card(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    page = ContentPage.objects.create(
        title="Arrival Info",
        slug="arrival-info",
        body_markdown="# Arrival",
    )
    client.force_login(admin)

    response = client.get("/admin/pages/")
    body = response.content.decode()

    assert response.status_code == 200
    assert f'href="/admin/pages/{page.slug}/"' in body
    assert "Edit: Arrival Info" in body
    assert f'href="/pages/{page.slug}/"' in body
    assert "Create Page" in body
    assert 'class="danger-button"' not in body


def test_admin_can_create_content_page(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    create_response = client.post(
        "/admin/pages/",
        {
            "action": "create",
            "title": "Arrival",
            "slug": "arrival",
            "body_markdown": "# Arrival",
        },
    )

    assert create_response.status_code == 302
    page = ContentPage.objects.get(slug="arrival")
    assert page.title == "Arrival"


def test_admin_page_edit_loads_by_slug(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    ContentPage.objects.create(title="Arrival", slug="arrival", body_markdown="# Arrival")
    client.force_login(admin)

    response = client.get("/admin/pages/arrival/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Edit Page: Arrival" in body
    assert 'value="Arrival"' in body
    assert 'value="arrival"' in body
    assert "# Arrival" in body
    assert "Update and Back" in body
    assert "Update and View" in body
    assert "Delete Page" in body
    assert 'class="danger-button"' in body


def test_admin_page_edit_unknown_slug_returns_404(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.get("/admin/pages/missing-page/")

    assert response.status_code == 404


def test_admin_can_update_page_and_back(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    page = ContentPage.objects.create(
        title="Arrival",
        slug="arrival",
        body_markdown="# Arrival",
    )
    client.force_login(admin)

    response = client.post(
        "/admin/pages/arrival/",
        {
            "title": "Updated Arrival",
            "slug": "updated-arrival",
            "body_markdown": "# Updated",
            "redirect_to": "back",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/pages/"
    page.refresh_from_db()
    assert page.title == "Updated Arrival"
    assert page.slug == "updated-arrival"
    assert page.body_markdown == "# Updated"


def test_admin_can_update_page_and_view(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    ContentPage.objects.create(title="Arrival", slug="arrival", body_markdown="# Arrival")
    client.force_login(admin)

    response = client.post(
        "/admin/pages/arrival/",
        {
            "title": "Updated Arrival",
            "slug": "updated-arrival",
            "body_markdown": "# Updated",
            "redirect_to": "view",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/pages/updated-arrival/"


def test_admin_page_edit_rejects_duplicate_slug(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    ContentPage.objects.create(title="Taken", slug="taken", body_markdown="Taken")
    page = ContentPage.objects.create(title="Arrival", slug="arrival", body_markdown="# Arrival")
    client.force_login(admin)

    response = client.post(
        "/admin/pages/arrival/",
        {
            "title": "Arrival",
            "slug": "taken",
            "body_markdown": "# Arrival",
            "redirect_to": "back",
        },
    )

    assert response.status_code == 200
    assert b"Content page with this Slug already exists." in response.content
    page.refresh_from_db()
    assert page.slug == "arrival"


def test_admin_can_delete_content_page_from_edit_page(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    page = ContentPage.objects.create(title="Arrival", slug="arrival", body_markdown="# Arrival")
    client.force_login(admin)

    response = client.post("/admin/pages/arrival/", {"action": "delete"})

    assert response.status_code == 302
    assert response["Location"] == "/admin/pages/"
    assert not ContentPage.objects.filter(pk=page.pk).exists()


def test_admin_page_delete_protected_page_shows_error(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    page = ContentPage.objects.create(title="Arrival", slug="arrival", body_markdown="# Arrival")
    CampYear.objects.create(year=2026, dashboard_pre_page=page)
    client.force_login(admin)

    response = client.post("/admin/pages/arrival/", {"action": "delete"}, follow=True)

    assert response.status_code == 200
    assert ContentPage.objects.filter(pk=page.pk).exists()
    assert b"Page is in use and cannot be deleted." in response.content


def test_menus_admin_lists_menus_with_item_summary_and_create_card(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    menu = Menu.objects.create(menu_name="camp-info")
    MenuItem.objects.create(menu=menu, label="Arrival", url="/pages/arrival/", display_order=1)
    MenuItem.objects.create(menu=menu, label="Packing", url="/pages/packing/", display_order=2)
    client.force_login(admin)

    response = client.get("/admin/menus/")
    body = response.content.decode()

    assert response.status_code == 200
    assert 'href="/admin/menus/camp-info/"' in body
    assert "Edit: camp-info" in body
    assert "Arrival, Packing" in body
    assert "Create Menu" in body
    assert "Create Menu Item" not in body


def test_admin_can_create_menu(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.post(
        "/admin/menus/",
        {"action": "create_menu", "menu_name": "camp-info"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/menus/camp-info/"
    assert Menu.objects.filter(menu_name="camp-info").exists()


def test_admin_menu_edit_loads_items_and_url_suggestions(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    CampYear.objects.create(year=2026)
    ContentPage.objects.create(title="Arrival", slug="arrival", body_markdown="# Arrival")
    root_menu, _ = Menu.objects.get_or_create(menu_name=Menu.ROOT_MENU_NAME)
    camp_menu = Menu.objects.create(menu_name="camp-info")
    MenuItem.objects.create(menu=root_menu, label="Arrival", url="/pages/arrival/", display_order=1)
    client.force_login(admin)

    response = client.get("/admin/menus/root/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Edit Menu: root" in body
    assert 'href="/admin/menu-items/' in body
    assert "Edit: Arrival" in body
    assert "/pages/arrival/" in body
    assert "The root menu cannot be deleted." in body
    assert 'src="/static/js/admin-menus.js"' in body
    assert 'data-url-combobox-input="true"' in body
    assert 'data-url-suggestion="/dashboard/"' in body
    assert 'data-url-suggestion="/2026/dashboard/"' in body
    assert 'data-url-suggestion="/2026/taxes/"' in body
    assert 'data-url-suggestion="/profile/"' in body
    assert 'data-url-suggestion="/pages/arrival/"' in body
    assert f'data-url-suggestion="/menu/{camp_menu.menu_name}/"' in body


def test_admin_can_create_route_scoped_menu_item(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    menu = Menu.objects.create(menu_name="camp-info")
    MenuItem.objects.create(
        menu=menu,
        label="Arrival",
        url="/pages/arrival/",
        display_order=1,
    )
    client.force_login(admin)

    response = client.post(
        "/admin/menus/camp-info/",
        {"action": "create_item", "label": "Packing", "url": "/pages/packing/"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/menus/camp-info/#menu-items"
    item = MenuItem.objects.get(menu=menu, label="Packing")
    assert item.url == "/pages/packing/"
    assert item.display_order == 2


def test_admin_can_move_menu_item_up(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    menu = Menu.objects.create(menu_name="camp-info")
    first = MenuItem.objects.create(
        menu=menu,
        label="Arrival",
        url="/pages/arrival/",
        display_order=1,
    )
    second = MenuItem.objects.create(
        menu=menu,
        label="Packing",
        url="/pages/packing/",
        display_order=2,
    )
    client.force_login(admin)

    response = client.post(
        "/admin/menus/camp-info/",
        {"action": "menu_item_move_up", "item_id": str(second.id)},
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/menus/camp-info/#menu-items"
    first.refresh_from_db()
    second.refresh_from_db()
    assert second.display_order == 1
    assert first.display_order == 2


def test_admin_cannot_move_menu_item_from_another_menu(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    menu = Menu.objects.create(menu_name="camp-info")
    other_menu = Menu.objects.create(menu_name="other-info")
    other_item = MenuItem.objects.create(
        menu=other_menu,
        label="Other",
        url="/pages/other/",
        display_order=1,
    )
    client.force_login(admin)

    response = client.post(
        "/admin/menus/camp-info/",
        {"action": "menu_item_move_up", "item_id": str(other_item.id)},
    )

    assert response.status_code == 404
    assert Menu.objects.filter(pk=menu.pk).exists()


def test_admin_can_delete_non_root_menu(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    menu = Menu.objects.create(menu_name="camp-info")
    MenuItem.objects.create(
        menu=menu,
        label="Arrival",
        url="/pages/arrival/",
        display_order=1,
    )
    menu_id = menu.id
    client.force_login(admin)

    response = client.post("/admin/menus/camp-info/", {"action": "delete_menu"})

    assert response.status_code == 302
    assert response["Location"] == "/admin/menus/"
    assert not Menu.objects.filter(pk=menu_id).exists()
    assert not MenuItem.objects.filter(menu_id=menu_id).exists()


def test_admin_cannot_delete_root_menu(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    root_menu, _ = Menu.objects.get_or_create(menu_name=Menu.ROOT_MENU_NAME)
    client.force_login(admin)

    get_response = client.get("/admin/menus/root/")
    assert "The root menu cannot be deleted." in get_response.content.decode()

    response = client.post("/admin/menus/root/", {"action": "delete_menu"}, follow=True)

    assert response.status_code == 200
    assert Menu.objects.filter(pk=root_menu.pk).exists()
    assert b"The root menu cannot be deleted." in response.content


def test_admin_menu_item_edit_loads_form(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    menu = Menu.objects.create(menu_name="camp-info")
    item = MenuItem.objects.create(
        menu=menu,
        label="Arrival",
        url="/pages/arrival/",
        display_order=1,
    )
    client.force_login(admin)

    response = client.get(f"/admin/menu-items/{item.id}/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Edit Menu Item: Arrival" in body
    assert 'value="Arrival"' in body
    assert 'value="/pages/arrival/"' in body
    assert 'href="/admin/menus/camp-info/#menu-items"' in body
    assert "Delete Menu Item" in body


def test_admin_can_update_menu_item(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    menu = Menu.objects.create(menu_name="camp-info")
    item = MenuItem.objects.create(
        menu=menu,
        label="Arrival",
        url="/pages/arrival/",
        display_order=1,
    )
    client.force_login(admin)

    response = client.post(
        f"/admin/menu-items/{item.id}/",
        {"label": "Updated Arrival", "url": "https://example.com/arrival"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/menus/camp-info/#menu-items"
    item.refresh_from_db()
    assert item.label == "Updated Arrival"
    assert item.url == "https://example.com/arrival"


def test_admin_can_delete_menu_item(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    menu = Menu.objects.create(menu_name="camp-info")
    item = MenuItem.objects.create(
        menu=menu,
        label="Arrival",
        url="/pages/arrival/",
        display_order=1,
    )
    client.force_login(admin)

    response = client.post(f"/admin/menu-items/{item.id}/", {"action": "delete"})

    assert response.status_code == 302
    assert response["Location"] == "/admin/menus/camp-info/#menu-items"
    assert not MenuItem.objects.filter(pk=item.pk).exists()


def test_admin_can_upload_and_delete_media(client, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    upload_response = client.post(
        "/admin/media/",
        {"action": "upload", "title": "Map", "image": png_upload()},
    )
    media_item = MediaItem.objects.get(title="Map")
    list_response = client.get("/admin/media/")
    assert 'class="danger-button"' in list_response.content.decode()
    delete_response = client.post(
        "/admin/media/",
        {"action": "delete", "media_id": str(media_item.id)},
    )

    assert upload_response.status_code == 302
    assert delete_response.status_code == 302
    assert not MediaItem.objects.filter(title="Map").exists()


def test_admin_can_switch_stripe_mode(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.post(
        "/admin/stripe/",
        {"action": "switch_mode", "stripe_mode": "live"},
    )

    assert response.status_code == 302
    assert SiteSettings.load().stripe_mode == SiteSettings.StripeMode.LIVE


def test_admin_test_payment_cleanup_leaves_live_payments(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com")
    camp_year = CampYear.objects.create(year=2026)
    client.force_login(admin)
    Payment.objects.create(
        user=member,
        camp_year=camp_year,
        status=Payment.Status.CREATED,
        stripe_mode=Payment.StripeMode.TEST,
        tax_amount_cents=10000,
        add_on_amount_cents=0,
        total_amount_cents=10000,
        tax_tier_name_snapshot="Standard",
        tax_tier_minimum_cents_snapshot=10000,
        checkout_expires_at=timezone.now() + timedelta(hours=1),
    )
    live_payment = Payment.objects.create(
        user=member,
        camp_year=camp_year,
        status=Payment.Status.CREATED,
        stripe_mode=Payment.StripeMode.LIVE,
        tax_amount_cents=10000,
        add_on_amount_cents=0,
        total_amount_cents=10000,
        tax_tier_name_snapshot="Standard",
        tax_tier_minimum_cents_snapshot=10000,
        checkout_expires_at=timezone.now() + timedelta(hours=1),
    )
    page_response = client.get("/admin/stripe/")
    assert 'class="danger-button"' in page_response.content.decode()

    response = client.post(
        "/admin/stripe/",
        {"action": "delete_test_payments", "confirm": "delete"},
    )

    assert response.status_code == 302
    assert list(Payment.objects.values_list("id", flat=True)) == [live_payment.id]
