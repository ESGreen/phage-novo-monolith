from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards_payment_modes(apps, schema_editor):
    payment = apps.get_model("payments", "Payment")
    payment_log = apps.get_model("payments", "PaymentLog")

    payment.objects.filter(mode="test").update(mode="stripe_test")
    payment.objects.filter(mode="live").update(mode="stripe_live")
    payment.objects.filter(created_by__isnull=True).exclude(mode="manual").update(
        created_by_id=models.F("user_id"),
    )

    payment_log.objects.filter(mode="test").update(mode="stripe_test")
    payment_log.objects.filter(mode="live").update(mode="stripe_live")


def backwards_payment_modes(apps, schema_editor):
    payment = apps.get_model("payments", "Payment")
    payment_log = apps.get_model("payments", "PaymentLog")

    payment.objects.filter(mode="stripe_test").update(mode="test")
    payment.objects.filter(mode="stripe_live").update(mode="live")
    payment.objects.filter(mode="manual").update(mode="test")

    payment_log.objects.filter(mode="stripe_test").update(mode="test")
    payment_log.objects.filter(mode="stripe_live").update(mode="live")
    payment_log.objects.filter(mode="manual").update(mode="")


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="payment",
            name="payments_pa_stripe__3dc334_idx",
        ),
        migrations.RenameField(
            model_name="payment",
            old_name="stripe_mode",
            new_name="mode",
        ),
        migrations.RenameField(
            model_name="paymentlog",
            old_name="stripe_mode",
            new_name="mode",
        ),
        migrations.AlterField(
            model_name="payment",
            name="mode",
            field=models.CharField(
                choices=[
                    ("stripe_test", "Stripe test"),
                    ("stripe_live", "Stripe live"),
                    ("manual", "Manual"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="paymentlog",
            name="mode",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="payment",
            name="note",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="payment",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_payments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(forwards_payment_modes, backwards_payment_modes),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(
                fields=["mode", "status"],
                name="payments_pa_mode_b5538c_idx",
            ),
        ),
    ]
