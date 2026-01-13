"""
Agent Skills Package - All AI functionality for the vault system
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class VaultReader:
    """Read and search the Obsidian vault"""

    def __init__(self, vault_path: str = "AI_Employee_Vault"):
        self.vault_path = Path(vault_path)
        self.inbox_path = self.vault_path / "Inbox"
        self.needs_action_path = self.vault_path / "Needs_Action"
        self.done_path = self.vault_path / "Done"

    def read_file(self, filepath: str) -> Optional[str]:
        """Read a file from the vault"""
        full_path = self.vault_path / filepath
        if not full_path.exists():
            return None

        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()

    def search_files(self, query: str, folder: Optional[str] = None) -> List[Dict[str, str]]:
        """Search for files containing the query string"""
        results = []
        search_path = self.vault_path / folder if folder else self.vault_path

        for md_file in search_path.rglob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if query.lower() in content.lower():
                        rel_path = md_file.relative_to(self.vault_path)
                        # Extract a snippet around the match
                        lines = content.split('\n')
                        snippet = ""
                        for i, line in enumerate(lines):
                            if query.lower() in line.lower():
                                start = max(0, i - 1)
                                end = min(len(lines), i + 2)
                                snippet = '\n'.join(lines[start:end])
                                break

                        results.append({
                            "path": str(rel_path),
                            "snippet": snippet
                        })
            except Exception:
                continue

        return results

    def get_stats(self) -> Dict[str, int]:
        """Get vault statistics"""
        stats = {
            "inbox": len(list(self.inbox_path.glob("*.md"))),
            "needs_action": len(list(self.needs_action_path.glob("*.md"))),
            "done": len(list(self.done_path.glob("*.md"))),
            "total": len(list(self.vault_path.rglob("*.md")))
        }
        return stats


class VaultWriter:
    """Write to the Obsidian vault"""

    def __init__(self, vault_path: str = "AI_Employee_Vault"):
        self.vault_path = Path(vault_path)
        self.inbox_path = self.vault_path / "Inbox"
        self.needs_action_path = self.vault_path / "Needs_Action"
        self.done_path = self.vault_path / "Done"

        # Ensure folders exist
        self.inbox_path.mkdir(parents=True, exist_ok=True)
        self.needs_action_path.mkdir(parents=True, exist_ok=True)
        self.done_path.mkdir(parents=True, exist_ok=True)

    def create_note(self, title: str, content: str, folder: str = "Inbox") -> str:
        """Create a new note in the specified folder"""
        # Create safe filename
        safe_title = title.replace('/', '-').replace('\\', '-')[:50]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{safe_title}.md"

        folder_path = self.vault_path / folder
        folder_path.mkdir(parents=True, exist_ok=True)

        filepath = folder_path / filename

        # Add frontmatter
        frontmatter = f"""---
type: note
created: {datetime.now().isoformat()}
status: inbox
---

# {title}

{content}
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(frontmatter)

        return str(filepath.relative_to(self.vault_path))

    def create_task(self, title: str, description: str, priority: str = "medium") -> str:
        """Create a new task note in Needs_Action"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"TASK_{timestamp}_{title.replace(' ', '_')[:30]}.md"
        filepath = self.needs_action_path / filename

        content = f"""---
type: task
priority: {priority}
created: {datetime.now().isoformat()}
status: needs_action
---

# {title}

**Priority:** {priority.capitalize()}
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Description

{description}

## Action Items

- [ ] First action item
- [ ] Second action item

## Notes

<!-- Add progress notes here -->
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return str(filepath.relative_to(self.vault_path))


class EmailProcessor:
    """Process emails stored in the vault"""

    def __init__(self, vault_path: str = "AI_Employee_Vault"):
        self.vault_path = Path(vault_path)
        self.inbox_path = self.vault_path / "Inbox"
        self.needs_action_path = self.vault_path / "Needs_Action"
        self.done_path = self.vault_path / "Done"

    def list_inbox_emails(self) -> List[Dict[str, str]]:
        """List all emails in the inbox"""
        emails = []
        for md_file in self.needs_action_path.glob("EMAIL_*.md"):
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract frontmatter
            frontmatter = self._extract_frontmatter(content)

            # Extract title
            title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else md_file.stem

            emails.append({
                "filename": md_file.name,
                "title": title,
                "sender": frontmatter.get('sender', 'Unknown'),
                "date": frontmatter.get('date', 'Unknown'),
                "status": frontmatter.get('status', 'inbox')
            })

        return sorted(emails, key=lambda x: x['date'], reverse=True)

    def _extract_frontmatter(self, content: str) -> Dict[str, str]:
        """Extract YAML frontmatter from markdown content"""
        frontmatter = {}
        match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if match:
            for line in match.group(1).split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    frontmatter[key.strip()] = value.strip()
        return frontmatter


# ============ SKILL FUNCTIONS ============

def read_vault(filepath: str = None) -> str:
    """Skill function: Read a file from the vault"""
    reader = VaultReader()
    if filepath:
        content = reader.read_file(filepath)
        if content:
            return content
        return f"File not found: {filepath}"
    else:
        # List all files
        files = list(reader.vault_path.rglob("*.md"))
        output = f"# Vault Contents ({len(files)} files)\n\n"
        for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
            rel_path = f.relative_to(reader.vault_path)
            output += f"- **{rel_path}**\n"
        return output


def search_vault(query: str, folder: str = None) -> str:
    """Skill function: Search the vault"""
    reader = VaultReader()
    results = reader.search_files(query, folder)

    output = f"# Search Results: '{query}'\n\n"
    output += f"Found {len(results)} file(s)\n\n"

    for r in results:
        output += f"## {r['path']}\n```\n{r['snippet']}\n```\n\n"

    return output


def get_vault_stats() -> str:
    """Skill function: Get vault statistics"""
    reader = VaultReader()
    stats = reader.get_stats()

    output = "# Vault Statistics\n\n"
    output += f"- Inbox: {stats['inbox']} files\n"
    output += f"- Needs Action: {stats['needs_action']} files\n"
    output += f"- Done: {stats['done']} files\n"
    output += f"- Total: {stats['total']} files\n"

    return output


def list_inbox() -> str:
    """Skill function: List all emails in inbox"""
    processor = EmailProcessor()
    emails = processor.list_inbox_emails()

    output = f"# Inbox Emails ({len(emails)})\n\n"

    if not emails:
        output += "No emails in inbox.\n"
    else:
        for email in emails:
            output += f"## {email['title']}\n"
            output += f"- **From:** {email['sender']}\n"
            output += f"- **Date:** {email['date']}\n"
            output += f"- **File:** {email['filename']}\n\n"

    return output


def write_note(title: str, content: str, folder: str = "Inbox") -> str:
    """Skill function: Create a new note"""
    writer = VaultWriter()
    rel_path = writer.create_note(title, content, folder)
    return f"✓ Created note: {rel_path}"


def create_task(title: str, description: str, priority: str = "medium") -> str:
    """Skill function: Create a new task"""
    writer = VaultWriter()
    rel_path = writer.create_task(title, description, priority)
    return f"✓ Created task: {rel_path}"


def move_to_done(filepath: str) -> str:
    """Skill function: Move a file to Done folder"""
    vault_path = Path("AI_Employee_Vault")
    src_path = vault_path / filepath
    dst_path = vault_path / "Done" / Path(filepath).name

    if not src_path.exists():
        return f"✗ File not found: {filepath}"

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    src_path.rename(dst_path)
    return f"✓ Moved to Done: {filepath}"


def log_reply(message_id: str, reply_text: str) -> str:
    """Skill function: Log your reply to an email in the vault"""
    vault_path = Path("AI_Employee_Vault")
    needs_action_path = vault_path / "Needs_Action"

    # Try to find the file by message ID
    email_file = needs_action_path / f"{message_id}.md"

    if not email_file.exists():
        return f"✗ Email file not found for message ID: {message_id}"

    try:
        content = email_file.read_text(encoding='utf-8')
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

        # Replace the "No reply sent yet" with the actual reply
        new_reply_section = f"""## 💬 Your Reply

**Sent:** {timestamp}

{reply_text}
"""
        content = content.replace('*No reply sent yet*', new_reply_section)

        # Update the Last Updated timestamp
        content = re.sub(
            r'\*\*Last Updated:\*\* .*',
            f'**Last Updated:** {datetime.now().isoformat()}',
            content
        )

        email_file.write_text(content, encoding='utf-8')
        return f"✓ Reply logged for email: {message_id}"
    except Exception as e:
        return f"✗ Error logging reply: {e}"


# ============ IMPORT NEW SKILLS ============

# Email Planning Skills
try:
    from skills.email_planner import (
        plan_email,
        analyze_pending_emails,
        show_email_plan
    )
    EMAIL_PLANNER_AVAILABLE = True
except ImportError:
    EMAIL_PLANNER_AVAILABLE = False

# Email Sender Skills
try:
    from skills.email_sender import (
        send_email as send_email_skill,
        create_email_draft,
        list_sent_emails,
        enable_dry_run,
        disable_dry_run
    )
    EMAIL_SENDER_AVAILABLE = True
except ImportError:
    EMAIL_SENDER_AVAILABLE = False

# LinkedIn Manager Skills
try:
    from skills.linkedin_manager import (
        create_linkedin_post,
        post_from_email,
        list_linkedin_posts,
        show_post_templates
    )
    LINKEDIN_MANAGER_AVAILABLE = True
except ImportError:
    LINKEDIN_MANAGER_AVAILABLE = False

# CEO Briefing Skills
try:
    from skills.ceo_briefing import (
        generate_weekly_briefing,
        create_business_goals,
        get_business_summary
    )
    CEO_BRIEFING_AVAILABLE = True
except ImportError:
    CEO_BRIEFING_AVAILABLE = False

# Keyword Analyzer Skills
try:
    from skills.keyword_analyzer import (
        analyze_message
    )
    KEYWORD_ANALYZER_AVAILABLE = True
except ImportError:
    KEYWORD_ANALYZER_AVAILABLE = False

# Email to Inbox Skills
try:
    from skills.email_to_inbox import EmailToInboxMover, move_email_to_inbox
    EMAIL_TO_INBOX_AVAILABLE = True
except ImportError:
    EMAIL_TO_INBOX_AVAILABLE = False

# Task Processor Skills
try:
    from skills.task_processor import (
        create_task as create_task_processor,
        list_tasks as list_tasks_processor,
        get_next_task
    )
    TASK_PROCESSOR_AVAILABLE = True
except ImportError:
    TASK_PROCESSOR_AVAILABLE = False

# Dashboard Updater Skills
try:
    from skills.dashboard_updater import (
        update_dashboard,
        get_dashboard_stats
    )
    DASHBOARD_UPDATER_AVAILABLE = True
except ImportError:
    DASHBOARD_UPDATER_AVAILABLE = False

# Database MCP Skills
try:
    from skills.mcp_database import (
        db_create_task,
        db_get_task,
        db_list_tasks,
        db_get_next_task,
        db_update_task_status,
        db_create_email,
        db_get_email,
        db_list_emails,
        db_update_email_status,
        db_create_plan,
        db_update_plan_status,
        db_list_plans,
        db_create_event,
        db_list_events,
        db_get_stats,
        db_search,
        db_export_to_json,
        db_sync_tasks_from_vault,
        db_close
    )
    DATABASE_MCP_AVAILABLE = True
except ImportError:
    DATABASE_MCP_AVAILABLE = False

# Meeting Scheduler Skills
try:
    from skills.meeting_scheduler_skill import (
        schedule_meeting_from_email,
        get_meeting_suggestions,
        schedule_all_meetings,
        review_meeting_request
    )
    MEETING_SCHEDULER_AVAILABLE = True
except ImportError:
    MEETING_SCHEDULER_AVAILABLE = False


__all__ = [
    # Original skills
    'read_vault',
    'search_vault',
    'get_vault_stats',
    'list_inbox',
    'write_note',
    'create_task',
    'move_to_done',
    'log_reply',
    # Email Planning skills
    'plan_email',
    'analyze_pending_emails',
    'show_email_plan',
    # Email Sender skills
    'send_email_skill',
    'create_email_draft',
    'list_sent_emails',
    'enable_dry_run',
    'disable_dry_run',
    # LinkedIn Manager skills
    'create_linkedin_post',
    'post_from_email',
    'list_linkedin_posts',
    'show_post_templates',
    # CEO Briefing skills
    'generate_weekly_briefing',
    'create_business_goals',
    'get_business_summary',
    # Keyword Analyzer skills
    'analyze_message',
    # Task Processor skills
    'create_task_processor',
    'list_tasks_processor',
    'get_next_task',
    # Email to Inbox skills
    'move_email_to_inbox',
    'check_completed_plans',
    # Database MCP skills
    'db_create_task',
    'db_get_task',
    'db_list_tasks',
    'db_get_next_task',
    'db_update_task_status',
    'db_create_email',
    'db_get_email',
    'db_list_emails',
    'db_update_email_status',
    'db_create_plan',
    'db_update_plan_status',
    'db_list_plans',
    'db_create_event',
    'db_list_events',
    'db_get_stats',
    'db_search',
    'db_export_to_json',
    'db_sync_tasks_from_vault',
    'db_close',
    # Meeting Scheduler skills
    'schedule_meeting_from_email',
    'get_meeting_suggestions',
    'schedule_all_meetings',
    'review_meeting_request',
    # CEO Briefing skills
    'generate_weekly_briefing',
    'create_business_goals',
    'get_business_summary',
    # Dashboard Updater skills
    'update_dashboard',
    'get_dashboard_stats',
]
