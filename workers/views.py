
# views.py — gerekli importları kontrol et / güncelle
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
import logging

from .models import WorkerProfile, TodayReport, WorkerTask, TaskSubItem
from .forms import DailyReportForm
from .task_mapping import TASK_MAPPING
from workers.forms import WorkerProfileForm


from .services.ai_service import (
    update_subtasks_with_report,
    update_subtasks_status,
)

from .services.jira_service import (
    get_jira_client,
    get_jira_tasks_for_user,
    move_task,
    add_comment
)
from workers.services.ai_service import analyze_task_and_attach_files
from workers.services.jira_service import get_worker_tasks


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
    user = request.user
    profile, created = WorkerProfile.objects.get_or_create(user=user)

    # Eğer Jira bilgileri yoksa veya ilk defa giriş yapılıyorsa güncelle
    if created or not profile.jira_account_id:
        try:
            jira = get_jira_client()   # user parametresi kaldırıldı
            jira_user = jira.myself()
            profile.jira_account_id = jira_user.get("accountId")
            profile.display_name = jira_user.get("displayName")
            profile.email = jira_user.get("emailAddress")
            profile.save()
        except Exception as e:
            logger.error(f"Jira fetch error: {e}")

    # Kullanıcı kendi alanlarını form ile güncelleyebilir
    if request.method == "POST":
        form = WorkerProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("workers:my_profile")  # URL name namespace ile olmalı
    else:
        form = WorkerProfileForm(instance=profile)

    return render(request, "workers_module/profile.html", {"profile": profile, "form": form})

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

    # Kullanıcı planı kontrolü (AI ve opsiyonel dosya kontrolü için)
    profile = getattr(request.user, "workerprofile", None)
    user_plan = getattr(profile, "plan", "basic") if profile else "basic"

    response_data = {
        "status": "success",
        "report_id": report.id,
        "updated_tasks": []
    }

    # AI planı aktifse
    if "ai" in getattr(profile, "plan_features", []):
        try:
            jira_tasks = get_jira_tasks_for_user(request.user)
        except Exception as e:
            logger.error(f"Jira taskları alınamadı: {e}")
            jira_tasks = []

        for jt in jira_tasks:
            task_key = jt.get("key")
            description = jt.get("description", "")

            # WorkerTask oluştur veya al
            worker_task, _ = WorkerTask.objects.get_or_create(
                jira_key=task_key,
                assignee=request.user,
                defaults={
                    "title": jt.get("summary", ""),
                    "description": description
                }
            )

            # 1. Description’dan alt-görev çıkar ve DB’ye ekle
            try:
                ai_result = update_subtasks_with_report(task_key, description, max_subtasks=5)
                subtasks_ai = ai_result.get("subtasks", [])
                for st in subtasks_ai:
                    TaskSubItem.objects.get_or_create(
                        task=worker_task,
                        content=st["content"]
                    )
            except Exception as e:
                logger.warning(f"{task_key} için AI alt-görev çıkarılamadı: {e}")

            # 2. Kullanıcı raporuna göre alt-görevleri güncelle
            try:
                db_subitems = list(worker_task.subitems.all())
                subtasks_dict = [{"content": s.content} for s in db_subitems]

                ai_progress = update_subtasks_status(task_key, subtasks_dict, report.report_text)

                for idx, st in enumerate(ai_progress.get("subtasks", [])):
                    if idx < len(db_subitems):
                        sub = db_subitems[idx]
                        sub.is_done = st.get("is_done", False)
                        sub.save()

                progress = ai_progress.get("progress", 0)
                action = ai_progress.get("action", "in_progress")

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
            except Exception as e:
                logger.warning(f"{task_key} alt-görevleri güncellenemedi: {e}")

    # Dosya kontrolü opsiyonel
    if "file_check" in getattr(profile, "plan_features", []):
        try:
            from .services.file_service import check_files
            check_files(request.user)
        except Exception as e:
            logger.warning(f"Dosya kontrolü sırasında hata: {e}")

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

    last_report = TodayReport.objects.filter(user=user).order_by('-created_at').first()
    last_report_text = last_report.report_text if last_report else ""

    for jt in jira_tasks:
        task_key = jt["key"]
        description = jt.get("description") or ""

        # WorkerTask al/oluştur
        task, _ = WorkerTask.objects.get_or_create(
            jira_key=task_key,
            assignee=user,
            defaults={"title": jt.get("summary", ""), "description": description}
        )

        # Sadece DB’de alt-görev yoksa AI çağrısı yap
        if not task.subitems.exists():
            try:
                ai_result = update_subtasks_with_report(task_key, description, max_subtasks=5)
                for st in ai_result.get("subtasks", []):
                    TaskSubItem.objects.create(task=task, content=st["content"], is_done=False)
            except Exception as e:
                logger.warning(f"{task_key} için AI alt-görev çıkarılamadı: {e}")

        # DB alt-görevleri al
        db_subitems = list(task.subitems.all())
        subtasks_dict = [{"content": s.content, "is_done": s.is_done} for s in db_subitems]

        # Son rapora göre is_done güncelle
        try:
            ai_progress = update_subtasks_status(task_key, subtasks_dict, last_report_text)
            for idx, st in enumerate(ai_progress.get("subtasks", [])):
                if idx < len(db_subitems):
                    db_subitems[idx].is_done = st.get("is_done", False)
                    db_subitems[idx].save()
        except Exception as e:
            logger.warning(f"{task_key} alt-görev durumu güncellenemedi: {e}")

        # Progress hesapla
        done_count = sum(1 for s in db_subitems if s.is_done)
        total_count = len(db_subitems)
        progress = round((done_count / total_count) * 100, 1) if total_count else 0

        # Tüm alt-görevler tamamlandıysa Jira’da Done
        if progress == 100:
            move_task(task_key, "done")
            add_comment(task_key, f"Tüm alt-görevler tamamlandı: {last_report_text}")

        task_details.append({
            "task": task,
            "subtasks": [{"content": s.content, "is_done": s.is_done} for s in db_subitems],
            "progress": progress
        })

    return render(request, "workers_module/view_progress.html", {"task_details": task_details})



@login_required
def view_team(request):
    return render(request, 'workers/team_dashboard.html')
