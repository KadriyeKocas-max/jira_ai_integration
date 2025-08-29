from django.urls import path

from .views import dashboard
from .views import reports

urlpatterns = [
    path('', dashboard, name='manager-dashboard'),
    path('reports/', reports, name='manager-reports'),
]
