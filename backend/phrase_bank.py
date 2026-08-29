"""
Canned EMS phrase bank — used as a fallback for ghost-text suggestions
if the AI suggestion call is slow or fails, so the demo never visibly breaks.

Keyed loosely by keywords found in the text typed so far. This is intentionally
simple (substring match) since it's a safety net, not the primary suggestion path.
"""

PHRASE_BANK = [
    ("chest pain", "Patient reports chest pain radiating to the left arm, onset approximately 20 minutes prior to EMS arrival."),
    ("short of breath", "Patient reports shortness of breath, worsening over the past hour, no relief with rest."),
    ("oxygen", "Administered oxygen via nasal cannula at 4L/min, SpO2 improved following treatment."),
    ("aspirin", "Administered 324mg aspirin PO per protocol, no adverse reaction noted."),
    ("iv", "IV established in the right antecubital vein, 18-gauge, normal saline at TKO rate."),
    ("nausea", "Patient reports nausea, denies vomiting, administered antiemetic per protocol."),
    ("fall", "Patient found on the ground following a witnessed fall, denies loss of consciousness."),
    ("unresponsive", "Patient found unresponsive, airway patent, breathing spontaneously."),
    ("transport", "Patient transported to the receiving facility without incident, vitals stable throughout transport."),
    ("refused", "Patient alert and oriented x4, refused transport against medical advice, refusal form signed."),
    ("allergic", "No known drug allergies reported by patient."),
    ("pain scale", "Patient rates pain 7 out of 10 on the numeric pain scale."),
]

DEFAULT_SUGGESTION = "Patient assessed, vitals within normal limits, no acute distress noted."


def get_fallback_suggestion(current_text: str) -> str:
    """Return a canned phrase suggestion based on simple keyword matching."""
    lowered = current_text.lower()
    for keyword, phrase in PHRASE_BANK:
        if keyword in lowered and phrase.lower() not in lowered:
            return phrase
    return DEFAULT_SUGGESTION
