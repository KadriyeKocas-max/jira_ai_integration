from django.contrib import admin
from .models import TodayReport  # modelini import et

@admin.register(TodayReport)
class TodayReportAdmin(admin.ModelAdmin):
    list_display = ("user", "report_text", "created_at")  # tablo görünümü için alanlar
    search_fields = ("user__username", "report_text")
    list_filter = ("created_at",)
