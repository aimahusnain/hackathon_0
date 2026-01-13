"""
Email Sender Skill - Send emails via Gmail API

This skill provides functionality to send emails using Gmail API.
It includes draft creation, sending, and logging capabilities.

Usage:
    from skills.email_sender import EmailSender

    sender = EmailSender(vault_path="./AI_Employee_Vault")
    sender.send_email("to@example.com", "Subject", "Body")
"""

import base64
import json
import logging
from pathlib import Path
from email.message import EmailMessage
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

import pickle
import os
from dotenv import load_dotenv

from skills.vault_update import VaultUpdater
from skills.dashboard_updater import DashboardUpdater


class EmailSender:
    """
    Send emails via Gmail API.

    Features:
    - Send emails directly
    - Save drafts
    - Log all sent emails to vault
    - Support for attachments
    - Dry-run mode for testing
    """

    def __init__(self, vault_path: str = None, credentials_path: str = None, dry_run: bool = False):
        """Initialize the email sender.

        Args:
            vault_path: Path to the Obsidian vault
            credentials_path: Path to Gmail token.json file
            dry_run: If True, log emails without sending
        """
        self._vault_path = Path(vault_path) if vault_path else Path("./AI_Employee_Vault")
        self._updater = VaultUpdater(str(self._vault_path))
        self._dashboard_updater = DashboardUpdater(str(self._vault_path))
        self._dry_run = dry_run

        # Setup logging
        self._logger = logging.getLogger('EmailSender')

        # Initialize Gmail service
        self._service = None
        if GMAIL_AVAILABLE:
            self._service = self._authenticate(credentials_path)
        else:
            self._logger.warning('Gmail API not available. Install google-auth-oauthlib and google-api-python-client')

        # Sent emails folder
        self._sent_folder = self._vault_path / 'Logs' / 'Sent_Emails'
        self._sent_folder.mkdir(parents=True, exist_ok=True)

    def _authenticate(self, credentials_path: str = None):
        """Authenticate with Gmail API."""
        if not GMAIL_AVAILABLE:
            return None

        load_dotenv()

        try:
            creds = None

            # Try pickle files first (used by GmailWatcher)
            pickle_paths = []
            if credentials_path:
                pickle_paths.append(Path(credentials_path))
            pickle_paths.append(Path('Sessions/token.pickle'))
            pickle_paths.append(Path('token.pickle'))
            pickle_paths.append(self._vault_path / 'Sessions/token.pickle')

            for pickle_path in pickle_paths:
                if pickle_path.exists():
                    try:
                        with open(pickle_path, 'rb') as token:
                            creds = pickle.load(token)
                        self._logger.info(f'Loaded credentials from {pickle_path}')
                        break
                    except Exception as e:
                        self._logger.debug(f'Failed to load {pickle_path}: {e}')
                        continue

            # Try JSON files as fallback
            if not creds:
                json_paths = [
                    Path('token.json'),
                    Path('.credentials/token.json'),
                    self._vault_path / 'token.json'
                ]
                for json_path in json_paths:
                    if json_path.exists():
                        try:
                            creds = Credentials.from_authorized_user_file(str(json_path))
                            self._logger.info(f'Loaded credentials from {json_path}')
                            break
                        except Exception as e:
                            self._logger.debug(f'Failed to load {json_path}: {e}')
                            continue

            # Refresh if expired
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self._logger.info('Credentials refreshed successfully')
                except Exception as e:
                    self._logger.error(f'Failed to refresh credentials: {e}')
                    creds = None

            if not creds or not creds.valid:
                # Try to create new credentials from environment variables
                client_id = os.getenv('GMAIL_CLIENT_ID')
                client_secret = os.getenv('GMAIL_CLIENT_SECRET')

                if client_id and client_secret:
                    self._logger.warning('Credentials expired. Please run Gmail watcher to re-authenticate.')
                    self._logger.info('Or, authenticate now by running: python -c "from Watchers.gmail_watcher import GmailWatcher; GmailWatcher()"')
                    return None
                else:
                    self._logger.warning('No valid Gmail credentials found and no OAuth config in .env')
                    self._logger.info('Please add GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET to .env file')
                    return None

            service = build('gmail', 'v1', credentials=creds)
            self._logger.info('Gmail service initialized successfully')
            return service

        except Exception as e:
            self._logger.error(f'Gmail authentication failed: {e}')
            return None

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: List[str] = None,
        bcc: List[str] = None,
        reply_to: str = None
    ) -> bool:
        """Send an email.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text or HTML)
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            reply_to: Reply-to address (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Create email message
            message = EmailMessage()
            message.set_content(body)

            message['To'] = to
            message['Subject'] = subject

            if cc:
                message['Cc'] = ', '.join(cc)
            if bcc:
                message['Bcc'] = ', '.join(bcc)
            if reply_to:
                message['Reply-To'] = reply_to

            # Encode message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            # Dry run mode
            if self._dry_run:
                self._logger.info(f'[DRY RUN] Would send email to {to}')
                self._log_email(to, subject, body, 'dry_run')
                return True

            # Send via Gmail API
            if not self._service:
                self._logger.error('Gmail service not available')
                self._log_email(to, subject, body, 'failed', 'Gmail service not available')
                return False

            send_message = {
                'raw': encoded_message
            }

            result = self._service.users().messages().send(
                userId='me',
                body=send_message
            ).execute()

            message_id = result.get('id')
            self._logger.info(f'Email sent successfully: {message_id}')

            # Log to vault
            self._log_email(to, subject, body, 'sent', message_id)

            # Update dashboard
            try:
                self._dashboard_updater.record_email_sent(auto=False)
            except Exception as e:
                self._logger.warning(f'Failed to update dashboard: {e}')

            return True

        except HttpError as e:
            error_msg = f'Gmail API error: {e}'
            self._logger.error(error_msg)
            self._log_email(to, subject, body, 'failed', error_msg)
            return False
        except Exception as e:
            error_msg = f'Error sending email: {e}'
            self._logger.error(error_msg)
            self._log_email(to, subject, body, 'failed', error_msg)
            return False

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str
    ) -> Optional[str]:
        """Create a draft email (doesn't send).

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body

        Returns:
            Draft ID if successful, None otherwise
        """
        try:
            if not self._service:
                self._logger.error('Gmail service not available')
                return None

            message = EmailMessage()
            message.set_content(body)
            message['To'] = to
            message['Subject'] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            draft_message = {
                'message': {
                    'raw': encoded_message
                }
            }

            result = self._service.users().drafts().create(
                userId='me',
                body=draft_message
            ).execute()

            draft_id = result.get('id')
            self._logger.info(f'Draft created: {draft_id}')

            # Log to vault
            self._log_email(to, subject, body, 'draft', draft_id)

            return draft_id

        except Exception as e:
            self._logger.error(f'Error creating draft: {e}')
            return None

    def _log_email(
        self,
        to: str,
        subject: str,
        body: str,
        status: str,
        message_id: str = None
    ) -> None:
        """Log email to vault.

        Args:
            to: Recipient
            subject: Subject
            body: Email body
            status: Status (sent, failed, draft, dry_run)
            message_id: Gmail message ID (optional)
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"SENT_EMAIL_{timestamp}.md"
        filepath = self._sent_folder / filename

        status_emoji = {
            'sent': '✅',
            'failed': '❌',
            'draft': '📝',
            'dry_run': '🧪'
        }.get(status, '📧')

        content = f"""---
type: sent_email
status: {status}
message_id: {message_id or 'N/A'}
to: {to}
subject: {subject}
sent: {datetime.now().isoformat()}
---

# {status_emoji} Email {status.title()}: {subject}

**To:** {to}
**Subject:** {subject}
**Status:** {status.upper()}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Email Body

{body}

---

## Metadata

- **Message ID:** {message_id or 'N/A'}
- **Status:** {status}
- **Logged:** {datetime.now().isoformat()}

---

*Logged by AI Employee Email Sender*
"""

        filepath.write_text(content, encoding='utf-8')

    def get_recent_sent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get list of recently sent emails.

        Args:
            limit: Maximum number of emails to return

        Returns:
            List of sent email dictionaries
        """
        emails = []

        for log_file in sorted(self._sent_folder.glob('SENT_EMAIL_*.md'), reverse=True)[:limit]:
            try:
                content = log_file.read_text(encoding='utf-8')

                # Extract frontmatter
                metadata = {}
                if content.startswith('---'):
                    frontmatter_end = content.find('---', 3)
                    if frontmatter_end != -1:
                        frontmatter = content[3:frontmatter_end]
                        for line in frontmatter.strip().split('\n'):
                            if ':' in line:
                                key, value = line.split(':', 1)
                                metadata[key.strip()] = value.strip()

                emails.append({
                    'file': log_file.name,
                    'metadata': metadata
                })
            except Exception:
                continue

        return emails

    def set_dry_run(self, dry_run: bool) -> None:
        """Enable or disable dry run mode.

        Args:
            dry_run: True to enable dry run mode
        """
        self._dry_run = dry_run
        if dry_run:
            self._logger.info('Dry run mode enabled - emails will be logged but not sent')
        else:
            self._logger.info('Dry run mode disabled - emails will be sent')


# ============ SKILL FUNCTIONS ============

def send_email(
    to: str,
    subject: str,
    body: str,
    cc: List[str] = None
) -> str:
    """Skill function: Send an email.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body
        cc: CC recipients (optional)

    Returns:
        Success/failure message
    """
    sender = EmailSender()
    success = sender.send_email(to, subject, body, cc=cc)

    if success:
        return f"✅ Email sent successfully to {to}"
    else:
        return f"❌ Failed to send email to {to}"


def create_email_draft(to: str, subject: str, body: str) -> str:
    """Skill function: Create an email draft.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body

    Returns:
        Draft ID or error message
    """
    sender = EmailSender()
    draft_id = sender.create_draft(to, subject, body)

    if draft_id:
        return f"✅ Draft created: {draft_id}"
    else:
        return f"❌ Failed to create draft"


def list_sent_emails(limit: int = 10) -> str:
    """Skill function: List recently sent emails.

    Args:
        limit: Maximum number of emails to show

    Returns:
        Formatted list of sent emails
    """
    sender = EmailSender()
    emails = sender.get_recent_sent(limit)

    if not emails:
        return "📭 No sent emails found"

    output = f"📧 Recently Sent Emails (last {len(emails)})\n\n"

    for email in emails:
        metadata = email['metadata']
        status = metadata.get('status', 'unknown').upper()
        to = metadata.get('to', 'Unknown')
        subject = metadata.get('subject', 'No Subject')
        sent = metadata.get('sent', 'Unknown')

        output += f"- **{email['file']}**\n"
        output += f"  Status: {status}\n"
        output += f"  To: {to}\n"
        output += f"  Subject: {subject}\n"
        output += f"  Sent: {sent}\n\n"

    return output


def enable_dry_run() -> str:
    """Skill function: Enable dry run mode (test without sending)."""
    sender = EmailSender()
    sender.set_dry_run(True)
    return "✅ Dry run mode enabled - emails will be logged but not sent"


def disable_dry_run() -> str:
    """Skill function: Disable dry run mode (actually send emails)."""
    sender = EmailSender()
    sender.set_dry_run(False)
    return "✅ Dry run mode disabled - emails will be sent normally"


__all__ = [
    'EmailSender',
    'send_email',
    'create_email_draft',
    'list_sent_emails',
    'enable_dry_run',
    'disable_dry_run'
]
