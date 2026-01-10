"""AI Employee - Main Runner

Launches watcher scripts for monitoring Gmail and other sources.
Creates action items in the Obsidian vault when new items are detected.
"""

import argparse
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import List, Tuple, Optional

import msvcrt  # Windows-specific for key detection
from dotenv import load_dotenv

from Watchers.gmail_watcher import GmailWatcher
from Watchers.whatsapp_watcher import WhatsAppWatcher

# Load environment variables from .env file
load_dotenv()


# Setup logging with UTF-8 support for Windows
import codecs

# Create a custom stream handler that handles Unicode properly
class UTF8StreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            # Ensure message is ASCII-safe for console output
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
logger = logging.getLogger('AI_Employee')


class AIEmployeeManager:
    """
    Manages multiple watcher threads.

    This class is responsible for initializing, starting, and stopping
    all watcher instances in separate threads.

    Attributes:
        _vault_path (Path): Private path to the Obsidian vault
        _watchers (List[Tuple[str, BaseWatcher]]): Private list of (name, watcher) tuples
        _running (bool): Private flag indicating if manager is running
        _threads (List[threading.Thread]): Private list of active threads
    """

    def __init__(self, vault_path: str, enable_gmail: bool = True, enable_whatsapp: bool = True) -> None:
        """
        Initialize the AI Employee manager.

        Args:
            vault_path: Path to the Obsidian vault
            enable_gmail: Whether to enable Gmail watcher (default: True)
            enable_whatsapp: Whether to enable WhatsApp watcher (default: True)

        Raises:
            ValueError: If vault_path is invalid or no watchers are enabled
        """
        self._vault_path = Path(vault_path)
        self._watchers: List[Tuple[str, any]] = []
        self._running = False
        self._threads: List[threading.Thread] = []

        # Initialize watchers
        if enable_gmail:
            self._initialize_gmail_watcher()

        if enable_whatsapp:
            self._initialize_whatsapp_watcher()

        if not self._watchers:
            raise ValueError("At least one watcher must be enabled")

    def _initialize_gmail_watcher(self) -> None:
        """Initialize the Gmail watcher."""
        try:
            gmail_watcher = GmailWatcher(str(self._vault_path))
            self._watchers.append(('GmailWatcher', gmail_watcher))
            logger.info('Gmail Watcher initialized')
        except Exception as e:
            logger.warning(f'Could not initialize Gmail Watcher: {e}')
            logger.info('To enable Gmail: Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env')

    def _initialize_whatsapp_watcher(self) -> None:
        """Initialize the WhatsApp watcher."""
        try:
            whatsapp_watcher = WhatsAppWatcher(str(self._vault_path))
            self._watchers.append(('WhatsAppWatcher', whatsapp_watcher))
            logger.info('WhatsApp Watcher initialized')
        except Exception as e:
            logger.warning(f'Could not initialize WhatsApp Watcher: {e}')
            logger.info('To enable WhatsApp: Ensure Playwright is installed and run whatsapp_watcher.py once to scan QR')

    @property
    def vault_path(self) -> Path:
        """Get the vault path (read-only)."""
        return self._vault_path

    @property
    def is_running(self) -> bool:
        """Check if the manager is currently running (read-only)."""
        return self._running

    @property
    def watcher_count(self) -> int:
        """Get the number of active watchers (read-only)."""
        return len(self._watchers)

    def get_watcher_names(self) -> List[str]:
        """Get list of active watcher names."""
        return [name for name, _ in self._watchers]

    def start(self) -> None:
        """
        Start all watchers in separate threads.

        Raises:
            RuntimeError: If no watchers are configured
        """
        if not self._watchers:
            logger.error('No watchers to start!')
            raise RuntimeError("No watchers configured")

        self._running = True
        self._threads = []

        for name, watcher in self._watchers:
            thread = threading.Thread(
                target=watcher.run,
                name=name,
                daemon=True
            )
            thread.start()
            self._threads.append(thread)
            logger.info(f'Started {name} thread')

        # Main thread keeps running and checks for 'e' key press
        try:
            while self._running:
                if self._check_exit_key():
                    logger.info('Received "e" key press - stopping...')
                    self.stop()
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info('Received shutdown signal')
            self.stop()
        finally:
            self._wait_for_threads()

    def _check_exit_key(self) -> bool:
        """
        Check if exit key 'e' is pressed (Windows only).

        Returns:
            True if 'e' key was pressed, False otherwise
        """
        try:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                return key.lower() == b'e'
        except Exception:
            pass
        return False

    def _wait_for_threads(self) -> None:
        """Wait for all watcher threads to finish."""
        for thread in self._threads:
            thread.join(timeout=2)

    def stop(self) -> None:
        """Stop all watchers by setting the running flag to False."""
        if self._running:
            logger.info('Stopping AI Employee...')
            self._running = False

    def __repr__(self) -> str:
        """Return detailed string representation."""
        return (
            f"{self.__class__.__name__}("
            f"vault_path='{self._vault_path}', "
            f"watchers={self.get_watcher_names()}, "
            f"running={self._running})"
        )

    def __str__(self) -> str:
        """Return user-friendly string representation."""
        return f"AI Employee Manager with {self.watcher_count} watchers"

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        if exc_type:
            logger.error(f'Error during context: {exc_val}')
        return False


def create_vault_structure(vault_path: Path) -> None:
    """
    Create the vault folder structure if it doesn't exist.

    Args:
        vault_path: Path to the vault
    """
    logger.info('Creating vault structure...')
    vault_path.mkdir(parents=True, exist_ok=True)

    folders = ['Inbox', 'Needs_Action', 'Done', 'Pending_Approval']
    for folder in folders:
        (vault_path / folder).mkdir(exist_ok=True)

    logger.info('Vault structure created')


def setup_signal_handlers(manager: AIEmployeeManager) -> None:
    """
    Setup signal handlers for graceful shutdown.

    Args:
        manager: The AI Employee manager instance
    """
    def signal_handler(sig, frame):
        """Handle shutdown signals."""
        manager.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description='AI Employee - Watcher System for Obsidian Vault'
    )
    parser.add_argument(
        '--vault',
        default=None,
        help='Path to Obsidian vault (default: ./AI_Employee_Vault)'
    )
    parser.add_argument(
        '--no-gmail',
        action='store_true',
        help='Disable Gmail watcher'
    )
    parser.add_argument(
        '--no-whatsapp',
        action='store_true',
        help='Disable WhatsApp watcher'
    )
    parser.add_argument(
        '--vault-path',
        default=None,
        help='Alias for --vault'
    )

    return parser.parse_args()


def determine_vault_path(args: argparse.Namespace) -> Path:
    """
    Determine the vault path from arguments or default.

    Args:
        args: Parsed command line arguments

    Returns:
        Path to the vault
    """
    vault_path = args.vault or args.vault_path
    if not vault_path:
        vault_path = Path(__file__).parent / 'AI_Employee_Vault'

    return Path(vault_path)


def validate_and_create_vault(vault_path: Path) -> None:
    """
    Validate vault exists and create structure if needed.

    Args:
        vault_path: Path to the vault
    """
    if not vault_path.exists():
        logger.error(f'Vault not found: {vault_path}')
        create_vault_structure(vault_path)
    else:
        logger.info(f'Using vault: {vault_path}')


def main() -> None:
    """Main entry point for the AI Employee system."""
    args = parse_arguments()
    vault_path = determine_vault_path(args)

    validate_and_create_vault(vault_path)

    # Create and start manager
    try:
        manager = AIEmployeeManager(
            str(vault_path),
            enable_gmail=not args.no_gmail,
            enable_whatsapp=not args.no_whatsapp
        )

        setup_signal_handlers(manager)

        # Start watching
        logger.info('=' * 60)
        logger.info('AI Employee System Started')
        logger.info('=' * 60)
        logger.info(f'Active watchers: {", ".join(manager.get_watcher_names())}')
        logger.info('Watchers running. Press Ctrl+C or "e" to stop.')

        manager.start()

    except ValueError as e:
        logger.error(f'Configuration error: {e}')
        sys.exit(1)
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()