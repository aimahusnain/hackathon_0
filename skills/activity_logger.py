"""
AI Employee Activity Logger Skill

Logs all AI Employee activities to daily markdown files in the Logs folder.
Provides structured, searchable activity tracking.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional


class ActivityLogger:
    """
    Logs AI Employee activities to daily markdown files.

    Creates structured logs in the Logs folder with:
    - Daily activity summaries
    - Email processing events
    - Plan generation events
    - Errors and warnings
    - Performance metrics
    """

    def __init__(self, vault_path: str):
        """
        Initialize the activity logger.

        Args:
            vault_path: Path to the Obsidian vault
        """
        self.vault_path = Path(vault_path)
        self.logs_folder = self.vault_path / 'Logs'
        self.logs_folder.mkdir(parents=True, exist_ok=True)

        self._current_log_file = None
        self._daily_counts = {
            'emails_processed': 0,
            'plans_created': 0,
            'errors': 0,
            'warnings': 0,
        }

    def _get_todays_log_file(self) -> Path:
        """
        Get the path to today's log file.

        Returns:
            Path to today's log markdown file
        """
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = self.logs_folder / f'{today}.md'

        # If file doesn't exist, create it with header
        if not log_file.exists():
            self._initialize_daily_log(log_file)

        return log_file

    def _initialize_daily_log(self, log_file: Path) -> None:
        """
        Initialize a new daily log file with header.

        Args:
            log_file: Path to the log file to initialize
        """
        date_str = datetime.now().strftime('%Y-%m-%d')
        weekday = datetime.now().strftime('%A')

        header = f'''---
type: daily_log
date: {date_str}
weekday: {weekday}
status: active
---

# Activity Log: {date_str} ({weekday})

## Summary
<!-- Updated automatically throughout the day -->
- **Emails Processed:** 0
- **Plans Created:** 0
- **Errors:** 0
- **Warnings:** 0

---

## Timeline

### Morning (06:00 - 12:00)
<!-- Activities logged here -->

### Afternoon (12:00 - 18:00)
<!-- Activities logged here -->

### Evening (18:00 - 24:00)
<!-- Activities logged here -->

---

## Email Processing Log
<!-- New emails are logged here as they arrive -->

---

## Plans Generated
<!-- Plans created today are logged here -->

---

## Errors & Warnings
<!-- Errors and warnings logged here -->

---

## Performance Metrics
<!-- System performance and metrics -->

'''
        log_file.write_text(header)

    def log_email_received(
        self,
        msg_id: str,
        from_addr: str,
        subject: str,
        priority: str,
        action_file: str
    ) -> None:
        """
        Log an incoming email.

        Args:
            msg_id: Gmail message ID
            from_addr: Sender email address
            subject: Email subject
            priority: Detected priority level
            action_file: Created action file name
        """
        log_file = self._get_todays_log_file()
        timestamp = datetime.now().strftime('%H:%M:%S')

        entry = f'''
### [{timestamp}] New Email Received
- **From:** {from_addr}
- **Subject:** {subject}
- **Priority:** {priority.upper()}
- **Message ID:** {msg_id}
- **Action File:** [[{action_file}]]
'''

        # Add to email processing section
        content = log_file.read_text()
        section_marker = '## Email Processing Log'

        if section_marker in content:
            content = content.replace(
                section_marker,
                section_marker + entry
            )
            log_file.write_text(content)

        # Update count
        self._daily_counts['emails_processed'] += 1
        self._update_summary(log_file)

    def log_plan_created(
        self,
        plan_id: str,
        subject: str,
        complexity: float,
        source_email: str
    ) -> None:
        """
        Log a plan creation event.

        Args:
            plan_id: Plan identifier
            subject: Plan subject (from email)
            complexity: Complexity score
            source_email: Source email file
        """
        log_file = self._get_todays_log_file()
        timestamp = datetime.now().strftime('%H:%M:%S')

        entry = f'''
### [{timestamp}] Plan Created
- **Plan ID:** [[{plan_id}]]
- **Subject:** {subject}
- **Complexity:** {complexity}/1.0
- **Source:** [[{source_email}]]
'''

        # Add to plans section
        content = log_file.read_text()
        section_marker = '## Plans Generated'

        if section_marker in content:
            content = content.replace(
                section_marker,
                section_marker + entry
            )
            log_file.write_text(content)

        # Update count
        self._daily_counts['plans_created'] += 1
        self._update_summary(log_file)

    def log_email_moved_to_done(
        self,
        email_file: str,
        completed_date: str
    ) -> None:
        """
        Log an email moved to done.

        Args:
            email_file: Email file name
            completed_date: Completion timestamp
        """
        log_file = self._get_todays_log_file()
        timestamp = datetime.now().strftime('%H:%M:%S')

        entry = f'''
### [{timestamp}] Email Completed
- **File:** [[{email_file}]]
- **Moved to:** Done/
- **Completed:** {completed_date}
'''

        # Add to email processing section
        content = log_file.read_text()
        section_marker = '## Email Processing Log'

        if section_marker in content:
            # Insert before the next section
            insert_pos = content.find('\n## ', content.find(section_marker) + len(section_marker))
            if insert_pos == -1:
                content += entry
            else:
                content = content[:insert_pos] + entry + content[insert_pos:]

            log_file.write_text(content)

    def log_error(self, error_type: str, error_message: str, context: str = "") -> None:
        """
        Log an error.

        Args:
            error_type: Type of error (e.g., 'API Error', 'File Error')
            error_message: Error message
            context: Additional context (optional)
        """
        log_file = self._get_todays_log_file()
        timestamp = datetime.now().strftime('%H:%M:%S')

        entry = f'''
### [{timestamp}] ⚠️ Error: {error_type}
**Message:** {error_message}

**Context:**
{context}

---

'''

        # Add to errors section
        content = log_file.read_text()
        section_marker = '## Errors & Warnings'

        if section_marker in content:
            content = content.replace(
                section_marker,
                section_marker + entry
            )
            log_file.write_text(content)

        # Update count
        self._daily_counts['errors'] += 1
        self._update_summary(log_file)

    def log_warning(self, warning_type: str, warning_message: str) -> None:
        """
        Log a warning.

        Args:
            warning_type: Type of warning
            warning_message: Warning message
        """
        log_file = self._get_todays_log_file()
        timestamp = datetime.now().strftime('%H:%M:%S')

        entry = f'### [{timestamp}] ⚡ Warning: {warning_type}\n**Message:** {warning_message}\n\n'

        # Add to errors section
        content = log_file.read_text()
        section_marker = '## Errors & Warnings'

        if section_marker in content:
            # Find the end of the errors section
            next_section = content.find('\n## ', content.find(section_marker) + len(section_marker))

            if next_section == -1:
                content += entry
            else:
                content = content[:next_section] + entry + '\n' + content[next_section:]

            log_file.write_text(content)

        # Update count
        self._daily_counts['warnings'] += 1
        self._update_summary(log_file)

    def log_system_event(self, event_type: str, message: str) -> None:
        """
        Log a general system event.

        Args:
            event_type: Type of event (e.g., 'Startup', 'Shutdown', 'Configuration')
            message: Event message
        """
        log_file = self._get_todays_log_file()
        timestamp = datetime.now().strftime('%H:%M:%S')

        # Determine time period
        hour = datetime.now().hour
        if 6 <= hour < 12:
            period = 'Morning'
        elif 12 <= hour < 18:
            period = 'Afternoon'
        else:
            period = 'Evening'

        entry = f'- **[{timestamp}]** {event_type}: {message}\n'

        # Add to appropriate time period section
        content = log_file.read_text()
        section_marker = f'### {period} ('

        if section_marker in content:
            # Find the next section
            section_start = content.find(section_marker)
            next_section = content.find('\n###', section_start + 1)

            if next_section == -1:
                next_section = content.find('\n##', section_start)

            if next_section == -1:
                content += entry
            else:
                content = content[:next_section] + entry + content[next_section:]

            log_file.write_text(content)

    def _update_summary(self, log_file: Path) -> None:
        """
        Update the summary section with current counts.

        Args:
            log_file: Path to the log file
        """
        content = log_file.read_text()

        # Update summary counts
        summary = f'''## Summary
<!-- Updated automatically throughout the day -->
- **Emails Processed:** {self._daily_counts['emails_processed']}
- **Plans Created:** {self._daily_counts['plans_created']}
- **Errors:** {self._daily_counts['errors']}
- **Warnings:** {self._daily_counts['warnings']}'''

        content = re.sub(
            r'## Summary.*?(?=\n##)',
            summary,
            content,
            flags=re.DOTALL
        )

        log_file.write_text(content)

    def get_daily_stats(self) -> Dict[str, int]:
        """
        Get today's activity statistics.

        Returns:
            Dictionary with daily counts
        """
        return self._daily_counts.copy()

    def get_recent_activities(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get activities from the past N days.

        Args:
            days: Number of days to look back

        Returns:
            List of daily summaries
        """
        activities = []
        today = datetime.now()

        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            log_file = self.logs_folder / f'{date_str}.md'

            if log_file.exists():
                content = log_file.read_text()

                # Extract summary
                summary_match = re.search(
                    r'Emails Processed:\s*(\d+).*?Plans Created:\s*(\d+).*?Errors:\s*(\d+)',
                    content,
                    re.DOTALL
                )

                if summary_match:
                    activities.append({
                        'date': date_str,
                        'emails_processed': int(summary_match.group(1)),
                        'plans_created': int(summary_match.group(2)),
                        'errors': int(summary_match.group(3)),
                        'log_file': str(log_file.relative_to(self.vault_path))
                    })

        return activities


import re  # Import at module level


def main():
    """CLI interface for activity logger."""
    import argparse

    parser = argparse.ArgumentParser(description='AI Employee Activity Logger')
    parser.add_argument('--vault', default='./AI_Employee_Vault', help='Path to vault')
    parser.add_argument('--test', action='store_true', help='Run test logging')

    args = parser.parse_args()

    logger = ActivityLogger(args.vault)

    if args.test:
        # Test logging
        logger.log_system_event('Test', 'Activity logger test started')

        logger.log_email_received(
            msg_id='test123',
            from_addr='test@example.com',
            subject='Test Email',
            priority='normal',
            action_file='EMAIL_test123.md'
        )

        logger.log_plan_created(
            plan_id='PLAN_test123',
            subject='Test Plan',
            complexity=0.75,
            source_email='EMAIL_test123.md'
        )

        logger.log_email_moved_to_done(
            email_file='EMAIL_old123.md',
            completed_date=datetime.now().isoformat()
        )

        print(f"✓ Test logs created in: {logger.logs_folder}")
        print(f"  Today's stats: {logger.get_daily_stats()}")


if __name__ == '__main__':
    main()
