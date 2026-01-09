"""Gmail Watcher Implementation

Watches Gmail for new unread emails and creates action items in the Obsidian vault.
"""

import base64
import json
import os
import pickle
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Set

from dotenv import load_dotenv

from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

from base_watcher import BaseWatcher
from skills.plan_generator import PlanGenerator
from skills.activity_logger import ActivityLogger


class GmailWatcher(BaseWatcher):
    """
    Watches Gmail for new unread emails and creates action items.

    This class connects to Gmail API, monitors for new unread emails,
    and automatically creates markdown files in the Obsidian vault
    for each new email.

    Attributes:
        SCOPES (List[str]): OAuth scopes for Gmail API access
        _credentials_path (str): Private path to OAuth credentials file
        _token_path (str): Private path to OAuth token file
        _service: Private Gmail API service instance
        _processed_ids (Set[str]): Private set of processed email IDs
        _initialized (bool): Private flag for first-run state
    """

    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    def __init__(
        self,
        vault_path: str,
        token_path: Optional[str] = None,
        check_interval: int = 60
    ) -> None:
        """
        Initialize the Gmail watcher.

        Args:
            vault_path: Path to the Obsidian vault
            token_path: Path to OAuth token pickle file (default: 'token.pickle')
            check_interval: Seconds between email checks (default: 60)

        Raises:
            ValueError: If GMAIL_CLIENT_ID or GMAIL_CLIENT_SECRET not in environment
            ValueError: If vault_path is invalid
        """
        super().__init__(vault_path, check_interval)

        self._token_path = token_path or 'token.pickle'
        self._service = None
        self._processed_ids: Set[str] = set()
        self._initialized = False

        # Validate environment variables
        self._client_id = os.getenv('GMAIL_CLIENT_ID')
        self._client_secret = os.getenv('GMAIL_CLIENT_SECRET')

        if not self._client_id or not self._client_secret:
            raise ValueError(
                'GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in .env file\n'
                'Get credentials from: https://console.cloud.google.com/apis/credentials'
            )

        # Initialize authentication and cache
        self._load_processed_ids()
        self._authenticate()

        # Initialize plan generator and activity logger
        self._plan_generator = PlanGenerator(vault_path)
        self._activity_logger = ActivityLogger(vault_path)

    @property
    def service(self):
        """Get the Gmail API service (lazy loading)."""
        return self._service

    @property
    def processed_ids_count(self) -> int:
        """Get the count of processed email IDs (read-only)."""
        return len(self._processed_ids)

    @property
    def is_authenticated(self) -> bool:
        """Check if the watcher is authenticated with Gmail API."""
        return self._service is not None

    def _load_processed_ids(self) -> None:
        """Load previously processed message IDs from disk cache."""
        cache_file = self._vault_path / '.gmail_cache.json'
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                self._processed_ids = set(data.get('processed_ids', []))
                self._logger.info(f'Loaded {len(self._processed_ids)} processed IDs from cache')
            except (json.JSONDecodeError, IOError) as e:
                self._logger.error(f'Error loading cache: {e}')
                self._processed_ids = set()

    def _save_processed_ids(self) -> None:
        """Save processed message IDs to disk cache."""
        cache_file = self._vault_path / '.gmail_cache.json'
        try:
            cache_file.write_text(json.dumps({'processed_ids': list(self._processed_ids)}))
        except IOError as e:
            self._logger.error(f'Error saving cache: {e}')

    def _authenticate(self) -> None:
        """
        Authenticate with Gmail API using OAuth2 credentials from .env file.

        Raises:
            ValueError: If environment variables are not set
        """
        creds = None

        # Load existing token
        if os.path.exists(self._token_path):
            try:
                with open(self._token_path, 'rb') as token:
                    creds = pickle.load(token)
            except (pickle.PickleError, IOError) as e:
                self._logger.warning(f'Could not load token: {e}')

        # If no valid token, get new one
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    self._logger.error(f'Could not refresh token: {e}')
                    creds = None

            if not creds:
                # Create OAuth flow from environment variables
                client_config = {
                    'installed': {
                        'client_id': self._client_id,
                        'client_secret': self._client_secret,
                        'redirect_uris': ['http://localhost'],
                        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                        'token_uri': 'https://oauth2.googleapis.com/token'
                    }
                }

                flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)

                # Open browser for OAuth consent
                creds = flow.run_local_server(port=0)

            # Save credentials for future use
            try:
                with open(self._token_path, 'wb') as token:
                    pickle.dump(creds, token)
            except IOError as e:
                self._logger.error(f'Could not save token: {e}')

        self._service = build('gmail', 'v1', credentials=creds)
        self._logger.info('Gmail authentication successful')

    def check_for_updates(self) -> List[Dict[str, Any]]:
        """
        Check for new unread emails.

        On first run, marks all existing emails as processed without creating actions.
        On subsequent runs, returns only new emails.

        Returns:
            List of new unread email message dictionaries

        Raises:
            Exception: If API call fails after retries
        """
        if not self._service:
            self._logger.warning('Service not initialized, attempting authentication')
            self._authenticate()

        try:
            results = self._service.users().messages().list(
                userId='me',
                q='is:unread'
            ).execute()

            messages = results.get('messages', [])

            # First run: mark all existing messages as processed without creating actions
            if not self._initialized:
                self._processed_ids.update(m['id'] for m in messages)
                self._save_processed_ids()
                self._initialized = True
                self._logger.info(f'Initialized - marked {len(messages)} existing emails as processed')
                return []

            # Subsequent runs: only return truly new messages
            new_messages = [m for m in messages if m['id'] not in self._processed_ids]

            if new_messages:
                self._logger.info(f'Found {len(new_messages)} new messages')

            return new_messages

        except Exception as e:
            self._logger.error(f'Error checking for updates: {e}')
            return []

    def create_action_file(self, message: Dict[str, Any]) -> Optional[Path]:
        """
        Create a markdown file in Needs_Action for the email.

        Args:
            message: Gmail message dictionary containing at least 'id'

        Returns:
            Path to created file, or None if creation failed

        Raises:
            KeyError: If message doesn't contain 'id'
        """
        if not self._service:
            self._logger.error('Service not initialized')
            return None

        try:
            msg = self._service.users().messages().get(
                userId='me',
                id=message['id'],
                format='full'
            ).execute()

            # Extract headers
            headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}

            from_addr = headers.get('From', 'Unknown')
            subject = headers.get('Subject', 'No Subject')
            date = headers.get('Date', '')
            msg_id = message['id']

            # Get email body
            body = self._extract_body(msg)

            # Detect priority
            priority = self._detect_priority(subject, body, from_addr)

            # Create timestamp
            timestamp = datetime.now().isoformat()

            # Create markdown file
            filename = f'EMAIL_{msg_id[:8]}.md'
            filepath = self._needs_action / filename

            content = f'''---
type: email
message_id: {msg_id}
from: {from_addr}
subject: {subject}
received: {timestamp}
priority: {priority}
status: pending
---

# Email: {subject}

## From
{from_addr}

## Date
{date}

## Priority
{priority.upper()}

## Email Content
{body}

## Suggested Actions
- [ ] Read and understand the email
- [ ] Draft response if needed
- [ ] Flag for follow-up if required
- [ ] Archive once processed

## Processing Notes
<!-- Add notes here as you process the email -->
'''

            filepath.write_text(content)
            self._processed_ids.add(msg_id)
            self._save_processed_ids()

            self._logger.info(f'Created action file: {filepath}')

            # Log the email to activity logger
            try:
                self._activity_logger.log_email_received(
                    msg_id=msg_id,
                    from_addr=from_addr,
                    subject=subject,
                    priority=priority,
                    action_file=filepath.name
                )
            except Exception as e:
                self._logger.warning(f'Could not log email: {e}')

            # Generate plan if email requires it
            try:
                plan_file = self._plan_generator.generate_plan(
                    email_file=filepath,
                    subject=subject,
                    body=body,
                    from_addr=from_addr,
                    msg_id=msg_id
                )
                if plan_file:
                    self._logger.info(f'Generated plan: {plan_file}')
                    self._activity_logger.log_plan_created(
                        plan_id=plan_file.stem,
                        subject=subject,
                        complexity=self._plan_generator.requires_plan(subject, body, from_addr)[1],
                        source_email=filepath.name
                    )
            except Exception as e:
                self._logger.warning(f'Could not generate plan: {e}')

            return filepath

        except Exception as e:
            self._logger.error(f'Error creating action file: {e}')
            return None

    def _extract_body(self, message: Dict[str, Any]) -> str:
        """
        Extract the email body from the message payload.

        Args:
            message: Full Gmail message object

        Returns:
            Decoded email body as string
        """
        try:
            payload = message['payload']
            body = payload.get('body', {}).get('data', '')

            if not body and 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        body = part.get('body', {}).get('data', '')
                        break

            # Decode base64
            if body:
                try:
                    body = base64.urlsafe_b64decode(body).decode('utf-8', errors='ignore')
                except Exception:
                    body = message.get('snippet', '(Could not decode body)')

            # Also try to get snippet
            if not body:
                body = message.get('snippet', '')

            # Truncate if too long
            if len(body) > 5000:
                body = body[:5000] + '\n\n... (truncated)'

            return body or '(No content)'

        except Exception as e:
            self._logger.error(f'Error extracting body: {e}')
            return message.get('snippet', '(Unable to extract content)')

    def _detect_priority(self, subject: str, body: str, from_addr: str) -> str:
        """
        Detect email priority based on content analysis.

        Args:
            subject: Email subject line
            body: Email body content
            from_addr: Sender email address

        Returns:
            Priority level: 'high', 'normal', or 'low'
        """
        subject_lower = subject.lower()
        body_lower = body.lower()
        content = subject_lower + ' ' + body_lower

        # Urgent keywords
        urgent_keywords = ['urgent', 'asap', 'immediately', 'emergency', 'critical']
        if any(kw in content for kw in urgent_keywords):
            return 'high'

        # Normal emails
        return 'normal'

    def _check_and_move_completed_emails(self) -> None:
        """
        Check if emails in Needs_Action have been replied/read and move them to Done.

        Iterates through all email files in Needs_Action, checks if the corresponding
        email in Gmail is still unread, and moves read emails to the Done folder.
        """
        try:
            email_files = list(self._needs_action.glob('EMAIL_*.md'))
            if not email_files:
                return

            done_folder = self._vault_path / 'Done'
            done_folder.mkdir(parents=True, exist_ok=True)

            for email_file in email_files:
                try:
                    msg_id_match = self._extract_message_id_from_file(email_file)
                    if not msg_id_match:
                        continue

                    is_unread = self._is_email_unread(msg_id_match)

                    if not is_unread:
                        self._move_email_to_done(email_file, done_folder)

                except Exception as e:
                    self._logger.error(f'Error processing file {email_file}: {e}')
                    continue

        except Exception as e:
            self._logger.error(f'Error checking completed emails: {e}')

    def _extract_message_id_from_file(self, file_path: Path) -> Optional[str]:
        """
        Extract message ID from email file frontmatter.

        Args:
            file_path: Path to the email markdown file

        Returns:
            Message ID string, or None if not found
        """
        content = file_path.read_text()
        for line in content.split('\n'):
            if line.startswith('message_id:'):
                return line.split(':', 1)[1].strip()
        return None

    def _is_email_unread(self, msg_id: str) -> bool:
        """
        Check if an email is still unread in Gmail.

        Args:
            msg_id: Gmail message ID

        Returns:
            True if email is unread, False otherwise
        """
        try:
            msg = self._service.users().messages().get(
                userId='me',
                id=msg_id,
                format='metadata'
            ).execute()

            return any(label == 'UNREAD' for label in msg.get('labelIds', []))

        except Exception as e:
            self._logger.warning(f'Could not check email {msg_id}: {e}')
            return False

    def _move_email_to_done(self, email_file: Path, done_folder: Path) -> None:
        """
        Move an email file to the Done folder with status update.

        Args:
            email_file: Path to the email file
            done_folder: Path to the Done folder
        """
        content = email_file.read_text()
        updated_content = content.replace(
            'status: pending',
            f'status: completed\ncompleted_date: {datetime.now().isoformat()}'
        )

        dest_path = done_folder / email_file.name
        dest_path.write_text(updated_content)
        email_file.unlink()

        self._logger.info(f'Moved completed email to Done: {email_file.name}')

        # Log the completion to activity logger
        try:
            self._activity_logger.log_email_moved_to_done(
                email_file=email_file.name,
                completed_date=datetime.now().isoformat()
            )
        except Exception as e:
            self._logger.warning(f'Could not log email completion: {e}')

    def run(self) -> None:
        """
        Override run to include checking for completed emails.

        Extends the base run method to also move completed emails to Done.
        """
        self._logger.info(f'Starting {self.__class__.__name__}')

        # Log system startup
        try:
            self._activity_logger.log_system_event('Startup', 'Gmail Watcher started')
        except Exception as e:
            self._logger.warning(f'Could not log system startup: {e}')

        while True:
            try:
                # Check for new emails and create actions
                items = self.check_for_updates()
                for item in items:
                    self.create_action_file(item)

                # Check for completed emails and move to Done
                self._check_and_move_completed_emails()

            except Exception as e:
                self._logger.error(f'Error in main loop: {e}')
                try:
                    self._activity_logger.log_error(
                        error_type='Runtime Error',
                        error_message=str(e),
                        context=f'Gmail Watcher main loop'
                    )
                except Exception:
                    pass
                time.sleep(5)  # Wait before retrying to avoid rapid error loops
            time.sleep(self._check_interval)

    def __repr__(self) -> str:
        """Return detailed string representation."""
        return (
            f"{self.__class__.__name__}("
            f"vault_path='{self._vault_path}', "
            f"check_interval={self._check_interval}, "
            f"authenticated={self.is_authenticated}, "
            f"processed_count={self.processed_ids_count})"
        )


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    vault = Path(__file__).parent / 'AI_Employee_Vault'
    watcher = GmailWatcher(str(vault))
    watcher.run()
