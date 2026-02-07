# PubMed Slack Bot

A bot that monitors PubMed daily for new publications by any list of authors and posts announcements to Slack with author tagging. It runs for free using GitHub Actions on a daily schedule—no servers required. Use it to track your research group, collaborators, or any set of authors you're interested in.

## Features

- Fetches author list from a Google Sheet (supports name variants and institutional affiliations)
- Queries PubMed for recent publications using NCBI E-utilities
- Posts formatted announcements to Slack with author mentions
- Tracks posted papers to avoid duplicates
- Runs automatically via GitHub Actions (daily schedule)

## Create Your Own Instance

Follow this guide to set up your own PubMed Slack bot. You can track any set of authors — your research group, collaborators, or anyone whose publications you want to follow. The entire process uses free tiers of GitHub Actions, Google Sheets, and the PubMed API.

### What You'll Need

- A GitHub account
- A Slack workspace where you have permission to add apps
- A Google account (for Google Sheets and a service account)
- Python 3.11+ (for local testing only; not needed if you only run via GitHub Actions)

### Step 1: Fork or Copy This Repository

**Option A: Fork (recommended if you want to receive upstream updates)**

1. Click the **Fork** button at the top-right of this repository
2. This creates a copy under your GitHub account

**Option B: Use as a template (recommended for a clean start)**

1. Click **Use this template** > **Create a new repository** (if available), or:
2. Create a new repository on GitHub, clone this repo locally, and push it to your new repo:

```bash
git clone https://github.com/ORIGINAL_OWNER/pubmed_slackbot.git my-pubmed-bot
cd my-pubmed-bot
git remote set-url origin https://github.com/YOUR_USERNAME/my-pubmed-bot.git
git push -u origin main
```

### Step 2: Create a Slack App

1. Go to [Slack API Apps](https://api.slack.com/apps) and click **Create New App**
2. Choose **From scratch**, give it a name (e.g., "PubMed Bot"), and select your workspace
3. In the left sidebar, go to **OAuth & Permissions**
4. Scroll to **Scopes** > **Bot Token Scopes** and add `chat:write`
5. Scroll back up and click **Install to Workspace**, then approve the permissions
6. Copy the **Bot User OAuth Token** — it starts with `xoxb-`. Save this for later.
7. In Slack, create or choose a channel for the bot to post in
8. Invite the bot to that channel by typing `/invite @YourBotName` in the channel
9. Get the **Channel ID**: right-click the channel name > **View channel details** > the ID is at the bottom of the popup

### Step 3: Set Up Your Google Sheet

Create a new Google Sheet with these columns in the first row:

| pubmed_name | slack_user_id | name_variants | affiliation |
|-------------|---------------|---------------|-------------|
| Curie Marie | U01ABC123 | Curie M, Sklodowska-Curie M | University of Paris |
| Darwin Charles | U02DEF456 | Darwin C, Darwin CR | University of Cambridge |

**Column descriptions:**

- **`pubmed_name`** (required): The author's name as it appears on PubMed, in "Last First" format
- **`slack_user_id`** (optional): The member's Slack user ID for @mentions. Find it by clicking their profile in Slack > **More** > **Copy member ID**
- **`name_variants`** (optional): Comma-separated alternative name formats the author may appear under (e.g., maiden names, abbreviated names)
- **`affiliation`** (optional): Institutional keyword to filter results and reduce false positives for common names

Copy the **Sheet ID** from the URL — it's the long string between `/d/` and `/edit`:

```
https://docs.google.com/spreadsheets/d/THIS_IS_YOUR_SHEET_ID/edit
```

### Step 4: Create a Google Service Account

The bot reads your Google Sheet using a service account (a bot-specific Google identity).

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "PubMed Bot") or select an existing one
3. Enable the **Google Sheets API**:
   - Go to **APIs & Services** > **Library**
   - Search for "Google Sheets API" and click **Enable**
4. Create a service account:
   - Go to **APIs & Services** > **Credentials**
   - Click **Create Credentials** > **Service Account**
   - Give it a name (e.g., "pubmed-bot") and click through the remaining steps
5. Create a key for the service account:
   - Click on the newly created service account
   - Go to the **Keys** tab > **Add Key** > **Create new key** > **JSON**
   - A JSON file will download — keep this safe and do not commit it to git
6. Share your Google Sheet with the service account:
   - Open the downloaded JSON file and find the `client_email` field
   - In your Google Sheet, click **Share** and add that email address with **Viewer** access

### Step 5: Configure GitHub Actions Secrets

This is where you connect everything. The bot runs as a GitHub Actions workflow, and secrets are how you securely provide credentials.

1. Go to your repository on GitHub
2. Navigate to **Settings** > **Secrets and variables** > **Actions**
3. Click **New repository secret** and add each of the following:

| Secret name | Value |
|-------------|-------|
| `SLACK_BOT_TOKEN` | The `xoxb-...` token from Step 2 |
| `SLACK_CHANNEL_ID` | The channel ID from Step 2 (e.g., `C01234ABCDE`) |
| `GOOGLE_SHEET_ID` | The sheet ID from Step 3 |
| `GOOGLE_CREDENTIALS` | Base64-encoded service account JSON (see below) |
| `PUBMED_API_KEY` | *(optional)* NCBI API key for higher rate limits |

**To base64-encode your service account JSON:**

On macOS:
```bash
base64 -i your-service-account.json | tr -d '\n'
```

On Linux:
```bash
base64 -w 0 your-service-account.json
```

Copy the full output and paste it as the value for `GOOGLE_CREDENTIALS`.

### Step 6: Enable the Workflow

1. Go to the **Actions** tab in your repository
2. If prompted, click **I understand my workflows, go ahead and enable them**
3. You should see the "Daily PubMed Check" workflow listed

The bot will now run automatically every day at 8 AM UTC. To change the schedule, edit the cron expression in `.github/workflows/daily.yml`.

### Step 7: Test It

**Trigger a manual run from the GitHub UI:**

1. Go to **Actions** > **Daily PubMed Check** > **Run workflow**
2. Optionally enter a custom lookback period (default is 7 days)
3. Click **Run workflow** and watch the output

**Or use the GitHub CLI:**

```bash
# Trigger a run
gh workflow run daily.yml

# Watch it execute
gh run watch

# Check the logs if something goes wrong
gh run list --workflow=daily.yml
gh run view <run-id> --log
```

If everything is configured correctly, you'll see a new message in your Slack channel for each recent publication by your group members.

### Optional: Get a PubMed API Key

Without an API key, PubMed allows 3 requests/second. With a key, you get 10/second. This matters for larger groups.

1. Go to [NCBI Settings](https://www.ncbi.nlm.nih.gov/account/settings/)
2. Sign in or create an NCBI account
3. Under **API Key Management**, click **Create an API Key**
4. Add it as the `PUBMED_API_KEY` secret in your repository

## Local Development

If you want to run or test the bot on your own machine instead of (or in addition to) GitHub Actions:

### Installation

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Required variables:
- `SLACK_BOT_TOKEN`: Your Slack bot token (xoxb-...)
- `SLACK_CHANNEL_ID`: Target Slack channel ID
- `GOOGLE_SHEET_ID`: The ID from your Google Sheet URL
- `GOOGLE_CREDENTIALS_FILE`: Path to your service account JSON file

Optional:
- `PUBMED_API_KEY`: NCBI API key for higher rate limits

Install dependencies using [uv](https://github.com/astral-sh/uv) (recommended):

```bash
uv venv
uv pip install -r requirements.txt
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running Locally

Preview what would be posted (dry-run mode):

```bash
uv run python pubmed_bot.py --dry-run
```

Run for real (posts to Slack):

```bash
uv run python pubmed_bot.py
```

Adjust lookback period:

```bash
uv run python pubmed_bot.py --days 14
```

Test with specific authors (bypasses Google Sheet):

```bash
uv run python pubmed_bot.py --test-authors "Smith J, Doe A" --affiliation "UCSF" --dry-run
```

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| Workflow fails with "not_in_channel" | Bot isn't in the Slack channel | Invite the bot: `/invite @YourBotName` |
| No papers found | Authors may not have recent publications, or names don't match PubMed format | Use `--test-authors` with `--dry-run` to test name matching; check PubMed directly for the author name format |
| Google Sheets error | Service account doesn't have access | Share the sheet with the service account's `client_email` |
| "Invalid base64" in Actions | Credentials weren't encoded correctly | Re-run the base64 command and make sure there are no newlines |
| Duplicate posts after re-enabling | The `posted_papers.json` cache expired | This is normal on the first run after a gap; duplicates won't recur |

## How It Works

1. Loads the author list from your Google Sheet
2. For each author (and their name variants), queries PubMed for papers from the last N days
3. Aggregates results, mapping each paper to its group authors
4. Filters out papers that have already been posted
5. Fetches full paper details (title, authors, journal, date)
6. Posts formatted messages to Slack with author @mentions
7. Updates `posted_papers.json` to track what's been posted (persisted via GitHub Actions cache, not committed to the repo)

## Rate Limits

- PubMed: 3 requests/second without API key, 10/second with key
- Slack: 1 message/second (built-in delay)

## License

MIT
