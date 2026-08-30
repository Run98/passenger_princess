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
import json
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
from ai_suggestions import get_suggestion, get_structured_narrative

app = FastAPI(title="EMT Report Assistant (Demo)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only -- not for production
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
PHONE_DIR = BASE_DIR.parent / "phone_app"


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


class ScribbleIn(BaseModel):
    image_data: str  # base64-encoded PNG
    caption: str | None = ""


class PhotoIn(BaseModel):
    image_data: str  # base64-encoded image
    caption: str | None = ""


class SignatureIn(BaseModel):
    signer_name: str
    image_data: str  # base64-encoded PNG


class NarrativeIn(BaseModel):
    narrative: str
    finalized: bool = False


class StructuredNarrativeIn(BaseModel):
    format: str
    sections: dict[str, str]


class ArchiveIn(BaseModel):
    archived: bool


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
        # Archived (curated) examples surface first, so a reviewer opening
        # the Dashboard sees them immediately rather than having to hunt
        # through scratch/test calls.
        rows = conn.execute(
            "SELECT id, chief_complaint, patient_age, patient_sex, status, finalized, archived, created_at "
            "FROM calls ORDER BY archived DESC, created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def _get_call_or_404(call_id: str, conn):
    row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Call not found")
    return dict(row)


@app.put("/api/calls/{call_id}/archive")
def set_archived(call_id: str, body: ArchiveIn):
    """Mark/unmark a call as a curated example (see database.py's schema
    comment on the archived column)."""
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        conn.execute("UPDATE calls SET archived = ? WHERE id = ?", (int(body.archived), call_id))
    return {"status": "ok"}


@app.delete("/api/calls/{call_id}")
def delete_call(call_id: str):
    """Scrap a scratch/test call and everything captured under it."""
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        for table in ("dictations", "vitals", "timestamps", "scribbles", "photos", "signatures"):
            conn.execute(f"DELETE FROM {table} WHERE call_id = ?", (call_id,))
        conn.execute("DELETE FROM calls WHERE id = ?", (call_id,))
    return {"status": "ok"}


@app.get("/api/calls/{call_id}")
def get_call(call_id: str):
    with get_conn() as conn:
        call = _get_call_or_404(call_id, conn)
        timestamps = [dict(r) for r in conn.execute(
            "SELECT label, recorded_at FROM timestamps WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall()]
        vitals = [dict(r) for r in conn.execute(
            "SELECT id, bp, hr, spo2, rr, gcs, glucose, recorded_at FROM vitals WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall()]
        dictations = [dict(r) for r in conn.execute(
            "SELECT id, text, recorded_at FROM dictations WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall()]
        scribbles = [dict(r) for r in conn.execute(
            "SELECT id, image_data, caption, recorded_at FROM scribbles WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall()]
        photos = [dict(r) for r in conn.execute(
            "SELECT id, image_data, caption, recorded_at FROM photos WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall()]
        signature = conn.execute(
            "SELECT signer_name, image_data, signed_at FROM signatures WHERE call_id = ? ORDER BY signed_at DESC LIMIT 1", (call_id,)
        ).fetchone()
        return {
            "call": call, "timestamps": timestamps, "vitals": vitals, "dictations": dictations,
            "scribbles": scribbles, "photos": photos,
            "signature": dict(signature) if signature else None,
        }


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


@app.post("/api/calls/{call_id}/scribbles")
def add_scribble(call_id: str, scribble: ScribbleIn):
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        conn.execute(
            "INSERT INTO scribbles (call_id, image_data, caption) VALUES (?, ?, ?)",
            (call_id, scribble.image_data, scribble.caption or ""),
        )
    return {"status": "ok"}


@app.post("/api/calls/{call_id}/photos")
def add_photo(call_id: str, photo: PhotoIn):
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        conn.execute(
            "INSERT INTO photos (call_id, image_data, caption) VALUES (?, ?, ?)",
            (call_id, photo.image_data, photo.caption or ""),
        )
    return {"status": "ok"}


@app.post("/api/calls/{call_id}/signature")
def add_signature(call_id: str, sig: SignatureIn):
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        conn.execute(
            "INSERT INTO signatures (call_id, signer_name, image_data) VALUES (?, ?, ?)",
            (call_id, sig.signer_name, sig.image_data),
        )
        conn.execute("UPDATE calls SET status = 'signed' WHERE id = ?", (call_id,))
    return {"status": "ok"}


@app.get("/api/calls/{call_id}/assets")
def get_assets(call_id: str):
    """Unified, chronological list of every captured item for the
    Field Recording (populated) screen -- voice memos, vitals readings,
    scribbles, and photos, each individually listed and counted."""
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        items = []
        for i, row in enumerate(conn.execute(
            "SELECT id, text, recorded_at FROM dictations WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall(), start=1):
            items.append({"type": "voice", "id": row["id"], "index": i, "label": f"Voice memo {i}",
                          "detail": row["text"], "recorded_at": row["recorded_at"]})
        for i, row in enumerate(conn.execute(
            "SELECT id, bp, hr, spo2, rr, gcs, glucose, recorded_at FROM vitals WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall(), start=1):
            row = dict(row)
            detail = ", ".join(f"{k.upper()}: {v}" for k, v in row.items() if v is not None and k not in ("recorded_at", "id"))
            items.append({"type": "vitals", "id": row["id"], "index": i, "label": f"Vitals {i}",
                          "detail": detail, "recorded_at": row["recorded_at"]})
        for i, row in enumerate(conn.execute(
            "SELECT id, caption, recorded_at FROM scribbles WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall(), start=1):
            items.append({"type": "scribble", "id": row["id"], "index": i, "label": f"Scribble {i}",
                          "detail": row["caption"] or "injury diagram", "recorded_at": row["recorded_at"]})
        for i, row in enumerate(conn.execute(
            "SELECT id, caption, recorded_at FROM photos WHERE call_id = ? ORDER BY recorded_at", (call_id,)
        ).fetchall(), start=1):
            items.append({"type": "photo", "id": row["id"], "index": i, "label": f"Photo {i}",
                          "detail": row["caption"] or "photo", "recorded_at": row["recorded_at"]})
        items.sort(key=lambda x: x["recorded_at"])
        return items


@app.delete("/api/calls/{call_id}/assets/{asset_type}/{asset_id}")
def delete_asset(call_id: str, asset_type: str, asset_id: int):
    """Remove a single captured item (vitals reading, voice memo, scribble,
    or photo) without deleting the whole call."""
    table = {"voice": "dictations", "vitals": "vitals", "scribble": "scribbles", "photo": "photos"}.get(asset_type)
    if table is None:
        raise HTTPException(status_code=400, detail="Unknown asset type")
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        conn.execute(f"DELETE FROM {table} WHERE id = ? AND call_id = ?", (asset_id, call_id))
    return {"status": "ok"}


@app.put("/api/calls/{call_id}/dictations/{dictation_id}")
def edit_dictation(call_id: str, dictation_id: int, body: DictationIn):
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        conn.execute("UPDATE dictations SET text = ? WHERE id = ? AND call_id = ?", (body.text, dictation_id, call_id))
    return {"status": "ok"}


@app.put("/api/calls/{call_id}/vitals/{vitals_id}")
def edit_vitals(call_id: str, vitals_id: int, body: VitalsIn):
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        conn.execute(
            "UPDATE vitals SET bp = ?, hr = ?, spo2 = ?, rr = ?, gcs = ?, glucose = ? WHERE id = ? AND call_id = ?",
            (body.bp, body.hr, body.spo2, body.rr, body.gcs, body.glucose, vitals_id, call_id),
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


@app.post("/api/calls/{call_id}/generate-narrative")
async def generate_narrative(call_id: str, format: str = "standard"):
    """Phone app: generate the structured narrative from every captured
    asset so far, in the chosen documentation style (see
    narrative.NARRATIVE_FORMATS -- standard/SOAP/CHART)."""
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
        scribbles = [dict(r) for r in conn.execute(
            "SELECT id FROM scribbles WHERE call_id = ?", (call_id,)
        ).fetchall()]
        photos = [dict(r) for r in conn.execute(
            "SELECT id FROM photos WHERE call_id = ?", (call_id,)
        ).fetchall()]

    result = await get_structured_narrative(call, timestamps, vitals, dictations, scribbles, photos, format=format)

    with get_conn() as conn:
        conn.execute(
            "UPDATE calls SET narrative_format = ?, narrative_sections = ?, "
            "narrative_generated = 1, status = 'in_review' WHERE id = ?",
            (result["format"], json.dumps(result["sections"]), call_id),
        )
    return result


@app.put("/api/calls/{call_id}/structured-narrative")
def save_structured_narrative(call_id: str, body: StructuredNarrativeIn):
    """Phone app: save EMT edits to the structured narrative sections."""
    with get_conn() as conn:
        _get_call_or_404(call_id, conn)
        conn.execute(
            "UPDATE calls SET narrative_format = ?, narrative_sections = ? WHERE id = ?",
            (body.format, json.dumps(body.sections), call_id),
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

app.mount("/phone-static", StaticFiles(directory=str(PHONE_DIR / "static")), name="phone-static")


@app.get("/")
def index():
    # Demo2 scope: the phone app is the sole review/capture UI (no separate web app).
    return FileResponse(str(PHONE_DIR / "index.html"))


@app.get("/phone")
def phone_app():
    return FileResponse(str(PHONE_DIR / "index.html"))
