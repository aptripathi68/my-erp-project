from django.db import migrations


ROLE_GROUPS = [
    "Admin",
    "Planning",
    "Marketing",
    "Accounts",
    "Procurement",
    "Dispatch",
    "Management",
    "Store",
    "Viewer",
]


def create_role_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ROLE_GROUPS:
        Group.objects.get_or_create(name=name)


def remove_role_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLE_GROUPS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_alter_user_role"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_role_groups, remove_role_groups),
    ]
