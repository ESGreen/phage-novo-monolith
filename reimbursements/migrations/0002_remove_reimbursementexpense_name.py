from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("reimbursements", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="reimbursementexpense",
            name="name",
        ),
    ]
