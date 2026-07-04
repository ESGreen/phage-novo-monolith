from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from camp.models import CampYear, TaxAddOn, TaxOverride, TaxTier

pytestmark = pytest.mark.django_db


def create_user(email: str = "member@example.com"):
    return get_user_model().objects.create_user(email=email, password="test-password-1")


def create_camp_year(year: int = 2026) -> CampYear:
    return CampYear.objects.create(year=year)


def create_tax_tier(camp_year: CampYear, name: str = "Standard", minimum: int = 10000) -> TaxTier:
    now = timezone.now()
    return TaxTier.objects.create(
        camp_year=camp_year,
        name=name,
        minimum_amount_cents=minimum,
        start_date=now - timedelta(days=1),
        expiration_date=now + timedelta(days=1),
    )


def create_tax_add_on(camp_year: CampYear, name: str = "Hoodie", amount: int = 2500) -> TaxAddOn:
    now = timezone.now()
    return TaxAddOn.objects.create(
        camp_year=camp_year,
        name=name,
        amount_cents=amount,
        start_date=now - timedelta(days=1),
        expiration_date=now + timedelta(days=1),
    )


def test_taxes_page_requires_login(client) -> None:
    create_camp_year()

    response = client.get("/2026/taxes/")

    assert response.status_code == 302
    assert response["Location"] == "/login/?next=/2026/taxes/"


def test_unknown_tax_year_returns_404(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.get("/2026/taxes/")

    assert response.status_code == 404


def test_taxes_page_shows_unavailable_when_no_tiers(client) -> None:
    user = create_user()
    client.force_login(user)
    create_camp_year()

    response = client.get("/2026/taxes/")

    assert response.status_code == 200
    assert b"Taxes are not currently available" in response.content
    assert b"Start Checkout" not in response.content


def test_taxes_page_shows_multiple_available_tiers_and_add_ons(client) -> None:
    user = create_user()
    client.force_login(user)
    camp_year = create_camp_year()
    create_tax_tier(camp_year, name="Budget", minimum=5000)
    create_tax_tier(camp_year, name="Standard", minimum=10000)
    create_tax_add_on(camp_year, name="Hoodie", amount=2500)

    response = client.get("/2026/taxes/")

    assert response.status_code == 200
    assert b"Budget" in response.content
    assert b"$50.00 minimum" in response.content
    assert b"Standard" in response.content
    assert b"$100.00 minimum" in response.content
    assert b"Hoodie" in response.content
    assert b"$25.00" in response.content
    assert b"Start Checkout" in response.content


def test_reduced_minimum_override_is_shown_and_honored(client, mocker) -> None:
    user = create_user()
    client.force_login(user)
    camp_year = create_camp_year()
    tier = create_tax_tier(camp_year, name="Standard", minimum=10000)
    mocker.patch(
        "payments.stripe_client.stripe.checkout.Session.create",
        return_value={
            "id": "cs_test_reduced",
            "url": "https://checkout.example/reduced",
            "expires_at": int((timezone.now() + timedelta(hours=1)).timestamp()),
        },
    )
    TaxOverride.objects.create(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.REDUCED_MINIMUM,
        reduced_minimum_amount_cents=5000,
    )

    get_response = client.get("/2026/taxes/")
    post_response = client.post(
        "/2026/taxes/",
        {"tax_tier": str(tier.id), "tax_amount_dollars": "75.00", "add_ons": []},
    )

    assert b"reduced to $50.00" in get_response.content
    assert post_response.status_code == 302
    assert post_response["Location"] == "https://checkout.example/reduced"


def test_tax_waived_override_blocks_checkout_form(client) -> None:
    user = create_user()
    client.force_login(user)
    camp_year = create_camp_year()
    create_tax_tier(camp_year)
    TaxOverride.objects.create(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )

    response = client.get("/2026/taxes/")

    assert response.status_code == 200
    assert b"Taxes Waived" in response.content
    assert b"No payment is required" in response.content
    assert b"Start Checkout" not in response.content


def test_tax_page_rejects_below_minimum_amount(client) -> None:
    user = create_user()
    client.force_login(user)
    camp_year = create_camp_year()
    tier = create_tax_tier(camp_year, minimum=10000)

    response = client.post(
        "/2026/taxes/",
        {"tax_tier": str(tier.id), "tax_amount_dollars": "99.99", "add_ons": []},
    )

    assert response.status_code == 200
    assert b"Enter at least $100.00." in response.content


def test_dashboard_shows_waived_tax_status(client) -> None:
    user = create_user()
    client.force_login(user)
    camp_year = create_camp_year()
    TaxOverride.objects.create(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )

    response = client.get("/2026/dashboard/")

    assert response.status_code == 200
    assert b"Waived" in response.content
