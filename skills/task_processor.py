"""
Task Processor - Monitor and process Tasks folder for Claude Code

Watches the Tasks/ folder for new task files and provides a structured
way to provide tasks to Claude Code through markdown files.

Features:
- Monitor Tasks/ folder for new task files
- Parse task metadata
- Generate task summaries
- Update task status
- Track completion
"""

import logging
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class TaskStatus(Enum):
    """Task status values."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Task from Tasks/ folder."""
    filepath: Path
    title: str
    status: TaskStatus
    priority: int  # 1-5
    created: datetime
    assigned_to: str
    description: str
    context: str = ""
    expected_output: str = ""
    notes: str = ""
    completed_date: Optional[datetime] = None


class TaskProcessor:
    """
    Process tasks from Tasks/ folder.

    Provides functionality to read, update, and manage tasks
    created as markdown files in the vault.
    """

    def __init__(self, vault_path: str):
        """Initialize task processor.

        Args:
            vault_path: Path to Obsidian vault
        """
        self.vault_path = Path(vault_path)
        self.tasks_folder = self.vault_path / 'Tasks'
        self.tasks_folder.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger('TaskProcessor')

    def create_task(
        self,
        title: str,
        description: str,
        priority: int = 3,
        assigned_to: str = "claude-code",
        context: str = "",
        expected_output: str = ""
    ) -> Path:
        """Create a new task file.

        Args:
            title: Task title
            description: Detailed description
            priority: Priority level (1-5, default: 3)
            assigned_to: Who should handle the task
            context: Additional context
            expected_output: What success looks like

        Returns:
            Path to created task file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = re.sub(r'[^\w\s-]', '', title).replace(' ', '_')[:50]
        filename = f"TASK_{timestamp}_{safe_title}.md"
        filepath = self.tasks_folder / filename

        content = f"""---
type: task
status: pending
priority: {priority}
created: {datetime.now().isoformat()}
assigned_to: {assigned_to}
---

# {title}

**Status:** Pending
**Priority:** {priority}/5
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Assigned to:** {assigned_to}

---

## Description

{description}

---

## Context

{context if context else 'No additional context provided.'}

---

## Expected Output

{expected_output if expected_output else 'Task completed successfully.'}

---

## Progress

- [ ] Task started

---

## Notes

<!-- Add notes here as you work on the task -->

---

*Created by AI Employee System*
"""

        filepath.write_text(content, encoding='utf-8')
        self.logger.info(f'Task created: {filename}')

        return filepath

    def parse_task_file(self, filepath: Path) -> Optional[Task]:
        """Parse task file into Task object.

        Args:
            filepath: Path to task file

        Returns:
            Task object or None if parsing fails
        """
        try:
            content = filepath.read_text(encoding='utf-8')

            # Extract metadata from frontmatter
            metadata = {}
            if content.startswith('---'):
                frontmatter_end = content.find('---', 3)
                if frontmatter_end != -1:
                    frontmatter = content[3:frontmatter_end]
                    for line in frontmatter.strip().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            metadata[key.strip()] = value.strip()

            # Extract title from first # heading
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else filepath.stem

            # Extract sections
            description = self._extract_section(content, 'Description') or ''
            context = self._extract_section(content, 'Context') or ''
            expected_output = self._extract_section(content, 'Expected Output') or ''
            notes = self._extract_section(content, 'Notes') or ''

            # Parse status
            status_str = metadata.get('status', 'pending').lower()
            status_map = {
                'pending': TaskStatus.PENDING,
                'in_progress': TaskStatus.IN_PROGRESS,
                'completed': TaskStatus.COMPLETED,
                'blocked': TaskStatus.BLOCKED,
                'cancelled': TaskStatus.CANCELLED
            }
            status = status_map.get(status_str, TaskStatus.PENDING)

            # Parse priority
            priority = int(metadata.get('priority', 3))

            # Parse assigned_to
            assigned_to = metadata.get('assigned_to', 'claude-code')

            # Parse created date
            created_str = metadata.get('created', datetime.now().isoformat())
            created = datetime.fromisoformat(created_str)

            # Parse completed date if status is completed
            completed_date = None
            if status == TaskStatus.COMPLETED:
                completed_str = metadata.get('completed')
                if completed_str:
                    completed_date = datetime.fromisoformat(completed_str)

            return Task(
                filepath=filepath,
                title=title,
                status=status,
                priority=priority,
                created=created,
                assigned_to=assigned_to,
                description=description,
                context=context,
                expected_output=expected_output,
                notes=notes,
                completed_date=completed_date
            )

        except Exception as e:
            self.logger.error(f'Failed to parse task file {filepath}: {e}')
            return None

    def _extract_section(self, content: str, section_name: str) -> Optional[str]:
        """Extract a section from markdown content.

        Args:
            content: Markdown content
            section_name: Name of section to extract

        Returns:
            Section content or None
        """
        pattern = rf'## {section_name}\s*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        assigned_to: Optional[str] = None
    ) -> List[Task]:
        """List tasks with optional filtering.

        Args:
            status: Filter by status
            assigned_to: Filter by assignee

        Returns:
            List of tasks
        """
        tasks = []

        for task_file in self.tasks_folder.glob('TASK_*.md'):
            task = self.parse_task_file(task_file)
            if task:
                # Apply filters
                if status and task.status != status:
                    continue
                if assigned_to and task.assigned_to != assigned_to:
                    continue

                tasks.append(task)

        # Sort by priority (descending) and created date (ascending)
        tasks.sort(key=lambda t: (-t.priority, t.created))

        return tasks

    def update_task_status(
        self,
        filepath: Path,
        status: TaskStatus,
        notes: str = ""
    ) -> bool:
        """Update task status.

        Args:
            filepath: Path to task file
            status: New status
            notes: Optional notes to add

        Returns:
            True if successful
        """
        try:
            task = self.parse_task_file(filepath)
            if not task:
                return False

            content = filepath.read_text(encoding='utf-8')

            # Update status in frontmatter
            content = re.sub(
                r'status:\s*\w+',
                f'status: {status.value}',
                content
            )

            # Add completion date if completed
            if status == TaskStatus.COMPLETED:
                if 'completed:' not in content[:content.index('---', 3)]:
                    # Add completed field to frontmatter
                    content = re.sub(
                        r'created:.*',
                        f'created: {task.created.isoformat()}\ncompleted: {datetime.now().isoformat()}',
                        content,
                        count=1
                    )

            # Add notes if provided
            if notes:
                # Append to Notes section
                notes_section = f'\n\n{datetime.now().strftime("%Y-%m-%d %H:%M")}: {notes}'
                if '## Notes' in content:
                    # Insert before the end marker
                    content = content.replace(
                        '*Created by AI Employee System*',
                        f'{notes_section}\n\n---\n\n*Created by AI Employee System*'
                    )
                else:
                    # Add Notes section
                    content = content.replace(
                        '*Created by AI Employee System*',
                        f'## Notes\n\n{notes_section}\n\n---\n\n*Created by AI Employee System*'
                    )

            filepath.write_text(content, encoding='utf-8')
            self.logger.info(f'Task updated: {filepath.name} -> {status.value}')

            return True

        except Exception as e:
            self.logger.error(f'Failed to update task {filepath}: {e}')
            return False

    def get_task_summary(self) -> str:
        """Get summary of all tasks.

        Returns:
            Formatted summary
        """
        tasks = self.list_tasks()

        if not tasks:
            return "📋 No tasks in queue"

        # Count by status
        status_counts = {}
        for task in tasks:
            status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1

        # Build summary
        summary = f"📋 Task Summary ({len(tasks)} total)\n\n"

        summary += "**By Status:**\n"
        for status, count in sorted(status_counts.items()):
            emoji = {
                'pending': '⏳',
                'in_progress': '🔄',
                'completed': '✅',
                'blocked': '🚫',
                'cancelled': '❌'
            }.get(status, '📝')
            summary += f"  {emoji} {status.replace('_', ' ').title()}: {count}\n"

        # Priority tasks
        high_priority = [t for t in tasks if t.priority >= 4 and t.status != TaskStatus.COMPLETED]
        if high_priority:
            summary += f"\n**🔴 High Priority ({len(high_priority)}):**\n"
            for task in high_priority[:5]:
                summary += f"  - [{task.priority}/5] {task.title}\n"

        # Recent pending tasks
        pending = [t for t in tasks if t.status == TaskStatus.PENDING]
        if pending:
            summary += f"\n**⏳ Pending ({len(pending)}):**\n"
            for task in pending[:5]:
                summary += f"  - [{task.priority}/5] {task.title}\n"

        return summary

    def get_next_task(self, assigned_to: str = "claude-code") -> Optional[Task]:
        """Get the next task to work on.

        Args:
            assigned_to: Filter by assignee

        Returns:
            Next task or None
        """
        tasks = self.list_tasks(
            status=TaskStatus.PENDING,
            assigned_to=assigned_to
        )

        if tasks:
            # Return highest priority task
            return tasks[0]

        return None


# ============ SKILL FUNCTIONS ============

def create_task(
    title: str,
    description: str,
    priority: int = 3,
    assigned_to: str = "claude-code",
    context: str = "",
    expected_output: str = ""
) -> str:
    """Skill function: Create a new task.

    Args:
        title: Task title
        description: Detailed description
        priority: Priority level (1-5)
        assigned_to: Who should handle it
        context: Additional context
        expected_output: What success looks like

    Returns:
        Confirmation message
    """
    processor = TaskProcessor("./AI_Employee_Vault")
    filepath = processor.create_task(
        title=title,
        description=description,
        priority=priority,
        assigned_to=assigned_to,
        context=context,
        expected_output=expected_output
    )

    return f"✅ Task created: {filepath.name}"


def list_tasks(status: str = None, assigned_to: str = None) -> str:
    """Skill function: List tasks.

    Args:
        status: Filter by status
        assigned_to: Filter by assignee

    Returns:
        Formatted task list
    """
    processor = TaskProcessor("./AI_Employee_Vault")

    status_filter = TaskStatus(status) if status else None
    tasks = processor.list_tasks(status=status_filter, assigned_to=assigned_to)

    if not tasks:
        return f"📋 No tasks found"

    output = f"📋 Tasks ({len(tasks)})\n\n"

    for task in tasks:
        status_emoji = {
            TaskStatus.PENDING: '⏳',
            TaskStatus.IN_PROGRESS: '🔄',
            TaskStatus.COMPLETED: '✅',
            TaskStatus.BLOCKED: '🚫',
            TaskStatus.CANCELLED: '❌'
        }.get(task.status, '📝')

        output += f"{status_emoji} **{task.title}**\n"
        output += f"  Priority: {task.priority}/5\n"
        output += f"  Status: {task.status.value}\n"
        output += f"  Created: {task.created.strftime('%Y-%m-%d %H:%M')}\n"

        if task.description:
            desc_preview = task.description[:100] + '...' if len(task.description) > 100 else task.description
            output += f"  Description: {desc_preview}\n"

        output += f"  File: {task.filepath.name}\n\n"

    return output


def get_next_task(assigned_to: str = "claude-code") -> str:
    """Skill function: Get next task to work on.

    Args:
        assigned_to: Filter by assignee

    Returns:
        Next task details or empty message
    """
    processor = TaskProcessor("./AI_Employee_Vault")
    task = processor.get_next_task(assigned_to)

    if not task:
        return f"🎉 No pending tasks for {assigned_to}!"

    return f"""🎯 Next Task for {assigned_to}

**Title:** {task.title}
**Priority:** {task.priority}/5
**Created:** {task.created.strftime('%Y-%m-%d %H:%M')}

## Description

{task.description}

"""

__all__ = [
    'TaskProcessor',
    'Task',
    'TaskStatus',
    'create_task',
    'list_tasks',
    'get_next_task'
]
