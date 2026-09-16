from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("camp", "0003_campyear_camp_survey"),
    ]

    operations = [
        migrations.CreateModel(
            name="Reimbursement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reimbursement_number", models.CharField(max_length=20, unique=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("submitted", "Submitted"), ("paid", "Paid"), ("rejected", "Rejected")], default="draft", max_length=20)),
                ("requester_notes", models.TextField(blank=True, max_length=10000)),
                ("payer_notes", models.TextField(blank=True, max_length=10000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("rejected_at", models.DateTimeField(blank=True, null=True)),
                ("camp_year", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reimbursements", to="camp.campyear")),
                ("paid_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="paid_reimbursements", to=settings.AUTH_USER_MODEL)),
                ("rejected_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="rejected_reimbursements", to=settings.AUTH_USER_MODEL)),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reimbursements", to=settings.AUTH_USER_MODEL)),
                ("split_from", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="split_reimbursements", to="reimbursements.reimbursement")),
            ],
        ),
        migrations.CreateModel(
            name="ReimbursementExpenseCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("camp_year", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reimbursement_expense_categories", to="camp.campyear")),
            ],
        ),
        migrations.CreateModel(
            name="ReimbursementPayoutProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("method", models.CharField(choices=[("paper_check", "Paper check"), ("zelle", "Zelle")], max_length=20)),
                ("zelle_email", models.EmailField(blank=True, max_length=254)),
                ("check_payee_name", models.CharField(blank=True, max_length=200)),
                ("check_address_line_1", models.CharField(blank=True, max_length=200)),
                ("check_address_line_2", models.CharField(blank=True, max_length=200)),
                ("check_city", models.CharField(blank=True, max_length=200)),
                ("check_state", models.CharField(blank=True, max_length=2)),
                ("check_postal_code", models.CharField(blank=True, max_length=10)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="reimbursement_payout_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ReimbursementExpense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(max_length=2000)),
                ("amount_cents", models.PositiveBigIntegerField()),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="expenses", to="reimbursements.reimbursementexpensecategory")),
                ("reimbursement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="expenses", to="reimbursements.reimbursement")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="ReimbursementPayoutSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("method", models.CharField(choices=[("paper_check", "Paper check"), ("zelle", "Zelle")], max_length=20)),
                ("zelle_email", models.EmailField(blank=True, max_length=254)),
                ("check_payee_name", models.CharField(blank=True, max_length=200)),
                ("check_address_line_1", models.CharField(blank=True, max_length=200)),
                ("check_address_line_2", models.CharField(blank=True, max_length=200)),
                ("check_city", models.CharField(blank=True, max_length=200)),
                ("check_state", models.CharField(blank=True, max_length=2)),
                ("check_postal_code", models.CharField(blank=True, max_length=10)),
                ("reimbursement", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="payout_snapshot", to="reimbursements.reimbursement")),
            ],
        ),
        migrations.CreateModel(
            name="ReimbursementReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("receipt_type", models.CharField(choices=[("image", "Image"), ("pdf", "PDF"), ("explanation", "Explanation")], max_length=20)),
                ("original_filename", models.CharField(blank=True, max_length=255)),
                ("file_path", models.CharField(blank=True, max_length=500)),
                ("content_type", models.CharField(blank=True, max_length=100)),
                ("size_bytes", models.PositiveBigIntegerField(blank=True, null=True)),
                ("explanation", models.TextField(blank=True, max_length=10000)),
                ("reimbursement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="receipts", to="reimbursements.reimbursement")),
            ],
        ),
        migrations.AddIndex(model_name="reimbursement", index=models.Index(fields=["camp_year", "status"], name="reimburseme_camp_ye_740a21_idx")),
        migrations.AddIndex(model_name="reimbursement", index=models.Index(fields=["requester", "camp_year", "created_at"], name="reimburseme_request_d4ed04_idx")),
        migrations.AddConstraint(model_name="reimbursement", constraint=models.CheckConstraint(condition=models.Q(models.Q(("paid_at__isnull", False), ("paid_by__isnull", False), ("status", "paid")), models.Q(models.Q(("status", "paid"), _negated=True), ("paid_at__isnull", True), ("paid_by__isnull", True)), _connector="OR"), name="reimbursement_paid_metadata_consistent")),
        migrations.AddConstraint(model_name="reimbursement", constraint=models.CheckConstraint(condition=models.Q(models.Q(("rejected_at__isnull", False), ("rejected_by__isnull", False), ("status", "rejected")), models.Q(models.Q(("status", "rejected"), _negated=True), ("rejected_at__isnull", True), ("rejected_by__isnull", True)), _connector="OR"), name="reimbursement_rejected_metadata_consistent")),
        migrations.AddConstraint(model_name="reimbursementexpensecategory", constraint=models.UniqueConstraint(Lower("name"), models.F("camp_year"), name="unique_reimbursement_category_name_ci_year")),
        migrations.AddConstraint(model_name="reimbursementexpense", constraint=models.CheckConstraint(condition=models.Q(("amount_cents__gt", 0)), name="reimbursement_expense_amount_positive")),
        migrations.AddConstraint(model_name="reimbursementexpense", constraint=models.CheckConstraint(condition=models.Q(("amount_cents__lte", 100000000)), name="reimbursement_expense_amount_maximum")),
    ]
