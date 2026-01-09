"""Gmail Watcher Implementation

Watches Gmail for new unread emails and creates action items in the Obsidian vault.
"""

import base64
import json
import os
import pickle
import re
import sys
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


class GmailWatcher(BaseWatcher):
    """
    Watches Gmail for new unread emails from Primary category and intelligently filters them.

    Monitors only Primary category emails (not Promotions/Social/Updates) and uses
    keyword analysis to determine which ones require action (questions, requests, tasks).
    Only creates files for emails that need action. Creates clean, modern markdown files
    in the Needs_Action folder. Emails stay in Needs_Action until manually moved by the user.

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
                q='is:unread category:primary'
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
        Create a markdown file in Needs_Action for the email if action is required.

        Only creates a file if the email contains action indicators (questions,
        requests, tasks, deadlines). Otherwise, marks as processed and skips.

        Args:
            message: Gmail message dictionary containing at least 'id'

        Returns:
            Path to created file, or None if no action needed or creation failed

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

            # Helper function to remove problematic Unicode characters
            def sanitize_unicode(text):
                """Remove zero-width and other problematic Unicode characters."""
                if not text:
                    return text
                # Remove zero-width spaces and other invisible/problematic chars
                text = text.replace('\u200b', '')  # Zero-width space
                text = text.replace('\u200c', '')  # Zero-width non-joiner
                text = text.replace('\u200d', '')  # Zero-width joiner
                text = text.replace('\ufeff', '')  # Zero-width no-break space (BOM)
                text = text.replace('\u00a0', ' ')  # Non-breaking space to regular space
                return text

            # Sanitize headers immediately after extraction
            from_addr = sanitize_unicode(from_addr)
            subject = sanitize_unicode(subject)
            date = sanitize_unicode(date)

            # Sanitize subject for use in markdown
            subject = subject.replace('\r', '').replace('\n', ' ').strip()
            if not subject:
                subject = 'No Subject'

            # Get email body
            body = self._extract_body(msg)

            # Sanitize body to remove problematic Unicode characters
            body = sanitize_unicode(body)

            # Check if email needs action
            needs_action = self._email_needs_action(subject, body, from_addr)
            # Sanitize subject for logging to avoid encoding issues
            safe_subject = subject.encode('ascii', errors='replace').decode('ascii')
            self._logger.info(f'Email "{safe_subject}" needs action: {needs_action}')

            if not needs_action:
                self._logger.info(f'Skipping email (no action required): {safe_subject}')
                self._processed_ids.add(msg_id)
                self._save_processed_ids()
                return None

            # Detect priority
            priority = self._detect_priority(subject, body, from_addr)

            # Create timestamp
            timestamp = datetime.now().isoformat()

            # Generate descriptive filename (description < 30 chars)
            # Use subject, truncate if necessary
            description = subject.strip()

            # Clean description for filename
            # Remove special characters, keep alphanumeric and spaces
            description = re.sub(r'[^\w\s-]', '', description)
            # Replace multiple spaces with single space
            description = re.sub(r'\s+', ' ', description)

            # Truncate to 27 chars (leaving room for ... if needed)
            if len(description) > 27:
                description = description[:27].strip()

            # Remove any remaining spaces and replace with hyphens
            description = description.replace(' ', '-')
            # Remove multiple consecutive hyphens
            description = re.sub(r'-+', '-', description)
            # Remove leading/trailing hyphens
            description = description.strip('-')

            # Create filename with message ID suffix for uniqueness
            filename = f'EMAIL - {description}_{msg_id[:8]}.md'
            filepath = self._needs_action / filename

            # If file already exists, update it instead of overwriting
            if filepath.exists():
                self._logger.info(f'File already exists, updating: {filename}')
                return None

            # Format priority with emoji
            priority_emoji = {'high': '🔴', 'normal': '🟡', 'low': '🟢'}.get(priority, '🟡')

            # Parse date to cleaner format
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date)
                clean_date = dt.strftime('%Y-%m-%d %H:%M')
            except Exception:
                clean_date = date

            # Build modern content
            content = f'''---
message_id: {msg_id}
from: {from_addr}
subject: {subject}
received: {timestamp}
priority: {priority}
---

# {subject}

**From:** {from_addr}
**Date:** {clean_date}
**Priority:** {priority_emoji} {priority.capitalize()}

---

{body}

---

## 💬 Your Reply

*No reply sent yet*

---

**Last Updated:** {timestamp}
'''

            # Validate content before writing
            if not content or len(content.strip()) < 50:
                self._logger.warning(f'Content too short or empty, skipping: {safe_subject}')
                self._processed_ids.add(msg_id)
                self._save_processed_ids()
                return None

            # Write file with explicit UTF-8 encoding using open() for better control
            self._logger.info(f'About to write file: {filepath.name} (content length: {len(content)})')

            try:
                with open(filepath, 'w', encoding='utf-8', errors='replace') as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk

                # Verify file was written correctly
                if not filepath.exists():
                    self._logger.error(f'File was not created: {filepath.name}')
                    return None

                file_size = filepath.stat().st_size
                if file_size == 0:
                    self._logger.error(f'File is empty after write: {filepath.name}')
                    filepath.unlink()
                    return None

                self._logger.info(f'File written successfully: {filepath.name} ({file_size} bytes)')

            except UnicodeEncodeError as ue:
                self._logger.error(f'Unicode encoding error: {ue}')
                # Fallback: try writing with ASCII replacement
                try:
                    content_safe = content.encode('ascii', errors='replace').decode('ascii')
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content_safe)
                        f.flush()
                        os.fsync(f.fileno())
                except Exception as e2:
                    self._logger.error(f'Fallback encoding also failed: {e2}')
                    raise
            self._processed_ids.add(msg_id)
            self._save_processed_ids()

            self._logger.info(f'Created action file: {filepath}')

            return filepath

        except Exception as e:
            import traceback
            self._logger.error(f'Error creating action file: {e}')
            self._logger.debug(f'Traceback: {traceback.format_exc()}')
            # Clean up any partially created file
            try:
                if 'filepath' in locals() and filepath.exists():
                    # Check if file is empty (blank file)
                    if filepath.stat().st_size == 0:
                        self._logger.warning(f'Removing blank file: {filepath.name}')
                        filepath.unlink()
                    else:
                        self._logger.warning(f'File exists but not empty ({filepath.stat().st_size} bytes), keeping it')
            except Exception as cleanup_error:
                self._logger.debug(f'Cleanup error: {cleanup_error}')
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

    def _email_needs_action(self, subject: str, body: str, from_addr: str) -> bool:
        """
        Determine if an email requires action based on content analysis.

        Args:
            subject: Email subject line
            body: Email body content
            from_addr: Sender email address

        Returns:
            True if email requires action, False otherwise
        """
        subject_lower = subject.lower()
        body_lower = body.lower()
        content = subject_lower + ' ' + body_lower

        # Action-required indicators
        action_indicators = [
            # Questions
            '?', 'question', 'help', 'assist',
            # Requests
            'please', 'can you', 'could you', 'would you', 'need you',
            'required', 'request', 'review', 'approve',
            # Tasks
            'to do', 'todo', 'task', 'action', 'follow up', 'followup',
            'respond', 'reply', 'call', 'meeting',
            # Deadlines
            'deadline', 'due', 'urgent', 'asap', 'immediately',
            # Direct questions
            'any update', 'update on', 'status of', 'what about',
            'how about', 'when can', 'let me know'
        ]

        return any(indicator in content for indicator in action_indicators)

    def _detect_priority(self, subject: str, body: str, from_addr: str) -> str:
        """
        Detect email priority based on content analysis and sender.

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

        # High priority: urgent keywords + time-sensitive
        urgent_keywords = ['urgent', 'asap', 'immediately', 'emergency', 'critical',
                          'deadline', 'time sensitive', 'important', 'priority']
        if any(kw in content for kw in urgent_keywords):
            return 'high'

        # High priority: direct questions requiring response
        question_patterns = ['?', 'can you', 'could you', 'would you', 'please',
                           'need your', 'waiting for', 'response needed']
        if any(pattern in content for pattern in question_patterns):
            # Check if from important sender (could be configured)
            important_domains = ['@tahaamin', '@ceo', '@director', '@manager']
            if any(domain in from_addr.lower() for domain in important_domains):
                return 'high'
            return 'normal'

        # Normal priority: work-related content
        work_keywords = ['meeting', 'review', 'approve', 'task', 'project',
                        'report', 'update', 'follow up', 'action']
        if any(kw in content for kw in work_keywords):
            return 'normal'

        # Low priority: informational, FYI, newsletters
        low_priority = ['fyi', 'for your information', 'newsletter', 'update',
                       'notification', 'automated', 'no response needed']
        if any(kw in content for kw in low_priority):
            return 'low'

        return 'normal'

    def run(self) -> None:
        """
        Main loop to check for new emails and create action files.

        Keeps emails in Needs_Action until manually moved by user.
        """
        self._logger.info(f'Starting {self.__class__.__name__}')

        while True:
            try:
                # Check for new emails and create actions
                items = self.check_for_updates()
                for item in items:
                    self.create_action_file(item)

            except Exception as e:
                self._logger.error(f'Error in main loop: {e}')
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
    # Setup logging with UTF-8 support
    class UTF8StreamHandler(logging.StreamHandler):
        def emit(self, record):
            try:
                msg = self.format(record)
                msg = msg.encode('ascii', errors='replace').decode('ascii')
                stream = self.stream
                stream.write(msg + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            UTF8StreamHandler(sys.stdout),
            logging.FileHandler('ai_employee.log', encoding='utf-8')
        ]
    )

    vault = Path(__file__).parent / 'AI_Employee_Vault'
    watcher = GmailWatcher(str(vault))
    watcher.run()