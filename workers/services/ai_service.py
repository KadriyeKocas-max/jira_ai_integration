# ai_service.py — advanced, context-aware

import json
import re
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)
client = OpenAI()

def extract_subtasks_from_description(description, task_key=None, max_items=2):
    """
    Basit fallback:
    - Cümlelere böl
    - Anahtar kelimeleri ('talep', 'hazırla', 'sunulacak', 'rapor') bul
    - Mantıklı top-level görevleri çıkar
    """
    max_items = int(max_items)
    # Satırlara böl
    lines = re.split(r'[\r\n]+', description)
    candidates = []
    for line in lines:
        s = line.strip()
        if s:
            norm = re.sub(r'\s+', ' ', s).strip()
            candidates.append(norm)
    
    if not candidates:
        candidates = [x.strip() for x in re.split(r'[.?!]\s*', description) if x.strip()]
    
    # Öncelikli cümleler
    priority = []
    for c in candidates:
        if re.search(r'\b(talep|hazırla|sunulacak|rapor|erişim|eğitim)\b', c, flags=re.I):
            priority.append(c)
    
    chosen = priority[:max_items] if priority else candidates[:max_items]
    
    results = []
    for c in chosen:
        r = c.rstrip('.').strip()
        if len(r) > 160:
            r = r[:160].rsplit(' ', 1)[0] + '...'
        results.append({"content": r, "is_done": False})
    
    return {"subtasks": results}


def update_subtasks_with_report(task_key, description, max_subtasks=2, model="gpt-4o-mini"):
    """
    AI ile description’dan **context-aware top-level deliverable** çıkartır.
    Döndürür: {"task_key": task_key, "subtasks": [{"content": "...", "is_done": False}, ...]}
    """
    # enforce integer
    if not isinstance(max_subtasks, int):
        try:
            max_subtasks = int(max_subtasks)
        except:
            max_subtasks = 2

    # Prompt — context-aware
    prompt = f"""
You are a task-summarization assistant. GIVEN a Jira task description, OUTPUT **only** a JSON object with up to {max_subtasks} top-level deliverable subtasks.
Rules:
- Consider the whole description context to identify top-level deliverables.
- Some subtasks may depend on earlier sentences; infer logically.
- Do not break into too many small steps; aim for 1-2 concise items per task.
- Return JSON only, no explanation or markdown.
- Use concise, imperative noun-phrase style.

Return JSON exactly:
{{
  "task_key": "{task_key}",
  "subtasks": [
    {{ "content": "..." }}
  ]
}}

Description:
\"\"\"{description}\"\"\"
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise task summarizer. Return only JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=400,
        )

        content = response.choices[0].message.content.strip()
        # Kod bloklarını temizle
        content_clean = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
        # JSON blok yakala
        m = re.search(r'(\{.*\})', content_clean, flags=re.DOTALL)
        json_text = m.group(1) if m else content_clean
        data = json.loads(json_text)

        # Normalize
        subs = data.get("subtasks", []) if isinstance(data, dict) else []
        subs = subs[:max_subtasks]
        normalized = []
        for s in subs:
            c = s.get("content") if isinstance(s, dict) else str(s)
            c = c.strip().rstrip('.')
            if c and c[0].islower():
                c = c[0].upper() + c[1:]
            normalized.append({"content": c, "is_done": False})

        return {"task_key": task_key, "subtasks": normalized}

    except Exception as e:
        logger.warning(f"AI parse failed: {e} | falling back")
        # fallback
        fallback = extract_subtasks_from_description(description, max_items=max_subtasks)
        return {"task_key": task_key, "subtasks": fallback}
