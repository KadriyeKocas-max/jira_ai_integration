# workers/services/ai_service.py
import os
from openai import AzureOpenAI

def analyze_with_ai(text):
    # Burada gerçek Azure OpenAI çağrısı olur
    return f"AI analizi sonucu: {text}"

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-05-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

def analyze_task(form_text: str) -> dict:
    """
    Kullanıcıdan gelen form verisini AI ile analiz eder
    ve Jira için uygun bir aksiyon çıkarır.
    """
    prompt = f"""
    Kullanıcıdan gelen task bilgisi:
    {form_text}

    Bunu çözümle:
    1. Jira'ya yeni bir epic mi oluşturulmalı?
    2. Var olan bir epic'e yorum mu eklenmeli?
    3. Task kapatılmalı mı?
    Bana JSON formatında dön:
    {{
      "action": "create_epic" | "add_comment" | "close_task",
      "title": "...",
      "description": "...",
      "task_key": "NSDT-123"
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "Sen bir Jira asistanısın."},
                  {"role": "user", "content": prompt}],
        temperature=0.2
    )

    content = response.choices[0].message.content.strip()

    import json
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"action": "error", "message": content}
