"""
Dashboard Updater Skill

Automatically updates Dashboard.md with current statistics and activity.
This keeps the dashboard in sync with actual vault state.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger('DashboardUpdater')


class DashboardUpdater:
    """Updates Dashboard.md with current statistics."""

    def __init__(self, vault_path: str = None):
        """Initialize dashboard updater.

        Args:
            vault_path: Path to Obsidian vault
        """
        self.vault_path = Path(vault_path) if vault_path else Path("./AI_Employee_Vault")
        self.dashboard_path = self.vault_path / 'Dashboard.md'
        self.stats_file = self.vault_path / '.dashboard_stats.json'

        # Load previous stats
        self._load_stats()

    def _load_stats(self) -> None:
        """Load previous statistics."""
        if self.stats_file.exists():
            try:
                data = json.loads(self.stats_file.read_text())
                self.total_emails_processed = data.get('total_emails_processed', 0)
                self.total_auto_sent = data.get('total_auto_sent', 0)
                self.total_plans_created = data.get('total_plans_created', 0)
                self.start_date = data.get('start_date', datetime.now().isoformat())
            except Exception as e:
                logger.error(f'Error loading stats: {e}')
                self.total_emails_processed = 0
                self.total_auto_sent = 0
                self.total_plans_created = 0
                self.start_date = datetime.now().isoformat()
        else:
            self.total_emails_processed = 0
            self.total_auto_sent = 0
            self.total_plans_created = 0
            self.start_date = datetime.now().isoformat()

    def _save_stats(self) -> None:
        """Save statistics to file."""
        try:
            data = {
                'total_emails_processed': self.total_emails_processed,
                'total_auto_sent': self.total_auto_sent,
                'total_plans_created': self.total_plans_created,
                'start_date': self.start_date,
                'last_updated': datetime.now().isoformat()
            }
            self.stats_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f'Error saving stats: {e}')

    def get_current_stats(self) -> Dict:
        """Get current vault statistics.

        Returns:
            Dictionary with current stats
        """
        stats = {
            'pending_emails': 0,
            'pending_plans': 0,
            'done_today': 0,
            'auto_sent_today': 0,
            'recent_activity': []
        }

        # Count pending emails
        needs_action = self.vault_path / 'Needs_Action'
        if needs_action.exists():
            stats['pending_emails'] = len(list(needs_action.glob('EMAIL*.md'))) + \
                                     len(list(needs_action.glob('EMAIL - *.md')))

        # Count pending plans
        plans = self.vault_path / 'Plans'
        if plans.exists():
            stats['pending_plans'] = len(list(plans.glob('PLAN*.md')))

        # Count done today
        done = self.vault_path / 'Done'
        if done.exists():
            today = datetime.now().strftime('%Y-%m-%d')
            for file in done.glob('*.md'):
                try:
                    # Check file modification time
                    mtime = datetime.fromtimestamp(file.stat().st_mtime)
                    if mtime.strftime('%Y-%m-%d') == today:
                        stats['done_today'] += 1
                except Exception:
                    pass

        # Count auto-sent today
        auto_sent = self.vault_path / 'Logs' / 'Auto_Sent'
        if auto_sent.exists():
            today = datetime.now().strftime('%Y-%m-%d')
            for file in auto_sent.glob('AUTO_SENT*.md'):
                try:
                    # Parse date from filename
                    file_date = file.stem.split('_')[1]  # AUTO_SENT_YYYYMMDD_HHMMSS
                    if file_date.startswith(today.replace('-', '')):
                        stats['auto_sent_today'] += 1
                except Exception:
                    pass

        # Get recent activity (last 5 actions)
        stats['recent_activity'] = self._get_recent_activity()

        return stats

    def _get_recent_activity(self) -> List[Dict]:
        """Get recent activity from logs.

        Returns:
            List of recent activity items
        """
        activities = []

        # Check auto-sent logs
        auto_sent = self.vault_path / 'Logs' / 'Auto_Sent'
        if auto_sent.exists():
            for file in sorted(auto_sent.glob('*.md'), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
                try:
                    content = file.read_text()
                    # Extract recipient
                    for line in content.split('\n'):
                        if line.startswith('recipient:'):
                            recipient = line.split(':', 1)[1].strip()
                            break
                    else:
                        recipient = 'Unknown'

                    activities.append({
                        'type': 'auto_sent',
                        'description': f'Auto-sent email to {recipient}',
                        'time': datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                    })
                except Exception:
                    pass

        # Check sent emails
        sent_emails = self.vault_path / 'Logs' / 'Sent_Emails'
        if sent_emails.exists():
            for file in sorted(sent_emails.glob('*.md'), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
                if len(activities) >= 5:
                    break
                try:
                    content = file.read_text()
                    for line in content.split('\n'):
                        if line.startswith('to:'):
                            recipient = line.split(':', 1)[1].strip()
                            break
                    else:
                        recipient = 'Unknown'

                    activities.append({
                        'type': 'sent',
                        'description': f'Sent email to {recipient}',
                        'time': datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                    })
                except Exception:
                    pass

        return activities[:5]

    def update_dashboard(self) -> None:
        """Update Dashboard.md with current statistics."""
        try:
            stats = self.get_current_stats()

            # Build dashboard content
            content = f"""# AI Employee Dashboard

> Real-time summary of email activity, pending messages, and active projects.

**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## Quick Stats

| Metric          | Value  |
| --------------- | ------ |
| Pending Emails  | {stats['pending_emails']} |
| Pending Plans   | {stats['pending_plans']} |
| Done Today      | {stats['done_today']} |
| Auto-Sent Today | {stats['auto_sent_today']} |
| **Total Processed** | {self.total_emails_processed} |
| **Total Auto-Sent** | {self.total_auto_sent} |

---

## Priority Action Items

### 📧 Pending Emails
"""

            # Add pending emails
            needs_action = self.vault_path / 'Needs_Action'
            if needs_action.exists():
                emails = sorted(needs_action.glob('EMAIL*.md'), key=lambda x: x.stat().st_mtime, reverse=True)[:10]
                emails.extend(sorted(needs_action.glob('EMAIL - *.md'), key=lambda x: x.stat().st_mtime, reverse=True)[:10])

                for email_file in emails[:10]:
                    try:
                        content_file = email_file.read_text()
                        # Extract subject
                        subject = 'No Subject'
                        for line in content_file.split('\n'):
                            if line.startswith('subject:'):
                                subject = line.split(':', 1)[1].strip()
                                break

                        priority = '🟡 Normal'
                        if 'priority: high' in content_file.lower():
                            priority = '🔴 High'
                        elif 'priority: critical' in content_file.lower():
                            priority = '🚨 Critical'

                        content += f"- {priority} [{subject}]({email_file.name})\n"
                    except Exception:
                        content += f"- {email_file.name}\n"

            content += "\n### 📋 Pending Plans\n"

            # Add pending plans
            plans = self.vault_path / 'Plans'
            if plans.exists():
                plan_files = sorted(plans.glob('PLAN*.md'), key=lambda x: x.stat().st_mtime, reverse=True)[:5]

                for plan_file in plan_files:
                    try:
                        plan_content = plan_file.read_text()
                        subject = 'Plan'
                        for line in plan_content.split('\n'):
                            if line.startswith('subject:') or line.startswith('email_file:'):
                                subject = line.split(':', 1)[1].strip()
                                break

                        content += f"- [{subject}]({plan_file.name})\n"
                    except Exception:
                        content += f"- {plan_file.name}\n"

            content += "\n---\n\n## Recent Activity\n\n"

            # Add recent activity
            if stats['recent_activity']:
                for activity in stats['recent_activity']:
                    icon = '📤' if activity['type'] == 'auto_sent' else '✅'
                    content += f"- {icon} **{activity['time']}**: {activity['description']}\n"
            else:
                content += "No recent activity recorded.\n"

            content += "\n---\n\n## Quick Links\n\n"
            content += "- [[Needs_Action]] - Items requiring attention\n"
            content += "- [[Plans]] - Active plans awaiting review\n"
            content += "- [[Approved]] - Ready to execute\n"
            content += "- [[Done]] - Completed tasks\n"
            content += "- [[Logs]] - Activity logs\n"
            content += "- [[Briefings]] - CEO Briefings\n"

            content += "\n---\n\n## System Status\n\n"
            content += f"| Watcher | Status |\n"
            content += f"|---------|--------|\n"
            content += f"| Gmail Watcher | 🟢 Active |\n"
            content += f"| WhatsApp Watcher | 🟢 Active |\n"
            content += f"| Approval Watcher | 🟢 Active |\n"

            content += f"\n---\n\n***Generated by AI Employee*** | *Running since {self.start_date[:10]}***\n"

            # Write dashboard
            self.dashboard_path.write_text(content, encoding='utf-8')

            logger.info(f'Dashboard updated at {datetime.now().strftime("%H:%M:%S")}')

        except Exception as e:
            logger.error(f'Error updating dashboard: {e}')

    def record_email_sent(self, auto: bool = False) -> None:
        """Record an email being sent.

        Args:
            auto: Whether this was an auto-sent email
        """
        self.total_emails_processed += 1
        if auto:
            self.total_auto_sent += 1
        self._save_stats()
        self.update_dashboard()

    def record_plan_created(self) -> None:
        """Record a plan being created."""
        self.total_plans_created += 1
        self._save_stats()
        self.update_dashboard()

    def record_task_completed(self) -> None:
        """Record a task being completed."""
        self._save_stats()
        self.update_dashboard()


# ============ SKILL FUNCTIONS ============

def update_dashboard() -> str:
    """Skill function: Update the dashboard.

    Returns:
        Summary of update
    """
    updater = DashboardUpdater()
    updater.update_dashboard()
    stats = updater.get_current_stats()

    return f"""Dashboard updated!

Pending Emails: {stats['pending_emails']}
Pending Plans: {stats['pending_plans']}
Done Today: {stats['done_today']}
Auto-Sent Today: {stats['auto_sent_today']}

Total Processed: {updater.total_emails_processed}
Total Auto-Sent: {updater.total_auto_sent}
"""


def get_dashboard_stats() -> str:
    """Skill function: Get dashboard statistics.

    Returns:
        Statistics summary
    """
    updater = DashboardUpdater()
    stats = updater.get_current_stats()

    output = "# Dashboard Statistics\n\n"
    output += f"## Current Status\n"
    output += f"- Pending Emails: {stats['pending_emails']}\n"
    output += f"- Pending Plans: {stats['pending_plans']}\n"
    output += f"- Done Today: {stats['done_today']}\n"
    output += f"- Auto-Sent Today: {stats['auto_sent_today']}\n\n"

    output += f"## All-Time Stats\n"
    output += f"- Total Processed: {updater.total_emails_processed}\n"
    output += f"- Total Auto-Sent: {updater.total_auto_sent}\n"
    output += f"- Total Plans: {updater.total_plans_created}\n"

    return output


__all__ = [
    'DashboardUpdater',
    'update_dashboard',
    'get_dashboard_stats'
]
