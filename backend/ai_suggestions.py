"""
AI-powered inline ghost-text suggestions for the report narrative editor.

Uses the Claude API (Haiku, for low latency) to suggest a short continuation
of the sentence/paragraph the EMT is typing, using the call's context
(chief complaint, vitals, timestamps, dictated notes) so suggestions are
relevant to the specific patient rather than generic.

Falls back silently to a canned phrase bank if the API call fails or is slow,
per the "demo reliability over completeness" principle in CLAUDE.md.
"""
import os
import json
import asyncio
from phrase_bank import get_fallback_suggestion
from narrative import build_structured_fallback

MODEL = "claude-haiku-4-5-20251001"
TIMEOUT_SECONDS = 2.5
NARRATIVE_TIMEOUT_SECONDS = 6.0

_client = None


def _get_client():
    """Lazily create the Anthropic client so the app can run without a key
    (falling back to the phrase bank) for local demo/testing."""
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        try:
            import anthropic
            _client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            return None
    return _client


def _build_context_prompt(call_context: dict, current_text: str) -> str:
    parts = []
    if call_context.get("chief_complaint"):
        parts.append(f"Chief complaint: {call_context['chief_complaint']}")
    if call_context.get("vitals"):
        v = call_context["vitals"]
        vitals_str = ", ".join(f"{k.upper()}: {val}" for k, val in v.items() if val is not None)
        if vitals_str:
            parts.append(f"Latest vitals: {vitals_str}")
    if call_context.get("timestamps"):
        ts_str = ", ".join(f"{t['label']} at {t['recorded_at']}" for t in call_context["timestamps"])
        parts.append(f"Timeline: {ts_str}")
    if call_context.get("dictations"):
        parts.append("Dictated notes: " + " ".join(call_context["dictations"]))

    context_block = "\n".join(parts) if parts else "No additional call context available."

    return f"""You are helping an EMT write a patient care report narrative. \
Given the call context below and the sentence they've started typing, suggest \
a short, natural continuation (5-15 words) to complete the current sentence or \
clause. Use standard EMS documentation language. Do not repeat the text already \
typed. Respond with ONLY the suggested continuation text, no quotes, no explanation.

Call context:
{context_block}

Text typed so far:
"{current_text}"

Suggested continuation:"""


async def get_suggestion(current_text: str, call_context: dict) -> dict:
    """
    Returns {"suggestion": str, "source": "ai" | "fallback"}
    """
    if not current_text.strip():
        return {"suggestion": "", "source": "none"}

    client = _get_client()
    if client is not None:
        try:
            prompt = _build_context_prompt(call_context, current_text)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.messages.create,
                    model=MODEL,
                    max_tokens=40,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=TIMEOUT_SECONDS,
            )
            suggestion = response.content[0].text.strip().strip('"')
            if suggestion:
                return {"suggestion": suggestion, "source": "ai"}
        except Exception:
            # Any failure (timeout, API error, network) -> silent fallback
            pass

    return {"suggestion": get_fallback_suggestion(current_text), "source": "fallback"}


def _build_narrative_prompt(assets: dict) -> str:
    return f"""You are helping an EMT draft a patient care report from field-captured data. \
Given the assets below, produce a structured narrative with exactly three sections: \
chief_complaint, assessment, and treatment. Use standard EMS documentation language. \
Where you infer or paraphrase something not explicitly stated (e.g. converting a casual \
quote into clinical language, or inferring a timestamp), keep it clearly grounded in the \
provided data -- do not invent details that aren't supported by the assets.

Respond with ONLY a JSON object with exactly these keys: "chief_complaint", "assessment", \
"treatment". No markdown, no explanation, just the JSON object.

Patient: {assets.get('patient_age', '?')}-year-old {assets.get('patient_sex', '')}
Chief complaint (reported): {assets.get('chief_complaint', 'unspecified')}

Timeline: {assets.get('timeline', 'none recorded')}

Vitals readings: {assets.get('vitals', 'none recorded')}

Voice-dictated notes: {assets.get('dictations', 'none recorded')}

Other captured assets: {assets.get('scribbles_photos', 'none')}
"""


async def get_structured_narrative(call: dict, timestamps: list, vitals: list,
                                    dictations: list, scribbles: list, photos: list) -> dict:
    """
    Returns {"chief_complaint": str, "assessment": str, "treatment": str, "source": "ai"|"fallback"}
    Falls back to a template-based split if the AI call is unavailable or fails,
    per the "demo reliability over completeness" principle in CLAUDE.md.
    """
    client = _get_client()
    if client is not None:
        try:
            assets = {
                "patient_age": call.get("patient_age"),
                "patient_sex": call.get("patient_sex"),
                "chief_complaint": call.get("chief_complaint"),
                "timeline": "; ".join(f"{t['label']} at {t['recorded_at']}" for t in timestamps) or "none recorded",
                "vitals": "; ".join(
                    ", ".join(f"{k.upper()}: {v}" for k, v in row.items() if v is not None and k != "recorded_at")
                    for row in vitals
                ) or "none recorded",
                "dictations": " | ".join(d["text"] for d in dictations) or "none recorded",
                "scribbles_photos": f"{len(scribbles)} scribble(s), {len(photos)} photo(s)",
            }
            prompt = _build_narrative_prompt(assets)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.messages.create,
                    model=MODEL,
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=NARRATIVE_TIMEOUT_SECONDS,
            )
            raw = response.content[0].text.strip()
            # Strip accidental markdown code fences if the model adds them
            if raw.startswith("```"):
                raw = raw.strip("`")
                raw = raw[raw.find("{"):raw.rfind("}") + 1]
            parsed = json.loads(raw)
            if all(k in parsed for k in ("chief_complaint", "assessment", "treatment")):
                parsed["source"] = "ai"
                return parsed
        except Exception:
            pass

    fallback = build_structured_fallback(call, timestamps, vitals, dictations, scribbles, photos)
    fallback["source"] = "fallback"
    return fallback
