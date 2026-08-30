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

# Section labels per documentation style, in display order. "standard" is this
# app's original 3-section shape; SOAP and CHART are standard EMS
# documentation methods taught in some EMS systems for consistency across crews.
NARRATIVE_FORMATS = {
    "standard": ["Chief Complaint", "Assessment", "Treatment"],
    "soap": ["Subjective", "Objective", "Assessment", "Plan"],
    "chart": ["Chief Complaint", "History", "Assessment", "Rx (Treatment)", "Transport"],
}


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


def _demo_str(call: dict) -> str:
    age = call.get("patient_age")
    sex = call.get("patient_sex")
    demo_bits = [b for b in [f"{age}-year-old" if age else None, sex] if b]
    return " ".join(demo_bits) if demo_bits else "Patient"


def _timeline_bits(timestamps: list) -> list:
    ts_by_label = {t["label"]: t["recorded_at"] for t in timestamps}
    return [
        f"{label} at {ts_by_label[label]}"
        for label in TIMESTAMP_LABELS_ORDER
        if label in ts_by_label
    ]


def _vitals_line(vitals: list) -> str:
    if not vitals:
        return ""
    v = vitals[-1]
    vital_bits = []
    for key, fmt in [("bp", "BP {}"), ("hr", "HR {}"), ("spo2", "SpO2 {}%"),
                      ("rr", "RR {}"), ("gcs", "GCS {}"), ("glucose", "glucose {} mg/dL")]:
        if v.get(key) is not None:
            vital_bits.append(fmt.format(v[key]))
    return ("Vitals: " + ", ".join(vital_bits) + ".") if vital_bits else ""


def _assets_note(scribbles: list, photos: list) -> list:
    notes = []
    if scribbles:
        notes.append(f"{len(scribbles)} injury diagram(s)/scribble(s) attached for reference.")
    if photos:
        notes.append(f"{len(photos)} photo(s) attached for reference.")
    return notes


def build_structured_fallback(call: dict, timestamps: list, vitals: list, dictations: list,
                               scribbles: list, photos: list, format: str = "standard") -> dict:
    """
    Template-based fallback for the phone app's structured narrative, used
    when the AI call is unavailable/fails -- mirrors the "demo reliability
    over completeness" principle used for ghost-text. Returns a dict keyed
    by the section labels for the chosen format (see NARRATIVE_FORMATS).

    All formats draw on the same captured assets, split heuristically:
      - the patient's own chief complaint + first dictation reads as their
        reported history/subjective account
      - vitals + timeline read as objective/assessment data
      - remaining dictations are assumed to describe interventions/treatment
      - Transport-related timeline entries are called out separately for CHART
    """
    complaint = call.get("chief_complaint")
    demo_str = _demo_str(call)

    dictation_texts = [d["text"] for d in dictations]
    first_statement = dictation_texts[0] if dictation_texts else ""
    remaining_statements = dictation_texts[1:] if len(dictation_texts) > 1 else []

    history_line = f"{demo_str} patient, chief complaint of {complaint or 'unspecified complaint'}."
    if first_statement:
        history_line += f' Patient states: "{first_statement}"'

    timeline_bits = _timeline_bits(timestamps)
    vitals_line = _vitals_line(vitals)
    assets_notes = _assets_note(scribbles, photos)

    assessment_lines = []
    if timeline_bits:
        assessment_lines.append("Timeline: " + "; ".join(timeline_bits) + ".")
    if vitals_line:
        assessment_lines.append(vitals_line)
    assessment_lines.extend(assets_notes)
    assessment = " ".join(assessment_lines) or "No assessment details captured yet."

    treatment = " ".join(remaining_statements) or "No treatment details captured yet."

    if format == "soap":
        objective_lines = []
        if timeline_bits:
            objective_lines.append("Timeline: " + "; ".join(timeline_bits) + ".")
        if vitals_line:
            objective_lines.append(vitals_line)
        return {
            "Subjective": history_line,
            "Objective": " ".join(objective_lines) or "No objective data captured yet.",
            "Assessment": f"Clinical impression consistent with {complaint or 'reported complaint'}.",
            "Plan": treatment,
        }

    if format == "chart":
        transport_bits = [b for b in timeline_bits if b.startswith("Transport") or b.startswith("Hospital Arrival")]
        return {
            "Chief Complaint": f"{complaint or 'Unspecified complaint'}.",
            "History": history_line,
            "Assessment": assessment,
            "Rx (Treatment)": treatment,
            "Transport": ("; ".join(transport_bits) + ".") if transport_bits else "Transport details not yet recorded.",
        }

    # standard (default)
    return {
        "Chief Complaint": history_line,
        "Assessment": assessment,
        "Treatment": treatment,
    }
