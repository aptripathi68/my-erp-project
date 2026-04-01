from django.db import migrations


ROLE_GROUP_NAMES = [
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


def sync_existing_users(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("users", "User")

    group_map = {}
    for name in ROLE_GROUP_NAMES:
        group_map[name], _ = Group.objects.get_or_create(name=name)

    role_group_ids = [group.id for group in group_map.values()]

    through = User.groups.through

    for user in User.objects.all():
        through.objects.filter(user_id=user.id, group_id__in=role_group_ids).exclude(
            group_id=group_map[user.role].id
        ).delete()

        through.objects.get_or_create(user_id=user.id, group_id=group_map[user.role].id)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_create_role_groups"),
    ]

    operations = [
        migrations.RunPython(sync_existing_users, noop_reverse),
    ]
