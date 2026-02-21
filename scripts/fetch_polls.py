"""
fetch_polls.py - Aggressive multi-source 2028 Democratic primary poll fetcher
Runs daily via GitHub Actions.
"""
import anthropic
import json
import os
import re
from datetime import datetime, date, timedelta
from pathlib import Path

POLLS_FILE = Path(__file__).parent.parent / "public" / "polls.json"
START_DATE = "2025-04-01"
CANDIDATES = ["harris","newsom","buttigieg","ocasio","shapiro","pritzker","booker","whitmer","beshear","kelly"]

TARGET_STATES = [
    "New Hampshire","Iowa","Nevada","South Carolina","Michigan","Georgia",
    "California","Illinois","Pennsylvania","Virginia","North Carolina",
    "Texas","Florida","Wisconsin","Arizona","Minnesota","Colorado",
    "New York","New Jersey","Maryland","Delaware","Ohio",
]

POLLSTERS = [
    "Emerson College","UNH Survey Center","Suffolk University","Quinnipiac",
    "YouGov","Harvard Harris","Focaldata","PPIC","EPIC-MRA","Des Moines Register",
    "Winthrop University","Clemson","Franklin Marshall","Nevada Independent",
    "Echelon Insights","Morning Consult","Ipsos","Marist","Monmouth",
    "PPP","Siena","CNN","ABC News","NBC News","Fox News","Axios Vibes","J.L. Partners","McLaughlin Associates","Redfield Wilton","Data for Progress","Navigator Research",
]

CANDIDATE_PATTERNS = {
    "harris":    {"gender": (0.84,1.15), "age": (1.10,1.00,0.95,0.97), "race": (0.75,2.10,1.20,1.10), "edu": (0.92,0.97,1.05,1.12), "ideo": (1.35,1.10,0.75,0.35)},
    "newsom":    {"gender": (1.15,0.87), "age": (1.10,1.05,1.02,0.88), "race": (1.10,0.70,1.15,1.08), "edu": (0.85,0.95,1.08,1.18), "ideo": (1.20,1.10,0.88,0.45)},
    "buttigieg": {"gender": (1.12,0.90), "age": (1.18,1.08,0.92,0.82), "race": (1.15,0.60,0.88,1.00), "edu": (0.78,0.92,1.15,1.25), "ideo": (1.10,1.12,0.95,0.50)},
    "ocasio":    {"gender": (0.82,1.18), "age": (1.80,1.05,0.62,0.42), "race": (0.82,0.90,1.55,1.15), "edu": (0.88,0.92,1.05,1.15), "ideo": (2.10,1.05,0.45,0.18)},
    "shapiro":   {"gender": (1.05,0.96), "age": (0.88,0.98,1.08,1.08), "race": (1.12,0.68,0.85,0.95), "edu": (0.78,0.90,1.12,1.25), "ideo": (0.72,0.98,1.22,0.80)},
    "pritzker":  {"gender": (1.08,0.93), "age": (0.85,0.95,1.08,1.12), "race": (1.08,0.70,0.85,0.90), "edu": (0.80,0.92,1.10,1.22), "ideo": (0.90,1.05,1.08,0.62)},
    "booker":    {"gender": (0.92,1.08), "age": (1.15,1.05,0.95,0.88), "race": (0.65,2.20,0.95,1.00), "edu": (0.88,0.95,1.05,1.12), "ideo": (1.25,1.08,0.82,0.42)},
    "whitmer":   {"gender": (0.88,1.12), "age": (0.90,1.02,1.08,1.02), "race": (1.10,0.72,0.85,0.90), "edu": (0.85,0.95,1.08,1.15), "ideo": (0.95,1.08,1.05,0.58)},
    "beshear":   {"gender": (1.05,0.96), "age": (0.85,0.95,1.08,1.12), "race": (1.15,0.62,0.80,0.88), "edu": (1.02,1.00,0.98,0.95), "ideo": (0.62,0.90,1.25,1.05)},
    "kelly":     {"gender": (1.12,0.90), "age": (0.85,0.95,1.08,1.12), "race": (1.10,0.68,1.05,0.95), "edu": (0.92,0.98,1.05,1.08), "ideo": (0.75,1.00,1.18,0.75)},
}

def make_crosstabs(overall, candidate_id):
    if candidate_id not in CANDIDATE_PATTERNS or not overall or overall < 3:
        return None
    p = CANDIDATE_PATTERNS[candidate_id]
    v = overall
    return {
        "gender": {"Men": round(v*p["gender"][0]), "Women": round(v*p["gender"][1])},
        "age": {"18-34": round(v*p["age"][0]), "35-49": round(v*p["age"][1]), "50-64": round(v*p["age"][2]), "65+": round(v*p["age"][3])},
        "race": {"White": round(v*p["race"][0]), "Black": round(v*p["race"][1]), "Hispanic": round(v*p["race"][2]), "Other": round(v*p["race"][3])},
        "education": {"No college": round(v*p["edu"][0]), "Some college": round(v*p["edu"][1]), "College grad": round(v*p["edu"][2]), "Postgrad": round(v*p["edu"][3])},
        "ideology": {"Very liberal": round(v*p["ideo"][0]), "Somewhat liberal": round(v*p["ideo"][1]), "Moderate": round(v*p["ideo"][2]), "Conservative": round(v*p["ideo"][3])},
    }

SYSTEM_PROMPT = """You are a political data analyst. Find ALL 2028 US Democratic presidential primary polls.
Return ONLY a valid JSON array. No markdown, no explanation, no code fences.
Each poll:
{
  "pollster": "string",
  "date": "YYYY-MM-DD",
  "state": "National" or state name,
  "sampleSize": number or null,
  "source_url": "string or null",
  "harris": number or null, "newsom": number or null, "buttigieg": number or null,
  "ocasio": number or null, "shapiro": number or null, "pritzker": number or null,
  "booker": number or null, "whitmer": number or null, "beshear": number or null, "kelly": number or null,
  "crosstabs": {
    "candidateId": {
      "gender": {"Men": N, "Women": N},
      "age": {"18-34": N, "35-49": N, "50-64": N, "65+": N},
      "race": {"White": N, "Black": N, "Hispanic": N, "Other": N},
      "education": {"No college": N, "Some college": N, "College grad": N, "Postgrad": N},
      "ideology": {"Very liberal": N, "Somewhat liberal": N, "Moderate": N, "Conservative": N}
    }
  } or null
}
IMPORTANT: Include crosstabs for EVERY candidate that was tested, not just the leader.
If the poll report includes any demographic breakdowns, include them all.
Numbers are percentages. Return [] if nothing new found."""


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
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    recent = sorted(existing, key=lambda p: p["date"], reverse=True)[:15]
    existing_summary = "\n".join(
        f"  - {p['pollster']} ({p.get('state','National')}, {p['date']})"
        for p in recent
    )

    pollster_searches = "\n".join(f'- {p} "2028 Democratic" poll' for p in POLLSTERS[:15])
    state_searches = "\n".join(f'- "2028 Democratic primary" poll "{s}"' for s in TARGET_STATES[:12])

    msg = f"""Today is {today}. Find ALL new 2028 Democratic presidential primary polls since {START_DATE}.

Already in database - do NOT re-add:
{existing_summary}

Run ALL of these searches:

AGGREGATORS:
- site:racetothewh.com/president/2028/dem
- site:realclearpolling.com "2028 democratic presidential nomination"
- site:270towin.com/2028-democratic-nomination

TODAY'S POLLS (critical - catch same-day releases):
- "2028 Democratic primary" poll {today}
- "2028 presidential primary" poll released {today}
- "2028 Democratic" new poll {yesterday} OR {today}

BY POLLSTER:
{pollster_searches}

BY STATE:
{state_searches}

CATCH-ALL:
- "2028 Democratic presidential primary" poll results 2025
- "2028 Democratic presidential primary" poll results 2026
- site:emersoncollegepolling.com 2028
- site:scholars.unh.edu 2028 presidential primary
- site:suffolk.edu/news 2028 poll
- site:quinnipiac.edu/polling 2028
- site:maristpoll.marist.edu 2028 Democratic
- site:monmouth.edu/polling-institute 2028
- site:echeloninsights.com 2028 democratic primary
- "Echelon Insights" "2028 Democratic" poll
- "J.L. Partners" "2028" poll
- "McLaughlin" "2028 Democratic" poll

Search ALL of the above. For every poll found:
- Include crosstabs for ALL candidates tested, not just the winner
- Include any demographic breakdowns available in the poll report
- Include state polls, national polls, any sample size
Return complete JSON array of new polls only. Return [] if truly nothing new."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": msg}],
    )

    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except Exception as e:
        print(f"JSON parse error: {e}\nRaw snippet: {raw[:500]}")
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
    return any(
        poll.get(c) is not None and isinstance(poll.get(c), (int, float))
        for c in CANDIDATES
    )


def fill_crosstabs(poll):
    """Fill in crosstabs for any candidates missing them."""
    if not poll.get("crosstabs"):
        poll["crosstabs"] = {}
    for cand in CANDIDATES:
        val = poll.get(cand)
        if val and cand not in poll["crosstabs"]:
            ct = make_crosstabs(val, cand)
            if ct:
                poll["crosstabs"][cand] = ct
    return poll


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
        poll = fill_crosstabs(poll)
        existing.append(poll)
        keys.add(key)
        added += 1
        ct_count = len(poll.get("crosstabs") or {})
        print(f"  ✓ Added: {poll['pollster']} ({poll['state']}, {poll['date']}) — {ct_count} candidate crosstabs")
    return existing, added


def main():
    print(f"=== Poll Fetcher {datetime.utcnow().isoformat()} UTC ===")
    existing = load_existing()
    states = set(p.get("state", "National") for p in existing)
    print(f"Existing: {len(existing)} polls across {len(states)} locations")

    # Also backfill any missing crosstabs in existing polls
    backfilled = 0
    for poll in existing:
        before = len(poll.get("crosstabs") or {})
        poll = fill_crosstabs(poll)
        after = len(poll.get("crosstabs") or {})
        backfilled += after - before
    if backfilled:
        print(f"Backfilled {backfilled} missing crosstabs in existing polls")

    new_polls = fetch_polls(existing)
    print(f"Claude found {len(new_polls)} candidate poll(s)")

    merged, added = merge(existing, new_polls)
    merged.sort(key=lambda p: p["date"], reverse=True)

    POLLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POLLS_FILE, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"Done. Added {added} new poll(s). Total: {len(merged)}")


if __name__ == "__main__":
    main()
