# Passenger Princess — EMT Report Assistant (Demo v1)

A demo app showing how EMTs could write patient care reports faster: an
Apple Watch app for hands-free field capture, and a web app for reviewing
and finalizing the report with AI-assisted writing. See `CLAUDE.md` for the
full design rationale and scope.

## What's in this repo

```
backend/            FastAPI server, SQLite storage, auto-draft narrative, AI ghost-text suggestions
web/                 Web frontend (report review + editor UI)
watch_app/           Swift source scaffold for the watchOS app + iPhone relay app
requirements.txt     Python dependencies
CLAUDE.md            Project design doc / build guide
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

## Building the watch app

`watch_app/` contains the Swift source for the watchOS capture app and the
iPhone relay app, but **is not a buildable Xcode project by itself** — see
`watch_app/README.md` for how to drop these files into a new Xcode watchOS
project. This requires a Mac with Xcode and, to run on a physical Apple
Watch, an Apple Developer account.

## Demo scenario

The seeded call follows the reference walkthrough in `CLAUDE.md`: a
58-year-old male with chest pain, from dispatch through hospital handoff,
exercising every core feature (timestamps, vitals, voice dictation,
auto-draft, AI ghost-text editing) in one story.

## Current scope

This is a **prototype/demo**, not a production or HIPAA-certified tool.
See `CLAUDE.md` for what's deferred to later phases (EHR/CAD integration,
NEMSIS compliance, signatures, etc.).
