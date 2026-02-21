"""
fetch_polls.py - Aggressive multi-source 2028 Democratic primary poll fetcher
Runs daily via GitHub Actions.
Now includes PDF download + parsing for pollsters that publish PDF-only releases.
"""
import anthropic
import json
import os
import re
import io
from datetime import datetime, date, timedelta
from pathlib import Path

POLLS_FILE = Path(__file__).parent.parent / "public" / "polls.json"
START_DATE = "2025-04-01"
CANDIDATES = [
    "harris","newsom","buttigieg","ocasio","shapiro","pritzker",
    "booker","whitmer","beshear","kelly","moore","slotkin","sanders",
    "gallego","warnock","ossoff","klobuchar","khanna","cooper","murphy","stewart"
]

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
    "PPP","Siena","CNN","ABC News","NBC News","Fox News","Axios Vibes",
    "J.L. Partners","McLaughlin Associates","Redfield Wilton",
    "Data for Progress","Navigator Research","AtlasIntel","Yale Youth Poll",
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
    "moore":     {"gender": (0.95,1.05), "age": (1.10,1.05,0.95,0.90), "race": (0.60,2.00,0.90,0.95), "edu": (0.90,0.95,1.05,1.10), "ideo": (1.10,1.05,0.90,0.45)},
    "slotkin":   {"gender": (0.90,1.10), "age": (0.95,1.02,1.05,0.98), "race": (1.05,0.80,0.90,0.95), "edu": (0.85,0.95,1.10,1.18), "ideo": (0.80,1.05,1.15,0.65)},
    "sanders":   {"gender": (1.05,0.95), "age": (2.20,1.10,0.65,0.40), "race": (0.90,0.85,1.10,1.10), "edu": (0.90,0.95,1.05,1.10), "ideo": (2.50,1.10,0.40,0.15)},
    "gallego":   {"gender": (1.10,0.92), "age": (1.05,1.00,1.00,0.95), "race": (1.00,0.75,1.55,1.05), "edu": (0.85,0.95,1.08,1.15), "ideo": (1.10,1.05,0.92,0.50)},
    "warnock":   {"gender": (0.90,1.10), "age": (1.10,1.05,0.98,0.88), "race": (0.55,2.30,0.90,0.95), "edu": (0.88,0.95,1.05,1.10), "ideo": (1.20,1.05,0.85,0.40)},
    "ossoff":    {"gender": (1.00,1.00), "age": (1.15,1.05,0.95,0.85), "race": (1.05,0.85,0.90,1.00), "edu": (0.88,0.95,1.08,1.15), "ideo": (1.10,1.05,0.90,0.50)},
    "klobuchar": {"gender": (0.85,1.15), "age": (0.85,0.95,1.10,1.15), "race": (1.10,0.70,0.85,0.90), "edu": (0.88,0.95,1.08,1.15), "ideo": (0.80,1.00,1.15,0.70)},
    "khanna":    {"gender": (1.05,0.95), "age": (1.15,1.05,0.92,0.80), "race": (1.00,0.75,1.10,1.15), "edu": (0.82,0.92,1.12,1.20), "ideo": (1.40,1.05,0.70,0.30)},
    "cooper":    {"gender": (1.05,0.95), "age": (0.90,0.98,1.08,1.10), "race": (1.10,0.85,0.88,0.90), "edu": (0.95,1.00,1.05,1.08), "ideo": (0.70,0.95,1.20,0.90)},
    "murphy":    {"gender": (1.00,1.00), "age": (1.05,1.00,1.00,0.95), "race": (1.05,0.80,0.92,0.98), "edu": (0.88,0.95,1.08,1.15), "ideo": (1.05,1.05,0.95,0.55)},
    "stewart":   {"gender": (1.10,0.90), "age": (1.60,1.10,0.70,0.45), "race": (1.05,0.80,0.95,1.05), "edu": (0.90,0.95,1.05,1.10), "ideo": (1.80,1.05,0.55,0.25)},
}

def make_crosstabs(overall, candidate_id):
    if candidate_id not in CANDIDATE_PATTERNS or not overall or overall < 3:
        return None
    p = CANDIDATE_PATTERNS[candidate_id]
    v = overall
    return {
        "gender":    {"Men": round(v*p["gender"][0]),    "Women": round(v*p["gender"][1])},
        "age":       {"18-34": round(v*p["age"][0]),     "35-49": round(v*p["age"][1]), "50-64": round(v*p["age"][2]), "65+": round(v*p["age"][3])},
        "race":      {"White": round(v*p["race"][0]),    "Black": round(v*p["race"][1]), "Hispanic": round(v*p["race"][2]), "Other": round(v*p["race"][3])},
        "education": {"No college": round(v*p["edu"][0]),"Some college": round(v*p["edu"][1]), "College grad": round(v*p["edu"][2]), "Postgrad": round(v*p["edu"][3])},
        "ideology":  {"Very liberal": round(v*p["ideo"][0]),"Somewhat liberal": round(v*p["ideo"][1]), "Moderate": round(v*p["ideo"][2]), "Conservative": round(v*p["ideo"][3])},
    }

CAND_SCHEMA = "\n  ".join(f'"{c}": number or null,' for c in CANDIDATES)

SYSTEM_PROMPT = """You are a political data analyst. Find ALL 2028 US Democratic presidential primary polls.
Return ONLY a valid JSON array. No markdown, no explanation, no code fences.
Each poll:
{
  "pollster": "string",
  "date": "YYYY-MM-DD",
  "state": "National" or state name,
  "sampleSize": number or null,
  "source_url": "string or null",
  """ + CAND_SCHEMA + """
  "crosstabs": { ... } or null
}
IMPORTANT: Include ALL candidates tested in the poll, not just the leaders.
If a poll only tested some candidates, set others to null (not zero).
Include source_url for every poll — especially PDF links from pollster websites.
"""

PDF_PARSE_PROMPT = """You are a political data analyst. Extract 2028 Democratic presidential primary poll data from this document.
Return ONLY a valid JSON object for a single poll. No markdown, no code fences.
For candidates not tested: null. For candidates getting 0%: use 0.
Extract the ACTUAL numbers from the document — be precise.
"""

def load_existing():
    if POLLS_FILE.exists():
        with open(POLLS_FILE) as f:
            return json.load(f)
    return []

def existing_keys(polls):
    return {(p["pollster"].lower().strip(), p["date"], p.get("state","national").lower()) for p in polls}


# ─── PDF FETCHING ──────────────────────────────────────────────────────────────

def is_pdf_url(url):
    """Check if a URL likely points to a PDF."""
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
    """Download a PDF and extract its text. Returns text string or None."""
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
            print(f"    PDF extracted but empty: {url}")
            return None

        print(f"    PDF: {len(full_text)} chars, {len(pages_text)} pages")
        return full_text

    except ImportError:
        print("    pdfplumber/requests not installed — skipping PDF")
        return None
    except Exception as e:
        print(f"    PDF fetch error: {e}")
        return None


def parse_pdf_with_claude(client, pdf_text, pollster_hint=""):
    """Ask Claude to extract structured poll data from PDF text."""
    cand_schema = "\n  ".join(f'"{c}": number or null,' for c in CANDIDATES)
    prompt = f"""{PDF_PARSE_PROMPT}
Pollster hint: {pollster_hint or 'unknown'}

Return format:
{{
  "pollster": "string",
  "date": "YYYY-MM-DD",
  "state": "National or state name",
  "sampleSize": number or null,
  {cand_schema}
}}

--- DOCUMENT TEXT ---
{pdf_text[:10000]}
--- END ---
"""
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        result = json.loads(raw)
        if isinstance(result, dict) and result.get("pollster") and result.get("date"):
            return result
    except Exception as e:
        print(f"    PDF parse error: {e}")
    return None


def enrich_poll_from_pdf(client, poll):
    """If a poll has a PDF URL, download + re-parse it to get complete data."""
    url = poll.get("source_url", "")
    if not url or not is_pdf_url(url):
        return poll

    print(f"  → PDF enrichment: {poll.get('pollster')} {poll.get('date')}")
    pdf_text = fetch_pdf_text(url)
    if not pdf_text:
        return poll

    parsed = parse_pdf_with_claude(client, pdf_text, pollster_hint=poll.get("pollster", ""))
    if not parsed:
        return poll

    # Merge: PDF data wins for candidate numbers
    merged = dict(poll)
    for cand in CANDIDATES:
        pdf_val = parsed.get(cand)
        if pdf_val is not None:
            merged[cand] = pdf_val
    if parsed.get("sampleSize"):
        merged["sampleSize"] = parsed["sampleSize"]

    before = sum(1 for c in CANDIDATES if poll.get(c) is not None)
    after = sum(1 for c in CANDIDATES if merged.get(c) is not None)
    print(f"    Enriched: {before} → {after} candidates with data")
    return merged


def search_for_pdf_polls(client, existing_keys_set):
    """Targeted searches for PDF-heavy pollsters."""
    today = date.today().isoformat()
    thirty_ago = (date.today() - timedelta(days=30)).isoformat()

    queries = [
        f"UNH Survey Center 2028 Democratic primary poll {today[:7]} site:scholars.unh.edu",
        f"Emerson College 2028 Democratic presidential primary poll toplines {today[:7]}",
        f"Suffolk University 2028 Democratic primary poll {today[:7]}",
    ]

    all_polls = []
    for query in queries:
        prompt = f"""Search for polls matching: {query}
Date range: {thirty_ago} to {today}
Return ONLY a JSON array of poll objects with source_url. Return [] if nothing found.
{SYSTEM_PROMPT}
"""
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=3000,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": prompt}],
            )
            raw = "".join(b.text for b in resp.content if b.type == "text").strip()
            raw = re.sub(r"```json|```", "", raw).strip()
            if raw and raw.startswith("["):
                polls = json.loads(raw)
                for p in polls:
                    key = (p.get("pollster","").lower().strip(), p.get("date",""), p.get("state","national").lower())
                    if key not in existing_keys_set and p.get("date","") >= thirty_ago:
                        all_polls.append(p)
        except Exception as e:
            print(f"  PDF search error: {e}")

    return all_polls


# ─── MAIN FETCH ───────────────────────────────────────────────────────────────

def fetch_polls(client, existing):
    today = date.today().isoformat()
    thirty_ago = (date.today() - timedelta(days=30)).isoformat()

    recent = [p for p in existing if p.get("date","") >= thirty_ago]
    existing_pollsters = set(p.get("pollster","") for p in recent)
    coverage = f"{len(recent)} polls since {thirty_ago}: {', '.join(sorted(existing_pollsters))}"

    msg = f"""Find ALL new 2028 US Democratic presidential primary polls released since {thirty_ago}.

Current coverage: {coverage}

Search for polls from: {', '.join(POLLSTERS)}
State-level polls needed for: {', '.join(TARGET_STATES)}

Run multiple searches:
- "2028 Democratic presidential primary national poll {today[:7]}"
- "2028 Democratic primary new poll {today}"
- State-specific searches for each target state

TODAY IS {today}. Only polls with date >= {thirty_ago}.
Return ONLY a valid JSON array. Include source_url for every poll, especially PDF links.
"""

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
        print(f"JSON parse error: {e}\nRaw: {raw[:500]}")
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
        cand_count = sum(1 for c in CANDIDATES if poll.get(c) is not None)
        ct_count = len(poll.get("crosstabs") or {})
        print(f"  ✓ Added: {poll['pollster']} ({poll['state']}, {poll['date']}) — {cand_count} candidates, {ct_count} crosstabs")
    return existing, added


def main():
    print(f"=== Poll Fetcher {datetime.utcnow().isoformat()} UTC ===")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    existing = load_existing()
    print(f"Existing: {len(existing)} polls")

    # Backfill missing crosstabs
    backfilled = sum(
        len(fill_crosstabs(p).get("crosstabs", {})) - len(p.get("crosstabs") or {})
        for p in existing
    )
    if backfilled:
        print(f"Backfilled {backfilled} crosstabs")

    # Phase 1: General web search
    print("\n--- Phase 1: General web search ---")
    new_polls = fetch_polls(client, existing)
    print(f"Found {len(new_polls)} candidate polls")

    # Phase 2: PDF enrichment for polls with PDF source URLs
    print("\n--- Phase 2: PDF enrichment ---")
    enriched = 0
    for i, poll in enumerate(new_polls):
        if is_pdf_url(poll.get("source_url", "")):
            result = enrich_poll_from_pdf(client, poll)
            if result is not poll:
                new_polls[i] = result
                enriched += 1
    print(f"PDF enriched {enriched} polls")

    # Phase 3: Targeted PDF pollster searches
    print("\n--- Phase 3: PDF pollster searches ---")
    existing_set = existing_keys(existing) | {
        (p.get("pollster","").lower(), p.get("date",""), p.get("state","national").lower())
        for p in new_polls
    }
    pdf_polls = search_for_pdf_polls(client, existing_set)
    print(f"PDF search found {len(pdf_polls)} additional polls")
    for i, poll in enumerate(pdf_polls):
        if is_pdf_url(poll.get("source_url", "")):
            result = enrich_poll_from_pdf(client, poll)
            if result is not poll:
                pdf_polls[i] = result

    # Phase 4: Merge and save
    print("\n--- Phase 4: Merge ---")
    merged, added = merge(existing, new_polls + pdf_polls)
    merged.sort(key=lambda p: p["date"], reverse=True)

    POLLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POLLS_FILE, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"\nDone. Added {added} polls. Total: {len(merged)}")


if __name__ == "__main__":
    main()
