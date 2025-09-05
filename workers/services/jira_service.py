# workers/services/jira_service.py
import os
import logging
from jira import JIRA
from django.conf import settings

logger = logging.getLogger(__name__)

_jira_client = None

# AI action → Jira transition mapping
ACTION_TO_TRANSITION = {
    "done": ["Done", "Complete", "Resolve", "Close", "DONE"],
    "in_progress": ["In Progress", "Start Progress"],
    "to do": ["To Do", "Open"]
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
    """Kullanıcıya atanan Jira tasklarını getirir (summary + description + status)."""
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
            fields="summary,description,status,assignee,project"
        )
    except Exception as e:
        logger.error(f"Jira taskları alınamadı: {e}")
        return []

    return [
        {
            "key": issue.key,
            "summary": issue.fields.summary,
            "description": getattr(issue.fields, "description", "") or "",
            "status": issue.fields.status.name,
        }
        for issue in issues
    ]


def get_transition_id_by_name(issue_key, action_key):
    """
    Bir issue için verilen action_key'e (ör: 'done', 'in_progress') uygun transition ID'yi döner.
    """
    jira = get_jira_client()
    if jira is None:
        return None

    transitions = jira.transitions(issue_key)
    logger.info(f"{issue_key} için mevcut transitionlar: {[t['name'] for t in transitions]}")

    # action_key → olası transition isimleri
    possible_names = ACTION_TO_TRANSITION.get(action_key.lower(), [])
    if isinstance(possible_names, str):
        possible_names = [possible_names]

    for t in transitions:
        t_name = t["name"].lower()
        if any(p.lower() == t_name for p in possible_names):
            return t["id"]

    return None





def move_task(task_key, action):
    """
    Jira task'ını verilen AI aksiyonuna göre taşır.
    """
    jira = get_jira_client()
    if jira is None:
        return False

    transition_id = get_transition_id_by_name(task_key, action)
    if not transition_id:
        logger.warning(f"{task_key} için '{action}' transition bulunamadı.")
        return False

    try:
        jira.transition_issue(task_key, transition_id)
        logger.info(f"{task_key} → {action} taşındı.")
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

def get_worker_tasks(jira_username):
    issues = jira.search_issues(f'assignee={jira_username} AND status!=Done', maxResults=50)
    tasks = []
    for issue in issues:
        tasks.append({
            "key": issue.key,
            "title": issue.fields.summary,
            "description": issue.fields.description
        })
    return tasks