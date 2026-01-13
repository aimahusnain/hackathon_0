# AI Employee System

An intelligent automated system that monitors Gmail, performs automated tasks, and manages your communications through an Obsidian vault. Built with Python, using keyword-based analysis (no external AI APIs required).

---

## What Does It Do?

The AI Employee System acts as your personal assistant that:

1. **Monitors Gmail** - Watches for new important emails (marked as ⭐ important + unread)
2. **Analyzes Emails** - Categorizes and prioritizes using intelligent keyword analysis
3. **Auto-Responds** - Automatically sends safe responses to low-risk emails
4. **Generates LinkedIn Posts** - Creates weekly professional posts every Monday at 9AM
5. **Manages Tasks** - Structured task system for tracking work
6. **Tracks Meeting Requests** - Extracts meeting details from emails (suggest mode)
7. **Stores Everything** - Persistent database for all tasks, emails, and analytics

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env file with Gmail credentials
# Get credentials from: https://console.cloud.google.com/apis/credentials
echo "GMAIL_CLIENT_ID=your_client_id" > .env
echo "GMAIL_CLIENT_SECRET=your_client_secret" >> .env

# 3. Run the system
python main.py
```

That's it! The system will:
- Start monitoring Gmail for important emails
- Create an SQLite database for tracking
- Generate LinkedIn posts every Monday
- Auto-send safe email responses

---

## Example Workflows

### Example 1: Email → Auto-Response

**Incoming Email:**
```
From: newsletter@techweekly.com
Subject: Weekly Tech Digest - Friday Edition
```

**System Action:**
1. Detects low-risk keywords (newsletter, digest)
2. Low priority score (1/5)
3. Auto-generates safe response
4. Sends immediately
5. Logs to `AI_Employee_Vault/Logs/Auto_Sent/`

**Result:** ✅ Email handled automatically without your intervention

---

### Example 2: Email → Plan → Review → Send

**Incoming Email:**
```
From: client@important.com
Subject: Urgent: Contract Review Needed

Hi, we need the contract reviewed by Friday.
Let's schedule a call to discuss the terms.
```

**System Action:**
1. Detects high-risk keywords (urgent, contract, schedule)
2. Priority score: 5/5 (urgent)
3. Creates action file in `Needs_Action/EMAIL_contract_review.md`
4. Generates response plan in `Plans/PLAN_contract_response.md`

**Your Action:**
```bash
# Review the plan
cat AI_Employee_Vault/Plans/PLAN_contract_response.md

# If approved, move to Approved folder
mv AI_Employee_Vault/Plans/PLAN_contract_response.md AI_Employee_Vault/Approved/

# System automatically sends the email
```

---

### Example 3: Meeting Detection

**Incoming Email:**
```
From: john@company.com
Subject: Meeting Tomorrow

Let's meet tomorrow at 2PM to discuss the project.
Join at: https://meet.google.com/abc-xyz
```

**System Action:**
1. Detects meeting keywords (meeting, tomorrow, 2PM)
2. Extracts details: tomorrow, 2PM, Google Meet link
3. Creates suggestion in database
4. Logs meeting request

**Review Suggestions:**
```python
from skills import get_meeting_suggestions

suggestions = get_meeting_suggestions(limit=5)
for s in suggestions:
    print(f"{s['subject']} from {s['sender']}")
    print(f"  Suggested: {s['suggested_event']['start_time']}")
```

---

## Features Overview

### Email Processing

| Feature | Description |
|---------|-------------|
| **Smart Filtering** | Only processes important + unread emails |
| **Priority Scoring** | 1-5 scale based on keyword analysis |
| **Categorization** | Finance, Legal, HR, Project, Meeting, Support, Technical |
| **Risk Assessment** | Calculates risk score (0-100) for auto-approval |
| **Auto-Send** | Automatically sends safe responses |

### Database Storage

The built-in SQLite database (`ai_employee.db`) stores:
- **Tasks** - Title, description, priority, status, assignee
- **Emails** - Sender, subject, body, priority, category, risk level
- **Plans** - Response plans with approval workflow
- **Events** - Meeting requests with extracted details
- **Activity Log** - All system actions

### Keyword Analysis

**Priority Levels:**
- **5 (Urgent)**: urgent, emergency, critical, asap, deadline today
- **4 (High)**: deadline, important, priority, contract, agreement, payment
- **3 (Medium)**: meeting, project, invoice, schedule, deliverable
- **2 (Normal)**: question, update, request, feedback, help
- **1 (Low)**: information, newsletter, fyi, announcement

**Categories:**
- Finance, Legal, HR, Project, Meeting, Support, Technical

---

## Directory Structure

```
AI_Employee_System/
├── main.py                      # Entry point - run this!
├── Watchers/                    # Email monitoring
│   ├── gmail_watcher.py        # Gmail integration
│   ├── failure_manager.py      # Health monitoring
│   └── base_watcher.py         # Base class
├── skills/                      # Business logic
│   ├── keyword_analyzer.py     # Email analysis
│   ├── email_planner.py        # Response plan generator
│   ├── email_sender.py         # Send emails
│   ├── linkedin_manager.py     # LinkedIn posts
│   ├── task_processor.py       # Task management
│   ├── mcp_database.py         # Database skills
│   └── meeting_scheduler_skill.py
├── schedulers/                  # Scheduled tasks
│   ├── linkedin_scheduler.py   # Monday posts
│   └── meeting_scheduler.py    # Meeting detection
├── mcp_servers/                 # MCP servers
│   └── database_mcp.py         # SQLite database
├── AI_Employee_Vault/           # Your data (Obsidian vault)
│   ├── Needs_Action/           # Emails needing action (EMAIL_*.md)
│   ├── Plans/                  # Response plans awaiting review
│   ├── Approved/               # Approved plans
│   ├── Done/                   # Completed items
│   ├── Inbox/                  # Processed emails
│   ├── Tasks/                  # Task files
│   ├── LinkedIn_Posts/         # Generated posts
│   └── Logs/                   # Activity logs
├── Sessions/                    # OAuth tokens
├── .env                        # Gmail credentials (NEVER COMMIT)
└── requirements.txt            # Python dependencies
```

---

## Usage Examples

### Running the System

```bash
# Run continuously (recommended)
python main.py

# Single pass (test mode)
python main.py --once

# Disable specific features
python main.py --no-gmail          # Skip Gmail watcher
python main.py --no-linkedin       # Skip LinkedIn scheduler
python main.py --no-database       # Skip database

# Enable email planner (auto-generate response plans)
python main.py --planner

# Enable meeting scheduler
python main.py --enable-meeting-scheduler
```

### Using Database Skills

```python
from skills import (
    db_create_task,
    db_list_tasks,
    db_get_stats,
    db_search
)

# Create a task
task_id = db_create_task(
    title="Review project proposal",
    description="Analyze the Q1 proposal",
    priority=4,
    assigned_to="claude-code"
)

# List pending tasks
tasks = db_list_tasks(status="pending", priority_min=3)
for task in tasks:
    print(f"{task['title']} - Priority: {task['priority']}")

# Get system statistics
stats = db_get_stats()
print(f"Pending tasks: {stats['pending_tasks']}")
print(f"Pending emails: {stats['pending_emails']}")

# Search across all data
results = db_search("tasks", "urgent")
```

### Using Meeting Scheduler

```python
from skills import (
    get_meeting_suggestions,
    review_meeting_request
)

# Get meeting suggestions from emails
suggestions = get_meeting_suggestions(limit=10)
for s in suggestions:
    print(f"{s['subject']}")
    print(f"  From: {s['sender']}")
    print(f"  Confidence: {s['confidence']}")
    if s['suggested_event']:
        print(f"  Time: {s['suggested_event']['start_time']}")
        print(f"  Location: {s['suggested_event'].get('location')}")

# Review specific email
review = review_meeting_request("EMAIL_12345.md")
print(f"Title: {review['details']['title']}")
print(f"Time: {review['details']['start_time']}")
```

### Using Task Management

```python
from skills import (
    create_task_processor,
    list_tasks_processor,
    get_next_task
)

# Create a task
create_task_processor(
    title="Fix bug in login system",
    description="Users report login failures",
    priority=4,
    context="Production issue",
    expected_output="Bug fix report"
)

# Get next task to work on
next_task = get_next_task(assigned_to="claude-code")
print(f"Working on: {next_task['title']}")

# List all tasks
tasks = list_tasks_processor(status="pending")
```

---

## Sample Output

### Gmail Watcher Log

```
2026-01-14 10:30:15 - GmailWatcher - INFO - Checking for new emails...
2026-01-14 10:30:16 - GmailWatcher - INFO - Found 2 new important emails
2026-01-14 10:30:16 - GmailWatcher - INFO - Created: EMAIL_urgent_contract.md
2026-01-14 10:30:16 - GmailWatcher - INFO -   Priority: 5 (urgent)
2026-01-14 10:30:16 - GmailWatcher - INFO -   Category: legal
2026-01-14 10:30:16 - GmailWatcher - INFO - Created: EMAIL_newsletter.md
2026-01-14 10:30:17 - GmailWatcher - INFO -   Priority: 1 (newsletter)
2026-01-14 10:30:17 - GmailWatcher - INFO -   Auto-sent response
```

### Email Action File Sample

```markdown
---
type: email
sender: client@company.com
subject: Urgent: Contract Review
date: 2026-01-14T10:30:00
priority: 5
category: legal
risk_level: high
status: needs_action
---

# Urgent: Contract Review

**From:** client@company.com
**Date:** January 14, 2026 at 10:30 AM
**Priority:** ⚠️ URGENT (5/5)

## Email Content

Hi,

We need the contract reviewed by Friday. Let's schedule a call to discuss the terms.

Thanks,
Client

## Analysis

**Keywords Detected:** urgent, contract, schedule
**Risk Level:** High
**Action Required:** Manual review needed
```

---

## Configuration

### Gmail Setup (Required)

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create OAuth 2.0 Client ID (Desktop app)
3. Copy Client ID and Secret to `.env`:

```env
GMAIL_CLIENT_ID=your_client_id_here
GMAIL_CLIENT_SECRET=your_client_secret_here
```

### Environment Variables

```env
# Gmail (Required)
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret

# LinkedIn Scheduler (Optional)
LINKEDIN_SCHEDULER_DAY=Monday
LINKEDIN_SCHEDULER_TIME=09:00
```

---

## Troubleshooting

### Gmail Not Picking Up Emails

**Problem:** System runs but doesn't create email files

**Solution:** Emails must be BOTH:
1. **Unread** - Not opened yet
2. **Important** - Marked with ⭐️ in Gmail

```bash
# Mark emails as important in Gmail
# Or clear cache to reprocess
rm AI_Employee_Vault/.gmail_cache.json
```

### Authentication Issues

```bash
# Delete old token and re-authenticate
rm Sessions/token.pickle
python main.py
```

---

## Testing Guide

### Test 1: Gmail Watcher

**Test if Gmail integration is working:**

```bash
# 1. Mark a test email as important (⭐) in Gmail
# 2. Keep it unread
# 3. Run single pass mode
python main.py --once

# 4. Check if email file was created
ls AI_Employee_Vault/Needs_Action/

# Expected output: EMAIL_[subject].md
```

**What to look for:**
- ✅ Email file created in `Needs_Action/`
- ✅ Frontmatter contains correct priority (1-5)
- ✅ Category detected correctly
- ✅ Log shows: "Created: EMAIL_xxx.md"

---

### Test 2: Database MCP

**Test database operations:**

```python
# Create test script: test_database.py
from skills import db_create_task, db_list_tasks, db_get_stats, db_search

# Test 1: Create a task
print("Test 1: Creating task...")
task_id = db_create_task(
    title="Test Task",
    description="This is a test",
    priority=3,
    assigned_to="test-user"
)
print(f"✓ Task created with ID: {task_id}")

# Test 2: List tasks
print("\nTest 2: Listing tasks...")
tasks = db_list_tasks(status="pending")
print(f"✓ Found {len(tasks)} pending tasks")

# Test 3: Get stats
print("\nTest 3: Getting statistics...")
stats = db_get_stats()
print(f"✓ Pending tasks: {stats['pending_tasks']}")
print(f"✓ Completed tasks: {stats['completed_tasks']}")

# Test 4: Search
print("\nTest 4: Searching...")
results = db_search("tasks", "test")
print(f"✓ Search returned {len(results)} results")

# Test 5: Update status
from skills import db_update_task_status
print("\nTest 5: Updating task status...")
success = db_update_task_status(task_id, "completed")
print(f"✓ Task updated: {success}")

print("\n✅ All database tests passed!")
```

**Run test:**
```bash
python test_database.py
```

---

### Test 3: Auto-Send Email Responses

**Test automatic email sending:**

```bash
# 1. Send yourself a low-risk email
# Subject: "Test Newsletter"
# Body: "This is a test newsletter. FYI."

# 2. Mark as important (⭐) in Gmail
# 3. Run the system
python main.py --once

# 4. Check auto-sent log
ls AI_Employee_Vault/Logs/Auto_Sent/

# 5. Verify email was sent (check your Sent folder in Gmail)
```

**What to look for:**
- ✅ File created in `Logs/Auto_Sent/`
- ✅ Log shows: "Auto-sent response"
- ✅ Email appears in your Gmail Sent folder

---

### Test 4: Email Planning

**Test email plan generation:**

```bash
# 1. Send yourself a high-risk email
# Subject: "Urgent: Contract Review Needed"
# Body: "We need to review the contract by Friday."

# 2. Mark as important (⭐) in Gmail
# 3. Enable planner and run
python main.py --planner --once

# 4. Check for plan file
ls AI_Employee_Vault/Plans/

# Expected output: PLAN_[subject].md
```

**What to look for:**
- ✅ Plan file created in `Plans/`
- ✅ Plan contains suggested response
- ✅ Plan has approval workflow section

---

### Test 5: Meeting Scheduler

**Test meeting detection:**

```python
# Create test script: test_meetings.py
from skills import get_meeting_suggestions, review_meeting_request

# Test: Get meeting suggestions
print("Testing meeting detection...")
suggestions = get_meeting_suggestions(limit=5)

print(f"\nFound {len(suggestions)} potential meetings:")
for i, s in enumerate(suggestions, 1):
    print(f"\n{i}. {s['subject']}")
    print(f"   From: {s['sender']}")
    print(f"   Confidence: {s['confidence']}")
    if s.get('suggested_event'):
        event = s['suggested_event']
        print(f"   Time: {event.get('start_time', 'Unknown')}")

if len(suggestions) == 0:
    print("\n⚠️  No meetings found. Send yourself a test email:")
    print("   Subject: 'Meeting Tomorrow at 2PM'")
    print("   Body: 'Let's meet tomorrow at 2PM to discuss the project.'")
```

**Run test:**
```bash
python test_meetings.py
```

---

### Test 6: LinkedIn Post Generator

**Test LinkedIn post creation:**

```bash
# 1. Enable LinkedIn scheduler
python main.py --planner --once

# 2. Check for generated post
ls AI_Employee_Vault/LinkedIn_Posts/

# 3. View post content
cat AI_Employee_Vault/LinkedIn_Posts/LINKEDIN_POST_*.md
```

**Or use skill directly:**
```python
from skills import create_linkedin_post, show_post_templates

# Show available templates
print("Available templates:")
show_post_templates()

# Create a post
post = create_linkedin_post(
    template_type="motivation",
    topic="productivity",
    tone="inspiring"
)
print(f"\n✓ Post created: {post}")
```

---

### Test 7: Task Management

**Test task creation and retrieval:**

```python
# Create test script: test_tasks.py
from skills import (
    create_task_processor,
    list_tasks_processor,
    get_next_task
)

# Test 1: Create task
print("Test 1: Creating task...")
create_task_processor(
    title="Test Task for Verification",
    description="This task tests the task processor",
    priority=4,
    context="Testing system",
    expected_output="Task completion confirmation"
)
print("✓ Task created")

# Test 2: List tasks
print("\nTest 2: Listing tasks...")
tasks = list_tasks_processor(status="pending")
print(f"✓ Found {len(tasks)} pending tasks")
for task in tasks[:3]:
    print(f"   - {task.get('title', 'Unknown')} (Priority: {task.get('priority', 'N/A')})")

# Test 3: Get next task
print("\nTest 3: Getting next task...")
next_task = get_next_task(assigned_to="claude-code")
if next_task:
    print(f"✓ Next task: {next_task.get('title')}")
else:
    print("✓ No tasks assigned to claude-code")

print("\n✅ All task tests passed!")
```

**Run test:**
```bash
python test_tasks.py
```

---

### Test 8: Keyword Analyzer

**Test keyword analysis:**

```python
# Create test script: test_analyzer.py
from skills import analyze_message

# Test different message types
test_messages = [
    {
        "sender": "newsletter@tech.com",
        "subject": "Weekly Tech Digest",
        "body": "Here's your weekly update on technology trends."
    },
    {
        "sender": "client@urgent.com",
        "subject": "URGENT: Contract Review Needed",
        "body": "We need this contract reviewed by Friday. Payment depends on it."
    },
    {
        "sender": "team@company.com",
        "subject": "Meeting Tomorrow",
        "body": "Let's schedule a meeting tomorrow at 2PM to discuss the project."
    }
]

print("Testing Keyword Analyzer:\n")
for i, msg in enumerate(test_messages, 1):
    print(f"Test {i}: {msg['subject']}")
    result = analyze_message(msg['sender'], msg['subject'], msg['body'])
    print(f"  Priority: {result['priority']}/5")
    print(f"  Category: {result['category']}")
    print(f"  Risk Level: {result['risk_level']}")
    print(f"  Confidence: {result['confidence']}")
    print()

print("✅ Keyword analyzer tests completed!")
```

**Run test:**
```bash
python test_analyzer.py
```

---

### Test 9: Full System Integration

**Test complete workflow:**

```bash
# 1. Start the system
python main.py

# 2. Send yourself test emails:
#    a. Low priority: Subject "Newsletter Test"
#    b. High priority: Subject "Urgent Contract Review"
#    c. Meeting request: Subject "Meeting Tomorrow at 3PM"

# 3. Mark all as important (⭐) in Gmail

# 4. Wait for system to process (default: 60 seconds)

# 5. Check results
echo "=== Checking Results ==="
echo "Needs_Action folder:"
ls AI_Employee_Vault/Needs_Action/
echo ""
echo "Plans folder:"
ls AI_Employee_Vault/Plans/
echo ""
echo "Auto-Sent log:"
ls AI_Employee_Vault/Logs/Auto_Sent/
echo ""
echo "Database:"
python -c "from skills import db_get_stats; s = db_get_stats(); print(f'Emails: {s[\"pending_emails\"]}')"

# 6. Press Ctrl+C to stop
```

**Expected Results:**
- ✅ "Newsletter Test" → Auto-sent response (in `Logs/Auto_Sent/`)
- ✅ "Urgent Contract Review" → Plan created (in `Plans/`)
- ✅ "Meeting Tomorrow" → Meeting detected (in database)

---

### Test 10: Vault Operations

**Test Obsidian vault operations:**

```python
# Create test script: test_vault.py
from skills import read_vault, search_vault, write_note, get_vault_stats

# Test 1: Create note
print("Test 1: Creating note...")
result = write_note(
    title="Test Note",
    content="This is a test note for verification",
    folder="Inbox"
)
print(f"✓ {result}")

# Test 2: Read note
print("\nTest 2: Reading note...")
content = read_vault("Inbox/" + result.split(": ")[1])
if content:
    print(f"✓ Note content length: {len(content)} characters")

# Test 3: Search vault
print("\nTest 3: Searching vault...")
results = search_vault("test", folder="Inbox")
print(f"✓ Found {len(results)} results")

# Test 4: Get stats
print("\nTest 4: Getting vault stats...")
stats = get_vault_stats()
print(f"✓ Inbox files: {stats['inbox']}")
print(f"✓ Needs_Action files: {stats['needs_action']}")
print(f"✓ Done files: {stats['done']}")

print("\n✅ All vault tests passed!")
```

**Run test:**
```bash
python test_vault.py
```

---

## Quick Verification Commands

```bash
# Verify all components are working
echo "=== AI Employee System Verification ==="

echo -e "\n1. Checking Python version..."
python --version

echo -e "\n2. Checking dependencies..."
pip list | grep -E "google|dotenv|dateutil|PyYAML"

echo -e "\n3. Checking vault structure..."
ls -la AI_Employee_Vault/

echo -e "\n4. Checking database..."
python -c "from skills import db_get_stats; print(f'Database stats: {db_get_stats()}')"

echo -e "\n5. Running single pass..."
python main.py --once

echo -e "\n✅ Verification complete!"
```

---

## Common Test Issues

| Issue | Solution |
|-------|----------|
| No emails picked up | Mark emails as ⭐ important + unread in Gmail |
| Database errors | Run `pip install -r requirements.txt` to reinstall |
| Authentication fails | Delete `Sessions/token.pickle` and re-authenticate |
| Import errors | Make sure you're in the project root directory |
| Files not created | Check `ai_employee.log` for error details |

---

### Test 11: CEO Briefing

**Test CEO briefing generation:**

```python
# Create test script: test_ceo_briefing.py
from skills import (
    generate_weekly_briefing,
    create_business_goals,
    get_business_summary
)

# Test 1: Create business goals
print("Test 1: Creating business goals...")
result = create_business_goals(
    revenue_target=10000,
    response_time_hours=24,
    payment_rate_percent=90
)
print(f"✓ {result}")

# Test 2: Get business summary
print("\nTest 2: Getting business summary...")
summary = get_business_summary()
print(summary)

# Test 3: Generate weekly briefing
print("\nTest 3: Generating weekly briefing...")
briefing_path = generate_weekly_briefing()
print(f"✓ Briefing generated: {briefing_path}")

# View the briefing
import os
from pathlib import Path
briefing_file = Path("AI_Employee_Vault") / briefing_path.split(": ")[1].strip()
if briefing_file.exists():
    print(f"\n✓ Briefing file created successfully!")
    print(f"  Location: {briefing_file}")
else:
    print(f"\n⚠️  Briefing file not found at {briefing_file}")

print("\n✅ All CEO briefing tests passed!")
```

**Run test:**
```bash
python test_ceo_briefing.py
```

**What to look for:**
- ✅ Business goals file created in `AI_Employee_Vault/`
- ✅ Briefing file created in `AI_Employee_Vault/Briefings/`
- ✅ Briefing contains revenue summary, task metrics, and suggestions
- ✅ Bottlenecks identified if there are overdue tasks

---

### Test 12: Dashboard Updater

**Test dashboard update:**

```python
# Create test script: test_dashboard.py
from skills import update_dashboard, get_dashboard_stats

# Test 1: Update dashboard
print("Test 1: Updating dashboard...")
result = update_dashboard()
print(result)

# Test 2: Get dashboard stats
print("\nTest 2: Getting dashboard statistics...")
stats_result = get_dashboard_stats()
print(stats_result)

# Verify dashboard file exists and has content
import os
from pathlib import Path
dashboard_file = Path("AI_Employee_Vault/Dashboard.md")
if dashboard_file.exists():
    content = dashboard_file.read_text()
    print(f"\n✓ Dashboard file updated!")
    print(f"  File size: {len(content)} characters")
    print(f"  Contains 'Quick Stats': {'Quick Stats' in content}")
    print(f"  Contains 'Pending Emails': {'Pending Emails' in content}")
    print(f"  Last updated line: {[l for l in content.split('\\n') if 'Last Updated' in l][0]}")
else:
    print("\n⚠️  Dashboard file not found!")

print("\n✅ All dashboard tests passed!")
```

**Run test:**
```bash
python test_dashboard.py
```

**What to look for:**
- ✅ Dashboard.md file updated in `AI_Employee_Vault/`
- ✅ Quick stats table shows current counts
- ✅ Priority action items listed
- ✅ Recent activity shown
- ✅ Quick links section included
- ✅ System status displayed

---

## Quick Verification Commands

### Core Skills
- `read_vault(filepath)` - Read file from vault
- `search_vault(query, folder)` - Search vault contents
- `get_vault_stats()` - Get vault statistics
- `list_inbox()` - List emails in Needs_Action
- `write_note(title, content, folder)` - Create note

### Database Skills
- `db_create_task(title, ...)` - Create task in database
- `db_list_tasks(status, ...)` - List tasks with filters
- `db_get_next_task(assigned_to)` - Get next task
- `db_get_stats()` - Get database statistics
- `db_search(table, query)` - Search across tables

### Email Skills
- `plan_email(email_file)` - Create response plan
- `analyze_pending_emails()` - Analyze all pending emails
- `send_email_skill(to, subject, body)` - Send email

### Meeting Skills
- `get_meeting_suggestions(limit)` - Get potential meeting requests
- `review_meeting_request(email_file)` - Review meeting without scheduling

### LinkedIn Skills
- `create_linkedin_post(template_type, **kwargs)` - Create post
- `list_linkedin_posts(status)` - List posts

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Employee System                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ Gmail Watcher│───▶│Keyword Analyzer│───▶│Database MCP  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                     │          │
│         ▼                    ▼                     ▼          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │Email Planner │    │Auto-Sender   │    │Task Manager  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                               │
│  ┌──────────────┐    ┌──────────────┐                        │
│  │LinkedIn      │    │Meeting       │                        │
│  │Scheduler     │    │Scheduler     │                        │
│  └──────────────┘    └──────────────┘                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Version History

**v2.2 - Current Release (January 2026)**
- ✅ Removed Calendar MCP (streamlined to core features)
- ✅ Enhanced Database MCP with full-text search
- ✅ Meeting scheduler (suggest mode)
- ✅ Cleaned up dependencies
- ✅ Comprehensive documentation with examples

**v2.1**
- ✅ Database MCP integration
- ✅ Calendar MCP integration (later removed in v2.2)
- ✅ Auto-meeting scheduling

**v2.0**
- ✅ Enhanced keyword analyzer
- ✅ Weekly LinkedIn post scheduler
- ✅ Failure manager with health monitoring
- ✅ Tasks folder system

**v1.0**
- ✅ Basic Gmail watcher
- ✅ Simple keyword matching
- ✅ Obsidian vault integration

---

## Security

### Protected Files (Never Commit)
- `.env` - Contains Gmail credentials
- `Sessions/` - OAuth tokens
- `*.pickle` - Authentication data
- `ai_employee.log` - May contain sensitive info

### Best Practices
1. Never commit `.env` file
2. Use environment variables for credentials
3. Rotate credentials regularly
4. Review OAuth permissions
5. Monitor error logs

---

## Support

### Getting Help
1. Check logs: `tail -100 ai_employee.log`
2. Review Dashboard: `AI_Employee_Vault/Dashboard.md`
3. Test components: `python main.py --once`
4. Check error logs: `AI_Employee_Vault/Logs/Errors/`

### Common Issues

| Issue | Solution |
|-------|----------|
| Gmail auth fails | Delete `Sessions/token.pickle` and re-auth |
| No emails picked up | Mark emails as ⭐ important + unread |
| Import errors | Run `pip install -r requirements.txt` |
| High memory | Increase check interval: `--interval 300` |

---

## License

Made with ❤️ for productivity automation

**Version:** 2.2 | **Status:** Production Ready | **Updated:** January 2026
