from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

class WorkerProfile(models.Model):
    ROLE_CHOICES = [
        ("manager", "Manager"),
        ("worker", "Worker"),
    ]

    PLAN_CHOICES = [
        ("basic", "Basic"),   # AI + Jira
        ("pro", "Pro"),       # AI + Jira + File Check
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default="worker"   # 🔹 Varsayılan: worker
    )
    plan = models.CharField(
        max_length=50,
        choices=PLAN_CHOICES,
        default="basic"    # 🔹 Varsayılan: basic
    )

    def __str__(self):
        return f"{self.user.username} ({self.role}, {self.plan})"




class TodayReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    report_text = models.TextField()
    jira_task_key = models.CharField(max_length=50, blank=True, null=True)  # Örn: PROJ-123
    progress_made = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.created_at.date()}"

class WorkerTask(models.Model):
    jira_key = models.CharField(max_length=50)
    title = models.CharField(max_length=255, default="No Title")
    assignee = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class TaskSubItem(models.Model):
    task = models.ForeignKey(WorkerTask, on_delete=models.CASCADE, related_name='subitems')
    content = models.TextField()
    is_done = models.BooleanField(default=False)
