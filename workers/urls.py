from django.urls import path
from . import views

app_name = "workers"

urlpatterns = [
    path('', views.workers_home, name='workers-home'),  # ana sayfa
    path('profile/', views.my_profile, name='my_profile'),
    path("home/", views.home, name="home"),
    path('today-report/', views.today_report, name='today_report'),
    path('submit-report/', views.submit_report, name='submit-report'),
    path("jira/", views.jira_profile, name="jira_profile"),
    path('progress/', views.view_progress, name='view_progress'),
    path('team/', views.view_team, name='view_team'),
]
