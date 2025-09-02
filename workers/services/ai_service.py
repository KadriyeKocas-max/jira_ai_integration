# workers/services/ai_service.py
import os
import json
import re
import logging
from openai import OpenAI
from django.conf import settings
from .jira_service import move_task

logger = logging.getLogger(__name__)

# OpenAI client (öncelik settings, yoksa env)
api_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)


def analyze_task_text(text):
    """
    OpenAI ile text analizi yapar ve task için aksiyonları döndürür.
    Çıktı örneği:
    [
        {"task_key": "NSDT-001", "action": "in_progress"},
        {"task_key": "NSDT-002", "action": "done"}
    ]
    """
    prompt = f"""
    Kullanıcı şu işleri raporladı: "{text}".

    Eğer Jira task’larıyla ilgili bir güncelleme yapmamız gerekiyorsa,
    her task için şu formatta JSON üret:

    [{{"task_key": "ABC-123", "action": "in_progress"}}, ...]

    Action değerleri yalnızca: "in_progress" veya "done".
    Sadece geçerli JSON döndür.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )

        content = response.choices[0].message.content.strip()

        # Kod bloklarını temizle (```json ... ```)
        content_clean = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()

        return json.loads(content_clean)

    except json.JSONDecodeError as e:
        logger.error(f"AI JSON parse hatası: {e} | Output: {content}")
        return []
    except Exception as e:
        logger.error(f"OpenAI çağrı hatası: {e}")
        return []


def analyze_and_update_jira(report_text, jira_tasks):
    """
    AI analizi yapar ve Jira task’larını günceller.
    """
    actions = []
    new_local_tasks = []

    ai_results = analyze_task_text(report_text)

    # Jira task’larını dict olarak hızlı erişim için key->status
    jira_dict = {t["key"]: t for t in jira_tasks}

    for result in ai_results:
        task_key = result.get("task_key")
        action = result.get("action")

        if not task_key or not action:
            continue

        if task_key in jira_dict:
            # Artık move_task kendi mapping’ini yapıyor (in_progress → In Progress, done → Done)
            success = move_task(task_key, action)
            actions.append({"task_key": task_key, "action": action, "success": success})
        else:
            # Jira’da yok → local kaydet
            new_local_tasks.append({
                "description": result.get("description", report_text)
            })

    return {"actions": actions, "new_local_tasks": new_local_tasks}
