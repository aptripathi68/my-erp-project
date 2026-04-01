from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models

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
    
    def __str__(self):
        return f"{self.username} - {self.role}"
