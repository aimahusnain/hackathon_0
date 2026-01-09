# AI Employee Vault

An automated system that monitors Gmail and creates action items in an Obsidian vault for task management.

## How It Works

1. **Gmail Monitoring** - Watches your Gmail inbox for new unread emails at regular intervals (60 seconds by default)

2. **Authentication** - Uses OAuth2 flow with credentials from `.env` file:
   - First run: Opens browser for OAuth consent
   - Subsequent runs: Uses cached token (`token.pickle`)

3. **Email Processing** - For each new unread email:
   - Extracts sender, subject, date, and body
   - Creates a markdown file in the vault's `Inbox` folder
   - Marks email ID as processed to avoid duplicates

4. **Vault Structure** - Creates an Obsidian vault with organized folders:
   - `Inbox/` - New items from watchers
   - `Needs_Action/` - Items requiring attention
   - `Done/` - Completed items
   - `Pending_Approval/` - Items awaiting review
   - `Plans/` - Planning documents
   - `Logs/` - System logs

5. **Persistent Cache** - Maintains `.gmail_cache.json` to track processed email IDs across runs

## Setup

1. **Install Dependencies**
   ```bash
   uv sync
   ```

2. **Configure Gmail API**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a project and enable Gmail API
   - Create OAuth 2.0 credentials (Desktop app)
   - Copy Client ID and Client Secret

3. **Configure Environment Variables**
   - Create `.env` file in project root:
   ```bash
   GMAIL_CLIENT_ID=your_client_id_here
   GMAIL_CLIENT_SECRET=your_client_secret_here
   BANK_API_TOKEN=your_token
   WHATSAPP_SESSION_PATH=/secure/path/session
   ```

4. **Run the System**
   CURSOR:
   ```bash
   python main.py
   ```
   VSCOE:
   ```bash
   uv run python main.py
   ```
   Or with custom vault path:
   ```bash
   python main.py --vault /path/to/vault
   ```

5. **Stop the System**
   - Press `Ctrl+C` or press `e` key

## Project Structure

```
.
├── main.py              # Entry point, manages watcher threads
├── gmail_watcher.py     # Gmail monitoring implementation
├── base_watcher.py      # Base class for all watchers
├── skills/              # Additional skill modules
├── AI_Employee_Vault/   # Default Obsidian vault location
├── .env                 # Environment variables (Client ID/Secret)
├── token.pickle         # Cached OAuth token
└── .gmail_cache.json    # Processed email ID cache
```

## Dependencies

- `google-api-python-client` - Gmail API client
- `google-auth-oauthlib` - OAuth authentication
- `watchdog` - File system monitoring
- `pyyaml` - Configuration parsing
- `python-dotenv` - Environment variable loading
