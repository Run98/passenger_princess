"""
Seeds the database with the reference demo scenario from CLAUDE.md:
a single chest-pain call, walked start to finish.

Run:
    python seed_demo.py
"""
from database import init_db, get_conn

def seed():
    init_db()
    call_id = "demo1"

    with get_conn() as conn:
        # Reset any prior demo data so this is safely re-runnable.
        for table in ("dictations", "vitals", "timestamps", "calls"):
            conn.execute(f"DELETE FROM {table} WHERE call_id = ?" if table != "calls" else f"DELETE FROM {table} WHERE id = ?", (call_id,))

        conn.execute(
            "INSERT INTO calls (id, chief_complaint, patient_age, patient_sex) VALUES (?, ?, ?, ?)",
            (call_id, "chest pain", 58, "male"),
        )

        timestamps = [
            ("Dispatch", "2026-08-28T14:02:00"),
            ("On Scene", "2026-08-28T14:09:00"),
            ("Patient Contact", "2026-08-28T14:10:00"),
            ("Transport", "2026-08-28T14:22:00"),
            ("Hospital Arrival", "2026-08-28T14:38:00"),
        ]
        for label, ts in timestamps:
            conn.execute(
                "INSERT INTO timestamps (call_id, label, recorded_at) VALUES (?, ?, ?)",
                (call_id, label, ts),
            )

        conn.execute(
            "INSERT INTO vitals (call_id, bp, hr, spo2, rr, gcs, glucose) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (call_id, "150/95", 110, 94, 20, 15, 110),
        )

        dictations = [
            "58-year-old male, chief complaint chest pain, onset 20 minutes ago.",
            "Administered oxygen via nasal cannula at 4L/min, SpO2 improved following treatment.",
            "Administered 324mg aspirin PO per protocol, no adverse reaction noted.",
            "IV established in the right antecubital vein, 18-gauge, normal saline at TKO rate.",
        ]
        for text in dictations:
            conn.execute(
                "INSERT INTO dictations (call_id, text) VALUES (?, ?)",
                (call_id, text),
            )

    print(f"Seeded demo call '{call_id}'. Start the server and visit http://localhost:8000/report/{call_id}")


if __name__ == "__main__":
    seed()
