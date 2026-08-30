"""
Auto-draft narrative generation.

Assembles a first-pass patient care report narrative from captured
timestamps, vitals, and dictated voice notes -- so the EMT starts from a
draft rather than a blank page. This is a simple template-based assembly
for the demo, not an AI-authored narrative (the AI is used for ghost-text
suggestions during editing, see ai_suggestions.py).

Supports multiple documentation styles (see NARRATIVE_FORMATS): the app's
original free-form "standard" narrative, plus SOAP and CHART, which are
standard methods taught in some EMS systems to keep documentation
consistent across a crew. All styles draw on the same captured data --
only how it's organized into the single narrative textarea differs.
"""

TIMESTAMP_LABELS_ORDER = [
    "Dispatch",
    "On Scene",
    "Patient Contact",
    "Transport",
    "Hospital Arrival",
]

NARRATIVE_FORMATS = {
    "standard": "Standard",
    "soap": "SOAP",
    "chart": "CHART",
}


def _demo_str(call: dict) -> str:
    age = call.get("patient_age")
    sex = call.get("patient_sex")
    demo_bits = []
    if age:
        demo_bits.append(f"{age}-year-old")
    if sex:
        demo_bits.append(sex)
    return " ".join(demo_bits) if demo_bits else "Patient"


def _opening_line(call: dict) -> str:
    complaint = call.get("chief_complaint")
    opening = f"{_demo_str(call)} patient"
    if complaint:
        opening += f", chief complaint of {complaint}."
    else:
        opening += "."
    return opening


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
    return ("Vitals: " + ", ".join(vital_bits) + ".") if vital_bits else ""


def _build_standard(call: dict, timestamps: list, vitals: list, dictations: list) -> str:
    lines = [_opening_line(call)]

    timeline_bits = _timeline_bits(timestamps)
    if timeline_bits:
        lines.append("Timeline: " + "; ".join(timeline_bits) + ".")

    for d in dictations:
        lines.append(d["text"])

    vitals_line = _vitals_line(vitals)
    if vitals_line:
        lines.append(vitals_line)

    return "\n\n".join(lines)


def _build_soap(call: dict, timestamps: list, vitals: list, dictations: list) -> str:
    complaint = call.get("chief_complaint")
    lines = []

    subjective = _opening_line(call)
    for d in dictations:
        subjective += " " + d["text"]
    lines.append("Subjective: " + subjective)

    timeline_bits = _timeline_bits(timestamps)
    vitals_line = _vitals_line(vitals)
    objective_bits = []
    if timeline_bits:
        objective_bits.append("Timeline: " + "; ".join(timeline_bits) + ".")
    if vitals_line:
        objective_bits.append(vitals_line)
    lines.append("Objective: " + (" ".join(objective_bits) if objective_bits else "No objective data captured yet."))

    lines.append(f"Assessment: Clinical impression consistent with {complaint or 'reported complaint'}.")

    transport_bits = [b for b in timeline_bits if b.startswith("Transport") or b.startswith("Hospital Arrival")]
    plan = ("; ".join(transport_bits) + ".") if transport_bits else "Care per protocol; transport pending."
    lines.append("Plan: " + plan)

    return "\n\n".join(lines)


def _build_chart(call: dict, timestamps: list, vitals: list, dictations: list) -> str:
    complaint = call.get("chief_complaint")
    lines = [f"Chief Complaint: {complaint or 'Unspecified complaint'}."]

    history = _opening_line(call)
    for d in dictations:
        history += " " + d["text"]
    lines.append("History: " + history)

    timeline_bits = _timeline_bits(timestamps)
    vitals_line = _vitals_line(vitals)
    assessment_bits = []
    if timeline_bits:
        assessment_bits.append("Timeline: " + "; ".join(timeline_bits) + ".")
    if vitals_line:
        assessment_bits.append(vitals_line)
    lines.append("Assessment: " + (" ".join(assessment_bits) if assessment_bits else "No assessment details captured yet."))

    transport_bits = [b for b in timeline_bits if b.startswith("Transport") or b.startswith("Hospital Arrival")]
    lines.append("Transport: " + (("; ".join(transport_bits) + ".") if transport_bits else "Details not yet recorded."))

    return "\n\n".join(lines)


def build_draft_narrative(call: dict, timestamps: list, vitals: list, dictations: list,
                           format: str = "standard") -> str:
    if format == "soap":
        return _build_soap(call, timestamps, vitals, dictations)
    if format == "chart":
        return _build_chart(call, timestamps, vitals, dictations)
    return _build_standard(call, timestamps, vitals, dictations)
