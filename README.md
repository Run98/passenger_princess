# Passenger Princess — EMT Report Assistant (Demo v1)

A demo app showing how EMTs could write patient care reports faster: an
Apple Watch app for hands-free field capture, and a web app for reviewing
and finalizing the report with AI-assisted writing. See `CLAUDE.md` for the
full design rationale and scope.

## What's in this repo

```
backend/                       FastAPI server, SQLite storage, auto-draft narrative, AI ghost-text suggestions
web/                            Web frontend (report review + editor UI)
web/static/watch-mock.html      Browser-based watch app simulator (see below) -- no Xcode needed
watch_app/                      Swift source scaffold for the real watchOS app + iPhone relay app
requirements.txt                Python dependencies
CLAUDE.md                       Project design doc / build guide
```

## Running the web demo (backend + browser)

This is the part you can run right now without any Apple hardware.

```bash
pip install -r requirements.txt --break-system-packages   # or use a venv
cd backend
python seed_demo.py          # loads the reference chest-pain demo call
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000/** in a browser. Select the seeded demo
call, click **Load Auto-Draft** to see the narrative assembled from the
captured vitals/timestamps/dictation, then try typing in the narrative box —
a gray suggestion should appear inline; press **Tab** to accept it.

### Enabling real AI suggestions

Without an API key, ghost-text suggestions fall back automatically to a
canned EMS phrase bank (`backend/phrase_bank.py`) — the demo still works,
just with simpler suggestions. To get real context-aware AI suggestions:

```bash
export ANTHROPIC_API_KEY=your-key-here
```
then restart the server.

## Demoing the watch app (no Xcode needed)

With the backend running (see above), open
**http://localhost:8000/static/watch-mock.html** in a second browser tab.
This is a watch-styled simulator of the real Swift app — same three
screens (Timestamps, Vitals, Dictation) — that hits the same backend API
a paired iPhone would, so anything you do here shows up live in the web
report.

Click **+ New Demo Call**, then:
- **Timestamps** — tap through Dispatch, On Scene, Patient Contact, Transport, Hospital Arrival.
- **Vitals** — adjust BP/HR/SpO2/RR/GCS/glucose with the +/− steppers, then **Log Vitals**.
- **Dictation** — tap the mic. If your browser grants microphone access it transcribes live via the Web Speech API; otherwise (or if recognition fails/times out) it falls back to a scripted demo line after a few seconds, so the demo never gets stuck on "Listening...".

Click **Open Web Report ↗** at any point to see the call you just built in
the real web app — click **Load Auto-Draft** there to watch the narrative
assemble from what was just "captured."

This is a stand-in for presentations, not the real product. The real
watchOS + iPhone relay app requires an actual build — see the next section.

## Building the real watch app

`watch_app/` contains the Swift source for the watchOS capture app and the
iPhone relay app, but **is not a buildable Xcode project by itself** — see
`watch_app/README.md` for how to drop these files into a new Xcode watchOS
project. This requires a Mac with Xcode and, to run on a physical Apple
Watch, an Apple Developer account.

## Demo scenario

The seeded call (and the watch simulator's default "New Demo Call") follows
the reference walkthrough in `CLAUDE.md`: a 58-year-old male with chest
pain, from dispatch through hospital handoff, exercising every core
feature (timestamps, vitals, voice dictation, auto-draft, AI ghost-text
editing) in one story.

## Current scope

This is a **prototype/demo**, not a production or HIPAA-certified tool.
See `CLAUDE.md` for what's deferred to later phases (EHR/CAD integration,
NEMSIS compliance, signatures, etc.).
