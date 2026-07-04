from django.db import migrations


def create_site_settings(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettings.objects.get_or_create(pk=1, defaults={"stripe_mode": "test"})


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [migrations.RunPython(create_site_settings, migrations.RunPython.noop)]
