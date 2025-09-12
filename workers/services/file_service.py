import os

def match_task_to_files(task_summary, task_description, user_expertise, base_dir="P:/Performance"):
    """
    Task summary/description ile dosya adlarını eşleştirir.
    Önce kullanıcının expertise klasöründe, sonra diğerlerinde arar.
    """

    matched_files = []

    if not task_summary and not task_description:
        return matched_files

    task_summary = (task_summary or "").lower()
    task_description = (task_description or "").lower()

    # 1️⃣ Öncelikli klasör (kullanıcının uzmanlığı)
    if user_expertise:
        expertise_dir = os.path.join(base_dir, user_expertise)
        if os.path.exists(expertise_dir):
            for root, dirs, files in os.walk(expertise_dir):
                for f in files:
                    if task_summary in f.lower() or task_description in f.lower():
                        matched_files.append(os.path.join(root, f))

    # 2️⃣ Diğer klasörler
    for root, dirs, files in os.walk(base_dir):
        if user_expertise and user_expertise in root:
            # uzmanlık klasörü zaten bakıldı, tekrar geçme
            continue
        for f in files:
            if task_summary in f.lower() or task_description in f.lower():
                matched_files.append(os.path.join(root, f))

    return matched_files


def attach_files_to_task(jira_client, task, user, base_dir="P:/Performance"):
    """
    Eşleşen dosyaları bulup Jira task'ine ekler.
    """
    profile = getattr(user, "userprofile", None)
    expertise = getattr(profile, "expertise", None)

    matched = match_task_to_files(
        task_summary=task.summary,
        task_description=task.description,
        user_expertise=expertise,
        base_dir=base_dir,
    )

    for file_path in matched:
        try:
            with open(file_path, "rb") as f:
                jira_client.add_attachment(issue=task.key, attachment=f)
        except Exception as e:
            print(f"Dosya eklenemedi: {file_path} | Hata: {e}")
