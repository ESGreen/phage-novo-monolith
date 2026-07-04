from django.db import migrations


def create_root_menu(apps, schema_editor):
    Menu = apps.get_model("content", "Menu")
    Menu.objects.get_or_create(menu_name="root")


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0002_menu_menuitem"),
    ]

    operations = [migrations.RunPython(create_root_menu, migrations.RunPython.noop)]
