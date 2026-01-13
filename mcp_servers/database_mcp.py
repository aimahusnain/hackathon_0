"""
Database MCP Server
Provides SQLite database functionality for the AI Employee System
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

class DatabaseMCP:
    """Database MCP Server for AI Employee System"""

    def __init__(self, db_path: str = None):
        """Initialize database connection"""
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "..", "AI_Employee_Vault", "ai_employee.db")

        self.db_path = os.path.abspath(db_path)
        self.conn = None
        self.connect()
        self._create_tables()

    def connect(self):
        """Create database connection"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable dict-like access

    def _create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.conn.cursor()

        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                priority INTEGER DEFAULT 3,
                status TEXT DEFAULT 'pending',
                assigned_to TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                expected_output TEXT,
                context TEXT,
                metadata TEXT
            )
        """)

        # Emails table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT UNIQUE,
                sender TEXT,
                subject TEXT,
                body TEXT,
                received_at TIMESTAMP,
                priority INTEGER DEFAULT 3,
                category TEXT,
                risk_level TEXT DEFAULT 'low',
                status TEXT DEFAULT 'pending',
                action_file_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)

        # Plans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                email_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                executed_at TIMESTAMP,
                plan_file_path TEXT,
                metadata TEXT,
                FOREIGN KEY (email_id) REFERENCES emails(id)
            )
        """)

        # Events/Calendar table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                location TEXT,
                event_type TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email_id INTEGER,
                metadata TEXT,
                FOREIGN KEY (email_id) REFERENCES emails(id)
            )
        """)

        # Analytics/Activity log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id INTEGER,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    # ============ TASK OPERATIONS ============

    def create_task(self, title: str, description: str = None, priority: int = 3,
                    assigned_to: str = None, expected_output: str = None,
                    context: str = None, metadata: dict = None) -> int:
        """Create a new task"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (title, description, priority, assigned_to, expected_output, context, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, description, priority, assigned_to, expected_output, context,
              json.dumps(metadata) if metadata else None))
        self.conn.commit()
        self._log_activity("task_created", "task", cursor.lastrowid)
        return cursor.lastrowid

    def get_task(self, task_id: int) -> Optional[Dict]:
        """Get task by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_tasks(self, status: str = None, assigned_to: str = None,
                   priority_min: int = None, limit: int = None) -> List[Dict]:
        """List tasks with filters"""
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if assigned_to:
            query += " AND assigned_to = ?"
            params.append(assigned_to)
        if priority_min:
            query += " AND priority >= ?"
            params.append(priority_min)

        query += " ORDER BY priority DESC, created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def update_task_status(self, task_id: int, status: str) -> bool:
        """Update task status"""
        cursor = self.conn.cursor()
        update_data = {"status": status}
        if status == "completed":
            update_data["completed_at"] = datetime.now().isoformat()

        # Build dynamic update query
        set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
        values = list(update_data.values()) + [task_id]

        cursor.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        self.conn.commit()
        self._log_activity("task_updated", "task", task_id, f"Status: {status}")
        return cursor.rowcount > 0

    def get_next_task(self, assigned_to: str = None) -> Optional[Dict]:
        """Get next pending task by priority"""
        query = """
            SELECT * FROM tasks
            WHERE status = 'pending'
        """
        params = []

        if assigned_to:
            query += " AND assigned_to = ?"
            params.append(assigned_to)

        query += " ORDER BY priority DESC, created_at ASC LIMIT 1"

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    # ============ EMAIL OPERATIONS ============

    def create_email(self, email_id: str, sender: str, subject: str, body: str,
                     received_at: str, priority: int = 3, category: str = None,
                     risk_level: str = "low", action_file_path: str = None,
                     metadata: dict = None) -> int:
        """Create email record"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO emails (email_id, sender, subject, body, received_at, priority, category, risk_level, action_file_path, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (email_id, sender, subject, body, received_at, priority, category,
              risk_level, action_file_path, json.dumps(metadata) if metadata else None))
        self.conn.commit()
        self._log_activity("email_created", "email", cursor.lastrowid)
        return cursor.lastrowid

    def get_email(self, email_id: str) -> Optional[Dict]:
        """Get email by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM emails WHERE email_id = ?", (email_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_emails(self, status: str = None, category: str = None,
                    priority_min: int = None, limit: int = None) -> List[Dict]:
        """List emails with filters"""
        query = "SELECT * FROM emails WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if category:
            query += " AND category = ?"
            params.append(category)
        if priority_min:
            query += " AND priority >= ?"
            params.append(priority_min)

        query += " ORDER BY received_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def update_email_status(self, email_id: str, status: str) -> bool:
        """Update email status"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE emails SET status = ?, updated_at = ? WHERE email_id = ?",
                      (status, datetime.now().isoformat(), email_id))
        self.conn.commit()
        self._log_activity("email_updated", "email", email_id, f"Status: {status}")
        return cursor.rowcount > 0

    # ============ PLAN OPERATIONS ============

    def create_plan(self, title: str, description: str = None, email_id: int = None,
                    plan_file_path: str = None, metadata: dict = None) -> int:
        """Create a new plan"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO plans (title, description, email_id, plan_file_path, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (title, description, email_id, plan_file_path, json.dumps(metadata) if metadata else None))
        self.conn.commit()
        self._log_activity("plan_created", "plan", cursor.lastrowid)
        return cursor.lastrowid

    def update_plan_status(self, plan_id: int, status: str) -> bool:
        """Update plan status"""
        cursor = self.conn.cursor()
        update_data = {"status": status}
        if status == "approved":
            update_data["approved_at"] = datetime.now().isoformat()
        elif status == "executed":
            update_data["executed_at"] = datetime.now().isoformat()

        set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
        values = list(update_data.values()) + [plan_id]

        cursor.execute(f"UPDATE plans SET {set_clause} WHERE id = ?", values)
        self.conn.commit()
        self._log_activity("plan_updated", "plan", plan_id, f"Status: {status}")
        return cursor.rowcount > 0

    def list_plans(self, status: str = None, limit: int = None) -> List[Dict]:
        """List plans with filters"""
        query = "SELECT * FROM plans WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    # ============ EVENT/CALENDAR OPERATIONS ============

    def create_event(self, title: str, start_time: str, end_time: str = None,
                     description: str = None, location: str = None,
                     event_type: str = "meeting", email_id: int = None,
                     metadata: dict = None) -> int:
        """Create calendar event"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO events (title, start_time, end_time, description, location, event_type, email_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, start_time, end_time, description, location, event_type,
              email_id, json.dumps(metadata) if metadata else None))
        self.conn.commit()
        self._log_activity("event_created", "event", cursor.lastrowid)
        return cursor.lastrowid

    def list_events(self, status: str = None, start_after: str = None,
                    end_before: str = None, limit: int = None) -> List[Dict]:
        """List events with filters"""
        query = "SELECT * FROM events WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if start_after:
            query += " AND start_time > ?"
            params.append(start_after)
        if end_before:
            query += " AND end_time < ?"
            params.append(end_before)

        query += " ORDER BY start_time ASC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def update_event_status(self, event_id: int, status: str) -> bool:
        """Update event status"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE events SET status = ? WHERE id = ?", (status, event_id))
        self.conn.commit()
        self._log_activity("event_updated", "event", event_id, f"Status: {status}")
        return cursor.rowcount > 0

    # ============ ANALYTICS ============

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        cursor = self.conn.cursor()

        stats = {}

        # Task stats
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
        stats["pending_tasks"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
        stats["completed_tasks"] = cursor.fetchone()[0]

        # Email stats
        cursor.execute("SELECT COUNT(*) FROM emails WHERE status = 'pending'")
        stats["pending_emails"] = cursor.fetchone()[0]
        cursor.execute("SELECT category, COUNT(*) as count FROM emails GROUP BY category")
        stats["emails_by_category"] = dict(cursor.fetchall())

        # Plan stats
        cursor.execute("SELECT COUNT(*) FROM plans WHERE status = 'pending'")
        stats["pending_plans"] = cursor.fetchone()[0]

        # Recent activity
        cursor.execute("""
            SELECT action, entity_type, created_at
            FROM activity_log
            ORDER BY created_at DESC
            LIMIT 10
        """)
        stats["recent_activity"] = [dict(row) for row in cursor.fetchall()]

        return stats

    def search(self, table: str, query: str) -> List[Dict]:
        """Full-text search across specified table"""
        valid_tables = ["tasks", "emails", "plans", "events"]
        if table not in valid_tables:
            raise ValueError(f"Invalid table. Must be one of: {valid_tables}")

        # Search across text columns
        if table == "tasks":
            sql = """
                SELECT * FROM tasks
                WHERE title LIKE ? OR description LIKE ? OR context LIKE ?
                ORDER BY priority DESC, created_at DESC
            """
            pattern = f"%{query}%"
            cursor = self.conn.cursor()
            cursor.execute(sql, (pattern, pattern, pattern))

        elif table == "emails":
            sql = """
                SELECT * FROM emails
                WHERE subject LIKE ? OR body LIKE ? OR sender LIKE ?
                ORDER BY received_at DESC
            """
            pattern = f"%{query}%"
            cursor = self.conn.cursor()
            cursor.execute(sql, (pattern, pattern, pattern))

        else:
            sql = f"""
                SELECT * FROM {table}
                WHERE title LIKE ? OR description LIKE ?
                ORDER BY created_at DESC
            """
            pattern = f"%{query}%"
            cursor = self.conn.cursor()
            cursor.execute(sql, (pattern, pattern))

        return [dict(row) for row in cursor.fetchall()]

    # ============ UTILITY ============

    def _log_activity(self, action: str, entity_type: str, entity_id: int, details: str = None):
        """Log activity to database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO activity_log (action, entity_type, entity_id, details)
            VALUES (?, ?, ?, ?)
        """, (action, entity_type, entity_id, details))
        self.conn.commit()

    def export_to_json(self, table: str = None, output_path: str = None) -> str:
        """Export table(s) to JSON file"""
        if table:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT * FROM {table}")
            data = [dict(row) for row in cursor.fetchall()]
        else:
            # Export all tables
            data = {}
            for t in ["tasks", "emails", "plans", "events", "activity_log"]:
                cursor = self.conn.cursor()
                cursor.execute(f"SELECT * FROM {t}")
                data[t] = [dict(row) for row in cursor.fetchall()]

        if output_path is None:
            output_path = os.path.join(
                os.path.dirname(self.db_path),
                f"db_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


# ============ MCP SERVER INTERFACE ============

def start_server():
    """Start the MCP server (for external integration)"""
    # This would integrate with the MCP protocol
    # For now, we provide a Python API
    db = DatabaseMCP()
    print(f"Database MCP Server started at: {db.db_path}")
    return db


if __name__ == "__main__":
    # Test the database
    db = start_server()

    # Test: Create a task
    task_id = db.create_task(
        title="Test Task",
        description="This is a test task from MCP",
        priority=4,
        assigned_to="claude-code",
        context="Testing MCP integration"
    )
    print(f"Created task: {task_id}")

    # Test: Get task
    task = db.get_task(task_id)
    print(f"Retrieved task: {task}")

    # Test: Get stats
    stats = db.get_stats()
    print(f"Database stats: {stats}")

    db.close()
