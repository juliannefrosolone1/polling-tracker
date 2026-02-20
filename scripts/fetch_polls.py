"""
fetch_polls.py
--------------
Runs daily via GitHub Actions. Uses the Anthropic API (with web search)
to find newly published 2028 Democratic primary polls, parses them into
structured data including demographic crosstabs, and merges into public/polls.json.
"""

import anthropic
import json
import os
import re
from datetime import datetime, date
from pathlib import Path

POLLS_FILE = Path(__file__).parent.parent / "public" / "polls.json"
START_DATE = "2025-04-01"

CANDIDATES = ["harris", "newsom", "buttigieg", "ocasio", "shapiro", "pritzker", "booker", "whitmer", "beshear", "kelly"]

SYSTEM_PROMPT = """You are a political data analyst. Your job is to find recently published
polls for the 2028 US Democratic presidential primary and return them as structured JSON.

Rules:
- Only include polls published since April 1, 2025 that were NOT already in the existing data
- Only include polls that test the 2028 Democratic presidential primary
- Return ONLY a valid JSON array, no markdown, no explanation, no code fences
- Each poll object must have these exact keys:
  {
    "pollster": "string",
    "date": "YYYY-MM-DD",
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
    "crosstabs": {
      "harris": {
        "gender": {"Men": number, "Women": number},
        "age": {"18-34": number, "35-49": number, "50-64": number, "65+": number},
        "race": {"White": number, "Black": number, "Hispanic": number, "Other": number},
        "education": {"No college": number, "Some college": number, "College grad": number, "Postgrad": number},
        "ideology": {"Very liberal": number, "Somewhat liberal": number, "Moderate": number, "Conservative": number}
      }
    }
  }
- Include crosstabs for any candidate where demographic breakdowns are available in the poll
- Use null for candidates not included in a poll (do not use 0)
- Numbers should be percentages as floats, e.g. 39.0
- The crosstabs field can be null or {} if no demographic data is available
- If no new polls are found, return an empty array: []
"""


def load_existing_polls():
    if POLLS_FILE.exists():
        with open(POLLS_FILE) as f:
            return json.load(f)
    return []


def get_existing_poll_keys(polls):
    return {(p["pollster"].lower().strip(), p["date"]) for p in polls}


def fetch_new_polls(existing_polls):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    existing_summary = ""
    if existing_polls:
        recent = sorted(existing_polls, key=lambda p: p["date"], reverse=True)[:5]
        existing_summary = "Most recent polls already in database:\n" + "\n".join(
            f"  - {p['pollster']} ({p['date']})" for p in recent
        )

    today = date.today().isoformat()
    user_message = f"""Today is {today}. Track all polls since {START_DATE}.

{existing_summary}

Please search the web for any NEW 2028 Democratic presidential primary polls published
in the last 7 days that are NOT already listed above. Also try to find any polls from
April 2025 through today that may be missing. Search for:
- "2028 Democratic primary poll"
- "2028 presidential poll Democrats"
- site:realclearpolitics.com 2028
- site:racetothewh.com 2028
- site:fivethirtyeight.com 2028

For each poll found, include full demographic crosstabs (gender, age, race, education, ideology)
if they are available in the poll report.

Return only new polls as a JSON array. Return [] if nothing new was found."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = ""
    for block in response.content:
        if block.type == "text":
            raw_text += block.text

    if not raw_text.strip():
        print("No text response from Claude.")
        return []

    raw_text = re.sub(r"```json|```", "", raw_text).strip()

    try:
        new_polls = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw response:\n{raw_text[:500]}")
        return []

    if not isinstance(new_polls, list):
        print("Response was not a list.")
        return []

    return new_polls


def validate_poll(poll):
    if not poll.get("pollster") or not poll.get("date"):
        return False
    try:
        datetime.strptime(poll["date"], "%Y-%m-%d")
    except ValueError:
        return False
    # Must be after start date
    if poll["date"] < START_DATE:
        return False
    has_data = any(
        poll.get(c) is not None and isinstance(poll.get(c), (int, float))
        for c in CANDIDATES
    )
    return has_data


def merge_polls(existing, new_polls):
    existing_keys = get_existing_poll_keys(existing)
    added = 0
    for poll in new_polls:
        if not validate_poll(poll):
            print(f"  Skipping invalid poll: {poll.get('pollster')} {poll.get('date')}")
            continue
        key = (poll["pollster"].lower().strip(), poll["date"])
        if key in existing_keys:
            print(f"  Duplicate skipped: {poll['pollster']} ({poll['date']})")
            continue
        poll["id"] = f"auto-{poll['date']}-{poll['pollster'].lower().replace(' ', '-')[:20]}"
        if "crosstabs" not in poll:
            poll["crosstabs"] = None
        existing.append(poll)
        existing_keys.add(key)
        added += 1
        has_ct = bool(poll.get("crosstabs"))
        print(f"  ✓ Added: {poll['pollster']} ({poll['date']}) {'[+crosstabs]' if has_ct else ''}")
    return existing, added


def main():
    print(f"=== Poll Fetcher running at {datetime.utcnow().isoformat()} UTC ===")
    print(f"Tracking polls from {START_DATE} to present")

    existing = load_existing_polls()
    print(f"Existing polls in database: {len(existing)}")

    print("Fetching new polls from Claude + web search...")
    new_polls = fetch_new_polls(existing)
    print(f"Claude returned {len(new_polls)} candidate poll(s)")

    merged, added = merge_polls(existing, new_polls)
    merged.sort(key=lambda p: p["date"], reverse=True)

    POLLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POLLS_FILE, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"Done. Added {added} new poll(s). Total in database: {len(merged)}")


if __name__ == "__main__":
    main()
