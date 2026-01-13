"""
CEO Briefing Skill - Generate Monday Morning Business Briefings

This skill generates weekly CEO briefings by analyzing:
- Business goals and progress
- Completed tasks from the week
- Bank transactions and revenue
- Bottlenecks and issues
- Proactive suggestions for improvement

Usage:
    from skills.ceo_briefing import CEOBriefing

    briefing = CEOBriefing(vault_path="./AI_Employee_Vault")
    briefing.generate_weekly_briefing()
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

from skills.vault_update import VaultUpdater


@dataclass
class WeeklyMetrics:
    """Weekly business metrics."""
    total_revenue: float = 0.0
    new_clients: int = 0
    tasks_completed: int = 0
    tasks_pending: int = 0
    emails_sent: int = 0
    linkedin_posts: int = 0
    bottlenecks: List[Dict] = field(default_factory=list)
    subscription_costs: Dict[str, float] = field(default_factory=dict)


class CEOBriefing:
    """
    Generate Monday Morning CEO Briefings.

    Features:
    - Revenue tracking and analysis
    - Task completion metrics
    - Bottleneck identification
    - Cost optimization suggestions
    - Deadline reminders
    """

    def __init__(self, vault_path: str = None):
        """Initialize CEO Briefing generator.

        Args:
            vault_path: Path to Obsidian vault
        """
        self.vault_path = Path(vault_path) if vault_path else Path("./AI_Employee_Vault")
        self.updater = VaultUpdater(str(self.vault_path))

        # Briefings folder
        self.briefings_folder = self.vault_path / 'Briefings'
        self.briefings_folder.mkdir(parents=True, exist_ok=True)

        # Goals file
        self.goals_file = self.vault_path / 'Business_Goals.md'

        # Logging
        self.logger = logging.getLogger('CEOBriefing')

    def generate_weekly_briefing(self, week_start: datetime = None) -> str:
        """Generate weekly CEO briefing.

        Args:
            week_start: Start of the week (default: last Monday)

        Returns:
            Path to generated briefing
        """
        # Determine week range
        if week_start is None:
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        # Collect metrics
        metrics = self._collect_weekly_metrics(week_start, week_end)

        # Load business goals
        goals = self._load_business_goals()

        # Generate briefing
        briefing_content = self._generate_briefing_content(
            week_start, week_end, metrics, goals
        )

        # Save briefing
        filename = f"{week_start.strftime('%Y-%m-%d')}_Monday_Briefing.md"
        filepath = self.briefings_folder / filename
        filepath.write_text(briefing_content, encoding='utf-8')

        self.logger.info(f'Generated weekly briefing: {filename}')
        return str(filepath.relative_to(self.vault_path))

    def _collect_weekly_metrics(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> WeeklyMetrics:
        """Collect metrics for the week.

        Args:
            week_start: Start of week
            week_end: End of week

        Returns:
            WeeklyMetrics object
        """
        metrics = WeeklyMetrics()

        # Check Done folder for completed tasks
        done_folder = self.vault_path / 'Done'
        if done_folder.exists():
            for task_file in done_folder.glob('*.md'):
                # Check if modified this week
                mtime = datetime.fromtimestamp(task_file.stat().st_mtime)
                if week_start <= mtime <= week_end:
                    metrics.tasks_completed += 1

        # Check Needs_Action for pending tasks
        needs_action = self.vault_path / 'Needs_Action'
        if needs_action.exists():
            metrics.tasks_pending = len(list(needs_action.glob('*.md')))

        # Check LinkedIn posts
        linkedin_folder = self.vault_path / 'LinkedIn_Posts'
        if linkedin_folder.exists():
            for post_file in linkedin_folder.glob('LI_*.md'):
                mtime = datetime.fromtimestamp(post_file.stat().st_mtime)
                if week_start <= mtime <= week_end:
                    metrics.linkedin_posts += 1

        # Check sent emails
        sent_folder = self.vault_path / 'Logs' / 'Sent_Emails'
        if sent_folder.exists():
            for email_file in sent_folder.glob('SENT_EMAIL_*.md'):
                mtime = datetime.fromtimestamp(email_file.stat().st_mtime)
                if week_start <= mtime <= week_end:
                    metrics.emails_sent += 1

        # Analyze accounting file for revenue
        accounting_file = self.vault_path / 'Accounting' / 'Current_Month.md'
        if accounting_file.exists():
            metrics.total_revenue = self._extract_revenue(accounting_file)

        # Identify bottlenecks
        metrics.bottlenecks = self._identify_bottlenecks()

        return metrics

    def _extract_revenue(self, accounting_file: Path) -> float:
        """Extract revenue from accounting file.

        Args:
            accounting_file: Path to accounting file

        Returns:
            Total revenue
        """
        try:
            content = accounting_file.read_text(encoding='utf-8')
            # Look for revenue patterns
            import re
            amounts = re.findall(r'\$?([\d,]+\.?\d*)\s*(?:revenue|income|payment)', content.lower())
            total = sum(float(a.replace(',', '')) for a in amounts)
            return total
        except Exception as e:
            self.logger.error(f'Error extracting revenue: {e}')
            return 0.0

    def _identify_bottlenecks(self) -> List[Dict[str, Any]]:
        """Identify bottlenecks and issues.

        Returns:
            List of bottleneck dictionaries
        """
        bottlenecks = []

        # Check for overdue tasks
        needs_action = self.vault_path / 'Needs_Action'
        if needs_action.exists():
            for task_file in needs_action.glob('*.md'):
                try:
                    content = task_file.read_text(encoding='utf-8')
                    # Check for priority indicators
                    if 'priority: critical' in content or 'priority: high' in content:
                        # Extract age
                        mtime = datetime.fromtimestamp(task_file.stat().st_mtime)
                        age_days = (datetime.now() - mtime).days

                        if age_days > 2:
                            bottlenecks.append({
                                'type': 'overdue_task',
                                'file': task_file.name,
                                'age_days': age_days,
                                'priority': 'high' if 'critical' in content else 'medium'
                            })
                except Exception:
                    continue

        return bottlenecks

    def _load_business_goals(self) -> Dict[str, Any]:
        """Load business goals from file.

        Returns:
            Dictionary of goals
        """
        if not self.goals_file.exists():
            return self._create_default_goals()

        try:
            content = self.goals_file.read_text(encoding='utf-8')
            # Parse frontmatter
            if content.startswith('---'):
                frontmatter_end = content.find('---', 3)
                if frontmatter_end != -1:
                    import yaml
                    frontmatter = content[3:frontmatter_end]
                    return yaml.safe_load(frontmatter) or {}
            return {}
        except Exception as e:
            self.logger.error(f'Error loading goals: {e}')
            return self._create_default_goals()

    def _create_default_goals(self) -> Dict[str, Any]:
        """Create default business goals.

        Returns:
            Default goals dictionary
        """
        return {
            'revenue_target_monthly': 10000,
            'client_response_time_hours': 24,
            'invoice_payment_rate_percent': 90
        }

    def _generate_briefing_content(
        self,
        week_start: datetime,
        week_end: datetime,
        metrics: WeeklyMetrics,
        goals: Dict[str, Any]
    ) -> str:
        """Generate briefing content.

        Args:
            week_start: Start of week
            week_end: End of week
            metrics: Weekly metrics
            goals: Business goals

        Returns:
            Briefing content as markdown
        """
        # Calculate progress toward goals
        revenue_target = goals.get('revenue_target_monthly', 10000)
        revenue_progress = (metrics.total_revenue / revenue_target * 100) if revenue_target > 0 else 0

        content = f"""---
type: ceo_briefing
period: {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}
generated: {datetime.now().isoformat()}
---

# Monday Morning CEO Briefing

**Period:** {week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## Executive Summary

{'✅ Strong week with revenue ahead of target.' if metrics.total_revenue > revenue_target / 4 else '⚠️ Mixed results. See details below.'}

---

## Revenue & Financials

**This Week:** ${metrics.total_revenue:,.2f}
**Monthly Target:** ${revenue_target:,.2f}
**MTD Progress:** {revenue_progress:.1f}%

{'📈 On track to meet monthly target' if revenue_progress >= 25 else '📉 Below target - need to accelerate'}

"""

        # Tasks section
        content += f"""
---

## Task Summary

**Completed:** {metrics.tasks_completed} tasks
**Pending:** {metrics.tasks_pending} tasks
**Completion Rate:** {(metrics.tasks_completed / max(metrics.tasks_completed + metrics.tasks_pending, 1)) * 100:.1f}%

| Metric | Count |
|--------|-------|
| Emails Sent | {metrics.emails_sent} |
| LinkedIn Posts | {metrics.linkedin_posts} |
| Tasks Completed | {metrics.tasks_completed} |
| Tasks Pending | {metrics.tasks_pending} |

"""

        # Bottlenecks section
        if metrics.bottlenecks:
            content += """
---

## ⚠️ Bottlenecks & Issues

| Issue | Age | Priority |
|-------|-----|----------|
"""
            for b in metrics.bottlenecks:
                content += f"| {b['file']} | {b['age_days']} days | {b['priority'].upper()} |\n"
        else:
            content += "\n---\n\n## ✅ No Major Bottlenecks\n\nAll systems running smoothly!\n"

        # Proactive suggestions
        content += self._generate_suggestions(metrics)

        # Upcoming deadlines
        content += self._generate_deadlines_section()

        content += """
---

*Generated by AI Employee CEO Briefing System*
*For details, check: /Briefings, /Done, /Accounting*
"""

        return content

    def _generate_suggestions(self, metrics: WeeklyMetrics) -> str:
        """Generate proactive suggestions.

        Args:
            metrics: Weekly metrics

        Returns:
            Suggestions section as markdown
        """
        suggestions = """

---

## 💡 Proactive Suggestions

"""

        if metrics.tasks_pending > 10:
            suggestions += f"### 📋 Task Management\n- **High pending task count** ({metrics.tasks_pending} tasks)\n  - [ACTION] Consider batching similar tasks\n  - [ACTION] Delegate or defer low-priority items\n\n"

        if metrics.emails_sent == 0:
            suggestions += "### 📧 Communication\n- **No emails sent this week**\n  - [ACTION] Review pending communications\n  - [ACTION] Follow up with clients or prospects\n\n"

        if metrics.linkedin_posts == 0:
            suggestions += "### 📱 Social Media\n- **No LinkedIn activity this week**\n  - [ACTION] Consider sharing business updates\n  - [ACTION] Engage with network for visibility\n\n"

        if not suggestions.strip():
            suggestions += "### ✅ All Systems Optimized\nNo immediate actions required. Great job this week!\n\n"

        return suggestions

    def _generate_deadlines_section(self) -> str:
        """Generate upcoming deadlines section.

        Returns:
            Deadlines section as markdown
        """
        return """

---

## 📅 Upcoming Deadlines

### This Week
- [ ] Review and approve pending items in Human_Approval/
- [ ] Check accounting transactions for accuracy
- [ ] Update Business_Goals.md if needed

### Next Week
- [ ] Generate next CEO Briefing
- [ ] Review subscription costs and recurring expenses
- [ ] Plan content for LinkedIn posts

---

"""


# ============ SKILL FUNCTIONS ============

def generate_weekly_briefing(week_start: str = None) -> str:
    """Skill function: Generate weekly CEO briefing.

    Args:
        week_start: Start of week as YYYY-MM-DD (optional)

    Returns:
        Path to generated briefing
    """
    briefing = CEOBriefing()

    start_date = None
    if week_start:
        start_date = datetime.strptime(week_start, '%Y-%m-%d')

    path = briefing.generate_weekly_briefing(start_date)
    return f"✅ CEO Briefing generated: {path}"


def create_business_goals(
    revenue_target: float = 10000,
    response_time_hours: int = 24,
    payment_rate_percent: int = 90
) -> str:
    """Skill function: Create business goals file.

    Args:
        revenue_target: Monthly revenue target
        response_time_hours: Target client response time
        payment_rate_percent: Target invoice payment rate

    Returns:
        Success message
    """
    vault_path = Path("./AI_Employee_Vault")
    goals_file = vault_path / 'Business_Goals.md'

    content = f"""---
type: business_goals
last_updated: {datetime.now().isoformat()}
review_frequency: weekly
revenue_target_monthly: {revenue_target}
client_response_time_hours: {response_time_hours}
invoice_payment_rate_percent: {payment_rate_percent}
---

# Business Goals

## Monthly Revenue Target

**Goal:** ${revenue_target:,.2f}/month
**Current MTD:** $0.00 (to be calculated)
**Progress:** 0%

---

## Key Metrics to Track

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Client response time | < {response_time_hours} hours | > {response_time_hours * 2} hours |
| Invoice payment rate | > {payment_rate_percent}% | < 80% |
| Software costs | < $500/month | > $600/month |

---

## Active Projects

1. Project Alpha - Due TBD - Budget TBD
2. AI Employee Development - Ongoing

---

## Subscription Audit Rules

Flag for review if:
- No login in 30 days
- Cost increased > 20%
- Duplicate functionality with another tool

---

## Business Objectives

### Q1 2026
- [x] Set up AI Employee infrastructure
- [x] Implement Gmail and WhatsApp watchers
- [ ] Achieve consistent monthly revenue
- [ ] Build client portfolio

---

*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""

    goals_file.write_text(content, encoding='utf-8')

    return f"✅ Business goals created: {goals_file.name}"


def get_business_summary() -> str:
    """Skill function: Get current business summary.

    Returns:
        Business summary as text
    """
    briefing = CEOBriefing()
    goals = briefing._load_business_goals()

    summary = "📊 Business Summary\n\n"
    summary += f"**Monthly Revenue Target:** ${goals.get('revenue_target_monthly', 0):,.2f}\n"
    summary += f"**Target Response Time:** {goals.get('client_response_time_hours', 24)} hours\n"
    summary += f"**Target Payment Rate:** {goals.get('invoice_payment_rate_percent', 90)}%\n"

    # Get current metrics
    needs_action = Path("./AI_Employee_Vault") / 'Needs_Action'
    if needs_action.exists():
        pending = len(list(needs_action.glob('*.md')))
        summary += f"\n**Pending Tasks:** {pending}\n"

    done = Path("./AI_Employee_Vault") / 'Done'
    if done.exists():
        completed = len(list(done.glob('*.md')))
        summary += f"**Completed Tasks:** {completed}\n"

    return summary


__all__ = [
    'CEOBriefing',
    'generate_weekly_briefing',
    'create_business_goals',
    'get_business_summary'
]
