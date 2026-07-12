from django.db import migrations


def seed_root_menu_items(apps, schema_editor):
    Menu = apps.get_model("content", "Menu")
    MenuItem = apps.get_model("content", "MenuItem")
    root_menu, _ = Menu.objects.get_or_create(menu_name="root")
    if MenuItem.objects.filter(menu=root_menu).exists():
        return

    MenuItem.objects.create(menu=root_menu, label="Dashboard", url="/dashboard/", display_order=1)
    MenuItem.objects.create(menu=root_menu, label="Phage Book", url="/phagebook/", display_order=2)
    MenuItem.objects.create(menu=root_menu, label="Profile", url="/profile/", display_order=3)


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0003_create_root_menu"),
    ]

    operations = [migrations.RunPython(seed_root_menu_items, migrations.RunPython.noop)]
