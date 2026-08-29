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
