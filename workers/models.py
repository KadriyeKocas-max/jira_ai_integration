from django.db import models
from django.contrib.auth.models import User

class WorkerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.user.username



class TodayReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    report_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.created_at}"