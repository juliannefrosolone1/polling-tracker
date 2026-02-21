"""
backfill_polls.py - Re-complete existing polls that have missing candidate data.

Finds polls with null values for candidates that were likely tested,
searches for the original source (PDF or web), and fills in missing numbers.

Run manually:  python scripts/backfill_polls.py
Or with flag:  python scripts/backfill_polls.py --min-missing 3
"""

import anthropic
import json
import os
import re
import io
import argparse
from datetime import datetime
from pathlib import Path

POLLS_FILE = Path(__file__).parent.parent / "public" / "polls.json"

CANDIDATES = [
    "harris","newsom","buttigieg","ocasio","shapiro","pritzker",
    "booker","whitmer","beshear","kelly","moore","slotkin","sanders",
    "gallego","warnock","ossoff","klobuchar","khanna","cooper","murphy","stewart"
]

CANDIDATE_NAMES = {
    "harris": "Kamala Harris", "newsom": "Gavin Newsom", "buttigieg": "Pete Buttigieg",
    "ocasio": "Alexandria Ocasio-Cortez", "shapiro": "Josh Shapiro", "pritzker": "J.B. Pritzker",
    "booker": "Cory Booker", "whitmer": "Gretchen Whitmer", "beshear": "Andy Beshear",
    "kelly": "Mark Kelly", "moore": "Wes Moore", "slotkin": "Elissa Slotkin",
    "sanders": "Bernie Sanders", "gallego": "Ruben Gallego", "warnock": "Raphael Warnock",
    "ossoff": "Jon Ossoff", "klobuchar": "Amy Klobuchar", "khanna": "Ro Khanna",
    "cooper": "Roy Cooper", "murphy": "Chris Murphy", "stewart": "Jon Stewart",
}

# Pollsters that commonly test many candidates (worth backfilling aggressively)
FULL_FIELD_POLLSTERS = [
    "UNH Survey Center", "Emerson College", "Harvard Harris", "Echelon Insights",
    "Morning Consult", "Focaldata", "Suffolk University", "Yale Youth Poll",
    "Quinnipiac", "Marist", "Monmouth", "Siena"
]


def load_polls():
    with open(POLLS_FILE) as f:
        return json.load(f)

def save_polls(polls):
    polls.sort(key=lambda p: p["date"], reverse=True)
    with open(POLLS_FILE, "w") as f:
        json.dump(polls, f, indent=2)


def is_pdf_url(url):
    if not url:
        return False
    url_lower = url.lower()
    return (
        url_lower.endswith(".pdf") or
        "viewcontent.cgi" in url_lower or
        "/pdf/" in url_lower or
        ("article=" in url_lower and "context=" in url_lower)
    )


def fetch_pdf_text(url):
    try:
        import requests
        import pdfplumber

        headers = {"User-Agent": "Mozilla/5.0 (compatible; PollBot/1.0)"}
        resp = requests.get(url, timeout=45, headers=headers)
        if resp.status_code != 200:
            print(f"    PDF HTTP {resp.status_code}: {url}")
            return None

        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
        full_text = "\n".join(t for t in pages_text if t.strip())

        if not full_text.strip():
            return None

        print(f"    PDF extracted: {len(full_text)} chars, {len(pages_text)} pages")
        return full_text

    except ImportError:
        print("    pdfplumber/requests not installed")
        return None
    except Exception as e:
        print(f"    PDF fetch error: {e}")
        return None


def parse_numbers_from_pdf(client, pdf_text, poll, missing_candidates):
    """Ask Claude to extract specific missing candidate numbers from PDF text."""
    missing_names = [CANDIDATE_NAMES[c] for c in missing_candidates]
    cand_list = "\n".join(f'  "{c}": number or null,' for c in missing_candidates)

    prompt = f"""Extract 2028 Democratic presidential primary poll numbers from this document.
Pollster: {poll['pollster']}
Date: {poll['date']}
State: {poll.get('state', 'National')}

I need the vote share percentages for these specific candidates:
{chr(10).join(f'- {n}' for n in missing_names)}

Return ONLY a JSON object with these candidate IDs and their percentages (or null if not tested):
{{
{cand_list}
}}

Be precise — use the exact numbers from the document. No markdown, no explanation.

--- DOCUMENT ---
{pdf_text[:12000]}
--- END ---
"""
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        print(f"    Parse error: {e}")
        return None


def search_for_poll_data(client, poll, missing_candidates):
    """Use web search to find missing candidate numbers for a poll."""
    missing_names = [CANDIDATE_NAMES[c] for c in missing_candidates[:6]]  # top 6 missing
    cand_list = "\n".join(f'  "{c}": number or null,' for c in missing_candidates)

    query = f"""{poll['pollster']} {poll['date'][:7]} 2028 Democratic primary poll full results {' '.join(missing_names[:3])}"""

    prompt = f"""Search for the full results of this poll:
Pollster: {poll['pollster']}
Date: {poll['date']}
State: {poll.get('state', 'National')}

I need vote share percentages for these candidates who are missing from my data:
{chr(10).join(f'- {n}' for n in missing_names)}

Search query to use: "{query}"

Return ONLY a JSON object with candidate IDs and their percentages (or null if not tested/found):
{{
{cand_list}
}}

No markdown, no explanation. If you can't find the data, return all nulls.
"""
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(b.text for b in resp.content if b.type == "text").strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        if raw.startswith("{"):
            return json.loads(raw)
    except Exception as e:
        print(f"    Search error: {e}")
    return None


def find_pdf_url(client, poll):
    """If poll has a vague source URL (not a direct PDF), search for the actual PDF."""
    url = poll.get("source_url", "")
    if is_pdf_url(url):
        return url  # already have direct PDF link

    # Search for the PDF
    query = f'{poll["pollster"]} {poll["date"]} 2028 Democratic primary poll PDF toplines filetype:pdf OR site:scholars.unh.edu OR site:emersoncollegepolling.com'
    prompt = f"""Find the direct PDF URL for this poll release:
Pollster: {poll['pollster']}
Date: {poll['date']}

Search for it and return ONLY the direct PDF URL, nothing else. If not found, return: null
"""
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(b.text for b in resp.content if b.type == "text").strip()
        raw = raw.strip('"').strip()
        if raw and raw != "null" and raw.startswith("http") and is_pdf_url(raw):
            print(f"    Found PDF URL: {raw}")
            return raw
    except Exception as e:
        print(f"    PDF URL search error: {e}")
    return None


def backfill_poll(client, poll, min_missing=3):
    """Try to fill missing candidate data for a single poll. Returns updated poll or None."""
    missing = [c for c in CANDIDATES if poll.get(c) is None]

    if len(missing) < min_missing:
        return None  # Not enough missing to bother

    # Only backfill polls from pollsters known to test many candidates
    if not any(pf.lower() in poll["pollster"].lower() for pf in FULL_FIELD_POLLSTERS):
        return None

    print(f"\n  Backfilling: {poll['pollster']} ({poll.get('state','National')}, {poll['date']})")
    print(f"    Missing {len(missing)} candidates: {', '.join(missing)}")

    filled = None

    # Strategy 1: Try direct PDF URL
    source_url = poll.get("source_url", "")
    if is_pdf_url(source_url):
        print(f"    Trying direct PDF: {source_url[:60]}")
        pdf_text = fetch_pdf_text(source_url)
        if pdf_text:
            filled = parse_numbers_from_pdf(client, pdf_text, poll, missing)

    # Strategy 2: Search for PDF URL if we don't have one
    if not filled and not is_pdf_url(source_url):
        pdf_url = find_pdf_url(client, poll)
        if pdf_url:
            pdf_text = fetch_pdf_text(pdf_url)
            if pdf_text:
                filled = parse_numbers_from_pdf(client, pdf_text, poll, missing)
                if filled:
                    poll["source_url"] = pdf_url  # Update source URL to direct PDF

    # Strategy 3: Web search for the data
    if not filled:
        print(f"    Trying web search...")
        filled = search_for_poll_data(client, poll, missing)

    if not filled:
        print(f"    Could not find data")
        return None

    # Merge results - only update fields that were null and now have values
    updated = dict(poll)
    improved = 0
    for cand in missing:
        val = filled.get(cand)
        if val is not None and isinstance(val, (int, float)):
            updated[cand] = val
            improved += 1

    if improved == 0:
        print(f"    No new data found")
        return None

    print(f"    Filled in {improved} candidates: {', '.join(c for c in missing if updated.get(c) is not None)}")
    return updated


def main():
    parser = argparse.ArgumentParser(description="Backfill missing poll data")
    parser.add_argument("--min-missing", type=int, default=3, help="Minimum missing candidates to trigger backfill (default: 3)")
    parser.add_argument("--limit", type=int, default=20, help="Max polls to process (default: 20)")
    parser.add_argument("--pollster", type=str, default=None, help="Only backfill a specific pollster")
    parser.add_argument("--dry-run", action="store_true", help="Don't save changes, just show what would be updated")
    args = parser.parse_args()

    print(f"=== Poll Backfiller {datetime.utcnow().isoformat()} UTC ===")
    print(f"Min missing: {args.min_missing} | Limit: {args.limit} | Dry run: {args.dry_run}")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    polls = load_polls()
    print(f"Loaded {len(polls)} polls")

    # Find candidates for backfill
    candidates = []
    for poll in polls:
        missing_count = sum(1 for c in CANDIDATES if poll.get(c) is None)
        if missing_count < args.min_missing:
            continue
        if args.pollster and args.pollster.lower() not in poll["pollster"].lower():
            continue
        if not any(pf.lower() in poll["pollster"].lower() for pf in FULL_FIELD_POLLSTERS):
            continue
        candidates.append((missing_count, poll))

    # Sort by most missing first
    candidates.sort(key=lambda x: -x[0])
    candidates = candidates[:args.limit]

    print(f"\nFound {len(candidates)} polls to backfill:")
    for count, p in candidates:
        print(f"  {p['date']} {p['pollster']} ({p.get('state','National')}): {count} missing")

    if not candidates:
        print("Nothing to backfill!")
        return

    # Process each poll
    updated_count = 0
    poll_index = {p["id"]: i for i, p in enumerate(polls) if "id" in p}

    for _, poll in candidates:
        result = backfill_poll(client, poll, min_missing=args.min_missing)
        if result:
            if not args.dry_run:
                # Update in place
                idx = poll_index.get(poll.get("id"))
                if idx is not None:
                    polls[idx] = result
                updated_count += 1
            else:
                print(f"    [DRY RUN] Would update poll")

    if not args.dry_run and updated_count > 0:
        save_polls(polls)
        print(f"\n✓ Updated {updated_count} polls. Saved to {POLLS_FILE}")
    elif args.dry_run:
        print(f"\n[DRY RUN] Would have updated {updated_count} polls")
    else:
        print(f"\nNo polls needed updating")


if __name__ == "__main__":
    main()
