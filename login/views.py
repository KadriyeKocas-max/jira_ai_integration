# login/views.py
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from .models import UserProfile



def homepage(request):
    return render(request, "login_module/base_home.html")

def login_view(request):
    """Email ve şifre ile login"""
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        # form alanları boşsa
        if not email or not password:
            messages.error(request, "Lütfen email ve şifre girin.")
            return render(request, "login_module/login.html")

        # email ile kullanıcı bul
        try:
            user_obj = User.objects.get(email=email)
            username = user_obj.username
        except User.DoesNotExist:
            messages.error(request, "Bu email ile kayıtlı kullanıcı bulunamadı.")
            return render(request, "login_module/login.html")

        # authenticate
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # role kontrolü
            try:
                role = user.userprofile.role
            except UserProfile.DoesNotExist:
                role = None

            if role == "manager":
                return redirect("managers:dashboard")
            elif role == "worker":
                return redirect("workers:home")
            else:
                return redirect("login:home")  # fallback
        else:
            messages.error(request, "Şifre hatalı!")
            return render(request, "login_module/login.html")

    return render(request, "login_module/login.html")

def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")
        role = request.POST.get("role")

        # şifreler uyuşuyor mu?
        if password1 != password2:
            messages.error(request, "Şifreler uyuşmuyor!")
            return redirect("login:register")

        # username veya email zaten var mı?
        if User.objects.filter(username=username).exists():
            messages.error(request, "Bu kullanıcı adı zaten alınmış.")
            return redirect("login:register")
        if User.objects.filter(email=email).exists():
            messages.error(request, "Bu e-posta zaten kayıtlı.")
            return redirect("login:register")

        # kullanıcı oluştur
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.save()

        # profil ile role bağla
        UserProfile.objects.create(user=user, role=role)

        messages.success(request, "Kayıt başarılı! Giriş yapabilirsiniz.")
        return redirect("login:login")

    return render(request, "login_module/register.html")


def profile_redirect(request):
    """Profil ikonuna tıklandığında yönlendirme"""
    if request.user.is_authenticated:
        try:
            role = request.user.userprofile.role
        except UserProfile.DoesNotExist:
            role = None

        if role == "manager":
            return redirect("managers:dashboard")
        elif role == "worker":
            return redirect("workers:home")
        else:
            return redirect("login:home")

    return redirect("login:login")

def logout_view(request):
    logout(request)
    return redirect("login:login")
