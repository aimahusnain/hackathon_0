# AI Employee System

## Project Overview
Automated watcher system that monitors Gmail and creates action items in an Obsidian vault.

## Vault Structure
```
AI_Employee_Vault/
├── Inbox/           # Initial email storage
├── Needs_Action/    # Emails requiring attention (EMAIL_*.md)
├── Done/            # Completed/archived items
├── Plans/           # Strategy and planning documents
├── Logs/            # Activity logs
```

## Available Skills (skills/__init__.py)
- `read_vault(filepath)` - Read file from vault
- `search_vault(query, folder)` - Search vault contents
- `get_vault_stats()` - Get vault statistics
- `list_inbox()` - List emails in Needs_Action
- `write_note(title, content, folder)` - Create note
- `create_task(title, description, priority)` - Create task
- `move_to_done(filepath)` - Move file to Done folder
- `VaultUpdater` - Comprehensive vault update skill

## Key Components
- `gmail_watcher.py` - Monitors Gmail for unread important emails (uses VaultUpdater)
- `base_watcher.py` - Base watcher class
- `main.py` - Entry point for the system
- `skills/vault_update.py` - Vault update skill

## Environment Setup

### Gmail Authentication
The system uses OAuth2 credentials from `.env` file for Gmail authentication.

1. **Create `.env` file** in project root:
   ```env
   GMAIL_CLIENT_ID=your_client_id_here
   GMAIL_CLIENT_SECRET=your_client_secret_here
   ```

2. **Get credentials** from [Google Cloud Console](https://console.cloud.google.com/apis/credentials):
   - Create a new OAuth 2.0 Client ID
   - Application type: Desktop app
   - Copy Client ID and Client Secret to `.env`

3. **First run** will open browser for OAuth consent and save token to `token.pickle`

### Running the System
```bash
python main.py
```

Press `Ctrl+C` or `e` to stop the watchers.

Read /AI_Employee_Vault/Company_Handbook.md
