"""
Meeting Scheduler Skill Functions
Convenience functions for meeting scheduling
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from schedulers.meeting_scheduler import MeetingScheduler
    MEETING_SCHEDULER_AVAILABLE = True
except ImportError:
    MEETING_SCHEDULER_AVAILABLE = False


# Global meeting scheduler instance
_ms_instance = None


def get_meeting_scheduler(vault_path: str = None, auto_schedule: bool = False):
    """Get or create meeting scheduler instance"""
    global _ms_instance

    if not MEETING_SCHEDULER_AVAILABLE:
        raise Exception("Meeting Scheduler not available")

    if vault_path is None:
        vault_path = os.path.join(os.path.dirname(__file__), "..", "AI_Employee_Vault")

    if _ms_instance is None:
        _ms_instance = MeetingScheduler(vault_path, auto_schedule=auto_schedule)

    return _ms_instance


def schedule_meeting_from_email(email_file: str, auto_schedule: bool = True) -> dict:
    """
    Extract meeting details from an email and schedule it

    Args:
        email_file: Email filename (e.g., "EMAIL_12345.md")
        auto_schedule: If True, create the event; if False, suggest only

    Returns:
        Result dictionary with status and event details

    Example:
        result = schedule_meeting_from_email("EMAIL_12345.md")
        if result['status'] == 'scheduled':
            print(f"Created: {result['event']['link']}")
        elif result['status'] == 'suggested':
            print(f"Suggested: {result['details']['title']}")
    """
    ms = get_meeting_scheduler(auto_schedule=auto_schedule)
    return ms.process_email(email_file)


def get_meeting_suggestions(limit: int = 10) -> list:
    """
    Get list of emails that look like meeting requests

    Args:
        limit: Maximum number of suggestions

    Returns:
        List of suggested meetings with details

    Example:
        suggestions = get_meeting_suggestions(limit=5)
        for s in suggestions:
            print(f"{s['subject']} from {s['sender']}")
            if s['suggested_event']:
                print(f"  Time: {s['suggested_event']['start']}")
    """
    ms = get_meeting_scheduler(auto_schedule=False)
    return ms.get_meeting_suggestions(limit=limit)


def schedule_all_meetings(auto_schedule: bool = True) -> dict:
    """
    Process all pending emails and schedule meetings

    Args:
        auto_schedule: If True, create events; if False, suggest only

    Returns:
        Result dictionary with counts and details

    Example:
        result = schedule_all_meetings(auto_schedule=True)
        print(f"Scheduled: {result['scheduled_count']}")
        print(f"Errors: {result['error_count']}")
    """
    ms = get_meeting_scheduler(auto_schedule=auto_schedule)
    results = ms.process_all_pending_emails()

    scheduled_count = sum(1 for r in results if r['status'] == 'scheduled')
    suggested_count = sum(1 for r in results if r['status'] == 'suggested')
    error_count = sum(1 for r in results if r['status'] == 'error')

    return {
        'total': len(results),
        'scheduled_count': scheduled_count,
        'suggested_count': suggested_count,
        'error_count': error_count,
        'results': results
    }


def review_meeting_request(email_file: str) -> dict:
    """
    Review a meeting request email without scheduling

    Args:
        email_file: Email filename

    Returns:
        Dictionary with extracted meeting details

    Example:
        review = review_meeting_request("EMAIL_12345.md")
        print(f"Title: {review['details']['title']}")
        print(f"Time: {review['details']['start_time']}")
        print(f"Attendees: {review['details']['attendees']}")
    """
    ms = get_meeting_scheduler(auto_schedule=False)
    return ms.process_email(email_file)


if __name__ == "__main__":
    # Test the skills
    print("Testing Meeting Scheduler Skills...")

    # Get suggestions
    suggestions = get_meeting_suggestions(limit=5)
    print(f"\nFound {len(suggestions)} potential meetings:")
    for s in suggestions:
        print(f"  - {s['subject']} (confidence: {s['confidence']})")

    # Process first suggestion
    if suggestions:
        print(f"\nReviewing: {suggestions[0]['subject']}")
        result = review_meeting_request(suggestions[0]['email_file'])
        print(f"Status: {result['status']}")
        if result.get('details'):
            details = result['details']
            print(f"  Title: {details.get('title')}")
            print(f"  Time: {details.get('start_time')}")

    print("\nMeeting Scheduler Skills test complete!")
