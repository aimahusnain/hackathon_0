"""
Email to Inbox Mover - Moves emails from Needs_Action to Inbox when plans are completed.

This skill monitors the Done/ folder for newly completed plans and moves
their associated emails from Needs_Action/ to Inbox/.

Usage:
    from skills.email_to_inbox import EmailToInboxMover
    mover = EmailToInboxMover(vault_path)
    mover.check_and_move()
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from skills.vault_update import VaultUpdater


class EmailToInboxMover:
    """
    Monitor completed plans and move associated emails to Inbox.

    Workflow:
    1. Monitor Done/ folder for new plans
    2. Find the associated email in Needs_Action/
    3. Move email to Inbox/ with completion note
    """

    def __init__(self, vault_path: str):
        """Initialize the email mover.

        Args:
            vault_path: Path to Obsidian vault
        """
        self._vault_path = Path(vault_path)
        self._vault_updater = VaultUpdater(vault_path)
        self._logger = logging.getLogger('EmailToInboxMover')

        # Track processed plans to avoid re-processing
        self._processed_plans_file = self._vault_path / '.processed_plans.json'
        self._processed_plans = self._load_processed_plans()

        # Folder paths
        self._done_folder = self._vault_path / 'Done'
        self._needs_action = self._vault_path / 'Needs_Action'
        self._inbox = self._vault_path / 'Inbox'

    def _load_processed_plans(self) -> set:
        """Load set of already processed plan IDs."""
        if self._processed_plans_file.exists():
            try:
                import json
                data = json.loads(self._processed_plans_file.read_text())
                return set(data.get('processed_plans', []))
            except Exception as e:
                self._logger.warning(f'Could not load processed plans: {e}')
        return set()

    def _save_processed_plans(self) -> None:
        """Save set of processed plan IDs."""
        try:
            import json
            self._processed_plans_file.write_text(json.dumps({
                'processed_plans': list(self._processed_plans),
                'last_updated': datetime.now().isoformat()
            }))
        except Exception as e:
            self._logger.error(f'Could not save processed plans: {e}')

    def check_and_move(self) -> int:
        """Check for newly completed plans and move their emails to Inbox.

        Returns:
            Number of emails moved
        """
        moved_count = 0

        try:
            # Get all plan files in Done/
            plan_files = list(self._done_folder.glob('PLAN_*.md'))

            for plan_file in plan_files:
                plan_id = plan_file.stem  # Filename without extension

                # Skip if already processed
                if plan_id in self._processed_plans:
                    continue

                # Read plan to find associated email
                try:
                    content = plan_file.read_text(encoding='utf-8')

                    # Extract email_file from frontmatter
                    email_file_match = re.search(r'email_file:\s*([^\n]+)', content)
                    if not email_file_match:
                        self._logger.warning(f'No email_file found in {plan_id}')
                        self._processed_plans.add(plan_id)
                        continue

                    email_filename = email_file_match.group(1).strip()
                    email_path = self._needs_action / email_filename

                    # Check if email exists in Needs_Action
                    if not email_path.exists():
                        self._logger.warning(f'Email not found in Needs_Action: {email_filename}')
                        self._processed_plans.add(plan_id)
                        continue

                    # Move email to Inbox
                    inbox_path = self._inbox / email_filename

                    # Read email content
                    email_content = email_path.read_text(encoding='utf-8')

                    # Update frontmatter
                    frontmatter_match = re.match(r'^---\n(.*?)\n---\n', email_content, re.DOTALL)
                    if frontmatter_match:
                        frontmatter = frontmatter_match.group(1)
                        # Add completion info
                        frontmatter += f'\nplan_completed_at: {datetime.now().isoformat()}\nplan_id: {plan_id}\nstatus: completed'

                        # Reconstruct email
                        new_email_content = f"---\n{frontmatter}\n---\n{email_content[frontmatter_match.end():]}"

                        # Write to Inbox
                        inbox_path.write_text(new_email_content, encoding='utf-8')

                        # Remove from Needs_Action
                        email_path.unlink()

                        moved_count += 1
                        self._logger.info(f'✅ Moved {email_filename} to Inbox/ (plan: {plan_id})')
                    else:
                        self._logger.warning(f'Could not parse frontmatter for {email_filename}')

                except Exception as e:
                    self._logger.error(f'Error processing plan {plan_id}: {e}')

                # Mark as processed even if there was an error
                self._processed_plans.add(plan_id)

            # Save processed plans
            if moved_count > 0:
                self._save_processed_plans()

        except Exception as e:
            self._logger.error(f'Error in check_and_move: {e}')

        return moved_count

    def check_plan_completion(self, plan_id: str) -> bool:
        """Check if a specific plan is completed and move its email.

        Args:
            plan_id: Plan ID to check (e.g., 'PLAN_20260114_012150')

        Returns:
            True if email was moved, False otherwise
        """
        plan_file = self._done_folder / f'{plan_id}.md'

        if not plan_file.exists():
            self._logger.warning(f'Plan not found in Done/: {plan_id}')
            return False

        try:
            content = plan_file.read_text(encoding='utf-8')

            # Extract email_file from frontmatter
            email_file_match = re.search(r'email_file:\s*([^\n]+)', content)
            if not email_file_match:
                self._logger.warning(f'No email_file found in {plan_id}')
                return False

            email_filename = email_file_match.group(1).strip()
            email_path = self._needs_action / email_filename

            # Check if email exists in Needs_Action
            if not email_path.exists():
                self._logger.info(f'Email not in Needs_Action (may already be in Inbox): {email_filename}')
                return False

            # Move email to Inbox
            inbox_path = self._inbox / email_filename

            # Read email content
            email_content = email_path.read_text(encoding='utf-8')

            # Update frontmatter
            frontmatter_match = re.match(r'^---\n(.*?)\n---\n', email_content, re.DOTALL)
            if frontmatter_match:
                frontmatter = frontmatter_match.group(1)
                # Add completion info
                frontmatter += f'\nplan_completed_at: {datetime.now().isoformat()}\nplan_id: {plan_id}\nstatus: completed'

                # Reconstruct email
                new_email_content = f"---\n{frontmatter}\n---\n{email_content[frontmatter_match.end():]}"

                # Write to Inbox
                inbox_path.write_text(new_email_content, encoding='utf-8')

                # Remove from Needs_Action
                email_path.unlink()

                self._logger.info(f'✅ Moved {email_filename} to Inbox/ (plan: {plan_id})')
                return True
            else:
                self._logger.warning(f'Could not parse frontmatter for {email_filename}')
                return False

        except Exception as e:
            self._logger.error(f'Error moving email for plan {plan_id}: {e}')
            return False


# Convenience function
def move_email_to_inbox(vault_path: str, plan_id: str) -> bool:
    """Move email to Inbox when plan is completed.

    Args:
        vault_path: Path to vault
        plan_id: Plan ID (e.g., 'PLAN_20260114_012150')

    Returns:
        True if successful, False otherwise
    """
    mover = EmailToInboxMover(vault_path)
    return mover.check_plan_completion(plan_id)
