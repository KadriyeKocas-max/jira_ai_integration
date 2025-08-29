from django import forms
from .models import TodayReport

class DailyReportForm(forms.ModelForm):
    jira_task_key = forms.CharField(required=False)  # Jira issue key, örn: PROJ-123
    progress_made = forms.BooleanField(required=False)

    class Meta:
        model = TodayReport
        fields = ['report_text', 'jira_task_key', 'progress_made']
        widgets = {
            'report_text': forms.Textarea(attrs={
                'placeholder': 'Write what you did today...',
                'class': 'form-control',
                'rows': 5,
            }),
        }
