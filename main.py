"""
AI Employee System - Main Entry Point

Coordinates all watchers, schedulers, and skills for automated communication management.
Uses advanced keyword-based analysis (no external AI APIs required).

Usage:
    python main.py                    # Run all watchers continuously
    python main.py --once             # Single pass then exit
    python main.py --help             # Show all options

Features:
- Gmail monitoring with keyword analysis
- Weekly LinkedIn post generation (Mondays 9AM)
- Task management system
- Health monitoring and auto-recovery
"""

import argparse
import logging
import os
import signal
import sys
import time
import threading
from pathlib import Path
from typing import List, Optional, Tuple, Any

from dotenv import load_dotenv

# Watchers
from Watchers.gmail_watcher import GmailWatcher
from Watchers.failure_manager import FailureManager

# Skills
from skills.email_planner import EmailPlanner
from skills.linkedin_manager import LinkedInManager

# Schedulers
from schedulers.linkedin_scheduler import LinkedInScheduler
from schedulers.meeting_scheduler import MeetingScheduler

# MCP Servers
try:
    from mcp_servers.database_mcp import DatabaseMCP
    DATABASE_MCP_AVAILABLE = True
except ImportError:
    DATABASE_MCP_AVAILABLE = False

# Setup logging with UTF-8 support
import codecs
import io

# Reconfigure stdout to handle UTF-8 on Windows
if sys.platform == 'win32':
    # On Windows, wrap stdout with a UTF-8 writer
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer,
        encoding='utf-8',
        errors='replace',
        newline=None,
        line_buffering=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer,
        encoding='utf-8',
        errors='replace',
        newline=None,
        line_buffering=True
    )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('ai_employee.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('AI_Employee')


class AIEmployeeSystem:
    """
    Main AI Employee system orchestrator.

    Coordinates all watchers and schedulers with built-in health monitoring.
    """

    def __init__(
        self,
        vault_path: str,
        enable_gmail: bool = True,
        enable_linkedin: bool = True,
        enable_planner: bool = False,
        enable_database: bool = True,
        enable_meeting_scheduler: bool = False,
        auto_schedule_meetings: bool = False,
        check_interval: int = 60
    ):
        """Initialize the AI Employee system.

        Args:
            vault_path: Path to Obsidian vault
            enable_gmail: Enable Gmail watcher
            enable_linkedin: Enable LinkedIn scheduler
            enable_planner: Enable automatic email planning
            enable_database: Enable Database MCP
            enable_meeting_scheduler: Enable meeting scheduler
            auto_schedule_meetings: Automatically schedule meetings (vs suggest only)
            check_interval: Seconds between checks
        """
        self._vault_path = Path(vault_path)
        self._enable_gmail = enable_gmail
        self._enable_linkedin = enable_linkedin
        self._enable_planner = enable_planner
        self._enable_database = enable_database
        self._enable_meeting_scheduler = enable_meeting_scheduler
        self._auto_schedule_meetings = auto_schedule_meetings
        self._check_interval = check_interval

        self._watchers: List[Tuple[str, Any]] = []
        self._schedulers: List[Tuple[str, Any]] = []
        self._planner_thread = None
        self._meeting_scheduler_thread = None
        self._running = False

        # Failure manager for health monitoring
        self._failure_manager: Optional[FailureManager] = None

        # MCP Servers
        self._database_mcp = None
        self._meeting_scheduler = None

        # Initialize all components
        self._initialize_managers()
        self._initialize_mcp_servers()
        self._initialize_watchers()
        self._initialize_schedulers()

        logger.info('')
        logger.info('╔════════════════════════════════════════════════════════════╗')
        logger.info('║           ✨ AI Employee System Started                     ║')
        logger.info('╚════════════════════════════════════════════════════════════╝')
        logger.info('')
        logger.info(f'  📁 Vault: {self._vault_path}')
        logger.info(f'  👀 Watchers: {", ".join([name for name, _ in self._watchers]) or "None"}')
        logger.info(f'  ⏰ Schedulers: {", ".join([name for name, _ in self._schedulers]) or "None"}')

        # MCP status
        mcp_status = []
        if self._database_mcp:
            mcp_status.append("Database")
        if self._meeting_scheduler:
            mcp_status.append("Meeting Scheduler")
        logger.info(f'  🔧 MCPs: {", ".join(mcp_status) or "None"}')

        logger.info('')

    def _initialize_managers(self):
        """Initialize system managers."""
        try:
            self._failure_manager = FailureManager(
                vault_path=str(self._vault_path),
                health_check_interval=30,
                max_restart_attempts=3,
                alert_threshold=5
            )
            logger.info('✓ Failure Manager initialized')
        except Exception as e:
            logger.warning(f'Could not initialize Failure Manager: {e}')

    def _initialize_mcp_servers(self):
        """Initialize MCP servers."""
        # Database MCP
        if self._enable_database and DATABASE_MCP_AVAILABLE:
            try:
                db_path = self._vault_path / 'ai_employee.db'
                self._database_mcp = DatabaseMCP(str(db_path))
                logger.info(f'✓ Database MCP initialized ({db_path})')
            except Exception as e:
                logger.warning(f'Could not initialize Database MCP: {e}')

    def _initialize_watchers(self):
        """Initialize all enabled watchers."""
        # Gmail Watcher
        if self._enable_gmail:
            try:
                gmail_watcher = GmailWatcher(str(self._vault_path))
                self._watchers.append(('GmailWatcher', gmail_watcher))
                self._failure_manager.register_watcher('GmailWatcher', gmail_watcher)
                logger.info('✓ Gmail watcher initialized')
            except Exception as e:
                logger.error(f'Could not initialize Gmail watcher: {e}')

    def _initialize_schedulers(self):
        """Initialize all enabled schedulers."""
        # LinkedIn Scheduler
        if self._enable_linkedin:
            try:
                linkedin_scheduler = LinkedInScheduler(str(self._vault_path))
                self._schedulers.append(('LinkedInScheduler', linkedin_scheduler))
                logger.info('✓ LinkedIn scheduler initialized (posts on Mondays 9AM)')
            except Exception as e:
                logger.warning(f'Could not initialize LinkedIn scheduler: {e}')

        # Meeting Scheduler
        if self._enable_meeting_scheduler:
            try:
                self._meeting_scheduler = MeetingScheduler(
                    str(self._vault_path),
                    auto_schedule=self._auto_schedule_meetings
                )
                mode = "auto-schedule" if self._auto_schedule_meetings else "suggest"
                logger.info(f'✓ Meeting scheduler initialized (mode: {mode})')
            except Exception as e:
                logger.warning(f'Could not initialize Meeting Scheduler: {e}')

    def run_continuous(self):
        """Run all watchers continuously in separate threads."""
        logger.info('=' * 60)
        logger.info('Starting AI Employee System (Continuous Mode)')
        logger.info('=' * 60)
        logger.info('Press Ctrl+C to stop')

        self._running = True

        # Start failure manager monitoring
        if self._failure_manager:
            self._failure_manager.start_monitoring()

        # Start schedulers
        for name, scheduler in self._schedulers:
            try:
                if hasattr(scheduler, 'start'):
                    scheduler.start()
                    logger.info(f'▶ Started {name}')
            except Exception as e:
                logger.error(f'Failed to start {name}: {e}')

        # Start email planner in background if enabled
        if self._enable_planner:
            self._planner_thread = self._start_planner_thread()

        # Start meeting scheduler in background if enabled
        if self._enable_meeting_scheduler and self._meeting_scheduler:
            # Meeting scheduler now operates in suggest mode only (no calendar)
            logger.info('ℹ️ Meeting Scheduler running in suggest mode (use skills to review suggestions)')

        # Start watchers in threads
        threads = []
        for name, watcher in self._watchers:
            thread = threading.Thread(
                target=watcher.run,
                name=name,
                daemon=True  # Daemon threads will be killed when main exits
            )
            thread.start()
            threads.append(thread)
            logger.info(f'▶ Started {name} thread')

        # Print system status
        self._print_status()

        # Wait for interrupt signal
        try:
            while self._running:
                time.sleep(1)

                # Update failure manager heartbeats
                for name, watcher in self._watchers:
                    try:
                        # Check if the thread is still alive
                        is_healthy = any(t.name == name and t.is_alive() for t in threads)
                        self._failure_manager.update_heartbeat(name, is_healthy)
                    except Exception:
                        pass

        except KeyboardInterrupt:
            logger.info('\nReceived interrupt signal')
        finally:
            self.stop()

        # Brief wait for daemon threads to finish (max 2 seconds)
        for thread in threads:
            thread.join(timeout=2)

    def run_once(self):
        """Run all watchers once (single pass)."""
        logger.info('=' * 60)
        logger.info('Starting AI Employee System (Single Pass)')
        logger.info('=' * 60)

        # Run email planner if enabled
        if self._enable_planner:
            logger.info('Running email planner...')
            try:
                planner = EmailPlanner(str(self._vault_path))
                plans = planner.plan_all_emails()
                logger.info(f'✓ Created {len(plans)} email plans')
            except Exception as e:
                logger.error(f'Email planner error: {e}')

        # Run each watcher once
        total_items = 0
        for name, watcher in self._watchers:
            try:
                logger.info(f'Checking {name}...')
                items = watcher.check_for_updates()
                for item in items:
                    watcher.create_action_file(item)
                    total_items += 1
                logger.info(f'✓ {name} processed {len(items)} items')
            except Exception as e:
                logger.error(f'{name} error: {e}')

        logger.info('=' * 60)
        logger.info(f'Single pass completed ({total_items} items processed)')

    def _start_planner_thread(self):
        """Start email planner in background thread."""
        def planner_loop():
            planner = EmailPlanner(str(self._vault_path))
            while self._running:
                try:
                    logger.info('Running scheduled email planner...')
                    plans = planner.plan_all_emails()
                    logger.info(f'✓ Created {len(plans)} email plans')
                except Exception as e:
                    logger.error(f'Planner error: {e}')
                # Wait 30 minutes before next run
                for _ in range(30 * 60):
                    if not self._running:
                        break
                    time.sleep(1)

        thread = threading.Thread(
            target=planner_loop,
            name='EmailPlanner',
            daemon=True
        )
        thread.start()
        logger.info('▶ Started Email Planner thread (runs every 30 minutes)')
        return thread

    def _print_status(self):
        """Print system status."""
        logger.info('')
        logger.info('System Status:')
        logger.info(f'  Watchers: {len(self._watchers)} active')
        logger.info(f'  Schedulers: {len(self._schedulers)} active')
        logger.info(f'  Failure Manager: {"Active" if self._failure_manager else "Disabled"}')
        logger.info('')

    def stop(self):
        """Stop all watchers and cleanup."""
        logger.info('')
        logger.info('Stopping AI Employee System...')
        self._running = False

        # Signal all watchers to stop
        for name, watcher in self._watchers:
            try:
                if hasattr(watcher, 'stop'):
                    watcher.stop()
                    logger.info(f'✓ Signaled {name} to stop')
            except Exception as e:
                logger.error(f'Error stopping {name}: {e}')

        # Stop schedulers
        for name, scheduler in self._schedulers:
            try:
                if hasattr(scheduler, 'stop'):
                    scheduler.stop()
                    logger.info(f'✓ Stopped {name}')
            except Exception as e:
                logger.error(f'Error stopping {name}: {e}')

        # Stop failure manager
        if self._failure_manager:
            self._failure_manager.stop_monitoring()

        # Close MCP connections
        if self._database_mcp:
            try:
                self._database_mcp.close()
                logger.info('✓ Database MCP closed')
            except Exception as e:
                logger.error(f'Error closing Database MCP: {e}')

        # Print health report
        if self._failure_manager:
            try:
                report = self._failure_manager.get_health_report()
                logger.info('')
                logger.info('Final Health Report:')
                for watcher_name, health in report['watchers'].items():
                    status = health['status']
                    errors = health['error_count']
                    logger.info(f'  {watcher_name}: {status} ({errors} errors)')
            except Exception as e:
                logger.debug(f'Could not generate health report: {e}')

        logger.info('')
        logger.info('AI Employee System stopped')
        logger.info('=' * 60)


def setup_signal_handlers(system: AIEmployeeSystem):
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(sig, frame):
        logger.info(f'Received signal {sig}')
        system.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='AI Employee System - Monitor emails, chats, and automate tasks',
        epilog="""
Examples:
  python main.py                         # Run continuous mode (Database enabled by default)
  python main.py --once                  # Run once and exit
  python main.py --no-gmail              # Disable Gmail watcher
  python main.py --no-database           # Disable Database MCP
  python main.py --planner               # Enable email planner
  python main.py --enable-meeting-scheduler     # Enable meeting scheduler (suggest mode)

Vault Structure:
  AI_Employee_Vault/
  ├── Inbox/              # Initial items
  ├── Needs_Action/       # Actionable items
  ├── Plans/              # Response plans
  ├── Done/               # Completed items
  ├── Logs/               # Activity logs
  ├── LinkedIn_Posts/     # Generated posts
  └── Tasks/              # Tasks for Claude Code
        """
    )
    parser.add_argument(
        '--vault',
        default=None,
        help='Path to Obsidian vault (default: ./AI_Employee_Vault)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit (default: continuous mode)'
    )
    parser.add_argument(
        '--no-gmail',
        action='store_true',
        help='Disable Gmail watcher'
    )
    parser.add_argument(
        '--no-linkedin',
        action='store_true',
        help='Disable LinkedIn scheduler'
    )
    parser.add_argument(
        '--planner',
        action='store_true',
        help='Enable automatic email planning (runs every 30 minutes)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Check interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--enable-database',
        action='store_true',
        help='Enable Database MCP (enabled by default)'
    )
    parser.add_argument(
        '--no-database',
        action='store_true',
        help='Disable Database MCP'
    )
    parser.add_argument(
        '--enable-meeting-scheduler',
        action='store_true',
        help='Enable automatic meeting scheduler from emails'
    )

    return parser.parse_args()


def ensure_vault_structure(vault_path: Path):
    """Ensure vault structure exists."""
    folders = [
        'Inbox',
        'Needs_Action',
        'Done',
        'Plans',
        'Approved',
        'Rejected',
        'Logs',
        'Logs/Errors',
        'Logs/Auto_Sent',
        'LinkedIn_Posts',
        'Tasks'
    ]

    for folder in folders:
        (vault_path / folder).mkdir(parents=True, exist_ok=True)


def main():
    """Main entry point."""
    args = parse_arguments()

    # Determine vault path
    vault_path = args.vault or Path(__file__).parent / 'AI_Employee_Vault'
    vault_path = Path(vault_path)

    # Create vault if it doesn't exist
    if not vault_path.exists():
        vault_path.mkdir(parents=True, exist_ok=True)

    ensure_vault_structure(vault_path)

    # Create system
    system = AIEmployeeSystem(
        str(vault_path),
        enable_gmail=not args.no_gmail,
        enable_linkedin=not args.no_linkedin,
        enable_planner=args.planner,
        enable_database=not args.no_database,
        enable_meeting_scheduler=args.enable_meeting_scheduler,
        auto_schedule_meetings=False,  # Always suggest mode
        check_interval=args.interval
    )

    # Setup signal handlers
    setup_signal_handlers(system)

    # Run in continuous mode by default, or once if --once flag is provided
    if args.once:
        system.run_once()
    else:
        system.run_continuous()


if __name__ == '__main__':
    load_dotenv()
    main()
