# Passenger Princess — EMT Report Assistant (Demo 2: Watch + Phone App)

A demo app showing how EMTs could write patient care reports faster: an
Apple Watch app for hands-free field capture, and a phone app that both
captures richer field data and is where the EMT reviews the AI-drafted
narrative and signs off. See `CLAUDE.md` for the full design rationale and
scope. This demo drops the standalone web app from the earlier version —
the phone app is now the sole review/sign-off surface.

## What's in this repo

```
backend/            FastAPI server, SQLite storage, structured AI narrative generation
phone_app/           Phone app frontend (Dashboard -> Field Recording -> Prelim Report -> Approve & Sign)
watch_app/           Swift source scaffold for the watchOS app + iPhone relay app
requirements.txt     Python dependencies
CLAUDE.md            Project design doc / build guide
```

## Running the demo (backend + browser)

This is the part you can run right now without any Apple hardware.

```bash
pip install -r requirements.txt --break-system-packages   # or use a venv
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

## Building the watch app

`watch_app/` contains the Swift source for the watchOS capture app and the
iPhone relay app, but **is not a buildable Xcode project by itself** — see
`watch_app/README.md` for how to drop these files into a new Xcode watchOS
project. This requires a Mac with Xcode and, to run on a physical Apple
Watch, an Apple Developer account.

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
