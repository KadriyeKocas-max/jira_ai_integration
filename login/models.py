from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('manager', 'Manager'),
        ('worker', 'Worker'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='worker')

    def __str__(self):
        return f"{self.user.username} - {self.role}"
