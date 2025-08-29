from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import JsonResponse
from django.conf import settings

from .models import WorkerProfile, TodayReport
from .forms import DailyReportForm
from .task_mapping import TASK_MAPPING

from jira import JIRA
from .services.ai_service import analyze_task
from .services.jira_service import create_epic, add_comment, close_task
from .services.ai_service import analyze_with_ai
from .services.jira_service import update_jira
from .services.file_service import check_files

# Plan tiplerini simüle ediyoruz
PLANS = {
    "basic": ["ai", "jira"],              # AI + Jira
    "pro": ["ai", "jira", "file_check"]   # AI + Jira + Dosya Kontrolü
}


# Jira bağlantısı (settings.py’den alıyoruz)
jira = JIRA(
    server=settings.JIRA_URL,
    basic_auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
)


@login_required
def workers_home(request):
    return render(request, "workers_module/home.html")


@login_required
def my_profile(request):
    profile = WorkerProfile.objects.get(user=request.user)
    return render(request, "workers/profile.html", {'profile': profile})


def get_transition_id_by_name(issue_key, transition_name):
    """
    Belirtilen issue için, verilen transition_name'e karşılık gelen transition ID'yi döndürür.
    """
    transitions = jira.transitions(issue_key)
    for t in transitions:
        if t["name"].lower() == transition_name.lower():
            return t["id"]
    return None


def move_issue(issue_key, transition_type):
    """
    TASK_MAPPING'teki transition_type'a göre issue'yu taşır.
    """
    transition_name = TASK_MAPPING.get(transition_type)
    if not transition_name:
        return f"Transition type {transition_type} tanımlı değil."

    transition_id = get_transition_id_by_name(issue_key, transition_name)
    if not transition_id:
        return f"Issue {issue_key} için {transition_name} transition bulunamadı."

    jira.transition_issue(issue_key, transition_id)
    return f"Issue {issue_key}, {transition_name} durumuna geçirildi."


@login_required
def today_report(request):
    if request.method == 'POST':
        form = DailyReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.save()

            # Jira task key ve ilerleme bilgisi
            jira_task_key = form.cleaned_data.get("jira_task_key")
            print("Formdan gelen jira_task_key:", jira_task_key)
            progress_made = form.cleaned_data.get("progress_made", False)
            

            if jira_task_key:
                if progress_made:
                    result = move_issue(jira_task_key, "to_in_progress")
                else:
                    result = move_issue(jira_task_key, "to_done")

                print(result)  # log için

            return redirect('workers:workers-home')
    else:
        form = DailyReportForm()
    return render(request, 'workers_module/today_report.html', {'form': form})


@login_required
def home(request):
    submitted = request.GET.get("submitted", False)
    return render(request, "workers_module/home.html", {"submitted": submitted})

@login_required
def submit_report(request):
    if request.method == "POST":
        form = DailyReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.save()

            # Kullanıcının planını al (şimdilik sabit atayalım)
            user_plan = "pro"  # "basic" veya "pro"

            # AI Analizi
            if "ai" in PLANS[user_plan]:
                analysis = analyze_with_ai(report.report_text)
            else:
                analysis = None

            # Jira Güncellemesi
            if "jira" in PLANS[user_plan]:
                update_jira("TASK-123", analysis)

            # Dosya kontrolü (sadece Pro plan)
            if "file_check" in PLANS[user_plan]:
                check_files(request.user)

            return redirect("/workers/home/?submitted=true")


@login_required
def jira_profile(request):
    """
    Dashboard: Dahil olduğun projelerdeki tüm görevleri getir.
    """
    projects = getattr(settings, "MY_JIRA_PROJECTS", [])
    if not projects:
        return render(
            request,
            "workers_module/jira_dashboard.html",
            {"project_issues": {}, "error": "Dahil olduğun projeler settings.py içinde tanımlı değil."}
        )

    jql = f"project in ({','.join(projects)}) ORDER BY created DESC"
    issues = jira.search_issues(jql, maxResults=200, fields="summary,status,assignee,project")

    project_issues = {}
    for issue in issues:
        proj = issue.fields.project
        if proj.key not in project_issues:
            project_issues[proj.key] = {"name": proj.name, "issues": []}
        project_issues[proj.key]["issues"].append(issue)

    return render(
        request,
        "workers_module/jira_dashboard.html",
        {"project_issues": project_issues, "limited_to": projects}
    )


@login_required
def view_progress(request):
    return render(request, 'workers/progress.html')


@login_required
def view_team(request):
    return render(request, 'workers/team_dashboard.html')
