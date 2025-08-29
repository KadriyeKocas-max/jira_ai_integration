from django.shortcuts import render

def dashboard(request):
    return render(request, "managers/dashboard.html")

def reports(request):
    return render(request, "managers/reports.html")
