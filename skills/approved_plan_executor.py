"""
Approved Plan Executor - Monitors Approved/ folder and executes approved email plans.

This skill checks the Approved/ folder for plans that have been manually approved,
sends the emails, and moves the plans to Done/ with execution metadata.

Usage:
    from skills.approved_plan_executor import ApprovedPlanExecutor
    executor = ApprovedPlanExecutor(vault_path)
    executor.check_and_execute()
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


class ApprovedPlanExecutor:
    """
    Monitor Approved/ folder and execute approved email plans.

    Workflow:
    1. Monitor Approved/ folder for new plans
    2. Extract email details and suggested reply from plan
    3. Send email using EmailSender
    4. Move plan to Done/ with execution metadata
    5. Move associated email from Needs_Action to Inbox
    """

    def __init__(self, vault_path: str):
        """Initialize the approved plan executor.

        Args:
            vault_path: Path to Obsidian vault
        """
        self._vault_path = Path(vault_path)
        self._logger = logging.getLogger('ApprovedPlanExecutor')

        # Track processed plans to avoid re-processing
        self._processed_plans_file = self._vault_path / '.approved_plans_executed.json'
        self._processed_plans = self._load_processed_plans()

        # Folder paths
        self._approved_folder = self._vault_path / 'Approved'
        self._done_folder = self._vault_path / 'Done'
        self._needs_action = self._vault_path / 'Needs_Action'
        self._inbox = self._vault_path / 'Inbox'

        # Lazy load email sender
        self._email_sender = None

    def _load_processed_plans(self) -> set:
        """Load set of already processed plan IDs."""
        if self._processed_plans_file.exists():
            try:
                data = json.loads(self._processed_plans_file.read_text())
                return set(data.get('processed_plans', []))
            except Exception as e:
                self._logger.warning(f'Could not load processed plans: {e}')
        return set()

    def _save_processed_plans(self) -> None:
        """Save set of processed plan IDs."""
        try:
            self._processed_plans_file.write_text(json.dumps({
                'processed_plans': list(self._processed_plans),
                'last_updated': datetime.now().isoformat()
            }))
        except Exception as e:
            self._logger.error(f'Could not save processed plans: {e}')

    def _get_email_sender(self):
        """Lazy load the email sender."""
        if self._email_sender is None:
            try:
                from skills.email_sender import EmailSender
                self._email_sender = EmailSender(str(self._vault_path))
            except Exception as e:
                self._logger.error(f'Failed to load EmailSender: {e}')
                return None
        return self._email_sender

    def check_and_execute(self) -> int:
        """Check for newly approved plans and execute them.

        Returns:
            Number of plans executed
        """
        executed_count = 0

        try:
            # Ensure Approved folder exists
            if not self._approved_folder.exists():
                return 0

            # Get all plan files in Approved/
            plan_files = list(self._approved_folder.glob('PLAN_*.md'))

            for plan_file in plan_files:
                plan_id = plan_file.stem  # Filename without extension

                # Skip if already processed
                if plan_id in self._processed_plans:
                    continue

                # Execute the plan
                success = self._execute_plan(plan_file, plan_id)

                # Mark as processed (even if failed, to avoid infinite retry)
                self._processed_plans.add(plan_id)

                if success:
                    executed_count += 1

            # Save processed plans
            if executed_count > 0:
                self._save_processed_plans()

        except Exception as e:
            self._logger.error(f'Error in check_and_execute: {e}')

        return executed_count

    def _execute_plan(self, plan_file: Path, plan_id: str) -> bool:
        """Execute a single approved plan.

        Args:
            plan_file: Path to the plan file
            plan_id: Plan ID (filename without extension)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Read plan content
            content = plan_file.read_text(encoding='utf-8')

            # Extract email details from frontmatter
            email_file_match = re.search(r'email_file:\s*([^\n]+)', content)
            recipient_match = re.search(r'from:\s*([^\n]+)', content)
            subject_match = re.search(r'subject:\s*([^\n]+)', content)

            if not email_file_match or not recipient_match:
                self._logger.warning(f'Missing email metadata in {plan_id}')
                return False

            email_filename = email_file_match.group(1).strip()
            recipient = recipient_match.group(1).strip()

            # Extract subject from frontmatter or title
            if subject_match:
                subject = subject_match.group(1).strip()
            else:
                # Try to extract from # Title
                title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
                if title_match:
                    subject = title_match.group(1).replace('Email Response Plan: ', '').strip()
                else:
                    subject = "Re: (No Subject)"

            # Ensure subject starts with Re:
            if subject and not subject.startswith('Re:'):
                subject = f"Re: {subject}"

            # Extract suggested reply from plan
            reply_match = re.search(r'## Suggested Reply\s*```\s*(.*?)\s*```', content, re.DOTALL)
            if not reply_match:
                # Try without code blocks
                reply_match = re.search(r'## Suggested Reply\s*(.*?)\s*---', content, re.DOTALL)

            if not reply_match:
                self._logger.warning(f'No suggested reply found in {plan_id}')
                return False

            suggested_reply = reply_match.group(1).strip()

            # Send the email
            email_sender = self._get_email_sender()
            if not email_sender:
                self._logger.error(f'EmailSender not available for {plan_id}')
                return False

            success = email_sender.send_email(recipient, subject, suggested_reply)

            if success:
                self._logger.info(f'Sent email for approved plan: {plan_id}')

                # Move plan to Done with execution metadata
                self._move_plan_to_done(plan_file, plan_id, recipient, content)

                # Move associated email from Needs_Action to Inbox
                self._move_email_to_inbox(email_filename, plan_id)

                return True
            else:
                self._logger.warning(f'Failed to send email for plan: {plan_id}')
                return False

        except Exception as e:
            self._logger.error(f'Error executing plan {plan_id}: {e}')
            return False

    def _move_plan_to_done(self, plan_file: Path, plan_id: str, recipient: str, content: str) -> None:
        """Move executed plan to Done/ with metadata.

        Args:
            plan_file: Path to the plan file in Approved/
            plan_id: Plan ID
            recipient: Email recipient
            content: Plan content
        """
        try:
            done_path = self._done_folder / f'{plan_id}.md'

            # Update frontmatter with execution info
            frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
            if frontmatter_match:
                frontmatter = frontmatter_match.group(1)
                # Add execution metadata
                frontmatter += f'\nexecuted_at: {datetime.now().isoformat()}\nexecuted_to: {recipient}\nstatus: executed'

                # Reconstruct file
                new_content = f"---\n{frontmatter}\n---\n{content[frontmatter_match.end():]}"

                # Write to Done folder
                done_path.write_text(new_content, encoding='utf-8')

                # Remove from Approved
                plan_file.unlink()

                self._logger.info(f'Moved {plan_id} to Done/')
            else:
                self._logger.warning(f'Could not parse frontmatter for {plan_id}')

        except Exception as e:
            self._logger.error(f'Error moving plan to Done: {e}')

    def _move_email_to_inbox(self, email_filename: str, plan_id: str) -> None:
        """Move associated email from Needs_Action to Inbox.

        Args:
            email_filename: Name of the email file
            plan_id: Plan ID
        """
        try:
            email_path = self._needs_action / email_filename
            if not email_path.exists():
                self._logger.info(f'Email not in Needs_Action (may already be moved): {email_filename}')
                return

            # Read email content
            email_content = email_path.read_text(encoding='utf-8')

            # Update frontmatter
            frontmatter_match = re.match(r'^---\n(.*?)\n---\n', email_content, re.DOTALL)
            if frontmatter_match:
                frontmatter = frontmatter_match.group(1)
                # Add execution info
                frontmatter += f'\nplan_executed_at: {datetime.now().isoformat()}\nplan_id: {plan_id}\nstatus: executed'

                # Reconstruct email
                new_email_content = f"---\n{frontmatter}\n---\n{email_content[frontmatter_match.end():]}"

                # Write to Inbox
                inbox_path = self._inbox / email_filename
                inbox_path.write_text(new_email_content, encoding='utf-8')

                # Remove from Needs_Action
                email_path.unlink()

                self._logger.info(f'Moved {email_filename} to Inbox/')
            else:
                self._logger.warning(f'Could not parse frontmatter for {email_filename}')

        except Exception as e:
            self._logger.error(f'Error moving email to Inbox: {e}')


# Convenience function
def execute_approved_plans(vault_path: str) -> int:
    """Execute all approved plans in the Approved/ folder.

    Args:
        vault_path: Path to vault

    Returns:
        Number of plans executed
    """
    executor = ApprovedPlanExecutor(vault_path)
    return executor.check_and_execute()
