from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings

from .models import WorkerProfile, TodayReport
from .forms import DailyReportForm
from .task_mapping import TASK_MAPPING

from .services.jira_service import get_jira_tasks_for_user, get_jira_client, ACTION_TO_TRANSITION
from .services.ai_service import analyze_and_update_jira

# Plan tiplerini simüle ediyoruz
PLANS = {
    "basic": ["ai", "jira"],              # AI + Jira
    "pro": ["ai", "jira", "file_check"]   # AI + Jira + Dosya Kontrolü
}


@login_required
def workers_home(request):
    return render(request, "workers_module/home.html")


@login_required
def my_profile(request):
    profile = WorkerProfile.objects.get(user=request.user)
    return render(request, "workers/profile.html", {'profile': profile})


@login_required
def today_report(request):
    if request.method == "POST":
        form = DailyReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.save()
            return redirect("workers:home")
    else:
        form = DailyReportForm()
    return render(request, "workers_module/today_report.html", {"form": form})


@login_required
def home(request):
    submitted = request.GET.get("submitted", False)
    return render(request, "workers_module/home.html", {"submitted": submitted})



@login_required
def submit_report(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=405)

    form = DailyReportForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"status": "error", "errors": form.errors}, status=400)

    report = form.save(commit=False)
    report.user = request.user
    report.save()

    # Kullanıcının planını güvenli şekilde al
    profile = getattr(request.user, "workerprofile", None)
    user_plan = profile.plan if profile else "basic"

    response_data = {
        "status": "success",
        "report_id": report.id,
        "actions": [],
        "new_local_tasks": []
    }

    # Eğer AI planındaysa
    if "ai" in PLANS[user_plan]:
        jira_tasks = get_jira_tasks_for_user(request.user)
        result = analyze_and_update_jira(report.report_text, jira_tasks)
        response_data["actions"] = result.get("actions", [])
        response_data["new_local_tasks"] = result.get("new_local_tasks", [])

    # Eğer file_check planındaysa
    if "file_check" in PLANS[user_plan]:
        from .services.file_service import check_files
        check_files(request.user)

    return JsonResponse(response_data)


@login_required
def jira_profile(request):
    projects = getattr(settings, "MY_JIRA_PROJECTS", [])
    if not projects:
        return render(request, "workers_module/jira_dashboard.html", {
            "project_issues": {},
            "error": "Dahil olduğun projeler settings.py içinde tanımlı değil."
        })

    jira = get_jira_client()
    if jira is None:
        return render(request, "workers_module/jira_dashboard.html", {
            "project_issues": {},
            "error": "Jira’ya bağlanılamadı."
        })

    jql = f"project in ({','.join(projects)}) ORDER BY created DESC"
    try:
        issues = jira.search_issues(
            jql,
            maxResults=200,
            fields="summary,status,assignee,project"
        )
    except Exception as e:
        return render(request, "workers_module/jira_dashboard.html", {
            "project_issues": {},
            "error": f"Jira sorgu hatası: {e}"
        })

    project_issues = {}
    for issue in issues:
        proj = issue.fields.project
        if proj.key not in project_issues:
            project_issues[proj.key] = {"name": proj.name, "issues": []}
        project_issues[proj.key]["issues"].append(issue)

    return render(request, "workers_module/jira_dashboard.html", {
        "project_issues": project_issues,
        "limited_to": projects
    })



@login_required
def view_progress(request):
    return render(request, 'workers/progress.html')


@login_required
def view_team(request):
    return render(request, 'workers/team_dashboard.html')
