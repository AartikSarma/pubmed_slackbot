#!/usr/bin/env python3
"""
PubMed Slack Bot

Monitors PubMed for new publications by research group members and posts
announcements to Slack with author tagging.
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import gspread
import requests
from google.oauth2.service_account import Credentials
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# PubMed E-utilities base URLs
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# File paths
SCRIPT_DIR = Path(__file__).parent
POSTED_PAPERS_FILE = SCRIPT_DIR / "posted_papers.json"


def get_env_var(name: str, required: bool = True) -> str | None:
    """Get environment variable, raising error if required and missing."""
    value = os.environ.get(name)
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def get_google_credentials() -> Credentials:
    """Get Google credentials from environment or file."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_json:
        import base64
        creds_data = json.loads(base64.b64decode(creds_json))
    else:
        creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE")
        if not creds_file:
            raise ValueError(
                "Set GOOGLE_CREDENTIALS (base64) or GOOGLE_CREDENTIALS_FILE"
            )
        with open(creds_file) as f:
            creds_data = json.load(f)

    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    return Credentials.from_service_account_info(creds_data, scopes=scopes)


def get_authors_from_sheet(sheet_id: str) -> list[dict]:
    """
    Fetch author list from Google Sheet.

    Expected columns:
        - pubmed_name: Primary author name (e.g., "Sarma Aartik")
        - slack_user_id: Slack member ID (e.g., "U01ABC123")
        - name_variants: Comma-separated alternative names (optional)
        - affiliation: Institutional filter (optional, e.g., "UCSF")

    Returns list of dicts with keys: pubmed_name, slack_user_id, all_names, affiliation
    """
    credentials = get_google_credentials()
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(sheet_id).sheet1

    records = sheet.get_all_records()
    authors = []

    for row in records:
        pubmed_name = row.get("pubmed_name", "").strip()
        slack_user_id = row.get("slack_user_id", "").strip()
        name_variants = row.get("name_variants", "")
        affiliation = row.get("affiliation", "").strip() or None

        if not pubmed_name or not slack_user_id:
            continue

        all_names = [pubmed_name]
        if name_variants:
            variants = [v.strip() for v in name_variants.split(",") if v.strip()]
            all_names.extend(variants)

        authors.append({
            "pubmed_name": pubmed_name,
            "slack_user_id": slack_user_id,
            "all_names": all_names,
            "affiliation": affiliation,
        })

    return authors


def search_pubmed(
    author_name: str,
    days: int = 7,
    api_key: str | None = None,
    affiliation: str | None = None,
) -> list[str]:
    """
    Search PubMed for papers by author in the last N days.

    Args:
        author_name: Author name (e.g., "Sarma A" or "Sarma Aartik")
        days: Number of days to look back
        api_key: Optional NCBI API key
        affiliation: Optional institutional affiliation filter (e.g., "UCSF")

    Returns list of PMIDs.
    """
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
    date_to = datetime.now().strftime("%Y/%m/%d")

    # Build search term
    search_term = f'{author_name}[Author]'
    if affiliation:
        search_term = f'({search_term}) AND {affiliation}[Affiliation]'

    params = {
        "db": "pubmed",
        "term": search_term,
        "datetype": "edat",
        "mindate": date_from,
        "maxdate": date_to,
        "retmode": "json",
        "retmax": 100,
    }

    if api_key:
        params["api_key"] = api_key

    response = requests.get(ESEARCH_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    return data.get("esearchresult", {}).get("idlist", [])


def get_paper_details(pmids: list[str], api_key: str | None = None) -> list[dict]:
    """
    Fetch paper details for a list of PMIDs.

    Returns list of dicts with keys: pmid, title, authors, journal, pub_date
    """
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }

    if api_key:
        params["api_key"] = api_key

    response = requests.get(EFETCH_URL, params=params, timeout=30)
    response.raise_for_status()

    import xml.etree.ElementTree as ET
    root = ET.fromstring(response.content)

    papers = []
    for article in root.findall(".//PubmedArticle"):
        pmid_elem = article.find(".//PMID")
        title_elem = article.find(".//ArticleTitle")
        journal_elem = article.find(".//Journal/Title")

        authors_list = []
        for author in article.findall(".//Author"):
            lastname = author.findtext("LastName", "")
            initials = author.findtext("Initials", "")
            if lastname:
                authors_list.append(f"{lastname} {initials}".strip())

        pub_date_elem = article.find(".//PubDate")
        pub_date = ""
        if pub_date_elem is not None:
            year = pub_date_elem.findtext("Year", "")
            month = pub_date_elem.findtext("Month", "")
            pub_date = f"{month} {year}".strip()

        papers.append({
            "pmid": pmid_elem.text if pmid_elem is not None else "",
            "title": title_elem.text if title_elem is not None else "No title",
            "authors": authors_list,
            "journal": journal_elem.text if journal_elem is not None else "",
            "pub_date": pub_date,
        })

    return papers


def load_posted_papers() -> set[str]:
    """Load set of already-posted PMIDs."""
    if not POSTED_PAPERS_FILE.exists():
        return set()

    with open(POSTED_PAPERS_FILE) as f:
        data = json.load(f)
        return set(data.get("pmids", []))


def save_posted_papers(pmids: set[str]) -> None:
    """Save set of posted PMIDs."""
    data = {
        "pmids": sorted(pmids),
        "last_updated": datetime.now().isoformat(),
    }
    with open(POSTED_PAPERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def format_slack_message(paper: dict, group_authors: list[dict]) -> str:
    """Format a paper as a Slack message."""
    title = paper["title"]
    authors_str = ", ".join(paper["authors"][:10])
    if len(paper["authors"]) > 10:
        authors_str += f", et al. ({len(paper['authors'])} authors)"

    mentions = " ".join(f"<@{a['slack_user_id']}>" for a in group_authors)
    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/"

    journal_info = ""
    if paper["journal"]:
        journal_info = f"\n*Journal:* {paper['journal']}"
        if paper["pub_date"]:
            journal_info += f" ({paper['pub_date']})"

    return (
        f"*New Publication*\n\n"
        f"*Title:* {title}\n\n"
        f"*Authors:* {authors_str}{journal_info}\n\n"
        f"*Group members:* {mentions}\n\n"
        f"{pubmed_url}"
    )


def post_to_slack(
    client: WebClient,
    channel: str,
    paper: dict,
    group_authors: list[dict],
    dry_run: bool = False,
) -> bool:
    """Post a paper announcement to Slack."""
    message = format_slack_message(paper, group_authors)

    if dry_run:
        print(f"\n[DRY RUN] Would post to #{channel}:")
        print("-" * 50)
        print(message)
        print("-" * 50)
        return True

    try:
        client.chat_postMessage(channel=channel, text=message)
        return True
    except SlackApiError as e:
        print(f"Error posting to Slack: {e.response['error']}")
        return False


def normalize_author_name(name: str) -> str:
    """Normalize author name for comparison (lowercase, no extra spaces)."""
    return " ".join(name.lower().split())


def find_matching_group_authors(paper_authors: list[str], group_authors: list[dict]) -> list[dict]:
    """Find which group authors are on a paper."""
    matches = []
    paper_authors_normalized = [normalize_author_name(a) for a in paper_authors]

    for author in group_authors:
        for name in author["all_names"]:
            if normalize_author_name(name) in paper_authors_normalized:
                matches.append(author)
                break

    return matches


def main():
    parser = argparse.ArgumentParser(description="PubMed Slack Bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview messages without posting to Slack",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)",
    )
    parser.add_argument(
        "--test-authors",
        type=str,
        help="Comma-separated author names for testing (bypasses Google Sheet)",
    )
    parser.add_argument(
        "--affiliation",
        type=str,
        help="Filter by institutional affiliation (e.g., 'UCSF', 'Harvard')",
    )
    args = parser.parse_args()

    # Test mode with provided authors
    test_mode = args.test_authors is not None

    # Load configuration from environment
    slack_token = get_env_var("SLACK_BOT_TOKEN", required=not args.dry_run and not test_mode)
    channel_id = get_env_var("SLACK_CHANNEL_ID", required=not args.dry_run and not test_mode)
    sheet_id = get_env_var("GOOGLE_SHEET_ID", required=not test_mode)
    api_key = get_env_var("PUBMED_API_KEY", required=False)

    # Initialize Slack client
    slack_client = None
    if slack_token:
        slack_client = WebClient(token=slack_token)

    print(f"PubMed Slack Bot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Looking back {args.days} days for new papers")
    if args.dry_run:
        print("DRY RUN MODE - No messages will be posted")
    if test_mode:
        print("TEST MODE - Using provided authors instead of Google Sheet")

    # Load authors
    if test_mode:
        print("\nUsing test authors...")
        authors = []
        for name in args.test_authors.split(","):
            name = name.strip()
            if name:
                authors.append({
                    "pubmed_name": name,
                    "slack_user_id": "TEST_USER",
                    "all_names": [name],
                    "affiliation": None,  # Use --affiliation flag for test mode
                })
    else:
        print("\nLoading authors from Google Sheet...")
        authors = get_authors_from_sheet(sheet_id)
    print(f"Found {len(authors)} authors to track")

    # Load already-posted papers
    posted_pmids = load_posted_papers()
    print(f"Already posted {len(posted_pmids)} papers")

    # Search PubMed for each author
    print("\nSearching PubMed...")
    paper_to_authors: dict[str, list[dict]] = {}
    all_pmids: set[str] = set()

    delay = 0.4 if api_key else 0.35  # Respect rate limits

    # Command-line affiliation overrides per-author affiliations
    global_affiliation = getattr(args, 'affiliation', None)

    for i, author in enumerate(authors):
        # Use global affiliation if set, otherwise use author's affiliation
        affiliation = global_affiliation or author.get("affiliation")

        for name in author["all_names"]:
            pmids = search_pubmed(name, days=args.days, api_key=api_key, affiliation=affiliation)
            for pmid in pmids:
                all_pmids.add(pmid)
                if pmid not in paper_to_authors:
                    paper_to_authors[pmid] = []
                if author not in paper_to_authors[pmid]:
                    paper_to_authors[pmid].append(author)
            time.sleep(delay)

        if (i + 1) % 10 == 0:
            print(f"  Searched {i + 1}/{len(authors)} authors...")

    print(f"Found {len(all_pmids)} total papers")

    # Filter out already-posted papers
    new_pmids = all_pmids - posted_pmids
    print(f"New papers to post: {len(new_pmids)}")

    if not new_pmids:
        print("No new papers to post.")
        return

    # Fetch paper details
    print("\nFetching paper details...")
    papers = get_paper_details(list(new_pmids), api_key=api_key)

    # Post to Slack
    print("\nPosting to Slack...")
    posted_count = 0

    for paper in papers:
        pmid = paper["pmid"]
        group_authors = paper_to_authors.get(pmid, [])

        if not group_authors:
            # Re-check using paper's author list
            group_authors = find_matching_group_authors(paper["authors"], authors)

        if not group_authors:
            print(f"  Skipping PMID {pmid} - no matching group authors found")
            continue

        success = post_to_slack(
            slack_client, channel_id, paper, group_authors, dry_run=args.dry_run
        )

        if success:
            posted_pmids.add(pmid)
            posted_count += 1
            time.sleep(1)  # Respect Slack rate limits

    # Save updated posted papers
    if not args.dry_run:
        save_posted_papers(posted_pmids)
        print(f"\nSaved {len(posted_pmids)} total PMIDs to {POSTED_PAPERS_FILE}")

    print(f"\nDone! Posted {posted_count} new papers.")


if __name__ == "__main__":
    main()
