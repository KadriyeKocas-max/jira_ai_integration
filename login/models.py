from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('manager', 'Manager'),
        ('worker', 'Worker'),
    )

    EXPERTISE_CHOICES = (
        ("W&B", "Weight & Balance"),
        ("Route", "Route"),
        ("Terrain", "Terrain"),
        ("Navigation", "Navigation"),
        ("Fuel", "Fuel"),
        # istersen buraya sabit seçenekler ekleyebilirsin
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, null=True, blank=True)
    expertise = models.CharField(max_length=50, choices=EXPERTISE_CHOICES, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.role} - {self.expertise}"
