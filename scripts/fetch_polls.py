"""
fetch_polls.py - 2028 Democratic primary poll fetcher
Phase 0: requests-based scrape of racetothewh.com/president/2028/dem
Phase 1: Claude web search for anything the scrape misses
Runs daily via GitHub Actions.
"""
import anthropic
import json
import os
import re
import time
import requests
from datetime import datetime
from pathlib import Path

POLLS_FILE = Path(__file__).parent.parent / "public" / "polls.json"
START_DATE = "2025-01-01"

CANDIDATES = [
    "harris", "newsom", "buttigieg", "ocasio", "shapiro",
    "pritzker", "booker", "whitmer", "beshear", "kelly",
    "crow", "slotkin", "khanna", "ossoff", "murphy"
]

SYSTEM_PROMPT = """You are a political data analyst. Find 2028 US Democratic presidential primary polls.

Return ONLY a valid JSON array. No markdown, no explanation, no code fences. Start your response with [
Each poll object must follow this exact schema:
{
  "pollster": "string",
  "date": "YYYY-MM-DD",
  "state": "National" or state name (e.g. "Iowa", "New Hampshire"),
  "type": "National" or "Head-to-Head" or state name,
  "sampleSize": number or null,
  "source_url": "string or null",
  "harris": number or null,
  "newsom": number or null,
  "buttigieg": number or null,
  "ocasio": number or null,
  "shapiro": number or null,
  "pritzker": number or null,
  "booker": number or null,
  "whitmer": number or null,
  "beshear": number or null,
  "kelly": number or null,
  "crow": number or null,
  "slotkin": number or null,
  "khanna": number or null,
  "ossoff": number or null,
  "murphy": number or null,
  "crosstabs": null
}
Numbers are percentages (e.g. 23.0 not 0.23). Use null for missing candidates.
Return [] if nothing new found."""


def load_existing():
    if POLLS_FILE.exists():
        with open(POLLS_FILE) as f:
            return json.load(f)
    return []


def existing_keys(polls):
    return {
        (p["pollster"].lower().strip(), p["date"], p.get("state", "National").lower())
        for p in polls
    }


def parse_json_response(raw):
    """Safely extract JSON array from a response string."""
    raw = re.sub(r"```json|```", "", raw).strip()
    if "[" in raw:
        raw = raw[raw.index("["):]
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except Exception as e:
        print(f"  JSON parse error: {e}. Raw: {raw[:200]}")
        return []


def scrape_racetothewh():
    """Phase 0: Fetch racetothewh.com with requests and extract polls via Claude."""
    print("  [Phase 0] Fetching racetothewh.com with requests...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get(
            "https://www.racetothewh.com/president/2028/dem",
            headers=headers,
            timeout=20
        )
        resp.raise_for_status()
        html = resp.text
        print(f"  [Phase 0] Got {len(html)} chars of HTML")
    except Exception as e:
        print(f"  [Phase 0] requests error: {e}")
        return []

    # Strip HTML tags to get readable text
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    print(f"  [Phase 0] Stripped to {len(text)} chars of text")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Extract ALL polls from this page text as a JSON array. Look for rows with a date, pollster name, and candidate percentages.\n\n{text[:8000]}"}],
        )
        raw = "".join(b.text for b in response.content if b.type == "text").strip()
        polls = parse_json_response(raw)
        print(f"  [Phase 0] Extracted {len(polls)} poll(s) from racetothewh.com")
        return polls
    except Exception as e:
        print(f"  [Phase 0] Claude extraction error: {e}")
        return []


def fetch_polls_claude(existing):
    """Phase 1: Claude web search for polls not already in existing list."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    recent = sorted(existing, key=lambda p: p["date"], reverse=True)[:20]
    existing_summary = "\n".join(
        f"- {p['pollster']} | {p.get('state', 'National')} | {p['date']}"
        for p in recent
    )

    msg = f"""Search for ALL 2028 Democratic presidential primary polls published in the last 30 days.

ALREADY IN OUR DATABASE (do not re-add these):
{existing_summary}

Search for:
1. New national primary polls (all pollsters)
2. State polls: Iowa, New Hampshire, Nevada, South Carolina, Michigan, Georgia, California, Illinois, Pennsylvania, Virginia, North Carolina
3. Head-to-head matchups (e.g. Harris vs Newsom)
4. Any poll from: Manhattan Institute, J.L. Partners, UNH, Emerson, Suffolk, YouGov, Quinnipiac, Morning Consult, Ipsos, PRRI, Monmouth, CBS News, Fox News, CNN, NBC News, ABC/WaPo

Return the full JSON array of new polls not in the existing database. Start your response with ["""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": msg}],
        )
        time.sleep(30)
        raw = "".join(b.text for b in response.content if b.type == "text").strip()
        polls = parse_json_response(raw)
        print(f"  [Phase 1] Found {len(polls)} poll(s)")
        return polls
    except anthropic.RateLimitError as e:
        print(f"  [Phase 1] Rate limit hit, skipping: {e}")
        return []
    except Exception as e:
        print(f"  [Phase 1] Error: {e}")
        return []


def validate(poll):
    if not poll.get("pollster") or not poll.get("date"):
        return False
    try:
        datetime.strptime(poll["date"], "%Y-%m-%d")
    except ValueError:
        return False
    if poll["date"] < START_DATE:
        return False
    return any(
        poll.get(c) is not None and isinstance(poll.get(c), (int, float))
        for c in CANDIDATES
    )


def merge(existing, new_polls):
    keys = existing_keys(existing)
    added = 0
    for poll in new_polls:
        if not validate(poll):
            print(f"  Skip invalid: {poll.get('pollster')} {poll.get('date')}")
            continue
        if "state" not in poll or not poll["state"]:
            poll["state"] = "National"
        key = (poll["pollster"].lower().strip(), poll["date"], poll["state"].lower())
        if key in keys:
            print(f"  Duplicate: {poll['pollster']} ({poll['state']}, {poll['date']})")
            continue
        state_slug = poll["state"].lower().replace(" ", "-")
        poll["id"] = f"auto-{poll['date']}-{state_slug}-{poll['pollster'].lower().replace(' ', '')[:12]}"
        if "crosstabs" not in poll:
            poll["crosstabs"] = None
        existing.append(poll)
        keys.add(key)
        added += 1
        print(f"  ✓ Added: {poll['pollster']} ({poll['state']}, {poll['date']})")
    return existing, added


def main():
    print(f"=== Poll Fetcher {datetime.utcnow().isoformat()} UTC ===")
    existing = load_existing()
    print(f"Existing: {len(existing)} polls")

    all_new = []

    # Phase 0: requests-based scrape of racetothewh.com
    print("\n--- Phase 0: racetothewh.com scrape ---")
    scraped = scrape_racetothewh()
    all_new.extend(scraped)

    # Phase 1: Claude web search for anything else
    print("\n--- Phase 1: Claude web search ---")
    combined = existing + all_new
    claude_polls = fetch_polls_claude(combined)
    all_new.extend(claude_polls)

    # Merge everything
    print(f"\n--- Merging {len(all_new)} candidate poll(s) ---")
    merged, added = merge(existing, all_new)
    merged.sort(key=lambda p: p["date"], reverse=True)

    POLLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POLLS_FILE, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"\nDone. Added {added} new poll(s). Total: {len(merged)}")


if __name__ == "__main__":
    main()
