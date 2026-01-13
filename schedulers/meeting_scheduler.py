"""
Meeting Scheduler - Automatically schedule meetings from emails
"""

import os
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger('MeetingScheduler')


class MeetingScheduler:
    """
    Automatically detects meeting requests in emails and schedules them in Google Calendar.
    """

    # Patterns to detect meeting-related emails
    MEETING_KEYWORDS = [
        'meeting', 'schedule', 'call', 'zoom', 'teams', 'google meet',
        'appointment', 'conference', 'sync', 'standup', 'review',
        'discussion', 'catch up', '1:1', 'one-on-one', 'interview',
        'demo', 'presentation', 'webinar'
    ]

    # Patterns to detect time expressions
    TIME_PATTERNS = [
        r'\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)',  # 10:30 AM
        r'\d{1,2}\s*(?:AM|PM|am|pm)',  # 10 AM
        r'(?:noon|midnight|morning|afternoon|evening)',
    ]

    # Patterns to detect date expressions
    DATE_PATTERNS = [
        r'\d{4}-\d{2}-\d{2}',  # 2026-01-15
        r'\d{1,2}/\d{1,2}/\d{4}',  # 1/15/2026
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}',  # Jan 15, 2026
        r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}',  # Monday, Jan 15
        r'tomorrow|today|next week|next monday|next tuesday|next wednesday|next thursday|next friday',
        r'this (?:monday|tuesday|wednesday|thursday|friday)',
    ]

    def __init__(self, vault_path: str, auto_schedule: bool = False):
        """Initialize Meeting Scheduler

        Args:
            vault_path: Path to Obsidian vault
            auto_schedule: If True, automatically schedule meetings (default: False = suggest only)
        """
        self._vault_path = Path(vault_path)
        self._needs_action_path = self._vault_path / "Needs_Action"
        self._auto_schedule = auto_schedule

        # Try to import calendar MCP
        try:
            from skills.mcp_calendar import get_calendar
            self._calendar = get_calendar()
            self._calendar_available = True
            logger.info('✓ Calendar MCP connected')
        except Exception as e:
            self._calendar_available = False
            self._calendar = None
            logger.warning(f'Calendar MCP not available: {e}')

    def process_email(self, email_file: str) -> Dict:
        """
        Process an email and extract/schedule meeting details

        Args:
            email_file: Path to email markdown file

        Returns:
            Result dictionary with status and details
        """
        if not self._calendar_available:
            return {
                'status': 'error',
                'message': 'Calendar MCP not available. Run: python main.py --enable-calendar'
            }

        email_path = self._needs_action_path / email_file
        if not email_path.exists():
            return {
                'status': 'error',
                'message': f'Email file not found: {email_file}'
            }

        # Read email content
        with open(email_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract metadata
        metadata = self._extract_email_metadata(content)

        # Check if this looks like a meeting request
        meeting_score = self._calculate_meeting_score(content)

        if meeting_score < 2:
            return {
                'status': 'not_meeting',
                'message': 'Email does not appear to be a meeting request',
                'score': meeting_score
            }

        # Extract meeting details
        meeting_details = self._extract_meeting_details(content, metadata)

        if not meeting_details:
            return {
                'status': 'no_details',
                'message': 'Could not extract meeting details (date/time not found)',
                'suggestion': 'Please manually review the email'
            }

        # Create or suggest event
        if self._auto_schedule:
            try:
                result = self._calendar.create_event(**meeting_details)
                return {
                    'status': 'scheduled',
                    'message': f'Meeting scheduled: {meeting_details["title"]}',
                    'event': result,
                    'details': meeting_details
                }
            except Exception as e:
                return {
                    'status': 'error',
                    'message': f'Failed to schedule: {e}',
                    'details': meeting_details
                }
        else:
            # Suggestion mode - return extracted details for review
            return {
                'status': 'suggested',
                'message': f'Meeting detected: {meeting_details["title"]}',
                'details': meeting_details,
                'email_file': email_file
            }

    def process_all_pending_emails(self) -> List[Dict]:
        """
        Process all pending emails in Needs_Action folder

        Returns:
            List of results for each email processed
        """
        results = []

        for email_file in self._needs_action_path.glob("EMAIL_*.md"):
            try:
                result = self.process_email(email_file.name)
                result['email_file'] = email_file.name
                results.append(result)

                # Log the result
                if result['status'] == 'scheduled':
                    logger.info(f"✓ Scheduled meeting from {email_file.name}")
                elif result['status'] == 'suggested':
                    logger.info(f"ℹ️ Suggested meeting from {email_file.name}")

            except Exception as e:
                logger.error(f"Error processing {email_file.name}: {e}")
                results.append({
                    'status': 'error',
                    'email_file': email_file.name,
                    'message': str(e)
                })

        return results

    def get_meeting_suggestions(self, limit: int = 10) -> List[Dict]:
        """
        Get list of emails that appear to be meeting requests

        Args:
            limit: Maximum number of suggestions

        Returns:
            List of suggested meetings with details
        """
        suggestions = []

        for email_file in self._needs_action_path.glob("EMAIL_*.md"):
            if len(suggestions) >= limit:
                break

            try:
                with open(email_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                score = self._calculate_meeting_score(content)

                if score >= 2:
                    metadata = self._extract_email_metadata(content)
                    details = self._extract_meeting_details(content, metadata)

                    suggestions.append({
                        'email_file': email_file.name,
                        'score': score,
                        'subject': metadata.get('subject', 'Unknown'),
                        'sender': metadata.get('sender', 'Unknown'),
                        'suggested_event': details,
                        'confidence': 'high' if score >= 4 else 'medium'
                    })

            except Exception as e:
                logger.debug(f"Error analyzing {email_file.name}: {e}")

        return suggestions

    def _calculate_meeting_score(self, content: str) -> int:
        """Calculate how likely an email is a meeting request (0-5 scale)"""
        score = 0
        content_lower = content.lower()

        # Check for meeting keywords
        for keyword in self.MEETING_KEYWORDS:
            if keyword in content_lower:
                score += 1
                if score >= 5:
                    break

        # Bonus points for time patterns
        if re.search('|'.join(self.TIME_PATTERNS), content):
            score += 1

        # Bonus points for date patterns
        if re.search('|'.join(self.DATE_PATTERNS), content, re.IGNORECASE):
            score += 1

        return min(score, 5)

    def _extract_email_metadata(self, content: str) -> Dict:
        """Extract metadata from email frontmatter"""
        metadata = {}

        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 2:
                for line in parts[1].strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip()] = value.strip().strip('\'"')

        return metadata

    def _extract_meeting_details(self, content: str, metadata: Dict) -> Optional[Dict]:
        """Extract meeting details from email content"""
        import re
        from dateutil import parser as date_parser

        # Extract sender for attendees
        sender = metadata.get('sender', '')
        attendees = [sender] if sender and '@' in sender else []

        # Extract subject for title
        subject = metadata.get('subject', '')
        title = subject or "Meeting from Email"

        # Extract body
        if content.startswith('---'):
            parts = content.split('---', 2)
            body = parts[2] if len(parts) >= 3 else content
        else:
            body = content

        # Try to extract date and time
        date_match = None
        time_match = None

        # Search for date patterns
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                date_match = match.group(0)
                break

        # Search for time patterns
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                time_match = match.group(0)
                break

        if not date_match:
            return None

        # Parse date and time
        try:
            # Combine date and time
            datetime_str = f"{date_match} {time_match or '09:00'}"

            # Handle relative dates
            date_match_lower = date_match.lower()
            today = datetime.now()

            if 'tomorrow' in date_match_lower:
                event_date = today + timedelta(days=1)
                datetime_str = datetime_str.replace('tomorrow', event_date.strftime('%Y-%m-%d'))
            elif 'today' in date_match_lower:
                datetime_str = datetime_str.replace('today', today.strftime('%Y-%m-%d'))
            elif 'next monday' in date_match_lower:
                days_ahead = 0 - today.weekday() + 7  # Next Monday
                event_date = today + timedelta(days=days_ahead)
                datetime_str = datetime_str.replace('next monday', event_date.strftime('%Y-%m-%d'))
            elif 'next tuesday' in date_match_lower:
                days_ahead = 1 - today.weekday() + 7  # Next Tuesday
                event_date = today + timedelta(days=days_ahead)
                datetime_str = datetime_str.replace('next tuesday', event_date.strftime('%Y-%m-%d'))
            elif 'next wednesday' in date_match_lower:
                days_ahead = 2 - today.weekday() + 7  # Next Wednesday
                event_date = today + timedelta(days=days_ahead)
                datetime_str = datetime_str.replace('next wednesday', event_date.strftime('%Y-%m-%d'))
            elif 'next thursday' in date_match_lower:
                days_ahead = 3 - today.weekday() + 7  # Next Thursday
                event_date = today + timedelta(days=days_ahead)
                datetime_str = datetime_str.replace('next thursday', event_date.strftime('%Y-%m-%d'))
            elif 'next friday' in date_match_lower:
                days_ahead = 4 - today.weekday() + 7  # Next Friday
                event_date = today + timedelta(days=days_ahead)
                datetime_str = datetime_str.replace('next friday', event_date.strftime('%Y-%m-%d'))

            # Parse the datetime
            event_start = date_parser.parse(datetime_str, fuzzy=True)

            # Build meeting details
            meeting_details = {
                'title': title,
                'start_time': event_start.isoformat(),
                'end_time': (event_start + timedelta(hours=1)).isoformat(),
                'description': f"Extracted from email\n\nFrom: {sender}\nSubject: {subject}\n\n{body[:500]}",
                'attendees': attendees,
                'event_type': 'meeting'
            }

            # Extract meeting link/URL if present
            link_patterns = [
                r'https://meet\.google\.com/[a-z-]+',
                r'https://zoom\.us/j/\S+',
                r'https://teams\.microsoft\.com\S+',
                r'join\.zoom\.us/\S+'
            ]

            for pattern in link_patterns:
                match = re.search(pattern, body)
                if match:
                    meeting_details['location'] = match.group(0)
                    break

            return meeting_details

        except Exception as e:
            logger.debug(f"Failed to parse datetime: {e}")
            return None


def main():
    """Test the meeting scheduler"""
    import sys

    vault_path = sys.argv[1] if len(sys.argv) > 1 else "AI_Employee_Vault"

    scheduler = MeetingScheduler(vault_path, auto_schedule=False)

    # Get meeting suggestions
    suggestions = scheduler.get_meeting_suggestions()

    print(f"\nFound {len(suggestions)} potential meeting requests:\n")

    for i, suggestion in enumerate(suggestions, 1):
        print(f"{i}. {suggestion['subject']}")
        print(f"   From: {suggestion['sender']}")
        print(f"   Confidence: {suggestion['confidence']}")
        if suggestion['suggested_event']:
            event = suggestion['suggested_event']
            print(f"   Suggested: {event.get('start', 'Unknown time')}")
        print()

    # Process first suggestion
    if suggestions:
        print("Processing first suggestion...")
        result = scheduler.process_email(suggestions[0]['email_file'])
        print(f"Result: {result['status']}")
        print(f"Message: {result.get('message', 'N/A')}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
