from __future__ import annotations

from datetime import time, timedelta
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from camp.models import CampYear, TaxAddOn, TaxOverride, TaxTier
from content.models import ContentPage, MediaItem, Menu, MenuItem
from core.models import SiteSettings
from payments.models import Payment

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


def create_tax_tier(
    camp_year: CampYear,
    *,
    name: str = "Standard",
    display_order: int = 1,
) -> TaxTier:
    now = timezone.now()
    return TaxTier.objects.create(
        camp_year=camp_year,
        name=name,
        minimum_amount_cents=10000,
        start_date=now,
        expiration_date=now + timedelta(days=30),
        display_order=display_order,
    )


def create_tax_add_on(
    camp_year: CampYear,
    *,
    name: str = "Hoodie",
    display_order: int = 1,
) -> TaxAddOn:
    now = timezone.now()
    return TaxAddOn.objects.create(
        camp_year=camp_year,
        name=name,
        amount_cents=2500,
        start_date=now,
        expiration_date=now + timedelta(days=30),
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


def test_admin_camp_year_edit_renders_tax_tier_move_buttons_at_boundaries(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    camp_year = CampYear.objects.create(year=2026)
    create_tax_tier(camp_year, name="Early", display_order=1)
    create_tax_tier(camp_year, name="Late", display_order=2)
    client.force_login(admin)

    response = client.get("/admin/camp/2026/")
    body = response.content.decode()

    assert response.status_code == 200
    assert body.count('value="tax_tier_move_up"') == 1
    assert body.count('value="tax_tier_move_down"') == 1


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
    create_tax_add_on(camp_year, name="Hoodie", display_order=2)
    client.force_login(admin)

    response = client.get("/admin/camp/2026/")
    body = response.content.decode()

    assert response.status_code == 200
    assert body.count('value="tax_add_on_move_up"') == 1
    assert body.count('value="tax_add_on_move_down"') == 1


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


def test_admin_can_create_and_delete_content_page(client) -> None:
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
    page = ContentPage.objects.get(slug="arrival")
    delete_response = client.post(
        "/admin/pages/",
        {"action": "delete", "page_id": str(page.id)},
    )

    assert create_response.status_code == 302
    assert delete_response.status_code == 302
    assert not ContentPage.objects.filter(slug="arrival").exists()


def test_admin_can_create_menu_and_menu_item(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    create_menu_response = client.post(
        "/admin/menus/",
        {"action": "create_menu", "menu_name": "camp-info"},
    )
    menu = Menu.objects.get(menu_name="camp-info")
    create_item_response = client.post(
        "/admin/menus/",
        {
            "action": "create_item",
            "menu": str(menu.id),
            "label": "Arrival",
            "url": "/pages/arrival/",
            "display_order": "1",
        },
    )

    assert create_menu_response.status_code == 302
    assert create_item_response.status_code == 302
    assert MenuItem.objects.get(menu=menu).label == "Arrival"


def test_admin_cannot_delete_root_menu(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)
    root_menu, _ = Menu.objects.get_or_create(menu_name=Menu.ROOT_MENU_NAME)

    response = client.post(
        "/admin/menus/",
        {"action": "delete_menu", "menu_id": str(root_menu.id)},
        follow=True,
    )

    assert response.status_code == 200
    assert Menu.objects.filter(pk=root_menu.pk).exists()
    assert b"The root menu cannot be deleted." in response.content


def test_admin_can_upload_and_delete_media(client, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    upload_response = client.post(
        "/admin/media/",
        {"action": "upload", "title": "Map", "image": png_upload()},
    )
    media_item = MediaItem.objects.get(title="Map")
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

    response = client.post(
        "/admin/stripe/",
        {"action": "delete_test_payments", "confirm": "delete"},
    )

    assert response.status_code == 302
    assert list(Payment.objects.values_list("id", flat=True)) == [live_payment.id]
