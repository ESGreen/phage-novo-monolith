from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("reimbursements", "0002_remove_reimbursementexpense_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="reimbursement",
            name="submitted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="submitted_reimbursements",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
