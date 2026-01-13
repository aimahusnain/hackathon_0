"""Watchers Package - Contains all watcher implementations."""

from .base_watcher import BaseWatcher
from .gmail_watcher import GmailWatcher
from .google_chat_watcher import GoogleChatWatcher
from .failure_manager import FailureManager

__all__ = [
    'BaseWatcher',
    'GmailWatcher',
    'GoogleChatWatcher',
    'FailureManager',
]
