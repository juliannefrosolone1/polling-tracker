"""
fetch_polls.py - 2028 Democratic primary poll fetcher
Phase 0: Direct scrape of racetothewh.com/president/2028/dem (Playwright)
Phase 1: Claude web search for anything the scrape misses
Runs daily via GitHub Actions.
"""
import anthropic
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

POLLS_FILE = Path(__file__).parent.parent / "public" / "polls.json"
START_DATE = "2025-01-01"

CANDIDATES = [
    "harris", "newsom", "buttigieg", "ocasio", "shapiro",
    "pritzker", "booker", "whitmer", "beshear", "kelly",
    "crow", "slotkin", "khanna", "ossoff", "murphy"
]

# Maps display names on racetothewh.com to our candidate keys
CANDIDATE_NAME_MAP = {
    "harris": "harris",
    "newsom": "newsom",
    "buttigieg": "buttigieg",
    "pete": "buttigieg",
    "ocasio": "ocasio",
    "aoc": "ocasio",
    "cortez": "ocasio",
    "shapiro": "shapiro",
    "pritzker": "pritzker",
    "booker": "booker",
    "whitmer": "whitmer",
    "beshear": "beshear",
    "kelly": "kelly",
    "crow": "crow",
    "slotkin": "slotkin",
    "khanna": "khanna",
    "ossoff": "ossoff",
    "murphy": "murphy",
}

SYSTEM_PROMPT = """You are a political data analyst. Find 2028 US Democratic presidential primary polls
that are NOT already in the existing list provided. Search broadly — national polls, state polls,
head-to-head matchups, all pollsters.

Return ONLY a valid JSON array. No markdown, no explanation, no code fences.
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


def parse_candidate_pct(text):
    """Parse 'Harris 23.0%' → ('harris', 23.0)"""
    if not text or not text.strip():
        return None, None
    m = re.match(r"([A-Za-z\-]+)\s+([\d.]+)%?", text.strip())
    if not m:
        return None, None
    name = m.group(1).lower()
    pct = float(m.group(2))
    key = CANDIDATE_NAME_MAP.get(name)
    return key, pct


def parse_date_added(text, year=2026):
    """Parse 'Mar 9' → '2026-03-09'"""
    if not text:
        return None
    try:
        dt = datetime.strptime(f"{text.strip()} {year}", "%b %d %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    # Try with full year already included
    try:
        dt = datetime.strptime(text.strip(), "%b %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    return None


def scrape_racetothewh():
    """Phase 0: Use Playwright to scrape the full poll table from racetothewh.com"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [Phase 0] Playwright not available, skipping direct scrape.")
        return []

    print("  [Phase 0] Launching Playwright to scrape racetothewh.com...")
    polls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("https://www.racetothewh.com/president/2028/dem", timeout=30000)
            # Wait for the poll table to render
            page.wait_for_selector("table", timeout=15000)
            time.sleep(2)  # Let JS finish rendering

            # Find all tables and look for the polls table
            tables = page.query_selector_all("table")
            print(f"  [Phase 0] Found {len(tables)} table(s) on page.")

            for table in tables:
                rows = table.query_selector_all("tr")
                if len(rows) < 3:
                    continue

                # Check if this looks like a polls table by inspecting headers
                header_row = rows[0]
                headers = [th.inner_text().strip().lower() for th in header_row.query_selector_all("th, td")]
                print(f"  [Phase 0] Table headers: {headers}")

                # Look for columns: #, Added, Type, Pollster, First, Second, Third
                if not any("pollster" in h or "first" in h or "added" in h for h in headers):
                    continue

                # Map column indices
                col_map = {}
                for i, h in enumerate(headers):
                    if "added" in h:
                        col_map["date"] = i
                    elif "type" in h:
                        col_map["type"] = i
                    elif "pollster" in h:
                        col_map["pollster"] = i
                    elif "first" in h:
                        col_map["first"] = i
                    elif "second" in h:
                        col_map["second"] = i
                    elif "third" in h:
                        col_map["third"] = i

                print(f"  [Phase 0] Column map: {col_map}")

                for row in rows[1:]:
                    cells = [td.inner_text().strip() for td in row.query_selector_all("td")]
                    if len(cells) < 4:
                        continue

                    def get(col_name):
                        idx = col_map.get(col_name)
                        if idx is not None and idx < len(cells):
                            return cells[idx]
                        return ""

                    raw_date = get("date")
                    pollster = get("pollster")
                    poll_type = get("type")

                    if not pollster or not raw_date:
                        continue

                    date_str = parse_date_added(raw_date)
                    if not date_str:
                        continue

                    # Determine state from type column
                    state = "National"
                    if poll_type and poll_type.lower() not in ("national", ""):
                        # Could be "Iowa", "New Hampshire", or "Harris Newsom" (head-to-head)
                        state = poll_type if not re.search(r"[A-Z][a-z]+ [A-Z][a-z]+", poll_type) else "National"

                    poll = {
                        "pollster": pollster,
                        "date": date_str,
                        "state": state,
                        "type": poll_type,
                        "sampleSize": None,
                        "source_url": "https://www.racetothewh.com/president/2028/dem",
                        "crosstabs": None,
                    }

                    # Initialize all candidates to null
                    for c in CANDIDATES:
                        poll[c] = None

                    # Parse First, Second, Third columns
                    for col_name in ("first", "second", "third"):
                        cell_text = get(col_name)
                        cand_key, pct = parse_candidate_pct(cell_text)
                        if cand_key and cand_key in CANDIDATES:
                            poll[cand_key] = pct

                    # Only include if at least one candidate has data
                    if any(poll[c] is not None for c in CANDIDATES):
                        polls.append(poll)
                        print(f"  [Phase 0] ✓ {pollster} ({state}, {date_str})")

        except Exception as e:
            print(f"  [Phase 0] Error during scrape: {e}")
        finally:
            browser.close()

    print(f"  [Phase 0] Scraped {len(polls)} poll row(s) from racetothewh.com")
    return polls


def fetch_polls_claude(existing):
    """Phase 1: Claude web search for polls not already in existing list"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Build a summary of what we already have for dedup context
    recent = sorted(existing, key=lambda p: p["date"], reverse=True)[:20]
    existing_summary = "\n".join(
        f"- {p['pollster']} | {p.get('state','National')} | {p['date']}"
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

Also check racetothewh.com/president/2028/dem for any polls listed there.

Return the full JSON array of new polls not in the existing database."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": msg}],
    )

    time.sleep(30)  # Rate limit buffer

    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    raw = re.sub(r"```json|```", "", raw).strip()
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except Exception as e:
        print(f"  [Phase 1] JSON parse error: {e}\nRaw: {raw[:300]}")
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

    # Phase 0: Direct scrape of racetothewh.com
    print("\n--- Phase 0: racetothewh.com direct scrape ---")
    scraped = scrape_racetothewh()
    all_new.extend(scraped)

    # Phase 1: Claude web search for anything else
    print("\n--- Phase 1: Claude web search ---")
    # Pass in both existing AND what we just scraped so Phase 1 doesn't duplicate Phase 0
    combined = existing + all_new
    claude_polls = fetch_polls_claude(combined)
    print(f"  [Phase 1] Found {len(claude_polls)} poll(s)")
    all_new.extend(claude_polls)

    # Merge everything into existing
    print(f"\n--- Merging {len(all_new)} candidate poll(s) ---")
    merged, added = merge(existing, all_new)
    merged.sort(key=lambda p: p["date"], reverse=True)

    POLLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POLLS_FILE, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"\nDone. Added {added} new poll(s). Total: {len(merged)}")


if __name__ == "__main__":
    main()
