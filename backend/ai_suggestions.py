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
import asyncio
from phrase_bank import get_fallback_suggestion

MODEL = "claude-haiku-4-5-20251001"
TIMEOUT_SECONDS = 2.5

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
