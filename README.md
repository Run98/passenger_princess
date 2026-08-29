# Passenger Princess — EMT Report Assistant (Demo 2: Watch + Phone App)

A demo app showing how EMTs could write patient care reports faster: an
Apple Watch app for hands-free field capture, and a phone app that both
captures richer field data and is where the EMT reviews the AI-drafted
narrative and signs off. See `CLAUDE.md` for the full design rationale and
scope. This demo drops the standalone web app from the earlier version —
the phone app is now the sole review/sign-off surface.

## What's in this repo

```
backend/                       FastAPI server, Postgres storage, structured AI narrative generation
phone_app/                      Phone app frontend (Dashboard -> Field Recording -> Prelim Report -> Approve & Sign)
phone_app/static/watch-mock.html Browser-based watch app simulator (see below) -- no Xcode needed
watch_app/                      Swift source scaffold for the real watchOS app + iPhone relay app
requirements.txt                Python dependencies
vercel.json                     Vercel deployment config (see "Deploying to Vercel" below)
CLAUDE.md                       Project design doc / build guide
```

## Running the demo (backend + browser)

This is the part you can run right now without any Apple hardware. It
needs a Postgres database to store call data — Vercel's serverless
functions have no persistent local disk, so this demo (like the eventual
production version) uses a real database instead of a local SQLite file.

For local development, the easiest option is Postgres via Homebrew:

```bash
brew install postgresql@16
brew services start postgresql@16
createdb emt_demo2
```

Or point `DATABASE_URL` at any hosted Postgres (Neon, Vercel Postgres,
Supabase, etc.) — free tiers work fine for this.

```bash
pip install -r requirements.txt --break-system-packages   # or use a venv
export DATABASE_URL="postgresql://localhost:5432/emt_demo2"   # adjust user/host as needed
cd backend
python seed_demo.py          # loads the reference chest-pain demo call
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000/** in a browser (Chrome recommended, for
voice dictation support via the Web Speech API). You'll land on the phone
app's Dashboard, showing the seeded demo call. Open it to see the five-screen
flow:

1. **Dashboard** — call list with Draft/In Review/Signed status.
2. **Field Recording** — tap Voice, Scribble, Vitals, or Photo to add assets; each is listed individually and can be added more than once.
3. **Generate PCR Narrative** — becomes enabled once at least one asset exists; produces a structured narrative (Chief Complaint / Assessment / Treatment).
4. **Prelim Report** — review and edit the AI-drafted sections (flagged "AI-drafted, tap to edit").
5. **Approve & Sign** — draw a signature and submit; the call's status becomes "Signed."

### Enabling real AI narrative generation

Without an API key, narrative generation falls back automatically to a
template-based split of the captured data (`backend/narrative.py`'s
`build_structured_fallback`) — the demo still works, just with simpler
narrative text. To get real AI-generated narratives:

```bash
export ANTHROPIC_API_KEY=your-key-here
```
then restart the server.

## Demoing the watch app (no Xcode needed)

With the backend running (see above), open
**http://localhost:8000/phone-static/watch-mock.html** in a second browser
tab. This is a watch-styled simulator of the real Swift app — same three
screens (Timestamps, Vitals, Dictation) — that hits the same backend API
the real watch relays through, so anything you do here shows up live on
the Phone App's Dashboard and Field Recording screen.

Click **+ New Demo Call**, then:
- **Timestamps** — tap through Dispatch, On Scene, Patient Contact, Transport, Hospital Arrival.
- **Vitals** — adjust BP/HR/SpO2/RR/GCS/glucose with the +/− steppers, then **Log Vitals**.
- **Dictation** — tap the mic. If your browser grants microphone access it transcribes live via the Web Speech API; otherwise (or if recognition fails/times out) it falls back to a scripted demo line after a few seconds, so the demo never gets stuck on "Listening...".

Click **Open Phone App ↗**, then open the new call from the Dashboard (it's
listed at the top) to see everything you just "captured" on the watch —
vitals and voice memos — already sitting in Field Recording, ready to layer
Scribble/Photo captures on top of before generating the narrative.

This is a stand-in for presentations, not the real product. The real
watchOS + iPhone relay app requires an actual build — see the next section.

## Building the real watch app

`watch_app/` contains the Swift source for the watchOS capture app and the
iPhone relay app, but **is not a buildable Xcode project by itself** — see
`watch_app/README.md` for how to drop these files into a new Xcode watchOS
project. This requires a Mac with Xcode and, to run on a physical Apple
Watch, an Apple Developer account.

## Deploying to Vercel

`vercel.json` routes every request to the single FastAPI app in
`backend/main.py` (including static asset requests, which the app already
serves itself via `StaticFiles`/`FileResponse` — no separate static
hosting setup needed).

1. Provision a Postgres database (Vercel Postgres, Neon, Supabase, etc. all
   work — for serverless, prefer a **pooled** connection string if your
   provider offers one, since each function invocation opens its own
   connection).
2. In the Vercel project settings, set the `DATABASE_URL` environment
   variable to that connection string. Optionally set `ANTHROPIC_API_KEY`
   too, for real AI narrative generation instead of the template fallback.
3. Run the schema + seed once against that same database from your machine
   (`DATABASE_URL=... python backend/seed_demo.py`), or call `init_db()` /
   hit any endpoint once — table creation is `CREATE TABLE IF NOT EXISTS`,
   so the first request against a fresh database creates the schema.
4. From the repo root: `vercel login` (interactive, opens a browser), then
   `vercel --prod`.

Note: `watch-mock.html` and the phone app both call the backend via
relative `fetch()` paths, so they work unmodified once deployed — no
hardcoded `localhost` URLs to change.

## Demo scenario

The seeded call follows the reference walkthrough in `CLAUDE.md`: a
58-year-old male with chest pain, from dispatch through hospital handoff —
starting with watch captures (timestamps, vitals, voice) and finishing with
the phone app's scribble/photo capture, AI-generated narrative review, and
signature sign-off.

## Current scope

This is a **prototype/demo**, not a production or HIPAA-certified tool.
See `CLAUDE.md` for what's deferred to later phases (EHR/CAD integration,
NEMSIS compliance, native iOS build of the phone app, etc.).
