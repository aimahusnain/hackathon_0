"""Gmail Watcher - Simple OOP Implementation

Monitors Gmail for new unread important emails and uses VaultUpdater skill
to create action items in the Obsidian vault.
"""

import base64
import json
import logging
import os
import pickle
import re
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Set

from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

from Watchers.base_watcher import BaseWatcher
from skills.vault_update import VaultUpdater

# Load environment variables
load_dotenv()


class GmailWatcher(BaseWatcher):
    """Monitors Gmail and creates action files using VaultUpdater."""

    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    def __init__(
        self,
        vault_path: str,
        token_path: Optional[str] = None,
        check_interval: int = 120
    ) -> None:
        """Initialize Gmail watcher.

        Args:
            vault_path: Path to Obsidian vault
            token_path: Path to OAuth token pickle file (default: Sessions/token.pickle)
            check_interval: Seconds between checks (default: 120)

        Raises:
            ValueError: If GMAIL_CLIENT_ID or GMAIL_CLIENT_SECRET not in .env
        """
        super().__init__(vault_path, check_interval)

        # Use Sessions folder by default
        if token_path is None:
            token_path = 'Sessions/token.pickle'
            # Ensure Sessions folder exists
            Path('Sessions').mkdir(exist_ok=True)

        self._token_path = token_path
        self._service = None
        self._processed_ids: Set[str] = set()
        self._vault_updater = VaultUpdater(vault_path)

        # Get credentials from .env
        self._client_id = os.getenv('GMAIL_CLIENT_ID')
        self._client_secret = os.getenv('GMAIL_CLIENT_SECRET')

        if not self._client_id or not self._client_secret:
            raise ValueError(
                'GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in .env file\n'
                'Get credentials from: https://console.cloud.google.com/apis/credentials'
            )

        self._load_cache()
        self._authenticate()

    def _load_cache(self) -> None:
        """Load processed message IDs from cache."""
        cache_file = self._vault_path / '.gmail_cache.json'
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                self._processed_ids = set(data.get('processed_ids', []))
                self._logger.info(f'Loaded {len(self._processed_ids)} processed IDs')
            except Exception as e:
                self._logger.error(f'Cache load error: {e}')

    def _save_cache(self) -> None:
        """Save processed message IDs to cache."""
        cache_file = self._vault_path / '.gmail_cache.json'
        try:
            cache_file.write_text(json.dumps({'processed_ids': list(self._processed_ids)}))
        except Exception as e:
            self._logger.error(f'Cache save error: {e}')

    def _authenticate(self) -> None:
        """Authenticate with Gmail API using OAuth2 credentials from .env."""
        creds = None

        # Load existing token
        if os.path.exists(self._token_path):
            try:
                with open(self._token_path, 'rb') as token:
                    creds = pickle.load(token)
            except Exception as e:
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
                creds = flow.run_local_server(port=0)

            # Save credentials for future use
            try:
                with open(self._token_path, 'wb') as token:
                    pickle.dump(creds, token)
            except Exception as e:
                self._logger.error(f'Could not save token: {e}')

        self._service = build('gmail', 'v1', credentials=creds)
        self._logger.info('Gmail authenticated')

    def check_for_updates(self) -> List[Dict[str, Any]]:
        """Check for new unread important emails.

        Returns:
            List of new message dictionaries
        """
        if not self._service:
            self._authenticate()

        try:
            results = self._service.users().messages().list(
                userId='me',
                q='is:unread is:important'
            ).execute()

            messages = results.get('messages', [])
            new_messages = [m for m in messages if m['id'] not in self._processed_ids]

            if new_messages:
                self._logger.info(f'Found {len(new_messages)} new messages')

            return new_messages

        except Exception as e:
            self._logger.error(f'Update check error: {e}')
            return []

    def create_action_file(self, message: Dict[str, Any]) -> Optional[Path]:
        """Create action file in vault using VaultUpdater.

        Args:
            message: Gmail message dict

        Returns:
            Path to created file or None
        """
        if not self._service:
            return None

        try:
            # Get full message
            msg = self._service.users().messages().get(
                userId='me',
                id=message['id']
            ).execute()

            # Extract email data
            email_data = self._extract_email_data(msg, message['id'])

            # Generate filename
            filename = self._generate_filename(email_data['subject'], message['id'])

            # Build markdown content
            content = self._build_markdown(email_data)

            # Write using VaultUpdater
            filepath = self._vault_updater.write_file(filename, content)

            # Mark as processed
            self._processed_ids.add(message['id'])
            self._save_cache()

            self._logger.info(f'Created: {filepath.name}')
            return filepath

        except Exception as e:
            self._logger.error(f'Action file creation error: {e}')
            return None

    def _extract_email_data(self, msg: Dict, msg_id: str) -> Dict[str, Any]:
        """Extract relevant data from Gmail message.

        Args:
            msg: Full Gmail message object
            msg_id: Message ID

        Returns:
            Dictionary with email data
        """
        # Extract headers
        headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}

        from_addr = headers.get('From', 'Unknown')
        subject = headers.get('Subject', 'No Subject')
        date_str = headers.get('Date', '')

        # Get body
        body = self._get_email_body(msg)

        # Parse date
        try:
            clean_date = parsedate_to_datetime(date_str).strftime('%Y-%m-%d %H:%M')
        except Exception:
            clean_date = date_str

        # Detect priority
        priority = self._detect_priority(subject, body, from_addr)

        return {
            'id': msg_id,
            'from': from_addr,
            'subject': subject,
            'date': clean_date,
            'body': body,
            'priority': priority,
            'timestamp': datetime.now().isoformat()
        }

    def _get_email_body(self, msg: Dict) -> str:
        """Extract email body from message.

        Args:
            msg: Gmail message object

        Returns:
            Email body as string
        """
        try:
            payload = msg['payload']
            body = payload.get('body', {}).get('data', '')

            if not body and 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        body = part.get('body', {}).get('data', '')
                        break

            # Decode base64
            if body:
                body = base64.urlsafe_b64decode(body).decode('utf-8', errors='ignore')

            # Fallback to snippet
            if not body:
                body = msg.get('snippet', '')

            # Truncate if too long
            if len(body) > 5000:
                body = body[:5000] + '\n\n... (truncated)'

            return body or '(No content)'

        except Exception as e:
            self._logger.error(f'Body extraction error: {e}')
            return msg.get('snippet', '(Unable to extract content)')

    def _detect_priority(self, subject: str, body: str, from_addr: str) -> str:
        """Detect email priority.

        Args:
            subject: Email subject
            body: Email body
            from_addr: Sender address

        Returns:
            Priority: 'high', 'normal', or 'low'
        """
        content = (subject + ' ' + body).lower()

        urgent = ['urgent', 'asap', 'immediately', 'emergency', 'critical',
                 'deadline', 'time sensitive', 'important', 'priority']

        if any(kw in content for kw in urgent):
            return 'high'

        questions = ['?', 'can you', 'could you', 'would you', 'please',
                    'need your', 'waiting for', 'response needed']

        if any(p in content for p in questions):
            return 'high' if any(d in from_addr.lower() for d in ['@ceo', '@director', '@manager']) else 'normal'

        work = ['meeting', 'review', 'approve', 'task', 'project',
               'report', 'update', 'follow up', 'action']

        if any(kw in content for kw in work):
            return 'normal'

        low = ['fyi', 'for your information', 'newsletter', 'notification']

        if any(kw in content for kw in low):
            return 'low'

        return 'normal'

    def _generate_filename(self, subject: str, msg_id: str) -> str:
        """Generate safe filename from subject.

        Args:
            subject: Email subject
            msg_id: Message ID

        Returns:
            Safe filename
        """
        # Clean subject
        description = subject.strip()
        description = re.sub(r'[^\w\s-]', '', description)
        description = re.sub(r'\s+', ' ', description)

        # Truncate
        if len(description) > 27:
            description = description[:27].strip()

        # Convert to filename
        description = description.replace(' ', '-')
        description = re.sub(r'-+', '-', description)
        description = description.strip('-')

        return f'EMAIL - {description}_{msg_id[:8]}.md'

    def _build_markdown(self, email_data: Dict[str, Any]) -> str:
        """Build markdown content for email.

        Args:
            email_data: Dictionary with email data

        Returns:
            Markdown content as string
        """
        priority_emoji = {'high': '🔴', 'normal': '🟡', 'low': '🟢'}.get(
            email_data['priority'], '🟡'
        )

        return f'''---
type: email
message_id: {email_data['id']}
from: {email_data['from']}
subject: {email_data['subject']}
received: {email_data['timestamp']}
priority: {email_data['priority']}
status: pending
---

# {email_data['subject']}

**From:** {email_data['from']}
**Date:** {email_data['date']}
**Priority:** {priority_emoji} {email_data['priority'].capitalize()}

---

## Email Content

{email_data['body']}

---

## Suggested Actions
- [ ] Reply to sender
- [ ] Forward to relevant party
- [ ] Archive after processing
- [ ] Move to Done when complete

---

**Last Updated:** {email_data['timestamp']}
'''

    def run(self) -> None:
        """Main watcher loop."""
        self._logger.info(f'Starting {self.__class__.__name__}')

        while True:
            try:
                items = self.check_for_updates()
                for item in items:
                    self.create_action_file(item)
            except Exception as e:
                self._logger.error(f'Loop error: {e}')
                time.sleep(5)
            time.sleep(self._check_interval)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"GmailWatcher("
            f"vault_path='{self._vault_path}', "
            f"check_interval={self._check_interval}, "
            f"processed={len(self._processed_ids)})"
        )


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    vault = Path(__file__).parent / 'AI_Employee_Vault'
    watcher = GmailWatcher(str(vault))
    watcher.run()
