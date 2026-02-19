# 2028 Democratic Primary Polling Tracker

An automatically-updating polling tracker powered by GitHub Actions + Anthropic API.

---

## How It Works

```
GitHub Actions (runs daily at 9am UTC)
  └── scripts/fetch_polls.py
        ├── Calls Claude API with web_search tool
        ├── Asks Claude to find new 2028 Dem primary polls published in the last 7 days
        ├── Parses results into structured JSON
        ├── Deduplicates against existing data
        └── Commits updated public/polls.json back to the repo

React App (hosted on Vercel/Netlify)
  └── Fetches /polls.json on load
  └── Shows weighted trend charts + data table
  └── Lets you manually add polls too
```

---

## Setup (takes ~10 minutes)

### 1. Create your GitHub repo

```bash
git init
git add .
git commit -m "Initial commit"
gh repo create dem-primary-tracker --public
git push -u origin main
```

### 2. Add your Anthropic API key as a GitHub Secret

1. Go to your repo on GitHub
2. Click **Settings → Secrets and variables → Actions**
3. Click **New repository secret**
4. Name: `ANTHROPIC_API_KEY`
5. Value: your key from https://console.anthropic.com

### 3. Deploy the React app to Vercel (free)

1. Go to https://vercel.com and sign in with GitHub
2. Click **Add New Project**
3. Import your `dem-primary-tracker` repo
4. Leave all settings as default
5. Click **Deploy**

Vercel will auto-deploy every time GitHub Actions commits updated poll data.

### 4. Verify it works

- Go to your repo → **Actions** tab
- Click **Fetch Latest Polls** → **Run workflow** (manual trigger)
- Watch the logs — it should find polls and commit an updated `public/polls.json`
- Your Vercel site will auto-redeploy with fresh data within ~1 minute

### 5. It's live!

From now on, every day at 9am UTC, GitHub Actions will:
- Search the web for new 2028 Democratic primary polls
- Add any new ones to `polls.json`
- Commit the update
- Trigger a Vercel redeploy

---

## File Structure

```
├── .github/
│   └── workflows/
│       └── fetch-polls.yml     ← GitHub Actions schedule
├── public/
│   └── polls.json              ← Auto-updated poll database
├── scripts/
│   └── fetch_polls.py          ← The poll-fetching script
├── src/
│   └── App.jsx                 ← The React tracker UI
└── package.json
```

---

## Customization

**Change the schedule:** Edit the cron in `.github/workflows/fetch-polls.yml`
- `"0 9 * * *"` = daily at 9am UTC
- `"0 9 * * 1"` = weekly on Mondays
- `"0 9 * * 1,4"` = twice a week (Mon + Thu)

**Add/remove candidates:** Edit `CANDIDATES` in both `src/App.jsx` and `scripts/fetch_polls.py`

**Adjust the poll search window:** Change the `7` in `fetch_polls.py`'s prompt to search further back

---

## Cost Estimate

- GitHub Actions: **free** (well within the free tier)
- Vercel hosting: **free**
- Anthropic API: ~$0.01–0.05 per daily run (Claude Opus + web search, very cheap)

---

## Notes

- Polls are weighted by **recency** (60-day half-life) and **sample size** (√n)
- The script won't add duplicate polls (deduplicates by pollster + date)
- You can still manually add polls via the UI (stored in your browser's localStorage)
- No candidates have formally declared as of February 2026
