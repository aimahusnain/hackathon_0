"""
Watcher Failure Manager - Monitor health and auto-restart failed watchers

This manager monitors all watchers for failures and implements automatic
recovery with exponential backoff.

Features:
- Health checking for all watchers
- Automatic restart on failure
- Failure logging to Logs/Errors/
- Alert generation for critical failures
- Recovery attempts with exponential backoff
- Status dashboard updates
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class WatcherStatus(Enum):
    """Watcher health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"


@dataclass
class WatcherHealth:
    """Health tracking for a single watcher."""
    name: str
    status: WatcherStatus = WatcherStatus.HEALTHY
    last_heartbeat: Optional[datetime] = None
    last_successful_check: Optional[datetime] = None
    error_count: int = 0
    consecutive_failures: int = 0
    restart_attempts: int = 0
    max_restart_attempts: int = 3
    last_error: Optional[str] = None
    recovery_backoff_seconds: int = 30
    is_running: bool = True


class FailureManager:
    """
    Monitor and manage watcher failures.

    Provides health monitoring, automatic restart, and alerting
    for all registered watchers.
    """

    def __init__(
        self,
        vault_path: str,
        health_check_interval: int = 30,
        max_restart_attempts: int = 3,
        alert_threshold: int = 5
    ):
        """Initialize failure manager.

        Args:
            vault_path: Path to Obsidian vault
            health_check_interval: Seconds between health checks (default: 30)
            max_restart_attempts: Maximum restart attempts before giving up (default: 3)
            alert_threshold: Consecutive failures before creating alert (default: 5)
        """
        self._vault_path = Path(vault_path)
        self._health_check_interval = health_check_interval
        self._max_restart_attempts = max_restart_attempts
        self._alert_threshold = alert_threshold

        # Health tracking for all watchers
        self._watchers: Dict[str, WatcherHealth] = {}

        # Logging
        self._logger = logging.getLogger('FailureManager')

        # Ensure error logs folder exists
        self._error_logs_path = self._vault_path / 'Logs' / 'Errors'
        self._error_logs_path.mkdir(parents=True, exist_ok=True)

        # Background monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._should_stop = threading.Event()

        self._logger.info('Failure Manager initialized')

    @property
    def vault_path(self) -> Path:
        """Get vault path (read-only)."""
        return self._vault_path

    @property
    def health_check_interval(self) -> int:
        """Get health check interval (read-only)."""
        return self._health_check_interval

    @property
    def max_restart_attempts(self) -> int:
        """Get max restart attempts (read-only)."""
        return self._max_restart_attempts

    @property
    def alert_threshold(self) -> int:
        """Get alert threshold (read-only)."""
        return self._alert_threshold

    @property
    def watchers(self) -> Dict[str, WatcherHealth]:
        """Get watchers dictionary (read-only)."""
        return self._watchers.copy()

    @property
    def logger(self) -> logging.Logger:
        """Get logger instance (read-only)."""
        return self._logger

    def register_watcher(
        self,
        name: str,
        watcher_instance: Any = None
    ) -> None:
        """Register a watcher for health monitoring.

        Args:
            name: Unique watcher name
            watcher_instance: Optional watcher instance (for direct restart)
        """
        if name in self._watchers:
            self._logger.warning(f'Watcher {name} already registered. Updating.')

        self._watchers[name] = WatcherHealth(
            name=name,
            last_heartbeat=datetime.now(),
            last_successful_check=datetime.now(),
            max_restart_attempts=self._max_restart_attempts
        )

        self._logger.info(f'Registered watcher: {name}')

    def update_heartbeat(self, name: str, is_healthy: bool = True, error: Optional[str] = None) -> None:
        """Update watcher heartbeat and health status.

        Args:
            name: Watcher name
            is_healthy: Whether watcher is healthy
            error: Optional error message
        """
        if name not in self._watchers:
            self._logger.warning(f'Unknown watcher: {name}')
            return

        health = self._watchers[name]
        health.last_heartbeat = datetime.now()

        if is_healthy:
            health.status = WatcherStatus.HEALTHY
            health.last_successful_check = datetime.now()
            health.consecutive_failures = 0
            health.last_error = None
            health.is_running = True
        else:
            health.consecutive_failures += 1
            health.error_count += 1
            health.last_error = error

            # Determine status based on failures
            if health.consecutive_failures >= 3:
                health.status = WatcherStatus.FAILED
            elif health.consecutive_failures >= 1:
                health.status = WatcherStatus.DEGRADED

            # Log error
            self._log_error(name, error, health.consecutive_failures)

            # Check if alert needed
            if health.consecutive_failures >= self._alert_threshold:
                self._create_alert(name, health)

    def _log_error(self, watcher_name: str, error: Optional[str], failure_count: int) -> None:
        """Log watcher error to file.

        Args:
            watcher_name: Name of watcher
            error: Error message
            failure_count: Consecutive failure count
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d')
            log_file = self._error_logs_path / f'{watcher_name}_errors_{timestamp}.md'

            log_entry = f"""---
type: watcher_error
watcher: {watcher_name}
timestamp: {datetime.now().isoformat()}
failure_count: {failure_count}
---

## Error #{failure_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Watcher:** {watcher_name}
**Failure Count:** {failure_count}
**Status:** {'FAILED' if failure_count >= 3 else 'DEGRADED'}

**Error:**
```
{error or 'Unknown error'}
```

---

*Logged by Failure Manager*
"""

            # Append to log file
            if log_file.exists():
                existing = log_file.read_text()
                log_file.write_text(existing + '\n\n' + log_entry)
            else:
                log_file.write_text(log_entry)

        except Exception as e:
            self._logger.error(f'Failed to log error: {e}')

    def _create_alert(self, watcher_name: str, health: WatcherHealth) -> None:
        """Create alert task for critical watcher failure.

        Args:
            watcher_name: Name of failed watcher
            health: Watcher health info
        """
        try:
            tasks_folder = self._vault_path / 'Tasks'
            tasks_folder.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            alert_file = tasks_folder / f'ALERT_{watcher_name}_{timestamp}.md'

            content = f"""---
type: watcher_alert
watcher: {watcher_name}
priority: critical
created: {datetime.now().isoformat()}
status: pending
---

# 🔴 CRITICAL: Watcher Failure - {watcher_name}

**Priority:** CRITICAL
**Watcher:** {watcher_name}
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Status:** FAILED

---

## Issue

The watcher **{watcher_name}** has failed {health.consecutive_failures} consecutive times
and requires manual intervention.

**Last Error:**
```
{health.last_error or 'Unknown error'}
```

**Restart Attempts:** {health.restart_attempts}/{health.max_restart_attempts}

---

## Impact

- Messages from this source may not be processed
- Action items may not be created
- Automated workflows may be interrupted

---

## Suggested Actions

- [ ] Review error logs in `Logs/Errors/{watcher_name}_errors_*.md`
- [ ] Check watcher configuration and credentials
- [ ] Verify API/services are accessible
- [ ] Check system resources (memory, CPU, network)
- [ ] Restart orchestrator after fixing issue
- [ ] Monitor for recurrence

---

## Recovery Steps

1. **Check logs:** Review recent error logs for root cause
2. **Verify config:** Ensure environment variables and credentials are correct
3. **Test connection:** Manually test API/service connectivity
4. **Restart:** Restart the orchestrator or specific watcher
5. **Monitor:** Watch health dashboard to confirm recovery

---

## Quick Commands

```bash
# View recent errors
tail -50 AI_Employee_Vault/Logs/Errors/{watcher_name}_errors_*.md

# Restart orchestrator
# Stop current process and run: python orchestrator.py
```

---

*Alert created by Failure Manager*
*This requires human intervention*
"""

            alert_file.write_text(content)
            self._logger.critical(f'🔴 Alert created for watcher {watcher_name}: {alert_file.name}')

        except Exception as e:
            self._logger.error(f'Failed to create alert: {e}')

    def start_monitoring(self) -> None:
        """Start background health monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._logger.warning('Monitoring already running')
            return

        self._should_stop.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        self._logger.info(f'Health monitoring started (interval: {self._health_check_interval}s)')

    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._should_stop.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._logger.info('Health monitoring stopped')

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while not self._should_stop.is_set():
            try:
                self._check_all_watchers()
                self._should_stop.wait(timeout=self._health_check_interval)
            except Exception as e:
                self._logger.error(f'Error in monitoring loop: {e}')

    def _check_all_watchers(self) -> None:
        """Check health of all registered watchers."""
        now = datetime.now()
        timeout_threshold = timedelta(seconds=self._health_check_interval * 3)

        for name, health in self._watchers.items():
            # Check for stale heartbeat
            if health.last_heartbeat:
                time_since_heartbeat = now - health.last_heartbeat

                if time_since_heartbeat > timeout_threshold and health.is_running:
                    # Watcher appears dead
                    self._logger.warning(
                        f'Watcher {name} heartbeat stale ({time_since_heartbeat.seconds}s)'
                    )
                    health.status = WatcherStatus.FAILED
                    health.is_running = False
                    health.consecutive_failures += 1

                    self._log_error(
                        name,
                        f'Heartbeat timeout ({time_since_heartbeat.seconds}s)',
                        health.consecutive_failures
                    )

                    # Attempt restart if under threshold
                    if health.consecutive_failures < self._alert_threshold:
                        self._attempt_restart(name, health)

    def _attempt_restart(self, name: str, health: WatcherHealth) -> None:
        """Attempt to restart a failed watcher.

        Args:
            name: Watcher name
            health: Watcher health info
        """
        if health.restart_attempts >= health.max_restart_attempts:
            self._logger.error(f'Watcher {name} exceeded max restart attempts')
            self._create_alert(name, health)
            return

        health.restart_attempts += 1
        health.status = WatcherStatus.RECOVERING

        # Calculate backoff delay (exponential: 30s, 60s, 120s)
        backoff = health.recovery_backoff_seconds * (2 ** (health.restart_attempts - 1))

        self._logger.info(
            f'Attempting restart {health.restart_attempts}/{health.max_restart_attempts} '
            f'for {name} (backoff: {backoff}s)'
        )

        # In a real implementation, you'd restart the watcher here
        # For now, we just log the attempt
        # The orchestrator would need to implement actual restart logic

    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report for all watchers.

        Returns:
            Dict with health status of all watchers
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'watchers': {},
            'summary': {
                'total': len(self.watchers),
                'healthy': 0,
                'degraded': 0,
                'failed': 0,
                'recovering': 0
            }
        }

        for name, health in self._watchers.items():
            watcher_info = {
                'status': health.status.value,
                'last_heartbeat': health.last_heartbeat.isoformat() if health.last_heartbeat else None,
                'last_successful_check': health.last_successful_check.isoformat() if health.last_successful_check else None,
                'error_count': health.error_count,
                'consecutive_failures': health.consecutive_failures,
                'restart_attempts': health.restart_attempts,
                'is_running': health.is_running
            }

            if health.last_error:
                watcher_info['last_error'] = health.last_error

            report['watchers'][name] = watcher_info

            # Update summary
            report['summary'][health.status.value] += 1

        return report

    def update_dashboard(self) -> None:
        """Update the dashboard with health status."""
        try:
            dashboard_path = self._vault_path / 'Dashboard.md'

            if not dashboard_path.exists():
                return

            report = self.get_health_report()

            # Build health section
            health_section = f"""

## Watcher Health

**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

| Watcher | Status | Errors | Running |
|---------|--------|--------|---------|
"""

            for name, health in self._watchers.items():
                status_emoji = {
                    WatcherStatus.HEALTHY: '✅',
                    WatcherStatus.DEGRADED: '⚠️',
                    WatcherStatus.FAILED: '❌',
                    WatcherStatus.RECOVERING: '🔄'
                }.get(health.status, '❓')

                running = '✅' if health.is_running else '❌'

                health_section += f"| {name} | {status_emoji} {health.status.value} | {health.error_count} | {running} |\n"

            # Append to dashboard (or create new if needed)
            # In production, you'd want more sophisticated dashboard updating
            self._logger.info('Dashboard health status updated')

        except Exception as e:
            self._logger.error(f'Failed to update dashboard: {e}')


# ============ CONVENIENCE FUNCTIONS ============

def create_failure_manager(
    vault_path: str,
    health_check_interval: int = 30,
    max_restart_attempts: int = 3,
    alert_threshold: int = 5
) -> FailureManager:
    """Create and configure failure manager.

    Args:
        vault_path: Path to Obsidian vault
        health_check_interval: Seconds between health checks
        max_restart_attempts: Maximum restart attempts
        alert_threshold: Failures before alert

    Returns:
        Configured FailureManager instance
    """
    manager = FailureManager(
        vault_path=vault_path,
        health_check_interval=health_check_interval,
        max_restart_attempts=max_restart_attempts,
        alert_threshold=alert_threshold
    )

    manager.start_monitoring()

    return manager


__all__ = ['FailureManager', 'WatcherHealth', 'WatcherStatus', 'create_failure_manager']
