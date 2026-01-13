"""
Google Chat Watcher - Monitors Google Chat DMs for important messages

This watcher monitors Google Chat direct messages (DMs) and creates
action files for messages matching configured keywords or detected
as important by the keyword analyzer.

Setup:
1. Create a Google Cloud project and enable Google Chat API
2. Create OAuth 2.0 Client ID (Desktop app)
3. Add GOOGLE_CHAT_CLIENT_ID and GOOGLE_CHAT_CLIENT_SECRET to .env
4. Configure GOOGLE_CHAT_SPACES in .env (comma-separated list of Space IDs)
5. Run the system - it will open browser for OAuth consent on first run

To find your Space IDs:
1. Open Google Chat in browser: https://chat.google.com/
2. Open the DM you want to monitor
3. Look at URL: https://chat.google.com/u/0/<SPACE_ID>
4. Copy the Space ID (e.g., AAAAMSNnnnnn)
"""

import logging
import os
import pickle
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

from Watchers.base_watcher import BaseWatcher
from skills.keyword_analyzer import KeywordAnalyzer


class GoogleChatWatcher(BaseWatcher):
    """Monitors Google Chat and creates action files."""

    SCOPES = ['https://www.googleapis.com/auth/chat']

    # Default keywords to watch for
    DEFAULT_KEYWORDS = [
        'urgent', 'asap', 'emergency', 'important',
        'invoice', 'payment', 'billing', 'pay',
        'help', 'support', 'issue', 'problem',
        'meeting', 'call', 'schedule', 'appointment',
        'project', 'task', 'deadline', 'deliverable',
        'pricing', 'quote', 'proposal'
    ]

    def __init__(
        self,
        vault_path: str,
        keywords: List[str] = None,
        check_interval: int = 60,
        token_path: Optional[str] = None
    ):
        """Initialize Google Chat watcher.

        Args:
            vault_path: Path to Obsidian vault
            keywords: Keywords to watch for (default: DEFAULT_KEYWORDS)
            check_interval: Seconds between checks (default: 60)
            token_path: Path to OAuth token pickle file (default: Sessions/chat_token.pickle)
        """
        super().__init__(vault_path, check_interval)

        load_dotenv()

        self._keywords = keywords if keywords is not None else self.DEFAULT_KEYWORDS

        # Use Sessions folder by default
        if token_path is None:
            token_path = 'Sessions/chat_token.pickle'
            # Ensure Sessions folder exists
            Path('Sessions').mkdir(exist_ok=True)

        self._token_path = token_path
        self._service = None

        # Get credentials from .env
        self._client_id = os.getenv('GOOGLE_CHAT_CLIENT_ID')
        self._client_secret = os.getenv('GOOGLE_CHAT_CLIENT_SECRET')

        if not self._client_id or not self._client_secret:
            self._logger.warning('Google Chat watcher disabled: GOOGLE_CHAT_CLIENT_ID or GOOGLE_CHAT_CLIENT_SECRET not set in .env')
            self._disabled = True
            return

        self._disabled = False

        # Create Chats folder for chat messages
        self._chats_folder = self._vault_path / 'Chats'
        self._chats_folder.mkdir(parents=True, exist_ok=True)

        # Initialize keyword analyzer for enhanced analysis
        self._keyword_analyzer = KeywordAnalyzer(
            company_handbook_path=str(self._vault_path / 'Company_Handbook.md')
        )

        # Cache processed messages
        self._cache_file = self._vault_path / '.google_chat_cache.json'
        self._processed_ids = self._load_cache()

        # Track watcher health
        self._last_successful_check = None
        self._error_count = 0

        # Authenticate only if not disabled
        if not hasattr(self, '_disabled') or not self._disabled:
            self._authenticate()

        # Quiet - only log warnings and errors
        self._logger.setLevel(logging.WARNING)

    def _authenticate(self) -> None:
        """Authenticate with Google Chat API using OAuth2 credentials from .env."""
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

        self._service = build('chat', 'v1', credentials=creds)
        self._logger.info('Google Chat authenticated')

    def _load_cache(self) -> set:
        """Load cache of processed message IDs."""
        if self._cache_file.exists():
            try:
                data = json.loads(self._cache_file.read_text())
                return set(data.get('processed_ids', []))
            except Exception as e:
                self._logger.error(f'Cache load error: {e}')
        return set()

    def _save_cache(self) -> None:
        """Save processed message IDs to cache."""
        try:
            self._cache_file.write_text(json.dumps({
                'processed_ids': list(self._processed_ids),
                'last_updated': datetime.now().isoformat()
            }))
        except Exception as e:
            self._logger.error(f'Cache save error: {e}')

    def check_for_updates(self) -> List[Dict[str, Any]]:
        """Check for new Google Chat messages.

        Returns:
            List of new message dictionaries
        """
        # Return early if disabled
        if hasattr(self, '_disabled') and self._disabled:
            return []
        # Load spaces from environment variable
        spaces_str = os.getenv('GOOGLE_CHAT_SPACES', '')
        if not spaces_str:
            self._logger.debug('No GOOGLE_CHAT_SPACES configured, skipping Google Chat check')
            return []

        spaces = [s.strip() for s in spaces_str.split(',') if s.strip()]

        # Normalize space IDs to ensure they start with "spaces/"
        normalized_spaces = []
        for space_id in spaces:
            if space_id.startswith('space/'):
                # User provided "space/XXXXX", convert to "spaces/XXXXX"
                normalized_spaces.append('spaces/' + space_id[6:])
            elif not space_id.startswith('spaces/'):
                # User provided just the ID, add "spaces/" prefix
                normalized_spaces.append('spaces/' + space_id)
            else:
                # Already in correct format
                normalized_spaces.append(space_id)

        spaces = normalized_spaces

        if not spaces:
            self._logger.debug('GOOGLE_CHAT_SPACES is empty, skipping Google Chat check')
            return []

        if not self._service:
            self._authenticate()

        try:
            # Collect all new messages
            all_messages = []

            for space_id in spaces:
                try:
                    # List messages in space (DM)
                    result = self._service.spaces().messages().list(
                        parent=space_id,
                        orderBy='create_time desc',
                        pageSize=10
                    ).execute()

                    messages = result.get('messages', [])

                    for msg in messages:
                        msg_id = msg.get('name', '').split('/')[-1]

                        # Skip if already processed
                        if msg_id in self._processed_ids:
                            continue

                        # Extract message text
                        text = ''
                        if 'argumentText' in msg:
                            text = msg['argumentText'].get('text', '')
                        elif 'text' in msg:
                            text = msg['text']

                        # Extract sender
                        sender = 'Unknown'
                        if 'sender' in msg:
                            user_name = msg['sender'].get('displayName', 'Unknown')
                            if not user_name:
                                user_name = msg['sender'].get('name', 'Unknown').split('/')[-1]
                            sender = user_name

                        # Only add if message has content
                        if text and text.strip():
                            all_messages.append({
                                'id': msg_id,
                                'sender': sender,
                                'message': text,
                                'space_id': space_id,
                                'timestamp': datetime.now().isoformat()
                            })

                            # Mark as processed
                            self._processed_ids.add(msg_id)

                except Exception as e:
                    error_str = str(e)
                    if '403' in error_str or 'insufficient authentication scopes' in error_str.lower():
                        self._logger.error(f'Permission denied for space: {space_id}')
                        self._logger.error(f'Make sure the Space ID is correct and you have access to it.')
                    else:
                        self._logger.error(f'Error checking space {space_id}: {e}')
                    continue

            # Save cache
            if all_messages:
                self._save_cache()
                self._last_successful_check = datetime.now()
                self._error_count = 0

            return all_messages

        except Exception as e:
            self._logger.error(f'Google Chat API error: {e}')
            self._error_count += 1
            return []

    def create_action_file(self, message: Dict[str, Any]) -> Optional[Path]:
        """Create action file for Google Chat message.

        Args:
            message: Message dictionary

        Returns:
            Path to created file or None if failed
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_sender = message['sender'].replace(' ', '_').replace('/', '_')[:50]
            filename = f"CHAT_{safe_sender}_{timestamp}.md"
            filepath = self._chats_folder / filename

            # Use keyword analyzer for enhanced analysis
            analysis = self._keyword_analyzer.analyze(
                sender=message['sender'],
                subject=f"Google Chat Message",
                body=message['message']
            )

            # Get matched keywords
            message_lower = message['message'].lower()
            matched_keywords = [kw for kw in self._keywords if kw.lower() in message_lower]

            content = f"""---
type: google_chat_message
from: {message['sender']}
space: {message.get('space_id', 'Unknown')}
received: {message['timestamp']}
priority: {analysis.priority_label}
status: pending
message_id: {message['id']}
keywords_matched: {', '.join(matched_keywords)}
category: {analysis.category}
risk_level: {analysis.risk_level}
auto_approve: {analysis.auto_approve}
---

# Google Chat Message: {message['sender']}

**Priority:** {analysis.priority_label.upper()} ({analysis.priority}/5)
**From:** {message['sender']}
**Space:** {message.get('space_id', 'Unknown')}
**Received:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Category:** {analysis.category}
**Risk Level:** {analysis.risk_level.upper()}
**Matched Keywords:** {', '.join(matched_keywords)}

---

## Message Content

{message['message']}

---

## AI Analysis

**Reason:** {analysis.reason}

**Confidence:** {analysis.confidence:.1%}

"""

            if analysis.business_terms:
                content += f"**Business Terms:** {', '.join(analysis.business_terms)}\n\n"

            if analysis.action_items:
                content += "**Action Items Detected:**\n"
                for item in analysis.action_items:
                    content += f"  - {item}\n"
                content += "\n"

            if analysis.risk_factors:
                content += "**Risk Factors:**\n"
                for factor in analysis.risk_factors:
                    content += f"  - {factor}\n"
                content += "\n"

            content += """---

## Suggested Actions

- [ ] Reply to message in Google Chat
- [ ] Create follow-up task if needed
- [ ] Archive after processing

---

## Quick Reply Suggestions

"""

            # Add quick reply suggestions based on analysis
            if analysis.suggested_reply:
                content += f"**Suggested Reply:**\n{analysis.suggested_reply}\n\n"
            else:
                content += "No auto-reply suggested. Manual review required.\n\n"

            # Category-specific suggestions
            if analysis.category == 'finance':
                content += "💰 **Financial**: Consider checking billing status or payment details\n\n"
            elif analysis.category == 'project':
                content += "📋 **Project**: Review project status and update timeline if needed\n\n"
            elif analysis.category == 'meeting':
                content += "📅 **Scheduling**: Consider proposing time slots or checking calendar\n\n"
            elif analysis.category == 'support':
                content += "🆘 **Support**: Investigate issue or prepare solution\n\n"

            content += """---

## Approval Workflow

**To Reply:**
1. Open Google Chat and navigate to the space
2. Draft your response
3. Mark as complete below
4. Move to `Done/` after responding

**To Archive:**
Move to `Done/` if no action needed

---

## Processing Notes

<!-- Add your notes here -->

---

*Created by AI Employee Google Chat Watcher*
"""

            filepath.write_text(content, encoding='utf-8')

            self._logger.info(f'Created action file: {filename}')
            return filepath

        except Exception as e:
            self._logger.error(f'Error creating action file: {e}')
            return None

    def get_health_status(self) -> Dict[str, Any]:
        """Get watcher health status.

        Returns:
            Dict with health information
        """
        return {
            'watcher': 'GoogleChatWatcher',
            'last_successful_check': self._last_successful_check.isoformat() if self._last_successful_check else None,
            'error_count': self._error_count,
            'processed_messages': len(self._processed_ids),
            'status': 'healthy' if self._error_count < 5 else 'degraded'
        }

    def run(self) -> None:
        """Main watcher loop."""
        self._logger.info(f'Starting {self.__class__.__name__}')

        try:
            while True:
                try:
                    messages = self.check_for_updates()
                    for message in messages:
                        self.create_action_file(message)
                except Exception as e:
                    self._logger.error(f'Loop error: {e}')
                    self._error_count += 1
                    time.sleep(5)
                time.sleep(self._check_interval)
        except KeyboardInterrupt:
            self._logger.info(f'{self.__class__.__name__} interrupted by user')
        finally:
            self._logger.info(f'{self.__class__.__name__} stopped')


# ============ CONVENIENCE FUNCTIONS ============

def run_watcher(
    vault_path: str = None,
    keywords: List[str] = None,
    check_interval: int = 60
):
    """Run Google Chat watcher.

    Args:
        vault_path: Path to Obsidian vault
        keywords: Keywords to watch for
        check_interval: Seconds between checks
    """
    vault = Path(vault_path) if vault_path else Path.cwd() / 'AI_Employee_Vault'

    watcher = GoogleChatWatcher(
        vault_path=str(vault),
        keywords=keywords,
        check_interval=check_interval
    )

    watcher.run()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    vault = Path(__file__).parent.parent / 'AI_Employee_Vault'
    run_watcher(str(vault), check_interval=60)


__all__ = ['GoogleChatWatcher', 'run_watcher']
