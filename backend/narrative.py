"""
Auto-draft narrative generation.

Assembles a first-pass patient care report narrative from captured
timestamps, vitals, and dictated voice notes -- so the EMT starts from a
draft rather than a blank page. This is a simple template-based assembly
for the demo, not an AI-authored narrative (the AI is used for ghost-text
suggestions during editing, see ai_suggestions.py).
"""

TIMESTAMP_LABELS_ORDER = [
    "Dispatch",
    "On Scene",
    "Patient Contact",
    "Transport",
    "Hospital Arrival",
]


def build_draft_narrative(call: dict, timestamps: list, vitals: list, dictations: list) -> str:
    lines = []

    # Opening line: patient demographics + chief complaint
    age = call.get("patient_age")
    sex = call.get("patient_sex")
    complaint = call.get("chief_complaint")
    demo_bits = []
    if age:
        demo_bits.append(f"{age}-year-old")
    if sex:
        demo_bits.append(sex)
    demo_str = " ".join(demo_bits) if demo_bits else "Patient"
    opening = f"{demo_str} patient"
    if complaint:
        opening += f", chief complaint of {complaint}."
    else:
        opening += "."
    lines.append(opening)

    # Timeline
    ts_by_label = {t["label"]: t["recorded_at"] for t in timestamps}
    timeline_bits = [
        f"{label} at {ts_by_label[label]}"
        for label in TIMESTAMP_LABELS_ORDER
        if label in ts_by_label
    ]
    if timeline_bits:
        lines.append("Timeline: " + "; ".join(timeline_bits) + ".")

    # Dictated notes (voice-captured in the field)
    for d in dictations:
        lines.append(d["text"])

    # Vitals (most recent set)
    if vitals:
        v = vitals[-1]
        vital_bits = []
        if v.get("bp"):
            vital_bits.append(f"BP {v['bp']}")
        if v.get("hr") is not None:
            vital_bits.append(f"HR {v['hr']}")
        if v.get("spo2") is not None:
            vital_bits.append(f"SpO2 {v['spo2']}%")
        if v.get("rr") is not None:
            vital_bits.append(f"RR {v['rr']}")
        if v.get("gcs") is not None:
            vital_bits.append(f"GCS {v['gcs']}")
        if v.get("glucose") is not None:
            vital_bits.append(f"glucose {v['glucose']} mg/dL")
        if vital_bits:
            lines.append("Vitals: " + ", ".join(vital_bits) + ".")

    return "\n\n".join(lines)


def build_structured_fallback(call: dict, timestamps: list, vitals: list, dictations: list,
                               scribbles: list, photos: list) -> dict:
    """
    Template-based fallback for the phone app's structured (3-section)
    narrative, used when the AI call is unavailable/fails -- mirrors the
    "demo reliability over completeness" principle used for ghost-text.

    Splits captured assets heuristically:
      - chief_complaint: patient demographics + chief complaint + first dictation
      - assessment: vitals + timeline + any scribble/photo references
      - treatment: remaining dictations (assumed to describe interventions)
    """
    age = call.get("patient_age")
    sex = call.get("patient_sex")
    complaint = call.get("chief_complaint")
    demo_bits = [b for b in [f"{age}-year-old" if age else None, sex] if b]
    demo_str = " ".join(demo_bits) if demo_bits else "Patient"

    dictation_texts = [d["text"] for d in dictations]
    first_statement = dictation_texts[0] if dictation_texts else ""
    remaining_statements = dictation_texts[1:] if len(dictation_texts) > 1 else []

    chief_complaint = f"{demo_str} patient, chief complaint of {complaint or 'unspecified complaint'}."
    if first_statement:
        chief_complaint += f' Patient states: "{first_statement}"'

    ts_by_label = {t["label"]: t["recorded_at"] for t in timestamps}
    timeline_bits = [
        f"{label} at {ts_by_label[label]}"
        for label in TIMESTAMP_LABELS_ORDER
        if label in ts_by_label
    ]
    assessment_lines = []
    if timeline_bits:
        assessment_lines.append("Timeline: " + "; ".join(timeline_bits) + ".")
    if vitals:
        v = vitals[-1]
        vital_bits = []
        for key, fmt in [("bp", "BP {}"), ("hr", "HR {}"), ("spo2", "SpO2 {}%"),
                          ("rr", "RR {}"), ("gcs", "GCS {}"), ("glucose", "glucose {} mg/dL")]:
            if v.get(key) is not None:
                vital_bits.append(fmt.format(v[key]))
        if vital_bits:
            assessment_lines.append("Vitals: " + ", ".join(vital_bits) + ".")
    if scribbles:
        assessment_lines.append(f"{len(scribbles)} injury diagram(s)/scribble(s) attached for reference.")
    if photos:
        assessment_lines.append(f"{len(photos)} photo(s) attached for reference.")
    assessment = " ".join(assessment_lines) or "No assessment details captured yet."

    treatment = " ".join(remaining_statements) or "No treatment details captured yet."

    return {
        "chief_complaint": chief_complaint,
        "assessment": assessment,
        "treatment": treatment,
    }
