# EMT Report Assistant — Project Guide

## Overview

A demo application showing how EMTs could complete patient care reports (PCRs) faster and with less friction, using an Apple Watch app for hands-free field capture and a web app for report review and finalization. This is a **prototype/demo**, not a production tool for a real EMS agency — the goal is to show the concept end-to-end, not to meet real-world compliance or integration requirements.

## Architecture

Two components:

1. **watchOS app (paired with iPhone)** — capture-only. No editing, review, or report assembly happens here. Captures voice, timestamps, and vitals, queues them locally, and relays through the paired iPhone companion app to the backend when connectivity is available.
2. **Web app** — receives synced data, auto-generates a draft narrative, and is where the EMT reviews, edits (via typing with AI ghost-text suggestions or further voice notes), and finalizes the report.

Data flows one direction for capture (watch → iPhone → backend) and the web app is the sole place for report review/editing.

### Sync / transport details

- **Watch → iPhone**: Bluetooth via Apple's Watch Connectivity framework (this is automatic/default and does not depend on internet access at all).
- **iPhone → backend**: normally wifi/cellular, offline-first (queues locally, syncs when connectivity returns). For demo reliability, also support a **direct Bluetooth connection from the iPhone to the machine running the backend** as a fallback — this lets the whole demo run without depending on venue wifi or any external internet connection.

## Tech Stack

- **Backend**: Python, FastAPI (async, so AI suggestion calls and sync don't block the UI)
- **Database**: SQLite (demo-appropriate; not a production-scale choice)
- **Watch/iPhone app**: Native watchOS + iOS (Swift), paired app relaying to the FastAPI backend
- **Speech-to-text**: Apple's on-device Speech framework (free, offline-capable, no cloud dependency — chosen for demo reliability). *Future upgrade path: Deepgram Nova-3 Medical, if this moves beyond demo/prototype, for better clinical vocabulary accuracy.*
- **AI text suggestions**: Claude API (Haiku, for low latency) generating context-aware inline ghost-text suggestions as the EMT types in the web app
- **Auth**: None for this demo (single-user, no login flow)

## Core Features (V1 / Demo Scope)

### Watch app (capture-only, minimal UI — few buttons, large tap targets)
- Voice dictation: single tap to start/stop recording; transcribed on-device via Apple's Speech framework
- One-tap event timestamps: dispatch, on-scene, patient contact, transport, hospital arrival
- Vitals quick-entry: BP, HR, SpO2, RR, GCS, blood glucose — fast tap/Digital Crown entry, not typing
- Offline-first: all captures queue locally on the paired iPhone and sync to the backend once connectivity is available

### Web app
- Receives synced captures (transcribed text, timestamps, vitals) from the watch/iPhone
- **Auto-drafts a narrative** from the captured data (vitals, timestamps, dictated notes) in standard EMS report structure
- **Typing input option** with **AI-powered inline ghost-text suggestions** (like Smart Compose):
  - Suggestions generated via Claude API (Haiku), using call context (chief complaint, vitals entered so far, timestamps, existing narrative) so predictions are relevant to the specific patient/call
  - Accept suggestion via Tab (or swipe)
  - Fallback: if the API call is slow or fails, silently fall back to a small canned EMS phrase bank so the demo never visibly breaks
- EMT reviews and edits the full report here before finalizing

## Deferred to Later Phases (explicitly out of scope for demo)

- EHR/CAD system integration
- NEMSIS compliance / real EMS agency data standards
- Barcode/photo capture (scene photos, medication barcodes)
- Digital signature capture (patient refusal/consent)
- Cloud medical-grade speech-to-text (Deepgram Nova-3 Medical)
- Multi-user auth, roles, permissions
- Production-scale database (Postgres, etc.)

## Demo Scenario (reference walkthrough)

A single end-to-end EMS call, used to demo every core feature in one story:

1. **Dispatch received** — EMT taps "Dispatch" timestamp on watch.
2. **On scene** — taps "On Scene" timestamp.
3. **Patient contact** — EMT dictates via voice: "58-year-old male, chief complaint chest pain, onset 20 minutes ago." Watch transcribes on-device, syncs text to app.
4. **Vitals entered** on watch: BP 150/95, HR 110, SpO2 94%, RR 20.
5. **Treatment** — EMT dictates or types (using ghost-text) on web app: oxygen administered, aspirin given, IV established.
6. **Transport / hospital arrival** — timestamps tapped on watch.
7. **Web app review** — EMT opens the web app, sees the auto-drafted narrative built from all captured data, refines a sentence using AI ghost-text suggestions, reviews the full report, and finalizes it.

This scenario should be the basis for any demo build, sample data, or walkthrough script.

## Design Principles

- **Minimal watch UI**: as few buttons/screens as possible. The watch is for capture in the field under time pressure, not data review.
- **Separation of concerns**: watch/iPhone = capture only; web app = review, editing, and finalization only.
- **Demo reliability over completeness**: prefer approaches that work offline and don't depend on live APIs during a presentation (on-device STT, fallback phrase bank) over more "accurate" but fragile cloud-dependent approaches.
- **HIPAA-minded, not HIPAA-certified**: use reasonable data handling practices (avoid unnecessary exposure of patient data, don't hardcode real PHI in samples) without treating this as a compliant production system.
