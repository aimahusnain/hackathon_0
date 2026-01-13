"""
Email Planning Skill - AI-powered email response planning

Analyzes emails and either:
- Auto-approves and sends safe responses
- Creates plans for human review when needed

Usage:
    from skills.email_planner import EmailPlanner

    planner = EmailPlanner(vault_path="./AI_Employee_Vault")
    results = planner.plan_all_emails()
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from skills.vault_update import VaultUpdater
from skills.keyword_analyzer import KeywordAnalyzer, KeywordAnalysis
from skills.dashboard_updater import DashboardUpdater

logger = logging.getLogger('EmailPlanner')


class EmailPlanner:
    """
    AI-powered email response planner with auto-approval.

    Workflow:
    1. Analyzes email using AI or keyword matching
    2. If safe and auto-approved → Send directly
    3. If needs review → Create plan in Plans/

    When Plans Are Created:
    - Emails that need a reply (contain questions, requests, etc.)
    - Risk level is LOW, MEDIUM, or HIGH (not SAFE)
    - Sensitive topics detected (legal, financial, commitments)

    When Emails Are Auto-Sent:
    - Safe acknowledgments (thank you, received, etc.)
    - No risk factors detected
    - Simple confirmations
    """

    def __init__(self, vault_path: str = None, use_ai: bool = True):
        """Initialize the email planner.

        Args:
            vault_path: Path to the Obsidian vault
            use_ai: Whether to use AI for analysis (True) or keyword matching (False)
        """
        self._vault_path = Path(vault_path) if vault_path else Path("./AI_Employee_Vault")
        self._updater = VaultUpdater(str(self._vault_path))
        self._dashboard_updater = DashboardUpdater(str(self._vault_path))
        self._needs_action = self._vault_path / 'Needs_Action'

        # CONSOLIDATED: Use Plans/ folder for all review plans
        self._plans_folder = self._vault_path / 'Plans'
        self._sent_folder = self._vault_path / 'Logs' / 'Auto_Sent'
        self._processed_cache = set()

        # Create folders
        self._plans_folder.mkdir(parents=True, exist_ok=True)
        self._sent_folder.mkdir(parents=True, exist_ok=True)

        # Initialize keyword analyzer
        self._use_ai = use_ai  # Kept for backwards compatibility, but always uses keywords now
        self._analyzer = KeywordAnalyzer(company_handbook_path=str(self._vault_path / 'Company_Handbook.md'))

        # Load processed cache
        self._load_cache()

        # Initialize email sender (for auto-approve)
        try:
            from skills.email_sender import EmailSender
            self._email_sender = EmailSender(str(self._vault_path))
        except Exception as e:
            logger.warning(f'EmailSender not available: {e}')
            self._email_sender = None

        logger.info(f'EmailPlanner initialized (AI: {use_ai})')

    @property
    def vault_path(self) -> Path:
        """Get vault path (read-only)."""
        return self._vault_path

    @property
    def needs_action(self) -> Path:
        """Get Needs_Action folder path (read-only)."""
        return self._needs_action

    @property
    def plans_folder(self) -> Path:
        """Get Plans folder path (read-only)."""
        return self._plans_folder

    @property
    def analyzer(self) -> KeywordAnalyzer:
        """Get keyword analyzer (read-only)."""
        return self._analyzer

    def _load_cache(self) -> None:
        """Load cache of processed email IDs."""
        cache_file = self._vault_path / '.email_planner_cache.json'
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                self._processed_cache = set(data.get('processed', []))
                logger.info(f'Loaded {len(self._processed_cache)} processed IDs from cache')
            except Exception as e:
                logger.error(f'Cache load error: {e}')
                self._processed_cache = set()

    def _save_cache(self) -> None:
        """Save processed email IDs to cache."""
        cache_file = self._vault_path / '.email_planner_cache.json'
        try:
            cache_file.write_text(json.dumps({'processed': list(self._processed_cache)}))
        except Exception as e:
            logger.error(f'Cache save error: {e}')

    def plan_all_emails(self) -> List[Dict[str, Any]]:
        """Plan responses for all emails in Needs_Action.

        Returns:
            List of result dictionaries with status
        """
        results = []

        # Get all email files (match both EMAIL*.md and EMAIL - *.md)
        email_files = list(self._needs_action.glob('EMAIL*.md')) + list(self._needs_action.glob('EMAIL - *.md'))
        email_files.extend(list(self._needs_action.glob('WHATSAPP*.md')) + list(self._needs_action.glob('WHATSAPP - *.md')))

        logger.info(f'Found {len(email_files)} emails to process')

        for email_file in email_files:
            try:
                # Skip if already processed
                if email_file.stem in self._processed_cache:
                    logger.debug(f'Skipping already processed: {email_file.name}')
                    continue

                # Read email content
                content = email_file.read_text(encoding='utf-8')

                # Extract metadata and body
                metadata, body = self._parse_email_file(content)

                # Analyze email
                analysis = self.analyze_email(metadata, body)

                result = {
                    'email_file': email_file.name,
                    'from': metadata.get('from', 'Unknown'),
                    'subject': metadata.get('subject', 'No Subject'),
                    'needs_reply': analysis.needs_reply,
                    'risk_level': analysis.risk_level,
                    'auto_approve': analysis.auto_approve,
                }

                if not analysis.needs_reply:
                    # No reply needed - just log and archive
                    result['action'] = 'archived'
                    result['reason'] = 'No reply needed'
                    self._archive_email(email_file, metadata)

                elif analysis.auto_approve:
                    # Auto-send the safe response
                    result['action'] = 'auto_sent'
                    result['reply'] = analysis.suggested_reply[:100] if analysis.suggested_reply else ''
                    success = self._auto_send_email(email_file, metadata, analysis)
                    result['success'] = success

                else:
                    # Create plan for human review
                    result['action'] = 'created_plan'
                    plan_id = self._create_review_plan(email_file.name, analysis, metadata, body)
                    result['plan_id'] = plan_id

                results.append(result)

                # Mark as processed
                self._processed_cache.add(email_file.stem)

            except Exception as e:
                logger.error(f'Error processing {email_file.name}: {e}')
                results.append({
                    'email_file': email_file.name,
                    'action': 'error',
                    'error': str(e)
                })
                continue

        # Save cache
        self._save_cache()

        return results

    def analyze_email(self, metadata: Dict, body: str) -> KeywordAnalysis:
        """Analyze email using keyword analyzer.

        Args:
            metadata: Email metadata
            body: Email body

        Returns:
            KeywordAnalysis object
        """
        return self._analyzer.analyze(
            sender=metadata.get('from', ''),
            subject=metadata.get('subject', ''),
            body=body
        )

    def _parse_email_file(self, content: str) -> tuple[Dict, str]:
        """Parse email file into metadata and body."""
        metadata = {}
        body = content

        # Extract frontmatter
        if content.startswith('---'):
            frontmatter_end = content.find('---', 3)
            if frontmatter_end != -1:
                frontmatter = content[3:frontmatter_end]
                body = content[frontmatter_end + 3:]

                # Parse frontmatter
                for line in frontmatter.strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip()] = value.strip()

        return metadata, body

    def _auto_send_email(self, email_file: Path, metadata: Dict, analysis: KeywordAnalysis) -> bool:
        """Auto-send an approved email.

        Args:
            email_file: Original email file
            metadata: Email metadata
            analysis: AI analysis

        Returns:
            True if sent successfully
        """
        if not self._email_sender or not analysis.suggested_reply:
            logger.warning('Cannot auto-send: EmailSender not available or no reply generated')
            return False

        try:
            recipient = metadata.get('from', '')
            subject = metadata.get('subject', '')
            if subject and not subject.startswith('Re:'):
                subject = f"Re: {subject}"

            # Send email
            success = self._email_sender.send_email(recipient, subject, analysis.suggested_reply)

            if success:
                # Log the auto-send
                self._log_auto_send(email_file.name, recipient, subject, analysis)

                # Mark original email as completed
                self._updater.update_frontmatter(
                    f"Needs_Action/{email_file.name}",
                    {'status': 'auto_sent', 'auto_sent_at': datetime.now().isoformat()}
                )

                # Move to Done
                self._updater.move_to_folder(f"Needs_Action/{email_file.name}", 'Done')

                # Update dashboard
                try:
                    self._dashboard_updater.record_email_sent(auto=True)
                except Exception as e:
                    logger.warning(f'Failed to update dashboard: {e}')

                logger.info(f'✅ Auto-sent reply for {email_file.name}')
                return True
            else:
                logger.error(f'Failed to auto-send for {email_file.name}')
                return False

        except Exception as e:
            logger.error(f'Auto-send error for {email_file.name}: {e}')
            return False

    def _create_review_plan(self, email_filename: str, analysis: KeywordAnalysis, metadata: Dict, body: str) -> str:
        """Create a plan for human review.

        Args:
            email_filename: Original email filename
            analysis: AI analysis
            metadata: Email metadata
            body: Email body

        Returns:
            Plan ID
        """
        # Generate plan ID
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        clean_name = email_filename.rsplit('.md', 1)[0] if email_filename.endswith('.md') else email_filename
        plan_id = f"PLAN_{timestamp}_{clean_name}"

        # Build plan content
        priority_emoji = {
            'critical': '🔴',
            'high': '🟠',
            'normal': '🟡',
            'low': '🟢'
        }.get(analysis.priority_label, '🟡')

        risk_emoji = {
            'safe': '✅',
            'low': '🟢',
            'medium': '🟡',
            'high': '🔴'
        }.get(analysis.risk_level, '🟡')

        content = f"""---
type: email_plan
plan_id: {plan_id}
email_file: {email_filename}
priority: {analysis.priority_label}
risk_level: {analysis.risk_level}
auto_approve: {str(analysis.auto_approve).lower()}
status: pending_approval
created: {datetime.now().isoformat()}
category: {analysis.category}
---

# Email Response Plan: {metadata.get('subject', 'No Subject')}

**From:** {metadata.get('from', 'Unknown')}
**Priority:** {priority_emoji} {analysis.priority_label.upper()}
**Risk Level:** {risk_emoji} {analysis.risk_level.upper()}
**Category:** {analysis.category.capitalize()}
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## AI Analysis

**Needs Reply:** {'✅ Yes' if analysis.needs_reply else '❌ No'}

**Reason:** {analysis.reason}

**Auto-Approve Decision:** {'✅ Auto-approved (sent directly)' if analysis.auto_approve else '⏳ Pending human review'}

"""

        if analysis.risk_factors:
            content += "**Risk Factors Detected:**\n"
            for factor in analysis.risk_factors:
                content += f"- ⚠️ {factor}\n"
            content += "\n"

        if analysis.conversation_context.get('conversation_aware'):
            content += f"📝 **Context:** {analysis.conversation_context.get('context_notes', 'Conversation history considered')}\n\n"

        content += """---

## Suggested Actions

"""

        # Add suggested actions based on category
        actions = self._generate_suggested_actions(analysis)
        for action in actions:
            content += f"- [ ] {action}\n"

        if analysis.suggested_reply:
            content += f"""

---

## 📝 AI-Generated Draft Reply

```
{analysis.suggested_reply}
```

**Instructions:**
1. Review the draft reply above
2. Edit as needed
3. To approve and send: Move this file to `Approved/` folder
4. To reject: Move to `Rejected/` folder
5. To modify: Edit this file directly

---

## Approval Workflow

**Status:** ⏳ Pending Human Review

**Next Steps:**
- Review AI analysis and draft reply
- Make any necessary edits
- Move file to trigger action:
  - Move to `AI_Employee_Vault/Approved/{plan_id}.md` → Send email
  - Move to `AI_Employee_Vault/Rejected/{plan_id}.md` → Cancel
  - Keep in `Plans/` → Hold for later

---

## Original Email

**Subject:** {metadata.get('subject', 'No Subject')}
**From:** {metadata.get('from', 'Unknown')}
**Date:** {metadata.get('date', '')}

{body[:500]}{'...' if len(body) > 500 else ''}

---

*Generated by AI Employee Email Planner*
*Analysis Method: {'AI' if self._use_ai else 'Keyword-based'}*
*Original Email: {email_filename}*
"""

        # Write plan file to Plans/ folder (CONSOLIDATED)
        plan_file = self._plans_folder / f'{plan_id}.md'
        plan_file.write_text(content, encoding='utf-8')

        # Update original email with plan reference
        self._updater.add_note(
            f"Needs_Action/{email_filename}",
            f"Plan created: {plan_id}.md in Plans/",
            "AI Analysis"
        )

        # Update dashboard
        try:
            self._dashboard_updater.record_plan_created()
        except Exception as e:
            logger.warning(f'Failed to update dashboard: {e}')

        logger.info(f'Created review plan: {plan_id}')
        return plan_id

    def _generate_suggested_actions(self, analysis: KeywordAnalysis) -> List[str]:
        """Generate suggested actions based on analysis."""
        actions = []

        # Priority-based actions
        if analysis.priority >= 4:
            actions.append('🚨 URGENT: Review and respond immediately')
        elif analysis.priority == 3:
            actions.append('⚡ HIGH: Respond within 2 hours')

        # Risk-based actions
        if analysis.risk_level == 'high':
            actions.append('⚠️ Review carefully - sensitive content detected')
            actions.append('Consider consulting with relevant stakeholders')

        # Category-based actions
        category_actions = {
            'invoice': ['Review invoice details', 'Check against records', 'Forward to accounting if needed'],
            'meeting': ['Check calendar availability', 'Confirm or propose time'],
            'project': ['Review requirements', 'Assess timeline and resources'],
            'support': ['Investigate issue', 'Prepare solution'],
        }

        if analysis.category in category_actions:
            actions.extend(category_actions[analysis.category])

        return actions

    def _archive_email(self, email_file: Path, metadata: Dict) -> None:
        """Archive email that doesn't need reply.

        Args:
            email_file: Email file path
            metadata: Email metadata
        """
        try:
            # Update status
            self._updater.update_frontmatter(
                f"Needs_Action/{email_file.name}",
                {'status': 'archived', 'archived_at': datetime.now().isoformat()}
            )

            # Move to Done
            self._updater.move_to_folder(f"Needs_Action/{email_file.name}", 'Done')

            logger.info(f'Archived (no reply needed): {email_file.name}')
        except Exception as e:
            logger.error(f'Archive error for {email_file.name}: {e}')

    def _log_auto_send(self, email_file: str, recipient: str, subject: str, analysis: KeywordAnalysis) -> None:
        """Log auto-sent email.

        Args:
            email_file: Original email filename
            recipient: Email recipient
            subject: Email subject
            analysis: AI analysis
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self._sent_folder / f'AUTO_SENT_{timestamp}.md'

        content = f"""---
type: auto_sent_email
original_email: {email_file}
recipient: {recipient}
subject: {subject}
risk_level: {analysis.risk_level}
sent_at: {datetime.now().isoformat()}
---

# ✅ Auto-Sent Email

**Original Email:** {email_file}
**To:** {recipient}
**Subject:** {subject}
**Risk Level:** {analysis.risk_level.upper()}
**Sent:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## AI Analysis

**Category:** {analysis.category}
**Priority:** {analysis.priority_label}
**Reason:** {analysis.reason}
**Risk Factors:** {', '.join(analysis.risk_factors) if analysis.risk_factors else 'None'}

---

## Auto-Sent Reply

```
{analysis.suggested_reply}
```

---

*Auto-approved and sent by AI Employee*
*AI Analysis: {'Claude' if self._use_ai else 'Keyword-based'}*
"""

        log_file.write_text(content, encoding='utf-8')


# ============ SKILL FUNCTIONS ============

def plan_email(email_file: str = None, use_ai: bool = True) -> str:
    """Skill function: Plan responses for emails.

    Args:
        email_file: Specific email filename (optional)
        use_ai: Use AI analysis (default: True)

    Returns:
        Summary of actions taken
    """
    planner = EmailPlanner(use_ai=use_ai)

    if email_file:
        # Plan single email
        try:
            email_path = planner.needs_action / email_file
            content = email_path.read_text(encoding='utf-8')
            metadata, body = planner._parse_email_file(content)
            analysis = planner.analyze_email(metadata, body)

            if analysis.auto_approve:
                success = planner._auto_send_email(email_path, metadata, analysis)
                return f"✅ Auto-sent reply for {email_file}\nRisk: {analysis.risk_level}\nSuccess: {success}"
            else:
                plan_id = planner._create_review_plan(email_file, analysis, metadata, body)
                return f"📋 Created plan: {plan_id}.md\nRisk: {analysis.risk_level}\nReason: {analysis.reason}"

        except Exception as e:
            return f"❌ Error: {e}"
    else:
        # Plan all emails
        results = planner.plan_all_emails()

        auto_sent = sum(1 for r in results if r.get('action') == 'auto_sent' and r.get('success'))
        plans_created = sum(1 for r in results if r.get('action') == 'created_plan')
        archived = sum(1 for r in results if r.get('action') == 'archived')
        errors = sum(1 for r in results if r.get('action') == 'error')

        output = f"📧 Email Planning Complete\n\n"
        output += f"✅ Auto-sent: {auto_sent}\n"
        output += f"📋 Plans created: {plans_created}\n"
        output += f"📦 Archived: {archived}\n"
        if errors > 0:
            output += f"❌ Errors: {errors}\n"

        return output


def analyze_pending_emails() -> str:
    """Skill function: Get summary of pending emails."""
    planner = EmailPlanner()
    email_files = list(planner.needs_action.glob('*.md'))

    if not email_files:
        return "📭 No pending emails"

    summary = f"📧 Pending Emails: {len(email_files)}\n\n"

    for email_file in email_files:
        try:
            content = email_file.read_text(encoding='utf-8')
            metadata, _ = planner._parse_email_file(content)

            subject = metadata.get('subject', 'No Subject')
            sender = metadata.get('from', 'Unknown')
            priority = metadata.get('priority', 'normal').upper()

            summary += f"- **{email_file.name}**\n"
            summary += f"  From: {sender}\n"
            summary += f"  Subject: {subject}\n"
            summary += f"  Priority: {priority}\n\n"
        except Exception:
            continue

    return summary


__all__ = [
    'EmailPlanner',
    'plan_email',
    'analyze_pending_emails'
]
