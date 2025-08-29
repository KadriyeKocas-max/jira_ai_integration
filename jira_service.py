# workers/services/jira_service.py
from jira import JIRA
import os

jira = JIRA(
    server=os.getenv("JIRA_SERVER"),
    basic_auth=(os.getenv("JIRA_USER"), os.getenv("JIRA_TOKEN"))
)

def update_jira(task_key, analysis_result):
    # Burada gerçek Jira API çağrısı olur
    return f"Jira'da {task_key} için güncelleme yapıldı: {analysis_result}"


def create_epic(title: str, description: str, project="NSDT"):
    issue = jira.create_issue(
        project=project,
        summary=title,
        description=description,
        issuetype={"name": "Epic"}
    )
    return issue.key

def add_comment(task_key: str, comment: str):
    jira.add_comment(task_key, comment)
    return True

def close_task(task_key: str):
    transitions = jira.transitions(task_key)
    close_transition = next((t for t in transitions if "Done" in t["name"]), None)
    if close_transition:
        jira.transition_issue(task_key, close_transition["id"])
        return True
    return False
