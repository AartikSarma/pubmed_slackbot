# PubMed Slack Bot

A bot that monitors PubMed daily for new publications by members of a research group and posts announcements to Slack with author tagging.

## Features

- Fetches author list from a Google Sheet (supports name variants and institutional affiliations)
- Queries PubMed for recent publications using NCBI E-utilities
- Posts formatted announcements to Slack with author mentions
- Tracks posted papers to avoid duplicates
- Runs automatically via GitHub Actions (daily schedule)

## Setup

### Prerequisites

- Python 3.11+
- A Slack workspace with bot permissions
- A Google Cloud service account
- A Google Sheet with author information

### 1. Slack Bot Setup

1. Go to [Slack API](https://api.slack.com/apps) and create a new app
2. Under "OAuth & Permissions", add the `chat:write` scope
3. Install the app to your workspace
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
5. Get the **Channel ID** where you want to post (right-click channel > View channel details)

### 2. Google Sheet Setup

Create a Google Sheet with the following columns:

| pubmed_name | slack_user_id | name_variants | affiliation |
|-------------|---------------|---------------|-------------|
| Sarma Aartik | U01ABC123 | Sarma A, Sarma AA | UCSF |
| Smith John | U02DEF456 | Smith J, Smith JD | Harvard |

- `pubmed_name`: Primary author name as it appears on PubMed
- `slack_user_id`: Slack member ID (find via user profile > More > Copy member ID). Optional - if omitted, the name will be shown without a mention.
- `name_variants`: Comma-separated alternative name formats (optional)
- `affiliation`: Institutional filter to reduce false positives for common names (optional)

### 3. Google Service Account Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Sheets API
4. Go to "Credentials" > "Create Credentials" > "Service Account"
5. Download the JSON key file
6. Share your Google Sheet with the service account email (found in the JSON file as `client_email`)

### 4. Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Required variables:
- `SLACK_BOT_TOKEN`: Your Slack bot token (xoxb-...)
- `SLACK_CHANNEL_ID`: Target Slack channel ID
- `GOOGLE_SHEET_ID`: The ID from your Google Sheet URL
- `GOOGLE_CREDENTIALS_FILE`: Path to your service account JSON file (for local development)

Optional:
- `PUBMED_API_KEY`: NCBI API key for higher rate limits (get one at [NCBI](https://www.ncbi.nlm.nih.gov/account/settings/))

### 5. Installation

Using [uv](https://github.com/astral-sh/uv) (recommended):

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

## Usage

### Local Development

Preview what would be posted (dry-run mode):

```bash
uv run python pubmed_bot.py --dry-run
```

Run for real:

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

### GitHub Actions (Automated Daily Runs)

The included workflow (`.github/workflows/daily.yml`) runs the bot daily at 8 AM UTC.

To set up:

1. Go to your repository's Settings > Secrets and variables > Actions
2. Add the following secrets:
   - `SLACK_BOT_TOKEN`
   - `SLACK_CHANNEL_ID`
   - `GOOGLE_CREDENTIALS` (base64-encoded service account JSON)
   - `GOOGLE_SHEET_ID`
   - `PUBMED_API_KEY` (optional)

To base64-encode your credentials:

```bash
base64 -i your-service-account.json | tr -d '\n'
```

You can also manually trigger the workflow from the Actions tab or the `gh` CLI (see below).

### Testing the Workflow with `gh` CLI

Install the [GitHub CLI](https://cli.github.com/) if you haven't already, then authenticate:

```bash
gh auth login
```

**Trigger a manual run:**

```bash
gh workflow run daily.yml
```

You can also pass a custom lookback period:

```bash
gh workflow run daily.yml -f days=14
```

**Check that the workflow appears and is enabled:**

```bash
gh workflow list
```

**Watch a run in real time:**

```bash
gh run watch
```

This will prompt you to select a run if multiple are in progress.

**List recent runs and their status:**

```bash
gh run list --workflow=daily.yml
```

**View logs for a specific run** (useful for debugging secret/config issues):

```bash
# List runs to find the run ID
gh run list --workflow=daily.yml

# View the full log
gh run view <run-id> --log
```

**Verify secrets are configured** (this lists secret names, not values):

```bash
gh secret list
```

You should see `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`, `GOOGLE_CREDENTIALS`, `GOOGLE_SHEET_ID`, and optionally `PUBMED_API_KEY`.

## How It Works

1. Loads author list from Google Sheet
2. For each author (and their name variants), queries PubMed for papers from the last N days
3. Aggregates results, mapping each paper to its group authors
4. Filters out papers that have already been posted
5. Fetches full paper details (title, authors, journal)
6. Posts formatted messages to Slack with author mentions
7. Updates `posted_papers.json` to track what's been posted

## Rate Limits

- PubMed: 3 requests/second without API key, 10/second with key
- Slack: 1 message/second (built-in delay)

## License

MIT
