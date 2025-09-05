# views.py — gerekli importları kontrol et / güncelle
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
import logging

from .models import WorkerProfile, TodayReport, WorkerTask, TaskSubItem
from .forms import DailyReportForm
from .task_mapping import TASK_MAPPING

from .services.ai_service import (
    extract_subtasks_from_description,
    update_subtasks_with_report
)

from .services.jira_service import (
    get_jira_client,
    get_jira_tasks_for_user,
    move_task,
    add_comment
)

logger = logging.getLogger(__name__)
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

    profile = getattr(request.user, "workerprofile", None)
    user_plan = profile.plan if profile else "basic"

    response_data = {
        "status": "success",
        "report_id": report.id,
        "updated_tasks": []
    }

    # AI planı aktifse
    if "ai" in PLANS.get(user_plan, []):
        jira_tasks = get_jira_tasks_for_user(request.user)
        jira_dict = {t["key"]: t for t in jira_tasks}

        for jt in jira_tasks:
            task_key = jt["key"]
            task_info = jira_dict.get(task_key)
            if not task_info:
                continue

            # WorkerTask oluştur / al
            worker_task, _ = WorkerTask.objects.get_or_create(
                jira_key=task_key,
                assignee=request.user,
                defaults={
                    "title": task_info.get("summary", ""),
                    "description": task_info.get("description", "")
                }
            )

            # 1. Description’dan alt-görev çıkar
            ai_result = extract_subtasks_from_description(
                task_key,
                worker_task.description
            )
            subtasks_ai = ai_result.get("subtasks", [])

            # DB’de alt-görevleri oluştur (ilk defa ise)
            for st in subtasks_ai:
                TaskSubItem.objects.get_or_create(
                    task=worker_task,
                    content=st["content"]
                )

            # 2. Kullanıcı raporuna göre alt-görevleri güncelle
            db_subitems = list(worker_task.subitems.all())
            subtasks_dict = [{"content": s.content} for s in db_subitems]

            ai_progress = update_subtasks_with_report(
                task_key,
                subtasks_dict,
                report.report_text
            )

            # AI sonucunu DB’ye işle
            for idx, st in enumerate(ai_progress["subtasks"]):
                if idx < len(db_subitems):
                    sub = db_subitems[idx]
                    sub.is_done = st["is_done"]
                    sub.save()

            progress = ai_progress.get("progress", 0)
            action = ai_progress.get("action", "in_progress")

            # Eğer tüm alt-görevler tamamlandıysa Jira’da Done
            if action == "done":
                move_task(task_key, "Done")
                add_comment(task_key, f"Tüm alt-görevler tamamlandı: {report.report_text}")

            response_data["updated_tasks"].append({
                "task_key": task_key,
                "progress": progress,
                "action": action,
                "subtasks": [
                    {"content": s.content, "is_done": s.is_done} for s in worker_task.subitems.all()
                ]
            })

    # Dosya kontrolü opsiyonel
    if "file_check" in PLANS.get(user_plan, []):
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
    user = request.user
    jira_tasks = get_jira_tasks_for_user(user)

    task_details = []

    # Kullanıcının en son günlük raporu
    last_report = TodayReport.objects.filter(user=user).order_by('-created_at').first()
    last_report_text = last_report.report_text if last_report else ""

    for jt in jira_tasks:
        task_key = jt["key"]
        description = jt.get("description") or ""

        # WorkerTask kaydını al/oluştur
        task, created = WorkerTask.objects.get_or_create(
            jira_key=task_key,
            assignee=user,
            defaults={
                "title": jt.get("summary", ""),
                "description": description
            }
        )

        # AI ile description’dan alt-görevleri çıkar
        ai_result = update_subtasks_with_report(task_key, description, max_subtasks=3)  # advanced, context-aware
        subtasks_from_ai = ai_result.get("subtasks", [])

        # DB’deki alt-görevleri güncelle / ekle
        existing_subs = list(task.subitems.all())

        for idx, st in enumerate(subtasks_from_ai):
            if idx < len(existing_subs):
                sub = existing_subs[idx]
                sub.content = st["content"]
                sub.save()
            else:
                TaskSubItem.objects.create(task=task, content=st["content"], is_done=st.get("is_done", False))

        # Kullanıcı raporuna göre alt-görev durumlarını AI ile güncelle
        db_subitems = list(task.subitems.all())
        subtasks_dict = [{"content": s.content, "is_done": s.is_done} for s in db_subitems]

        # Eğer ilerleme/güncelleme mantığı varsa (AI’den gelen progress/action)
        progress = ai_result.get("progress", 0)
        action = ai_result.get("action", "in_progress")

        # AI’den gelen is_done değerlerini DB’ye yansıt
        for idx, st in enumerate(subtasks_from_ai):
            if idx < len(db_subitems):
                sub = db_subitems[idx]
                sub.is_done = st.get("is_done", False)
                sub.save()

        # Eğer tüm alt-görevler tamamlandıysa Jira’yı Done yap
        if all(s.is_done for s in db_subitems):
            move_task(task_key, "Done")

        task_details.append({
            "task": task,
            "subtasks": [
                {"content": s.content, "is_done": s.is_done} for s in db_subitems
            ],
            "progress": progress,
            "action": action
        })

    return render(request, "workers_module/view_progress.html", {
        "task_details": task_details
    })



@login_required
def view_team(request):
    return render(request, 'workers/team_dashboard.html')
