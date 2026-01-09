# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Slack bot that monitors PubMed daily for new publications by members of a physician-scientist research group. Posts paper announcements to a Slack channel with title, PubMed link, and author tags, avoiding duplicate posts for collaborative papers.

## Commands

```bash
# Install dependencies (using uv)
uv venv && uv pip install -r requirements.txt

# Run with dry-run mode (preview without posting)
uv run python pubmed_bot.py --dry-run

# Run for real (posts to Slack)
uv run python pubmed_bot.py

# Adjust lookback period (default: 7 days)
uv run python pubmed_bot.py --days 14

# Test with specific authors (bypasses Google Sheet)
uv run python pubmed_bot.py --test-authors "Smith J, Doe A" --affiliation "UCSF" --dry-run
```

## Architecture

- **pubmed_bot.py**: Main script - fetches authors from Google Sheet, queries PubMed, posts to Slack
- **posted_papers.json**: Tracks PMIDs already posted (auto-updated by bot and committed by GitHub Actions)
- **Google Sheet**: Source of truth for author list (columns: pubmed_name, slack_user_id, name_variants, affiliation)

## Google Sheet Format

| pubmed_name | slack_user_id | name_variants | affiliation |
|-------------|---------------|---------------|-------------|
| Sarma Aartik | U01ABC123 | Sarma A, Sarma AA | UCSF |
| Smith John | U02DEF456 | Smith J, Smith JD | Harvard |

- `affiliation` is optional but recommended for common names to filter results

## Key Data Flow

1. Load authors from Google Sheet via gspread
2. For each author name (+ variants), query PubMed E-utilities (esearch) with optional affiliation filter
3. Aggregate papers, mapping each PMID to its group authors
4. Filter out already-posted PMIDs
5. Fetch paper details (efetch) and post to Slack
6. Update posted_papers.json

## Environment Variables

Required: `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`, `GOOGLE_SHEET_ID`, and either `GOOGLE_CREDENTIALS` (base64) or `GOOGLE_CREDENTIALS_FILE` (path)

Optional: `PUBMED_API_KEY` (recommended for higher rate limits)

## Development Notes

- PubMed searches use format: `"LastName FirstInitial[Author]"`
- NCBI rate limits: 3 req/sec without API key, 10 with key (0.35-0.4s delay between queries)
- Slack mentions use format: `<@USER_ID>`
- Google Sheet must be shared with the service account email
