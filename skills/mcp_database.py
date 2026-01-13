"""
Database MCP Integration Skills
Provides skill functions for database operations
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from mcp_servers.database_mcp import DatabaseMCP
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False


# Global database instance
_db_instance = None


def get_database():
    """Get or create database instance"""
    global _db_instance

    if not DATABASE_AVAILABLE:
        raise Exception("Database MCP not available")

    if _db_instance is None:
        _db_instance = DatabaseMCP()

    return _db_instance


# ============ TASK SKILLS ============

def db_create_task(title: str, description: str = None, priority: int = 3,
                   assigned_to: str = None, expected_output: str = None,
                   context: str = None, metadata: dict = None) -> int:
    """
    Create a new task in the database

    Args:
        title: Task title
        description: Task description
        priority: Priority level (1-5, default 3)
        assigned_to: Who is assigned (e.g., 'claude-code')
        expected_output: Expected output/deliverable
        context: Additional context
        metadata: Additional metadata as dict

    Returns:
        Task ID
    """
    db = get_database()
    return db.create_task(
        title=title,
        description=description,
        priority=priority,
        assigned_to=assigned_to,
        expected_output=expected_output,
        context=context,
        metadata=metadata
    )


def db_get_task(task_id: int) -> dict:
    """Get task by ID"""
    db = get_database()
    return db.get_task(task_id)


def db_list_tasks(status: str = None, assigned_to: str = None,
                  priority_min: int = None, limit: int = None) -> list:
    """
    List tasks with optional filters

    Args:
        status: Filter by status (pending, completed, etc.)
        assigned_to: Filter by assignee
        priority_min: Minimum priority level
        limit: Maximum number of results

    Returns:
        List of task dictionaries
    """
    db = get_database()
    return db.list_tasks(status=status, assigned_to=assigned_to,
                        priority_min=priority_min, limit=limit)


def db_get_next_task(assigned_to: str = None) -> dict:
    """
    Get next pending task by priority

    Args:
        assigned_to: Filter by assignee

    Returns:
        Task dictionary or None
    """
    db = get_database()
    return db.get_next_task(assigned_to=assigned_to)


def db_update_task_status(task_id: int, status: str) -> bool:
    """
    Update task status

    Args:
        task_id: Task ID
        status: New status (pending, completed, etc.)

    Returns:
        True if successful
    """
    db = get_database()
    return db.update_task_status(task_id, status)


# ============ EMAIL SKILLS ============

def db_create_email(email_id: str, sender: str, subject: str, body: str,
                    received_at: str, priority: int = 3, category: str = None,
                    risk_level: str = "low", action_file_path: str = None,
                    metadata: dict = None) -> int:
    """
    Create email record in database

    Args:
        email_id: Unique email identifier (Gmail message ID)
        sender: Sender email address
        subject: Email subject
        body: Email body content
        received_at: ISO datetime string
        priority: Priority level (1-5)
        category: Email category
        risk_level: Risk assessment (low, medium, high)
        action_file_path: Path to action file
        metadata: Additional metadata

    Returns:
        Database record ID
    """
    db = get_database()
    return db.create_email(
        email_id=email_id,
        sender=sender,
        subject=subject,
        body=body,
        received_at=received_at,
        priority=priority,
        category=category,
        risk_level=risk_level,
        action_file_path=action_file_path,
        metadata=metadata
    )


def db_get_email(email_id: str) -> dict:
    """Get email by ID"""
    db = get_database()
    return db.get_email(email_id)


def db_list_emails(status: str = None, category: str = None,
                   priority_min: int = None, limit: int = None) -> list:
    """
    List emails with optional filters

    Args:
        status: Filter by status
        category: Filter by category
        priority_min: Minimum priority level
        limit: Maximum number of results

    Returns:
        List of email dictionaries
    """
    db = get_database()
    return db.list_emails(status=status, category=category,
                         priority_min=priority_min, limit=limit)


def db_update_email_status(email_id: str, status: str) -> bool:
    """Update email status"""
    db = get_database()
    return db.update_email_status(email_id, status)


# ============ PLAN SKILLS ============

def db_create_plan(title: str, description: str = None, email_id: int = None,
                   plan_file_path: str = None, metadata: dict = None) -> int:
    """Create a new plan"""
    db = get_database()
    return db.create_plan(
        title=title,
        description=description,
        email_id=email_id,
        plan_file_path=plan_file_path,
        metadata=metadata
    )


def db_update_plan_status(plan_id: int, status: str) -> bool:
    """
    Update plan status

    Args:
        plan_id: Plan ID
        status: New status (pending, approved, executed, etc.)

    Returns:
        True if successful
    """
    db = get_database()
    return db.update_plan_status(plan_id, status)


def db_list_plans(status: str = None, limit: int = None) -> list:
    """List plans with optional filters"""
    db = get_database()
    return db.list_plans(status=status, limit=limit)


# ============ EVENT SKILLS ============

def db_create_event(title: str, start_time: str, end_time: str = None,
                    description: str = None, location: str = None,
                    event_type: str = "meeting", email_id: int = None,
                    metadata: dict = None) -> int:
    """
    Create calendar event in database

    Args:
        title: Event title
        start_time: Start time (ISO datetime string)
        end_time: End time (ISO datetime string)
        description: Event description
        location: Event location
        event_type: Type of event
        email_id: Associated email ID
        metadata: Additional metadata

    Returns:
        Event ID
    """
    db = get_database()
    return db.create_event(
        title=title,
        start_time=start_time,
        end_time=end_time,
        description=description,
        location=location,
        event_type=event_type,
        email_id=email_id,
        metadata=metadata
    )


def db_list_events(status: str = None, start_after: str = None,
                   end_before: str = None, limit: int = None) -> list:
    """List events with optional filters"""
    db = get_database()
    return db.list_events(status=status, start_after=start_after,
                         end_before=end_before, limit=limit)


# ============ ANALYTICS SKILLS ============

def db_get_stats() -> dict:
    """
    Get database statistics

    Returns:
        Dictionary with stats including:
        - pending_tasks: Number of pending tasks
        - completed_tasks: Number of completed tasks
        - pending_emails: Number of pending emails
        - emails_by_category: Emails grouped by category
        - pending_plans: Number of pending plans
        - recent_activity: Recent activity log
    """
    db = get_database()
    return db.get_stats()


def db_search(table: str, query: str) -> list:
    """
    Search across a table

    Args:
        table: Table name (tasks, emails, plans, events)
        query: Search query string

    Returns:
        List of matching records
    """
    db = get_database()
    return db.search(table=table, query=query)


def db_export_to_json(table: str = None, output_path: str = None) -> str:
    """
    Export database to JSON file

    Args:
        table: Specific table to export, or None for all tables
        output_path: Output file path (auto-generated if None)

    Returns:
        Path to exported JSON file
    """
    db = get_database()
    return db.export_to_json(table=table, output_path=output_path)


# ============ UTILITY SKILLS ============

def db_sync_tasks_from_vault() -> dict:
    """
    Sync tasks from Tasks/ folder to database

    Returns:
        Sync statistics
    """
    import os
    import re
    import json

    vault_path = os.path.join(os.path.dirname(__file__), "..", "AI_Employee_Vault", "Tasks")

    if not os.path.exists(vault_path):
        return {"status": "error", "message": "Tasks folder not found"}

    db = get_database()
    synced = 0
    skipped = 0

    for filename in os.listdir(vault_path):
        if not filename.endswith('.md'):
            continue

        filepath = os.path.join(vault_path, filename)

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse frontmatter
        frontmatter = {}
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 2:
                try:
                    for line in parts[1].strip().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            frontmatter[key.strip()] = value.strip().strip('"\'')
                except:
                    pass

        # Extract title from filename or frontmatter
        title = frontmatter.get('title') or filename.replace('.md', '')
        description = frontmatter.get('description') or parts[2] if len(parts) >= 3 else None
        priority = int(frontmatter.get('priority', 3))
        status = frontmatter.get('status', 'pending')
        assigned_to = frontmatter.get('assigned_to')

        # Create task in database
        try:
            db.create_task(
                title=title,
                description=description,
                priority=priority,
                assigned_to=assigned_to,
                context=f"Synced from {filename}"
            )
            synced += 1
        except:
            skipped += 1

    return {
        "status": "success",
        "synced": synced,
        "skipped": skipped
    }


def db_close():
    """Close database connection"""
    global _db_instance
    if _db_instance:
        _db_instance.close()
        _db_instance = None


if __name__ == "__main__":
    # Test database skills
    print("Testing Database MCP Skills...")

    # Create a test task
    task_id = db_create_task(
        title="Test Database Task",
        description="Testing MCP integration",
        priority=4,
        assigned_to="claude-code"
    )
    print(f"Created task: {task_id}")

    # List tasks
    tasks = db_list_tasks(status="pending", limit=5)
    print(f"Pending tasks: {len(tasks)}")

    # Get stats
    stats = db_get_stats()
    print(f"Stats: {stats}")

    db_close()
    print("Database MCP Skills test complete!")
