"""
LinkedIn Post Scheduler - Automatic weekly post generation

Generates LinkedIn posts on a scheduled basis (default: every Monday).
Posts are saved to AI_Employee_Vault/LinkedIn_Posts/ for review and posting.

Usage:
    from schedulers.linkedin_scheduler import LinkedInScheduler

    scheduler = LinkedInScheduler(vault_path="./AI_Employee_Vault")
    scheduler.start()
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from skills.linkedin_manager import LinkedInManager


@dataclass
class ScheduleConfig:
    """Scheduler configuration."""
    day_of_week: int = 0  # 0 = Monday, 6 = Sunday
    hour: int = 9  # 9 AM
    minute: int = 0
    enabled: bool = True


class LinkedInScheduler:
    """
    Automatic LinkedIn post generation scheduler.

    Generates weekly LinkedIn posts on a configurable schedule.
    Topics rotate through business insights, trends, and professional content.
    """

    # Weekly post topics
    POST_TOPICS = [
        {
            'type': 'insight',
            'name': 'Monday Motivation',
            'template_data': {
                'topic': 'Starting the Week Strong',
                'insight_1': '• Set 3 key priorities for the week',
                'insight_2': '• Focus on progress, not perfection',
                'insight_3': '• Celebrate small wins along the way',
                'hashtags': 'MondayMotivation Productivity Goals Success'
            }
        },
        {
            'type': 'insight',
            'name': 'Industry Insight',
            'template_data': {
                'topic': 'The Future of Work',
                'insight_1': '• Remote work is here to stay',
                'insight_2': '• AI is transforming workflows',
                'insight_3': '• Continuous learning is essential',
                'hashtags': 'FutureOfWork AI RemoteWork Technology'
            }
        },
        {
            'type': 'insight',
            'name': 'Leadership Lesson',
            'template_data': {
                'topic': 'Leadership in Action',
                'insight_1': '• Lead by example',
                'insight_2': '• Listen more than you speak',
                'insight_3': '• Empower your team to succeed',
                'hashtags': 'Leadership Management TeamWork Growth'
            }
        },
        {
            'type': 'insight',
            'name': 'Productivity Tip',
            'template_data': {
                'topic': 'Work Smarter, Not Harder',
                'insight_1': '• Time-block your most important tasks',
                'insight_2': '• Eliminate distractions during focus time',
                'insight_3': '• Take breaks to maintain peak performance',
                'hashtags': 'Productivity TimeManagement Efficiency WorkSmarter'
            }
        },
        {
            'type': 'insight',
            'name': 'Innovation Spotlight',
            'template_data': {
                'topic': 'Embracing Innovation',
                'insight_1': '• Challenge the status quo',
                'insight_2': '• Experiment with new approaches',
                'insight_3': '• Learn from failures and iterate',
                'hashtags': 'Innovation Technology DigitalTransformation Creativity'
            }
        }
    ]

    def __init__(
        self,
        vault_path: str,
        schedule: Optional[ScheduleConfig] = None
    ):
        """Initialize LinkedIn scheduler.

        Args:
            vault_path: Path to Obsidian vault
            schedule: Schedule configuration (default: Monday 9AM)
        """
        self._vault_path = Path(vault_path)
        self._schedule = schedule or ScheduleConfig()

        # Initialize LinkedIn manager
        self._linkedin_manager = LinkedInManager(str(self._vault_path))

        # Logging
        self._logger = logging.getLogger('LinkedInScheduler')

        # Scheduler state
        self._scheduler_thread: Optional[threading.Thread] = None
        self._should_stop = threading.Event()

        # Track last post generation
        self._last_generation: Optional[datetime] = None
        self._topic_index = 0

        # Load state from file if exists
        self._load_state()

        self._logger.info(f'LinkedIn Scheduler initialized')
        self._logger.info(f'Schedule: {self._get_schedule_description()}')

    def _get_schedule_description(self) -> str:
        """Get human-readable schedule description."""
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return f"{days[self._schedule.day_of_week]}s at {self._schedule.hour:02d}:{self._schedule.minute:02d}"

    def _load_state(self) -> None:
        """Load scheduler state from file."""
        state_file = self._vault_path / '.linkedin_scheduler_state.json'

        if state_file.exists():
            try:
                import json
                data = json.loads(state_file.read_text())

                last_gen = data.get('last_generation')
                if last_gen:
                    self._last_generation = datetime.fromisoformat(last_gen)

                self._topic_index = data.get('topic_index', 0)

                self._logger.info(f'State loaded: last_generation={last_gen}, topic_index={self._topic_index}')
            except Exception as e:
                self._logger.warning(f'Failed to load state: {e}')

    def _save_state(self) -> None:
        """Save scheduler state to file."""
        state_file = self._vault_path / '.linkedin_scheduler_state.json'

        try:
            import json
            data = {
                'last_generation': self._last_generation.isoformat() if self._last_generation else None,
                'topic_index': self._topic_index,
                'updated': datetime.now().isoformat()
            }

            state_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            self._logger.error(f'Failed to save state: {e}')

    def _should_generate_now(self) -> bool:
        """Check if it's time to generate a post.

        Returns:
            True if scheduled time has been reached
        """
        now = datetime.now()

        # Check if we already generated this week
        if self._last_generation:
            # Calculate Monday of current week
            monday_this_week = now - timedelta(days=now.weekday())
            monday_last_week = self._last_generation - timedelta(days=self._last_generation.weekday())

            # If last generation was this week, skip
            if monday_last_week >= monday_this_week:
                return False

        # Check if current time matches schedule
        if now.weekday() == self._schedule.day_of_week:
            # Check if we're past the scheduled time
            scheduled_time = now.replace(
                hour=self._schedule.hour,
                minute=self._schedule.minute,
                second=0,
                microsecond=0
            )

            if now >= scheduled_time:
                # Check if we haven't already generated today
                if self._last_generation:
                    if self._last_generation.date() == now.date():
                        return False

                return True

        return False

    def _generate_weekly_post(self) -> Optional[str]:
        """Generate the weekly LinkedIn post.

        Returns:
            Path to generated post or None
        """
        try:
            # Get current topic
            topic = self.POST_TOPICS[self._topic_index]
            self._logger.info(f'Generating post: {topic["name"]}')

            # Generate post
            post = self._linkedin_manager.generate_post(
                topic['type'],
                **topic['template_data']
            )

            # Add weekly tag to post
            post.content = f"📅 Weekly Post: {topic['name']}\n\n{post.content}"

            # Save post
            filepath = self._linkedin_manager.save_post(post)

            # Update state
            self._last_generation = datetime.now()

            # Move to next topic
            self._topic_index = (self._topic_index + 1) % len(self.POST_TOPICS)

            # Save state
            self._save_state()

            self._logger.info(f'✅ Weekly post generated: {filepath}')

            return filepath

        except Exception as e:
            self._logger.error(f'Failed to generate weekly post: {e}')
            return None

    def generate_now(self) -> Optional[str]:
        """Manually trigger post generation (for testing).

        Returns:
            Path to generated post or None
        """
        self._logger.info('Manual post generation triggered')
        return self._generate_weekly_post()

    def start(self) -> None:
        """Start the scheduler in background thread."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._logger.warning('Scheduler already running')
            return

        if not self._schedule.enabled:
            self._logger.info('Scheduler is disabled')
            return

        self._should_stop.clear()
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()

        self._logger.info(f'LinkedIn scheduler started (posts every {self._get_schedule_description()})')

    def stop(self) -> None:
        """Stop the scheduler."""
        self._should_stop.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
            self._logger.info('LinkedIn scheduler stopped')

    def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        self._logger.info('Scheduler loop started')

        while not self._should_stop.is_set():
            try:
                # Check if it's time to generate
                if self._should_generate_now():
                    self._generate_weekly_post()

                # Wait before next check (check every hour)
                self._should_stop.wait(timeout=3600)

            except Exception as e:
                self._logger.error(f'Error in scheduler loop: {e}')
                self._should_stop.wait(timeout=60)

        self._logger.info('Scheduler loop stopped')

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status.

        Returns:
            Dict with status information
        """
        now = datetime.now()

        # Calculate next scheduled time
        days_until_monday = (0 - now.weekday() + 7) % 7
        if days_until_monday == 0:
            # Today is Monday, check if we've passed the time
            scheduled_time = now.replace(
                hour=self._schedule.hour,
                minute=self._schedule.minute,
                second=0,
                microsecond=0
            )
            if now < scheduled_time:
                next_run = scheduled_time
            else:
                # Next Monday
                next_run = scheduled_time + timedelta(days=7)
        else:
            # Next Monday
            next_monday = now + timedelta(days=days_until_monday)
            next_run = next_monday.replace(
                hour=self._schedule.hour,
                minute=self._schedule.minute,
                second=0,
                microsecond=0
            )

        return {
            'enabled': self._schedule.enabled,
            'schedule': self._get_schedule_description(),
            'last_generation': self._last_generation.isoformat() if self._last_generation else None,
            'next_generation': next_run.isoformat(),
            'next_topic': self.POST_TOPICS[self._topic_index]['name'],
            'status': 'running' if self._scheduler_thread and self._scheduler_thread.is_alive() else 'stopped'
        }


# ============ CONVENIENCE FUNCTIONS ============

def create_scheduler(
    vault_path: str,
    day_of_week: int = 0,
    hour: int = 9,
    minute: int = 0
) -> LinkedInScheduler:
    """Create and start LinkedIn scheduler.

    Args:
        vault_path: Path to Obsidian vault
        day_of_week: Day to generate posts (0=Monday, 6=Sunday)
        hour: Hour to generate (0-23)
        minute: Minute to generate (0-59)

    Returns:
        Running LinkedInScheduler instance
    """
    schedule = ScheduleConfig(
        day_of_week=day_of_week,
        hour=hour,
        minute=minute,
        enabled=True
    )

    scheduler = LinkedInScheduler(vault_path, schedule)
    scheduler.start()

    return scheduler


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    vault = Path(__file__).parent.parent / 'AI_Employee_Vault'

    # Test: generate a post now
    scheduler = LinkedInScheduler(str(vault))
    print("Generating test post...")
    path = scheduler.generate_now()
    print(f"Post generated: {path}")

    # Show status
    status = scheduler.get_status()
    print(f"\nScheduler Status:")
    print(f"  Schedule: {status['schedule']}")
    print(f"  Next topic: {status['next_topic']}")
    print(f"  Next generation: {status['next_generation']}")


__all__ = ['LinkedInScheduler', 'ScheduleConfig', 'create_scheduler']
