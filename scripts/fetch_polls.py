"""
fetch_polls.py - Searches for national + state-level 2028 Democratic primary polls
Runs daily via GitHub Actions.
"""
import anthropic
import json
import os
import re
from datetime import datetime, date
from pathlib import Path

POLLS_FILE = Path(__file__).parent.parent / "public" / "polls.json"
START_DATE = "2025-04-01"
CANDIDATES = ["harris","newsom","buttigieg","ocasio","shapiro","pritzker","booker","whitmer","beshear","kelly"]

# All states worth searching — early primary contenders + large delegate states
TARGET_STATES = [
    "New Hampshire","Iowa","Nevada","South Carolina","Michigan","Georgia",
    "California","Illinois","Pennsylvania","Virginia","North Carolina",
    "Texas","Florida","Wisconsin","Arizona","Minnesota","Colorado","New York",
]

SYSTEM_PROMPT = """You are a political data analyst finding 2028 US Democratic presidential primary polls.
Return ONLY a valid JSON array, no markdown, no explanation.
Each poll object:
{
  "pollster": "string",
  "date": "YYYY-MM-DD",
  "state": "National" or state name,
  "sampleSize": number or null,
  "source_url": "string or null",
  "harris": number or null, "newsom": number or null, "buttigieg": number or null,
  "ocasio": number or null, "shapiro": number or null, "pritzker": number or null,
  "booker": number or null, "whitmer": number or null, "beshear": number or null, "kelly": number or null,
  "crosstabs": { "candidateId": { "gender": {...}, "age": {...}, "race": {...}, "education": {...}, "ideology": {...} } } or null
}
Use null for missing candidates. Numbers are percentages. Return [] if nothing new."""


def load_existing():
    if POLLS_FILE.exists():
        with open(POLLS_FILE) as f:
            return json.load(f)
    return []


def existing_keys(polls):
    return {(p["pollster"].lower().strip(), p["date"], p.get("state","National").lower()) for p in polls}


def fetch_polls(existing):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = date.today().isoformat()

    recent = sorted(existing, key=lambda p: p["date"], reverse=True)[:10]
    existing_summary = "\n".join(f"  - {p['pollster']} ({p.get('state','National')}, {p['date']})" for p in recent)

    state_searches = "\n".join(f'- "2028 Democratic primary poll {s}"' for s in TARGET_STATES[:8])

    msg = f"""Today is {today}. Find NEW 2028 Democratic presidential primary polls since {START_DATE}.

Already have:
{existing_summary}

Search for polls NOT listed above. Use these searches:
- "2028 Democratic presidential primary poll"
- site:racetothewh.com/president/2028/dem
- site:realclearpolling.com 2028 democratic primary
- site:emersoncollegepolling.com 2028
- site:suffolk.edu/news 2028 poll
- site:unh.edu 2028 poll
{state_searches}

Include state field ("National" or state name). Include crosstabs if available.
Return [] if no new polls found."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": msg}],
    )

    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    raw = re.sub(r"```json|```", "", raw).strip()
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except:
        print(f"JSON parse error. Raw: {raw[:300]}")
        return []


def validate(poll):
    if not poll.get("pollster") or not poll.get("date"):
        return False
    try:
        datetime.strptime(poll["date"], "%Y-%m-%d")
    except:
        return False
    if poll["date"] < START_DATE:
        return False
    return any(poll.get(c) is not None and isinstance(poll.get(c), (int, float)) for c in CANDIDATES)


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
        poll["id"] = f"auto-{poll['date']}-{state_slug}-{poll['pollster'].lower().replace(' ','')[:12]}"
        if "crosstabs" not in poll:
            poll["crosstabs"] = None
        existing.append(poll)
        keys.add(key)
        added += 1
        print(f"  ✓ {poll['pollster']} ({poll['state']}, {poll['date']})")
    return existing, added


def main():
    print(f"=== Poll Fetcher {datetime.utcnow().isoformat()} UTC ===")
    existing = load_existing()
    print(f"Existing: {len(existing)} polls across {len(set(p.get('state','National') for p in existing))} states")

    new_polls = fetch_polls(existing)
    print(f"Found {len(new_polls)} candidate(s)")

    merged, added = merge(existing, new_polls)
    merged.sort(key=lambda p: p["date"], reverse=True)

    POLLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POLLS_FILE, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"Done. Added {added}. Total: {len(merged)}")


if __name__ == "__main__":
    main()
