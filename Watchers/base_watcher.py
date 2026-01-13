"""Base Watcher Abstract Class

Provides the foundation for all watcher implementations in the AI Employee system.
"""

import time
import logging
import threading
from datetime import datetime
from pathlib import Path
from abc import ABC, abstractmethod
from typing import List, Optional, Any
from contextlib import contextmanager


class BaseWatcher(ABC):
    """
    Abstract base class for all watcher implementations.

    This class defines the interface that all watchers must implement and provides
    common functionality for vault management and running the watcher loop.

    Attributes:
        _vault_path (Path): Private path to the Obsidian vault
        _check_interval (int): Private interval in seconds between checks
        _needs_action (Path): Private path to the Needs_Action folder
        _logger (logging.Logger): Private logger instance
    """

    def __init__(self, vault_path: str, check_interval: int = 60) -> None:
        """
        Initialize the base watcher.

        Args:
            vault_path: Path to the Obsidian vault
            check_interval: Seconds between update checks (default: 60)

        Raises:
            ValueError: If check_interval is less than 1
        """
        if check_interval < 1:
            raise ValueError("check_interval must be at least 1 second")

        self._vault_path = Path(vault_path)
        self._check_interval = check_interval
        self._needs_action = self._vault_path / 'Needs_Action'
        self._logger = logging.getLogger(self.__class__.__name__)
        self._running = False
        self._stop_event = threading.Event()

        # Ensure vault structure exists
        self._ensure_vault_structure()

    @property
    def vault_path(self) -> Path:
        """Get the vault path (read-only access)."""
        return self._vault_path

    @property
    def check_interval(self) -> int:
        """Get the check interval in seconds (read-only access)."""
        return self._check_interval

    @property
    def needs_action(self) -> Path:
        """Get the Needs_Action folder path (read-only access)."""
        return self._needs_action

    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance (read-only access)."""
        return self._logger

    def _ensure_vault_structure(self) -> None:
        """
        Ensure all required directories and files exist in the vault.

        Creates the following structure:
        - Inbox/ (where watchers drop new tasks)
        - Needs_Action/ (actionable items)
        - Plans/ (Claude's generated plans)
        - Done/ (processed items)
        - Logs/ (activity logs)
        - Company_Handbook.md (rules and context for Claude)
        - Dashboard.md (simple summary)
        """
        directories = [
            self._vault_path / 'Inbox',
            self._vault_path / 'Needs_Action',
            self._vault_path / 'Plans',
            self._vault_path / 'Done',
            self._vault_path / 'Logs'
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        # Create Company_Handbook.md if it doesn't exist
        handbook = self._vault_path / 'Company_Handbook.md'
        if not handbook.exists():
            timestamp = datetime.now().isoformat()
            handbook.write_text(f'''# Company Handbook

## Purpose
This document contains rules, context, and guidelines for the AI Employee system.

## System Overview
The AI Employee monitors multiple sources (Gmail, WhatsApp, etc.) and creates actionable tasks in the Needs_Action folder.

## Workflow
1. Watchers detect new items and create files in Needs_Action/
2. Each item should be processed and either:
   - Completed (moved to Done/)
   - Archived or deleted
3. Plans and strategy documents go in Plans/
4. Activity logs are stored in Logs/

## Processing Rules
- Prioritize urgent items first
- Document decisions in the file's frontmatter
- Mark completed items with status: completed
- Move processed items to Done/

---
*Last updated: {timestamp}*
''')

        # Create Dashboard.md if it doesn't exist
        dashboard = self._vault_path / 'Dashboard.md'
        if not dashboard.exists():
            timestamp = datetime.now().isoformat()
            dashboard.write_text(f'''# AI Employee Dashboard

## Quick Stats
- Active watchers: N/A
- Pending actions: 0
- Completed today: 0

## Recent Activity
<!-- This section is updated automatically -->

## Quick Links
- [[Needs_Action]] - Items requiring attention
- [[Done]] - Completed items
- [[Plans]] - Strategy and planning
- [[Logs]] - Activity logs
- [[Company_Handbook]] - System documentation

---
*Dashboard initialized: {timestamp}*
''')

        # Quiet - don't log during initialization

    @abstractmethod
    def check_for_updates(self) -> List[Any]:
        """
        Check for new items to process.

        This method must be implemented by all subclasses.

        Returns:
            List of new items found since last check

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        pass

    @abstractmethod
    def create_action_file(self, item: Any) -> Optional[Path]:
        """
        Create an action file in the Needs_Action folder.

        This method must be implemented by all subclasses.

        Args:
            item: The item to create an action file for

        Returns:
            Path to the created file, or None if creation failed

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        pass

    def run(self) -> None:
        """
        Run the main watcher loop.

        Continuously checks for updates and creates action files until stopped.
        This method is designed to be overridden by subclasses that need
        additional functionality in their run loop.
        """
        self._running = True

        try:
            while self._running and not self._stop_event.is_set():
                try:
                    items = self.check_for_updates()
                    for item in items:
                        if not self._running or self._stop_event.is_set():
                            break
                        self.create_action_file(item)
                except Exception as e:
                    self._logger.error(f'Error in watcher loop: {e}')

                # Sleep with interrupt check
                self._stop_event.wait(timeout=self._check_interval)

        except KeyboardInterrupt:
            pass
        finally:
            self._running = False

    def stop(self) -> None:
        """Signal the watcher to stop running."""
        self._running = False
        self._stop_event.set()

    def __repr__(self) -> str:
        """Return string representation of the watcher."""
        return (
            f"{self.__class__.__name__}("
            f"vault_path='{self._vault_path}', "
            f"check_interval={self._check_interval})"
        )

    def __str__(self) -> str:
        """Return user-friendly string representation."""
        return f"{self.__class__.__name__} watching {self._vault_path}"

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        if exc_type:
            self._logger.error(f'Error during context: {exc_val}')
        return False