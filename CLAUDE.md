# AI Employee System

## Project Overview
An intelligent automated system that monitors Gmail and performs automated tasks including:
- Email monitoring and intelligent analysis
- Message tracking and action item generation
- Weekly LinkedIn post generation
- Task management for Claude Code
- **Automatic meeting scheduling from emails**
- Database and Calendar MCP integration
- Health monitoring and auto-recovery

## Architecture

### Main Entry Point: `main.py`
**This is the primary way to run the system.** main.py coordinates all watchers and schedulers.

**Features:**
- Manages multiple watchers in separate threads
- Includes failure management and health monitoring
- Coordinates schedulers (LinkedIn, etc.)
- Provides comprehensive system status
- UTF-8 encoding support for Windows/Mac/Linux

### Vault Structure
```
AI_Employee_Vault/
├── Inbox/              # Completed items moved from Needs_Action
├── Needs_Action/       # Actionable items requiring attention (EMAIL_*.md)
├── Plans/              # Strategy and planning documents awaiting review
├── Approved/           # Approved plans ready to execute
├── Rejected/           # Rejected plans
├── Done/               # Completed/archived items
├── Logs/               # Activity logs
│   ├── Auto_Sent/      # Auto-sent email logs
│   └── Errors/         # Watcher failure logs
├── LinkedIn_Posts/     # Generated LinkedIn posts (one per post)
├── Tasks/              # Tasks for Claude Code
├── Company_Handbook.md # System rules and context
└── Dashboard.md        # Quick overview and health status
```

## Core Components

### Watchers (Watchers/)
- **`gmail_watcher.py`** - Monitors Gmail for new important emails (unread + marked important) using enhanced keyword analysis
- **`base_watcher.py`** - Abstract base class for all watchers
- **`failure_manager.py`** - Health monitoring and auto-restart for all watchers

### Schedulers (schedulers/)
- **`linkedin_scheduler.py`** - Generates weekly LinkedIn posts every Monday at 9AM
- **`meeting_scheduler.py`** - Automatically detects meeting requests in emails and schedules them in Google Calendar

### MCP Servers (mcp_servers/)
- **`database_mcp.py`** - SQLite database for persistent storage (tasks, emails, plans, events)
- **`calendar_mcp.py`** - Google Calendar API integration for event management

### Skills (skills/)
- **`keyword_analyzer.py`** - Advanced keyword-based message analysis (replaces GLM API)
- **`task_processor.py`** - Process and manage Tasks folder for Claude Code
- **`email_planner.py`** - Generate response plans for emails
- **`email_sender.py`** - Send emails and log responses
- **`approved_plan_executor.py`** - Execute approved email plans
- **`email_to_inbox.py`** - Move emails to Inbox when plans complete
- **`linkedin_manager.py`** - Create and manage LinkedIn posts
- **`vault_update.py`** - Vault update utilities
- **`ceo_briefing.py`** - Generate business briefings
- **`mcp_database.py`** - Database MCP skill functions
- **`mcp_calendar.py`** - Calendar MCP skill functions
- **`meeting_scheduler_skill.py`** - Meeting scheduler skill functions

## Available Skills (from skills/__init__.py)

### Core Skills
- `read_vault(filepath)` - Read file from vault
- `search_vault(query, folder)` - Search vault contents
- `get_vault_stats()` - Get vault statistics
- `list_inbox()` - List emails in Needs_Action
- `write_note(title, content, folder)` - Create note
- `create_task(title, description, priority)` - Create task
- `move_to_done(filepath)` - Move file to Done folder

### New Skills
- `analyze_message(sender, subject, body)` - Analyze message using keyword analyzer
- `create_task_processor(title, description, ...)` - Create task in Tasks/ folder
- `list_tasks_processor(status, assigned_to)` - List tasks with filters
- `get_next_task(assigned_to)` - Get next task to work on

### Email Skills
- `plan_email(email_file)` - Create email response plan
- `analyze_pending_emails()` - Analyze all pending emails
- `send_email_skill(to, subject, body)` - Send email

### LinkedIn Skills
- `create_linkedin_post(template_type, **kwargs)` - Create LinkedIn post
- `list_linkedin_posts(status)` - List posts
- `show_post_templates()` - Show available templates

### Database MCP Skills
- `db_create_task(title, description, ...)` - Create task in database
- `db_list_tasks(status, assigned_to, ...)` - List tasks with filters
- `db_get_next_task(assigned_to)` - Get next pending task
- `db_create_email(email_id, sender, ...)` - Store email in database
- `db_list_emails(status, category, ...)` - List emails with filters
- `db_get_stats()` - Get database statistics
- `db_search(table, query)` - Search across tables

### Calendar MCP Skills
- `cal_create_event(title, start_time, ...)` - Create calendar event
- `cal_list_events(start_date, end_date, ...)` - List calendar events
- `cal_schedule_meeting(title, duration, ...)` - Smart scheduling
- `cal_find_free_slots(date, duration)` - Find available time
- `cal_get_calendar_stats(days)` - Get calendar statistics

### Meeting Scheduler Skills
- `schedule_meeting_from_email(email_file, auto_schedule)` - Schedule meeting from email
- `get_meeting_suggestions(limit)` - Get potential meeting requests
- `schedule_all_meetings(auto_schedule)` - Schedule all detected meetings
- `review_meeting_request(email_file)` - Review meeting without scheduling

## Environment Setup

### 1. Gmail Authentication
Create `.env` file in project root:
```env
# Gmail OAuth (Required)
GMAIL_CLIENT_ID=your_client_id_here
GMAIL_CLIENT_SECRET=your_client_secret_here
```

Get credentials from [Google Cloud Console](https://console.cloud.google.com/apis/credentials):
- Create OAuth 2.0 Client ID (Desktop app)
- Copy Client ID and Secret to `.env`

### 2. LinkedIn Scheduler Configuration (Optional)
```env
# LinkedIn Scheduler (Optional)
LINKEDIN_SCHEDULER_DAY=Monday
LINKEDIN_SCHEDULER_TIME=09:00
```

## Running the System

### Recommended: Continuous Mode
```bash
python main.py
```
This runs all watchers continuously with health monitoring.

### Single Pass Mode
```bash
python main.py --once
```
Checks for new items once and exits.

### Disable Specific Watchers
```bash
python main.py --no-gmail            # Disable Gmail
python main.py --no-linkedin         # Disable LinkedIn scheduler
```

### Enable Email Planner
```bash
python main.py --planner
```
Enables automatic email planning every 30 minutes.

### Custom Check Interval
```bash
python main.py --interval 120  # Check every 2 minutes
```

### Enable Calendar and Meeting Scheduler
```bash
# Calendar MCP is enabled by default - just run:
python main.py

# Disable Calendar MCP if needed
python main.py --no-calendar

# Enable Meeting Scheduler (suggest mode)
python main.py --enable-meeting-scheduler

# Enable Meeting Scheduler (auto-schedule mode)
python main.py --enable-meeting-scheduler --auto-schedule-meetings
```

## Key Features

### 1. Enhanced Keyword Analysis (No GLM Required)
The system uses sophisticated keyword-based analysis:
- Priority scoring (1-5 scale)
- Category detection (finance, legal, hr, project, etc.)
- Risk assessment with multiple factors
- Actionable item extraction
- Auto-approval logic for safe responses
- Confidence scoring

### 2. Auto-Send Email Responses
Automatically sends safe responses to low-risk emails:
- Keyword analysis determines if response is safe
- Low-risk emails sent immediately
- Plan created and moved to Done/ with metadata
- High-risk emails require manual review

### 3. Weekly LinkedIn Posts
Automatically generates professional LinkedIn posts every Monday at 9AM:
- Topics: Monday Motivation, Industry Insights, Leadership Lessons, etc.
- Saves to `LinkedIn_Posts/` folder for review
- Rotates through different post types
- No manual intervention required

### 4. Email Plan Approval Workflow
Review and approve email responses before sending:
- Plan created in `Plans/` folder
- Review suggested reply
- Move to `Approved/` to execute
- System sends email automatically
- Plan and email moved to `Done/` and `Inbox/`

### 5. Tasks Folder System
Create tasks for Claude Code by writing markdown files:
```bash
# Via skill function
create_task_processor(
    title="Review project proposal",
    description="Analyze the proposal and provide feedback",
    priority=4,
    context="Client sent this yesterday",
    expected_output="Detailed feedback document"
)
```

Or create markdown files manually in `AI_Employee_Vault/Tasks/`:
```markdown
---
type: task
status: pending
priority: 4
created: 2024-01-13T10:00:00
assigned_to: claude-code
---

# Task Title

**Description:** ...

**Context:** ...

**Expected Output:** ...
```

### 6. Automatic Meeting Scheduler
Automatically detects meeting requests in emails and schedules them in Google Calendar:

**Features:**
- Smart detection using meeting keywords (meeting, call, zoom, teams, etc.)
- Extracts dates and times from various formats
- Detects meeting links (Google Meet, Zoom, Teams)
- Two modes: Suggest (review first) or Auto-schedule (create immediately)

**Usage:**
```python
# Get meeting suggestions
from skills import get_meeting_suggestions
suggestions = get_meeting_suggestions(limit=10)

# Schedule a meeting from email
from skills import schedule_meeting_from_email
result = schedule_meeting_from_email("EMAIL_12345.md", auto_schedule=True)

# Schedule all detected meetings
from skills import schedule_all_meetings
result = schedule_all_meetings(auto_schedule=True)
```

### 7. Failure Manager
Monitors all watchers and:
- Tracks health status
- Auto-restarts failed watchers
- Logs errors to `Logs/Errors/`
- Creates alerts for critical failures
- Updates dashboard with status

## System Status & Monitoring

### Dashboard
Check `AI_Employee_Vault/Dashboard.md` for:
- Watcher health status
- Recent activity
- Quick links to important folders
- Task summaries

### Health Reports
The system automatically generates health reports showing:
- Watcher status (healthy/degraded/failed)
- Error counts
- Last successful check times
- Restart attempts

### Error Logs
All watcher failures are logged to `AI_Employee_Vault/Logs/Errors/`:
- `GmailWatcher_errors_YYYYMMDD.md`

## Workflow Examples

### Email Workflow
1. Gmail watcher detects new important email
2. Keyword analyzer categorizes and prioritizes
3. Action file created in `Needs_Action/`
4. System creates response plan
5. If low-risk: Auto-sends response immediately
6. If needs review: Plan saved to `Plans/` folder
7. You review and move plan to `Approved/`
8. System executes approved plan and sends email
9. Email and plan move to `Done/` and `Inbox/`

### LinkedIn Post Workflow
1. Monday 9AM: LinkedIn scheduler generates post
2. Post saved to `LinkedIn_Posts/`
3. Review and edit if needed
4. Post to LinkedIn (manual or via skill)
5. Track engagement in post file

### Task Workflow
1. Create task in `Tasks/` folder
2. Task processor monitors folder
3. Claude Code picks up next task
4. Complete task and update status
5. Mark as completed

## Troubleshooting

### Gmail Not Picking Up Emails

**Issue:** System runs but doesn't create .md files in Needs_Action

**Requirements:** Emails must be BOTH:
1. **Unread** - Not opened yet
2. **Important** - Marked with ⭐️ star in Gmail

**Solutions:**
1. **Mark emails as IMPORTANT** - Click the ⭐️ star in Gmail
2. **Check time window** - By default, only processes emails from last 7 days
   - Edit `Watchers/gmail_watcher.py` line 73 to extend:
   ```python
   self._cutoff_date = datetime.now() - timedelta(days=7)  # 7 days
   ```
3. **Clear processed cache:**
   ```bash
   rm AI_Employee_Vault/.gmail_cache.json
   ```
4. **Test with single pass:**
   ```bash
   python main.py --once
   ```

### Windows Encoding Errors (Fixed in v2.1)

**Issue:** "charmap codec can't encode character" when processing emails with emoji

**Status:** ✅ Fixed
- Windows console now uses UTF-8 encoding
- Emoji characters display correctly
- All file writes use UTF-8 encoding

### Gmail Authentication Issues
- Ensure Client ID and Secret are correct in `.env`
- First run will open browser for OAuth consent
- Token saved to `Sessions/token.pickle`
- If issues arise, delete token and re-authenticate

### Watchers Not Starting
- Check `ai_employee.log` for errors
- Verify all dependencies installed: `pip install -r requirements.txt`
- Ensure vault structure exists
- Check for port conflicts

### High Memory Usage
- Reduce check interval: `--interval 120`
- Disable unused watchers: `--no-linkedin`
- Run in single-pass mode: `--once`

## Development

### Project Structure
```
AI_Employee_System/
├── Watchers/           # Watcher implementations
├── skills/             # Skills and business logic
├── schedulers/         # Scheduled task runners
├── main.py             # Main entry point
├── AI_Employee_Vault/  # Obsidian vault
└── .env                # Environment variables
```

### Adding New Watchers
1. Extend `BaseWatcher` class
2. Implement `check_for_updates()` and `create_action_file()`
3. Add to main.py initialization
4. Register with failure manager

### Adding New Skills
1. Create skill function in `skills/`
2. Import in `skills/__init__.py`
3. Add to `__all__` list
4. Document in this file

## Best Practices

1. **Always use main.py** - It's the production entry point
2. **Monitor health dashboard** - Check Dashboard.md regularly
3. **Review auto-generated content** - Always review posts and responses
4. **Keep .env secure** - Never commit credentials
5. **Test changes** - Use `--once` flag before continuous mode
6. **Check error logs** - Review Logs/Errors/ regularly
7. **Update Company_Handbook.md** - Add custom keywords and rules

## Migration from Old System

### Changed Components
- ❌ GLM API → ✅ Enhanced keyword analyzer
- ❌ Gmail query: `is:unread` → ✅ `is:unread is:important` (only important emails)

### New Components (v2.1)
- ✅ Failure manager with health monitoring
- ✅ LinkedIn scheduler
- ✅ Task processor
- ✅ Keyword analyzer
- ✅ Auto-send email responses
- ✅ Email plan approval workflow
- ✅ Automatic email move to Inbox

### Recent Fixes (v2.1)
- ✅ Windows UTF-8 encoding support
- ✅ Fixed failure manager heartbeat tracking
- ✅ Auto-send safe email responses
- ✅ Email plan approval workflow (Plans/ → Approved/ → Done/)
- ✅ Automatic email move to Inbox when plans complete
- ✅ Improved error handling

Read /AI_Employee_Vault/Company_Handbook.md for system-specific rules and context.

---

**Version:** 2.1 | **Last Updated:** January 2026
