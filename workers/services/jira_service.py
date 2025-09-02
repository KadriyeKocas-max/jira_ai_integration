# workers/services/jira_service.py
import os
import logging
from jira import JIRA
from django.conf import settings

logger = logging.getLogger(__name__)

_jira_client = None

# AI action → Jira transition mapping
ACTION_TO_TRANSITION = {
    "done": "Done",
    "in_progress": "In Progress",
    "to do": "To Do",
}

def get_jira_client():
    """Singleton Jira client oluşturur."""
    global _jira_client
    if _jira_client is None:
        try:
            _jira_client = JIRA(
                server=settings.JIRA_URL,
                basic_auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
            )
        except Exception as e:
            logger.error(f"Jira bağlantısı kurulamadı: {e}")
            return None
    return _jira_client


def get_jira_tasks_for_user(user):
    """Kullanıcıya atanan Jira tasklarını getirir."""
    jira = get_jira_client()
    if jira is None:
        return []

    projects = getattr(settings, "MY_JIRA_PROJECTS", [])
    if not projects:
        logger.warning("MY_JIRA_PROJECTS ayarlarda tanımlı değil.")
        return []

    jql = f'assignee = "{user.email}" AND project in ({",".join(projects)}) ORDER BY created DESC'
    try:
        issues = jira.search_issues(
            jql,
            maxResults=100,
            fields="summary,status,assignee,project"
        )
    except Exception as e:
        logger.error(f"Jira taskları alınamadı: {e}")
        return []

    return [
        {
            "key": issue.key,
            "summary": issue.fields.summary,
            "status": issue.fields.status.name
        }
        for issue in issues
    ]


def get_transition_id_by_name(issue_key, transition_name):
    """Bir issue için verilen transition name'e karşılık gelen ID'yi döner."""
    jira = get_jira_client()
    if jira is None:
        return None

    transitions = jira.transitions(issue_key)  # direkt Jira’dan çekiyoruz
    for t in transitions:
        if t["name"].lower() == transition_name.lower():
            return t["id"]

    return None



def move_task(task_key, action):
    """
    Jira task'ını verilen AI aksiyonuna göre taşır.
    action: "in_progress" → "In Progress"
            "done"        → "Done"
            "to do"       → "To Do"
    """
    jira = get_jira_client()
    if jira is None:
        return False

    transition_name = ACTION_TO_TRANSITION.get(action.lower())
    if not transition_name:
        logger.error(f"Geçersiz action: {action}")
        return False

    transition_id = get_transition_id_by_name(task_key, transition_name)
    if not transition_id:
        logger.warning(f"{task_key} için '{transition_name}' transition bulunamadı.")
        return False

    try:
        jira.transition_issue(task_key, transition_id)
        logger.info(f"{task_key} → {transition_name} taşındı.")
        return True
    except Exception as e:
        logger.error(f"Task taşınamadı ({task_key}): {e}")
        return False



def add_comment(task_key, comment):
    """Bir Jira taskına yorum ekler."""
    jira = get_jira_client()
    if jira is None:
        return False

    try:
        jira.add_comment(task_key, comment)
        return True
    except Exception as e:
        logger.error(f"Yorum eklenemedi ({task_key}): {e}")
        return False
