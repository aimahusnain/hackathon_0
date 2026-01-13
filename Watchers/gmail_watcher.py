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
import sys
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Set

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

from Watchers.base_watcher import BaseWatcher
from skills.vault_update import VaultUpdater
from skills.email_to_inbox import EmailToInboxMover
from skills.approved_plan_executor import ApprovedPlanExecutor

# Load environment variables
load_dotenv()


class GmailWatcher(BaseWatcher):
    """Monitors Gmail and creates action files using VaultUpdater."""

    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']

    def __init__(
        self,
        vault_path: str,
        token_path: Optional[str] = None,
        check_interval: int = 30
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

        # Set cutoff date to only process recent emails (today onwards)
        from datetime import datetime, timedelta
        self._cutoff_date = datetime.now() - timedelta(days=7)  # Last 7 days

        # Cache the keyword analyzer for efficiency
        from skills.keyword_analyzer import KeywordAnalyzer
        self._analyzer = KeywordAnalyzer(company_handbook_path=str(Path(vault_path) / 'Company_Handbook.md'))
        self._email_sender = None
        self._email_mover = EmailToInboxMover(vault_path)  # Handles moving emails to Inbox when plans complete
        self._approved_executor = ApprovedPlanExecutor(vault_path)  # Executes approved plans from Approved/ folder

        # Lazy load email sender only when needed
        try:
            from skills.email_sender import EmailSender
            self._email_sender = EmailSender(vault_path)
        except Exception as e:
            self._logger.warning(f'EmailSender not available: {e}')

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

        # Mark last 50 important emails as processed to skip old messages
        self._initialize_processed_ids()

        # Quiet down the logger - only show important messages
        self._logger.setLevel(logging.WARNING)

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

    def _initialize_processed_ids(self) -> None:
        """Mark the last 50 important messages as processed on first run.

        This prevents the system from processing old emails on startup.
        Only runs if the cache is empty (first run).
        """
        # Skip if we already have processed IDs
        if self._processed_ids:
            self._logger.info(f'Cache has {len(self._processed_ids)} IDs, skipping initialization')
            return

        try:
            # Get last 50 important messages (read or unread)
            results = self._service.users().messages().list(
                userId='me',
                q='is:important',
                maxResults=50
            ).execute()

            messages = results.get('messages', [])

            if messages:
                # Mark all as processed
                for msg in messages:
                    self._processed_ids.add(msg['id'])

                # Save to cache
                self._save_cache()

                self._logger.info(f'Marked {len(messages)} existing emails as processed (starting fresh)')
            else:
                self._logger.info('No existing important emails found to mark as processed')

        except Exception as e:
            self._logger.warning(f'Could not initialize processed IDs: {e}')
            self._logger.warning('System will process all important emails on first run')

    def check_for_updates(self) -> List[Dict[str, Any]]:
        """Check for new unread important emails (only from last 24 hours).

        Returns:
            List of new message dictionaries
        """
        if not self._service:
            self._authenticate()

        try:
            results = self._service.users().messages().list(
                userId='me',
                q='is:unread is:important'  # Only new unread AND important emails
            ).execute()

            messages = results.get('messages', [])

            # Filter out old emails based on internalDate
            recent_messages = []
            for m in messages:
                # Skip if already processed
                if m['id'] in self._processed_ids:
                    continue

                # Get message metadata to check date (list API doesn't include internalDate)
                try:
                    msg_metadata = self._service.users().messages().get(
                        userId='me',
                        id=m['id'],
                        format='metadata',
                        fields='internalDate'
                    ).execute()
                    internal_date = int(msg_metadata.get('internalDate', 0))
                    msg_date = datetime.fromtimestamp(internal_date / 1000)
                except Exception:
                    # If we can't get the date, include it anyway (better to process than miss)
                    recent_messages.append(m)
                    continue

                # Only process messages from last 7 days
                if msg_date >= self._cutoff_date:
                    recent_messages.append(m)
                else:
                    # Mark old messages as processed so we don't check them again
                    self._processed_ids.add(m['id'])
                    self._logger.debug(f'Skipped old message from {msg_date.strftime("%Y-%m-%d")}: {m.get("id", "unknown")[:20]}')

            if recent_messages:
                self._logger.info(f'📧 {len(recent_messages)} new email(s)')

            # Save cache after filtering old messages
            self._save_cache()

            return recent_messages

        except Exception as e:
            self._logger.error(f'Update check error: {e}')
            return []

    def create_action_file(self, message: Dict[str, Any]) -> Optional[Path]:
        """Create action file in vault using VaultUpdater.

        NEW: Instantly analyzes email and creates plan if needed.

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

            # STEP 1: Always save original email to Needs_Action first
            self._save_to_needs_action(email_data, status='pending')

            # Parse email for analysis
            metadata = {
                'from': email_data['from'],
                'subject': email_data['subject'],
                'date': email_data['date'],
                'message_id': message['id']
            }
            body = email_data['body']

            # STEP 2: Instant analysis using keyword-based system
            analysis = self._analyzer.analyze(metadata['from'], metadata['subject'], body)

            if not analysis.needs_reply:
                # No reply needed - email already saved to Needs_Action
                self._logger.info(f'  📥 {email_data["subject"][:60]}')
                self._processed_ids.add(message['id'])
                self._save_cache()
                return self._vault_path / 'Needs_Action' / self._generate_filename(email_data['subject'], message['id'])

            elif analysis.auto_approve:
                # Auto-send safe responses immediately
                self._logger.info(f'  ✉️  Auto-replied: {email_data["subject"][:60]}')

                # Create plan first for record-keeping
                plan_id = self._create_plan_direct(metadata, body, analysis, email_data)
                plan_filename = f'{plan_id}.md'
                plan_path = self._vault_path / 'Plans' / plan_filename

                success = False  # Track if email was sent successfully
                if self._email_sender and analysis.suggested_reply:
                    recipient = email_data['from']
                    subject = email_data['subject']
                    if subject and not subject.startswith('Re:'):
                        subject = f"Re: {subject}"

                    # Send the email
                    success = self._email_sender.send_email(recipient, subject, analysis.suggested_reply)

                    if success:
                        # Log the auto-send
                        self._log_auto_send(message['id'], recipient, subject, analysis)

                        # Move plan to Done folder (with auto-sent timestamp)
                        done_filename = f'{plan_id}.md'
                        done_path = self._vault_path / 'Done' / done_filename

                        # Read plan content
                        plan_content = plan_path.read_text(encoding='utf-8')

                        # Update frontmatter with auto-sent info
                        frontmatter_match = re.match(r'^---\n(.*?)\n---\n', plan_content, re.DOTALL)
                        if frontmatter_match:
                            frontmatter = frontmatter_match.group(1)
                            # Add auto-sent timestamp
                            frontmatter += f'\nauto_sent_at: {datetime.now().isoformat()}\nauto_sent_to: {recipient}\nstatus: auto_sent'

                            # Reconstruct file
                            new_content = f"---\n{frontmatter}\n---\n{plan_content[frontmatter_match.end():]}"

                            # Write to Done folder
                            done_path.write_text(new_content, encoding='utf-8')

                            # Remove from Plans
                            plan_path.unlink()

                            self._logger.info(f'✅ Auto-sent reply for {message["id"]} - Plan moved to Done/')

                            # Move associated email from Needs_Action to Inbox
                            if self._email_mover.check_plan_completion(plan_id):
                                self._logger.info(f'📥 Moved associated email to Inbox/')
                        else:
                            self._logger.warning(f'Could not update plan frontmatter for {plan_id}')
                    else:
                        # If send failed, plan stays in Plans for manual review
                        self._logger.warning(f'Send failed, plan kept in Plans/: {plan_id}')
                else:
                    # No email sender available, plan stays in Plans for manual review
                    self._logger.info(f'No email sender, plan created in Plans/: {plan_id}')

                # Update the email in Needs_Action with plan reference
                filename = self._generate_filename(email_data['subject'], message['id'])
                plan_location = 'Done' if success else 'Plans'
                self._vault_updater.add_note(
                    f'Needs_Action/{filename}',
                    f'Auto-sent, plan moved to {plan_location}/: {plan_id}.md',
                    'AI Auto-Responder'
                )

                self._processed_ids.add(message['id'])
                self._save_cache()
                return self._vault_path / 'Needs_Action' / self._generate_filename(email_data['subject'], message['id'])

            else:
                # CREATE PLAN DIRECTLY in Plans/ folder
                plan_id = self._create_plan_direct(metadata, body, analysis, email_data)
                self._logger.info(f'Created plan: {plan_id}')

                # Update the email in Needs_Action with plan reference
                filename = self._generate_filename(email_data['subject'], message['id'])
                self._vault_updater.add_note(
                    f'Needs_Action/{filename}',
                    f'Plan created: {plan_id}.md in Plans/',
                    'AI Analysis'
                )

                # Mark as processed
                self._processed_ids.add(message['id'])
                self._save_cache()

                # Return both paths
                return self._vault_path / 'Plans' / f'{plan_id}.md'

        except Exception as e:
            self._logger.error(f'Action file creation error: {e}')
            return None

    def _save_to_needs_action(self, email_data: Dict, status: str = 'pending') -> None:
        """Save email to Needs_Action folder with status.

        Args:
            email_data: Email data dictionary
            status: Status to set (pending, auto_sent, etc.)
        """
        try:
            content = f"""---
type: email
message_id: {email_data['id']}
from: {email_data['from']}
subject: {email_data['subject']}
received: {email_data['timestamp']}
priority: {email_data['priority']}
status: {status}
---

# {email_data['subject']}

**From:** {email_data['from']}
**Date:** {email_data['date']}
**Priority:** {'🔴' if email_data['priority'] == 'high' else '🟡'} {email_data['priority'].capitalize()}

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
"""
            filename = self._generate_filename(email_data['subject'], email_data['id'])
            filepath = self._vault_path / 'Needs_Action' / filename
            filepath.write_text(content, encoding='utf-8')
            self._logger.info(f'Saved to Needs_Action: {filename}')
        except Exception as e:
            self._logger.error(f'Error saving to Needs_Action: {e}')

    def _log_auto_send(self, message_id: str, recipient: str, subject: str, analysis) -> None:
        """Log auto-sent email to Logs/Auto_Sent folder.

        Args:
            message_id: Gmail message ID
            recipient: Email recipient
            subject: Email subject
            analysis: Email analysis result
        """
        try:
            from datetime import datetime
            auto_sent_folder = self._vault_path / 'Logs' / 'Auto_Sent'
            auto_sent_folder.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = auto_sent_folder / f'AUTO_SENT_{timestamp}.md'

            content = f"""---
type: auto_sent_email
message_id: {message_id}
recipient: {recipient}
subject: {subject}
risk_level: {analysis.risk_level}
sent_at: {datetime.now().isoformat()}
---

# Auto-Sent Email

**Message ID:** {message_id}
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

*Auto-approved and sent by AI Employee Gmail Watcher*
*Analysis Method: Keyword-based*
"""
            log_file.write_text(content, encoding='utf-8')
            self._logger.info(f'Logged auto-send to {log_file.name}')
        except Exception as e:
            self._logger.error(f'Failed to log auto-send: {e}')

    def _create_plan_direct(
        self,
        metadata: Dict,
        body: str,
        analysis,
        email_data: Dict
    ) -> str:
        """Create plan file directly in Plans/ folder.

        Args:
            metadata: Email metadata
            body: Email body
            analysis: Email analysis result
            email_data: Raw email data

        Returns:
            Plan ID
        """
        from datetime import datetime

        # Generate plan ID
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Remove all Windows-invalid characters from subject
        safe_subject = metadata['subject']
        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            safe_subject = safe_subject.replace(char, '-')
        safe_subject = re.sub(r'-+', '-', safe_subject)  # Replace multiple dashes with single
        safe_subject = safe_subject[:50].strip('-')  # Truncate and remove leading/trailing dashes
        plan_id = f"PLAN_{timestamp}_{safe_subject}"

        # Generate email filename for reference
        email_filename = self._generate_filename(email_data['subject'], email_data['id'])

        # Priority emoji
        priority_emoji = {
            'critical': '',
            'high': '',
            'normal': '',
            'low': ''
        }.get(analysis.priority_label, '')

        # Build plan content
        content = f"""---
type: email_plan
plan_id: {plan_id}
email_file: {email_filename}
priority: {analysis.priority_label}
risk_level: {analysis.risk_level}
needs_reply: {analysis.needs_reply}
auto_approve: {analysis.auto_approve}
from: {metadata['from']}
subject: {metadata['subject']}
created: {datetime.now().isoformat()}
---

# Email Response Plan: {metadata['subject']}

**Priority:** {priority_emoji} {analysis.priority_label.upper()}
**From:** {metadata['from']}
**Risk Level:** {analysis.risk_level.upper()}

---

## Analysis

**Reason:** {analysis.reason}
**Category:** {analysis.category}

---

## Suggested Reply

```
{analysis.suggested_reply or "No reply suggested"}
```

---

## Next Steps

- [ ] Review the draft reply above
- [ ] Edit as needed
- [ ] To approve and send: Move this file to `Approved/` folder
- [ ] To reject: Move to `Rejected/` folder

---

## Original Email

**From:** {metadata['from']}
**Subject:** {metadata['subject']}
**Date:** {metadata.get('date', '')}

{body}

---

*Generated by AI Employee Gmail Watcher*
*Analysis Method: Keyword-based*
*Original Message ID: {metadata.get('message_id', 'N/A')}*
"""

        # Write to Plans/ folder
        plans_folder = self._vault_path / 'Plans'
        plans_folder.mkdir(parents=True, exist_ok=True)

        plan_file = plans_folder / f'{plan_id}.md'
        plan_file.write_text(content, encoding='utf-8')

        return plan_id

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

    def check_completed_plans(self) -> int:
        """Check for newly completed plans in Done/ and move their emails to Inbox.

        This handles plans that were manually moved to Done/ (not just auto-sent ones).

        Returns:
            Number of emails moved to Inbox
        """
        moved_count = 0
        try:
            moved_count = self._email_mover.check_and_move()
            if moved_count > 0:
                self._logger.info(f'📥 Moved {moved_count} email(s) to Inbox from completed plans')
        except Exception as e:
            self._logger.error(f'Error checking completed plans: {e}')
        return moved_count

    def execute_approved_plans(self) -> int:
        """Check for newly approved plans in Approved/ folder and execute them.

        This handles plans that you manually move to the Approved/ folder.

        Returns:
            Number of plans executed
        """
        executed_count = 0
        try:
            executed_count = self._approved_executor.check_and_execute()
            if executed_count > 0:
                self._logger.info(f'✅ Executed {executed_count} approved plan(s)')
        except Exception as e:
            self._logger.error(f'Error executing approved plans: {e}')
        return executed_count

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

                # Check for approved plans and execute them
                self.execute_approved_plans()

                # Check for completed plans and move their emails to Inbox
                self.check_completed_plans()
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
