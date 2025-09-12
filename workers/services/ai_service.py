import json
import re
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)
client = OpenAI()

from workers.services.file_service import attach_files_to_task
from workers.services.jira_service import get_jira_client

def update_subtasks_with_report(task_key, description, max_subtasks=2, model="gpt-4o-mini"):
    """
    Task description'dan AI ile alt-görev listesi çıkarır.
    NOT: Raporda olmayan görevleri eklemez.
    """
    if not description:
        return {"task_key": task_key, "subtasks": []}

    prompt = f"""
You are an assistant that extracts clear, actionable subtasks from a task description.
Rules:
- Output ONLY valid JSON.
- Do NOT invent new tasks that are not in the description.
- Max {max_subtasks} items.
- Subtasks should be short and actionable.
- JSON schema:
{{
  "task_key": "{task_key}",
  "subtasks": [
    {{"content": "...", "is_done": false}}
  ]
}}

Description:
\"\"\"{description}\"\"\"
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a precise subtask generator. Respond with JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=500,
        )

        content = response.choices[0].message.content.strip()
        m = re.search(r'(\{.*\})', content, flags=re.DOTALL)
        json_text = m.group(1) if m else content
        json_text = re.sub(r",\s*([}\]])", r"\1", json_text)

        data = json.loads(json_text)
        # sadece content var mı diye filtrele
        subtasks = [
            {"content": s.get("content", "").strip(), "is_done": False}
            for s in data.get("subtasks", [])
            if s.get("content")
        ]
        return {"task_key": task_key, "subtasks": subtasks}

    except Exception as e:
        logger.warning(f"AI parse failed for {task_key}: {e}")
        return {"task_key": task_key, "subtasks": []}



# --- Subtasks status güncelleme ---
def update_subtasks_status(task_key, subtasks, report_text, model="gpt-4o-mini"):
    """
    Günlük rapora göre hangi alt-görevlerin tamamlandığını AI ile işaretler.
    Sadece mevcut alt-görevleri kullanır, yeni görev eklemez.
    """
    if not subtasks:
        return {"task_key": task_key, "subtasks": []}

    prompt = f"""
You are an assistant that updates task progress.
Given a list of subtasks and a daily work report, mark which subtasks are DONE.

Rules:
- Output ONLY valid JSON.
- Do not invent new subtasks, use exactly the given list.
- If the report clearly indicates a subtask is finished, set is_done = true.
- Otherwise, keep is_done = false.

JSON schema:
{{
  "task_key": "{task_key}",
  "subtasks": [
    {{"content": "...", "is_done": true/false}}
  ]
}}

Subtasks:
{json.dumps(subtasks, indent=2)}

Report:
\"\"\"{report_text}\"\"\"
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a precise subtask status updater. Respond with JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=500,
        )

        content = response.choices[0].message.content.strip()
        m = re.search(r'(\{.*\})', content, flags=re.DOTALL)
        json_text = m.group(1) if m else content
        json_text = re.sub(r",\s*([}\]])", r"\1", json_text)

        data = json.loads(json_text)
        # is_done değerlerini boolean olarak zorla
        for s in data.get("subtasks", []):
            s["is_done"] = bool(s.get("is_done", False))
        return {"task_key": task_key, "subtasks": data.get("subtasks", [])}

    except Exception as e:
        logger.warning(f"AI status parse failed for {task_key}: {e}")
        return {"task_key": task_key, "subtasks": subtasks}



def run_ai_analysis(task):
    try:
        return {"task_key": task.get("key"), "analysis": "AI çıkarımı tamamlandı"}
    except Exception as e:
        logger.warning(f"AI analysis failed for {task.get('key')}: {e}")
        return {"task_key": task.get("key"), "analysis": None}


def analyze_task_and_attach_files(jira_client, task, user):
    try:
        analysis = run_ai_analysis(task)
        attach_files_to_task(jira_client, task, user)
        return analysis
    except Exception as e:
        logger.warning(f"Task analysis + file attach failed for {task.get('key')}: {e}")
        return {"task_key": task.get("key"), "analysis": None}