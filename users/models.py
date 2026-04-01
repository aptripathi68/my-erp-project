from django.contrib.auth.models import AbstractUser
from django.db import models


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


class User(AbstractUser):
    ROLE_CHOICES = [
        ('Admin', 'Administrator'),
        ('Planning', 'Planning'),
        ('Marketing', 'Marketing'),
        ('Accounts', 'Accounts'),
        ('Procurement', 'Procurement'),
        ('Dispatch', 'Dispatch'),
        ('Management', 'Management'),
        ('Store', 'Store Manager'),
        ('Viewer', 'Viewer Only'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Viewer')
    phone = models.CharField(max_length=15, blank=True)
    employee_id = models.CharField(max_length=50, blank=True)
    
    class Meta:
        db_table = 'users'

    def sync_role_group(self):
        """
        Keep Django auth groups aligned with the selected ERP role.
        Only the ERP role groups are normalized; unrelated groups stay untouched.
        """
        from django.contrib.auth.models import Group

        current_groups = self.groups.filter(name__in=ROLE_GROUP_NAMES)
        target_group, _ = Group.objects.get_or_create(name=self.role)

        stale_group_ids = list(current_groups.exclude(id=target_group.id).values_list("id", flat=True))
        if stale_group_ids:
            self.groups.remove(*stale_group_ids)

        if not self.groups.filter(id=target_group.id).exists():
            self.groups.add(target_group)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sync_role_group()
    
    def __str__(self):
        return f"{self.username} - {self.role}"
