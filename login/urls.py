# login/urls.py
from django.urls import path
from . import views

app_name = "login"  # namespace için

urlpatterns = [
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_redirect, name='profile_redirect'),
    path("logout/", views.logout_view, name="logout"),
    path("home/", views.homepage, name="home"),  # Base home sayfası
    
]
