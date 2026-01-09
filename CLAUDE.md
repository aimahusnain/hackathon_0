# AI Employee System

## Project Overview
Automated watcher system that monitors Gmail and creates action items in an Obsidian vault.

## Vault Structure
```
AI_Employee_Vault/
├── Inbox/           # Initial email storage
├── Needs_Action/    # Emails requiring attention (EMAIL_*.md)
├── Done/            # Completed/archived items
```

## Available Skills (skills/__init__.py)
- `read_vault(filepath)` - Read file from vault
- `search_vault(query, folder)` - Search vault contents
- `get_vault_stats()` - Get vault statistics
- `list_inbox()` - List emails in Needs_Action
- `write_note(title, content, folder)` - Create note
- `create_task(title, description, priority)` - Create task
- `move_to_done(filepath)` - Move file to Done folder

## Key Components
- `gmail_watcher.py` - Monitors Gmail for unread emails
- `base_watcher.py` - Base watcher class
- `main.py` - Entry point for the system

## Environment Setup
Required in `.env`:
```
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
```

Read /AI_Employee_Vault/Company_Handbook.md