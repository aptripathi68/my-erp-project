from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse


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


class UserManagementViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin1",
            password="test123",
            role="Admin",
            is_staff=True,
        )

    def test_admin_can_create_user_from_app_screen(self):
        self.client.login(username="admin1", password="test123")
        response = self.client.post(
            reverse("users:user_create"),
            {
                "username": "planner2",
                "first_name": "Plan",
                "last_name": "User",
                "email": "planner@example.com",
                "role": "Planning",
                "employee_id": "EMP-001",
                "phone": "9999999999",
                "password": "secret123",
                "confirm_password": "secret123",
                "is_staff": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        created = User.objects.get(username="planner2")
        self.assertEqual(created.role, "Planning")
        self.assertTrue(created.groups.filter(name="Planning").exists())

    def test_viewer_cannot_open_user_management(self):
        viewer = User.objects.create_user(username="viewer1", password="test123", role="Viewer")
        self.client.login(username="viewer1", password="test123")
        response = self.client.get(reverse("users:user_list"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "do not have permission")
