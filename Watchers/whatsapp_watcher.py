"""WhatsApp Watcher - Simple OOP Implementation

Monitors WhatsApp Web for new unread messages containing keywords
and uses VaultUpdater skill to create action items in the Obsidian vault.
Keeps browser open permanently for continuous monitoring.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Set

from playwright.sync_api import sync_playwright

from Watchers.base_watcher import BaseWatcher
from skills.vault_update import VaultUpdater


class WhatsAppWatcher(BaseWatcher):
    """Monitors WhatsApp Web and creates action files using VaultUpdater."""

    def __init__(
        self,
        vault_path: str,
        session_path: str = 'Sessions/whatsapp_session',
        keywords: Optional[List[str]] = None,
        check_interval: int = 30
    ) -> None:
        """Initialize WhatsApp watcher.

        Args:
            vault_path: Path to Obsidian vault
            session_path: Path to Playwright persistent session
            keywords: List of keywords to trigger action (default: urgent, asap, invoice, payment, help)
            check_interval: Seconds between checks (default: 30)
        """
        super().__init__(vault_path, check_interval)

        self.session_path = Path(session_path)
        self.session_path.mkdir(parents=True, exist_ok=True)

        self._keywords = keywords or ['urgent', 'asap', 'invoice', 'payment', 'help', 'task', 'meeting', 'deadline']
        self._processed_ids: Set[str] = set()
        self._vault_updater = VaultUpdater(vault_path)

        # Browser instance (kept open)
        self._browser = None
        self._page = None
        self._playwright = None

        self._load_cache()
        self._logger.info(f'WhatsApp Watcher initialized with keywords: {self._keywords}')
        self._logger.info(f'Session path: {self.session_path}')

    def _load_cache(self) -> None:
        """Load processed message IDs from cache."""
        cache_file = self._vault_path / '.whatsapp_cache.json'
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                self._processed_ids = set(data.get('processed_ids', []))
                self._logger.info(f'Loaded {len(self._processed_ids)} processed WhatsApp IDs')
            except Exception as e:
                self._logger.error(f'Cache load error: {e}')

    def _save_cache(self) -> None:
        """Save processed message IDs to cache."""
        cache_file = self._vault_path / '.whatsapp_cache.json'
        try:
            cache_file.write_text(json.dumps({'processed_ids': list(self._processed_ids)}))
        except Exception as e:
            self._logger.error(f'Cache save error: {e}')

    def _start_browser(self) -> bool:
        """Start browser and authenticate. Returns True if successful."""
        try:
            if self._browser and not self._browser.is_connected():
                self._browser = None
                self._page = None

            if self._browser:
                return True

            # Check if session exists (already authenticated)
            session_exists = (self.session_path / 'Default').exists() or (self.session_path / 'SingletonLock').exists()

            self._playwright = sync_playwright().start()

            # Launch browser with persistent context - ALWAYS visible
            self._browser = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.session_path),
                headless=False,  # Always visible
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
                viewport={'width': 1280, 'height': 800},
                locale='en-US',
                timezone_id='America/New_York'
            )

            # Get or create page
            if not self._browser.pages:
                self._page = self._browser.new_page()
            else:
                self._page = self._browser.pages[0]

            self._logger.info('Loading WhatsApp Web...')

            # Navigate to WhatsApp Web
            self._page.goto('https://web.whatsapp.com', wait_until='domcontentloaded', timeout=90000)

            # Wait for page to stabilize
            time.sleep(3)

            # Check authentication status
            self._logger.info('Checking authentication status...')

            authenticated = False

            # Try to find chat list (already logged in)
            try:
                self._page.wait_for_selector('[data-testid="chat-list"]', timeout=15000)
                authenticated = True
                self._logger.info('WhatsApp authenticated - chat list found')
            except Exception:
                self._logger.debug('Chat list not immediately available')

            # If not authenticated, wait for QR scan
            if not authenticated:
                try:
                    qr_element = self._page.wait_for_selector('[data-testid="qrcode"], canvas, [aria-label*="QR"]', timeout=10000)
                    if qr_element:
                        self._logger.warning('=' * 60)
                        self._logger.warning('WHATSAPP QR CODE DETECTED')
                        self._logger.warning('Please scan the QR code with your phone')
                        self._logger.warning('Browser window is open - scan now!')
                        self._logger.warning('=' * 60)

                        # Wait for user to scan (up to 2 minutes)
                        self._page.wait_for_selector('[data-testid="chat-list"]', timeout=120000)
                        authenticated = True
                        self._logger.info('QR code scanned successfully!')
                except Exception:
                    self._logger.error('QR code scan timeout')

            if not authenticated:
                # Take screenshot for debugging
                try:
                    screenshot_path = self._vault_path / 'whatsapp_debug.png'
                    self._page.screenshot(path=str(screenshot_path), full_page=True)
                    self._logger.info(f'Debug screenshot: {screenshot_path}')
                    self._logger.info('Waiting 30 seconds for manual inspection...')
                    time.sleep(30)
                except Exception:
                    pass

            # Wait for everything to stabilize
            time.sleep(2)

            # Verify chat list is available
            chat_list = self._page.query_selector('[data-testid="chat-list"]')
            if not chat_list:
                self._logger.error('Chat list not found after authentication')
                self._stop_browser()
                return False

            self._logger.info('WhatsApp browser ready and monitoring...')
            return True

        except Exception as e:
            self._logger.error(f'Browser start error: {e}')
            import traceback
            self._logger.debug(f'Traceback: {traceback.format_exc()}')
            self._stop_browser()
            return False

    def _stop_browser(self) -> None:
        """Stop browser."""
        try:
            if self._browser:
                self._browser.close()
                self._browser = None
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
            self._page = None
        except Exception as e:
            self._logger.debug(f'Browser stop error: {e}')

    def check_for_updates(self) -> List[Dict[str, Any]]:
        """Check for new unread messages with keywords.

        Returns:
            List of new message dictionaries
        """
        messages = []

        # Ensure browser is running
        if not self._browser or not self._page:
            if not self._start_browser():
                return []

        try:
            # Refresh the page to get latest messages
            self._logger.debug('Checking for new messages...')

            # Find chat list
            chat_list = self._page.query_selector('[data-testid="chat-list"]')
            if not chat_list:
                self._logger.warning('Chat list not found, restarting browser...')
                self._stop_browser()
                return []

            # Get all chat items
            all_chats = chat_list.query_selector_all('div[role="listitem"]')
            self._logger.debug(f'Scanning {len(all_chats)} chats...')

            for chat in all_chats:
                try:
                    # Check for unread badge
                    unread_badge = chat.query_selector('[data-testid="icon-unread-count"]')
                    has_unread = False

                    if unread_badge:
                        badge_text = unread_badge.inner_text()
                        if badge_text and badge_text.strip():
                            has_unread = True

                    # Alternative unread check
                    if not has_unread:
                        chat_html = chat.inner_html()
                        if 'unread' in chat_html.lower() or 'data-testid="unread"' in chat_html:
                            has_unread = True

                    if not has_unread:
                        continue

                    # Get sender name
                    sender = 'Unknown'
                    sender_elem = chat.query_selector('[data-testid="conversation-title"]')
                    if sender_elem:
                        sender_span = sender_elem.query_selector('span')
                        if sender_span:
                            sender = sender_span.inner_text().strip()
                        else:
                            sender = sender_elem.inner_text().strip()

                    if not sender or sender == 'Unknown':
                        title_elem = chat.query_selector('span[title]')
                        if title_elem:
                            sender = title_elem.get_attribute('title') or title_elem.inner_text().strip()

                    # Get message content
                    message_content = ''
                    try:
                        full_text = chat.inner_text()
                        lines = full_text.split('\n')

                        for line in lines:
                            line = line.strip()
                            if line and line != sender and not line.replace(':', '').replace(' ', '').replace('AM', '').replace('PM', '').isdigit():
                                if len(line) > 3:
                                    message_content = line
                                    break
                    except Exception:
                        message_content = full_text

                    if not message_content:
                        message_content = '(Could not extract message content)'

                    # Generate unique ID
                    message_id = f"{sender}_{hash(message_content)}"

                    # Skip already processed
                    if message_id in self._processed_ids:
                        continue

                    # Check for keywords
                    message_lower = message_content.lower()
                    if not any(kw in message_lower for kw in self._keywords):
                        self._logger.debug(f'Skip (no keywords): {sender}')
                        continue

                    messages.append({
                        'id': message_id,
                        'sender': sender,
                        'content': message_content,
                        'timestamp': datetime.now().isoformat()
                    })

                    self._logger.info(f'MATCH: {sender} - {message_content[:100]}')

                except Exception as e:
                    self._logger.debug(f'Error processing chat: {e}')
                    continue

        except Exception as e:
            self._logger.error(f'Update check error: {e}')
            # Try to restart browser on error
            self._stop_browser()

        if messages:
            self._logger.info(f'Found {len(messages)} new WhatsApp messages')

        return messages

    def create_action_file(self, message: Dict[str, Any]) -> Optional[Path]:
        """Create action file in vault using VaultUpdater.

        Args:
            message: WhatsApp message dict

        Returns:
            Path to created file or None
        """
        try:
            # Generate filename
            filename = self._generate_filename(message['sender'], message['id'])

            # Build markdown content
            content = self._build_markdown(message)

            # Write using VaultUpdater
            filepath = self._vault_updater.write_file(filename, content)

            # Mark as processed
            self._processed_ids.add(message['id'])
            self._save_cache()

            self._logger.info(f'Created WhatsApp action: {filepath.name}')
            return filepath

        except Exception as e:
            self._logger.error(f'Action file creation error: {e}')
            return None

    def _detect_priority(self, content: str) -> str:
        """Detect message priority."""
        content_lower = content.lower()

        urgent = ['urgent', 'asap', 'immediately', 'emergency', 'critical']
        if any(kw in content_lower for kw in urgent):
            return 'high'

        financial = ['invoice', 'payment', 'money', 'bill', 'refund']
        if any(kw in content_lower for kw in financial):
            return 'high'

        work = ['meeting', 'task', 'deadline', 'project', 'report']
        if any(kw in content_lower for kw in work):
            return 'normal'

        return 'low'

    def _generate_filename(self, sender: str, msg_id: str) -> str:
        """Generate safe filename from sender."""
        import re

        clean_sender = sender.strip()
        clean_sender = re.sub(r'[^\w\s-]', '', clean_sender)
        clean_sender = re.sub(r'\s+', ' ', clean_sender)

        if len(clean_sender) > 25:
            clean_sender = clean_sender[:25].strip()

        clean_sender = clean_sender.replace(' ', '-')
        clean_sender = re.sub(r'-+', '-', clean_sender)
        clean_sender = clean_sender.strip('-')

        unique_id = str(abs(hash(msg_id)))[:8]

        return f'WHATSAPP - {clean_sender}_{unique_id}.md'

    def _build_markdown(self, message_data: Dict[str, Any]) -> str:
        """Build markdown content for WhatsApp message."""
        priority = self._detect_priority(message_data['content'])
        priority_emoji = {'high': '🔴', 'normal': '🟡', 'low': '🟢'}.get(priority, '🟡')

        try:
            dt = datetime.fromisoformat(message_data['timestamp'])
            clean_time = dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            clean_time = message_data['timestamp']

        return f'''---
type: whatsapp
sender: {message_data['sender']}
message_id: {message_data['id']}
received: {message_data['timestamp']}
priority: {priority}
status: pending
---

# WhatsApp: {message_data['sender']}

**From:** {message_data['sender']}
**Date:** {clean_time}
**Priority:** {priority_emoji} {priority.capitalize()}

---

## Message Content

{message_data['content']}

---

## Suggested Actions
- [ ] Reply to message
- [ ] Forward to relevant person
- [ ] Take notes from conversation
- [ ] Move to Done when complete

---

**Last Updated:** {message_data['timestamp']}
'''

    def run(self) -> None:
        """Main watcher loop - keeps browser open permanently."""
        self._logger.info(f'Starting {self.__class__.__name__}')

        # Start browser once
        if not self._start_browser():
            self._logger.error('Failed to start WhatsApp browser')
            return

        try:
            while True:
                try:
                    items = self.check_for_updates()
                    for item in items:
                        self.create_action_file(item)
                except Exception as e:
                    self._logger.error(f'Loop error: {e}')
                    time.sleep(5)
                time.sleep(self._check_interval)
        except KeyboardInterrupt:
            self._logger.info(f'{self.__class__.__name__} interrupted by user')
        finally:
            self._logger.info('Stopping WhatsApp browser...')
            self._stop_browser()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"WhatsAppWatcher("
            f"vault_path='{self._vault_path}', "
            f"check_interval={self._check_interval}, "
            f"session_path='{self.session_path}', "
            f"keywords={self._keywords}, "
            f"processed={len(self._processed_ids)})"
        )


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    vault = Path(__file__).parent.parent / 'AI_Employee_Vault'
    watcher = WhatsAppWatcher(str(vault))
    watcher.run()
