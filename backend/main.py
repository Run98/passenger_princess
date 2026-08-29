"""
EMT Report Assistant - demo backend (FastAPI)

Receives captures relayed from the paired iPhone app (timestamps, vitals,
voice-dictated text), auto-drafts a narrative, and serves the web report
editor with AI-powered ghost-text suggestions.

Run locally:
    pip install -r requirements.txt
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Set ANTHROPIC_API_KEY in the environment to enable real AI suggestions;
without it, suggestions fall back to the canned phrase bank automatically.
"""
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Vercel's Python runtime imports this file directly without adding its
# directory to sys.path (unlike `uvicorn main:app` run from inside
# backend/), so the sibling-module imports below would otherwise fail.
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import init_db, get_conn
from narrative import build_draft_narrative
from ai_suggestions import get_suggestion

app = FastAPI(title="EMT Report Assistant (Demo)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only -- not for production
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
WEB_DIR = BASE_DIR.parent / "web"


@app.on_event("startup")
def on_startup():
    init_db()


# ---------- Schemas ----------

class NewCall(BaseModel):
    chief_complaint: str | None = None
    patient_age: int | None = None
    patient_sex: str | None = None


class TimestampIn(BaseModel):
    label: str  # e.g. "Dispatch", "On Scene", "Patient Contact", "Transport", "Hospital Arrival"
    recorded_at: str | None = None  # ISO string; defaults to now if omitted


class VitalsIn(BaseModel):
    bp: str | None = None
    hr: int | None = None
    spo2: int | None = None
    rr: int | None = None
    gcs: int | None = None
    glucose: int | None = None


class DictationIn(BaseModel):
    text: str


class NarrativeIn(BaseModel):
    narrative: str
    finalized: bool = False


class SuggestionIn(BaseModel):
    call_id: str
    current_text: str


# ---------- Call lifecycle ----------

@app.post("/api/calls")
def create_call(call: NewCall):
    call_id = str(uuid.uuid4())[:8]
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO calls (id, chief_complaint, patient_age, patient_sex) VALUES (?, ?, ?, ?)",
            (call_id, call.chief_complaint, call.patient_age, call.patient_sex),
        )
    return {"call_id": call_id}


@app.get("/api/calls")
def list_calls():
    with get_conn() as conn:
        rows = conn.execute("SELECT id, chief_complaint, patient_age, patient_sex, finalized, created_at FROM calls ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def _get_call_or_404(call_id: str, conn):
    row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Call not found")
    return dict(row)


@app.get("/api/calls/{call_id}")
def get_call(call_id: str):
    with get_conn() as conn:
        call = _get_call_or_404(call_id, conn)
        timestamps = [dict(r) for r in conn.execute(
            "SELECT label, recorded_at FROM timestamps WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall()]
        vitals = [dict(r) for r in conn.execute(
            "SELECT bp, hr, spo2, rr, gcs, glucose, recorded_at FROM vitals WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall()]
        dictations = [dict(r) for r in conn.execute(
            "SELECT text, recorded_at FROM dictations WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall()]
        return {"call": call, "timestamps": timestamps, "vitals": vitals, "dictations": dictations}


# ---------- Capture endpoints (called by the iPhone relay app) ----------

@app.post("/api/calls/{call_id}/timestamps")
def add_timestamp(call_id: str, ts: TimestampIn):
    recorded_at = ts.recorded_at or datetime.utcnow().isoformat()
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        conn.execute(
            "INSERT INTO timestamps (call_id, label, recorded_at) VALUES (?, ?, ?)",
            (call_id, ts.label, recorded_at),
        )
    return {"status": "ok"}


@app.post("/api/calls/{call_id}/vitals")
def add_vitals(call_id: str, vitals: VitalsIn):
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        conn.execute(
            "INSERT INTO vitals (call_id, bp, hr, spo2, rr, gcs, glucose) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (call_id, vitals.bp, vitals.hr, vitals.spo2, vitals.rr, vitals.gcs, vitals.glucose),
        )
    return {"status": "ok"}


@app.post("/api/calls/{call_id}/dictations")
def add_dictation(call_id: str, dictation: DictationIn):
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        conn.execute(
            "INSERT INTO dictations (call_id, text) VALUES (?, ?)",
            (call_id, dictation.text),
        )
    return {"status": "ok"}


# ---------- Narrative draft + editing ----------

@app.get("/api/calls/{call_id}/draft")
def get_draft(call_id: str):
    with get_conn() as conn:
        call = _get_call_or_404(call_id, conn)
        timestamps = [dict(r) for r in conn.execute(
            "SELECT label, recorded_at FROM timestamps WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall()]
        vitals = [dict(r) for r in conn.execute(
            "SELECT bp, hr, spo2, rr, gcs, glucose FROM vitals WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall()]
        dictations = [dict(r) for r in conn.execute(
            "SELECT text FROM dictations WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall()]
    draft = build_draft_narrative(call, timestamps, vitals, dictations)
    return {"draft": draft}


@app.put("/api/calls/{call_id}/narrative")
def save_narrative(call_id: str, body: NarrativeIn):
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        conn.execute(
            "UPDATE calls SET narrative = ?, finalized = ? WHERE id = ?",
            (body.narrative, int(body.finalized), call_id),
        )
    return {"status": "ok"}


# ---------- AI ghost-text suggestions ----------

@app.post("/api/suggest")
async def suggest(body: SuggestionIn):
    with get_conn() as conn:
        call = _get_call_or_404(body.call_id, conn)
        timestamps = [dict(r) for r in conn.execute(
            "SELECT label, recorded_at FROM timestamps WHERE call_id = ? ORDER BY recorded_at", (body.call_id,)
        ).fetchall()]
        vitals_rows = [dict(r) for r in conn.execute(
            "SELECT bp, hr, spo2, rr, gcs, glucose FROM vitals WHERE call_id = ? ORDER BY recorded_at", (body.call_id,)
        ).fetchall()]
        dictations = [r["text"] for r in conn.execute(
            "SELECT text FROM dictations WHERE call_id = ? ORDER BY recorded_at", (body.call_id,)
        ).fetchall()]

    call_context = {
        "chief_complaint": call.get("chief_complaint"),
        "vitals": vitals_rows[-1] if vitals_rows else {},
        "timestamps": timestamps,
        "dictations": dictations,
    }

    result = await get_suggestion(body.current_text, call_context)
    return result


# ---------- Serve the web frontend ----------

app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.get("/")
def index():
    return FileResponse(str(WEB_DIR / "index.html"))


@app.get("/report/{call_id}")
def report_page(call_id: str):
    return FileResponse(str(WEB_DIR / "index.html"))
