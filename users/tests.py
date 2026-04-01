from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


User = get_user_model()


class UserRoleSyncTests(TestCase):
    def test_user_role_adds_matching_group(self):
        user = User.objects.create_user(
            username="planner",
            password="test123",
            role="Planning",
        )

        self.assertTrue(user.groups.filter(name="Planning").exists())

    def test_role_change_replaces_old_role_group(self):
        user = User.objects.create_user(
            username="accounts1",
            password="test123",
            role="Accounts",
        )
        user.role = "Procurement"
        user.save()

        self.assertTrue(user.groups.filter(name="Procurement").exists())
        self.assertFalse(user.groups.filter(name="Accounts").exists())

    def test_non_role_groups_are_preserved(self):
        extra_group = Group.objects.create(name="Can Approve Special Cases")
        user = User.objects.create_user(
            username="manager1",
            password="test123",
            role="Management",
        )
        user.groups.add(extra_group)
        user.role = "Dispatch"
        user.save()

        self.assertTrue(user.groups.filter(name="Dispatch").exists())
        self.assertTrue(user.groups.filter(name="Can Approve Special Cases").exists())
