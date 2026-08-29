# EMT Report Assistant — Project Guide (Demo 2: Watch + Phone App)

## Overview

A demo application showing how EMTs could complete patient care reports (PCRs) faster: an Apple Watch app for hands-free field capture, and a phone app that both captures richer field data and is where the EMT reviews the AI-drafted narrative and signs off. This is a **prototype/demo**, not a production tool for a real EMS agency.

This is **demo2**, a revised scope from the original demo1: the standalone web app has been dropped. The phone app is now the sole review/edit/sign-off surface — there is no separate web interface in this version.

## Architecture

Two components:

1. **watchOS app (paired with iPhone)** — capture-only. No editing, review, or report assembly happens here. Captures voice, timestamps, and vitals, queues them locally, and relays through the paired iPhone app to the backend when connectivity is available.
2. **Phone app** — both a richer field-capture surface (voice, scribble/injury diagrams, vitals, photos) and the sole place the EMT reviews the AI-drafted structured narrative and signs off. Based on a collaborator's mockup: five screens — Dashboard → Field Recording (empty) → Field Recording (populated) → Prelim Report (review & edit) → Approve & Sign.

Both the watch and the phone app talk to the same Python/FastAPI backend. The watch relays through the phone's Watch Connectivity link (Bluetooth); the phone app talks to the backend directly over HTTP.

### Sync / transport details

- **Watch → iPhone**: Bluetooth via Apple's Watch Connectivity framework (automatic/default, no internet dependency).
- **iPhone (watch relay) → backend**: normally wifi/cellular, offline-first (queues locally, syncs when connectivity returns). For demo reliability, also support a **direct Bluetooth connection from the iPhone to the machine running the backend** as a fallback, so the whole demo can run without venue wifi.
- **Phone app → backend**: direct HTTP calls (same backend as above); no separate relay needed since the phone app *is* the phone.

## Tech Stack

- **Backend**: Python, FastAPI (async, so AI narrative generation doesn't block the UI)
- **Database**: SQLite (demo-appropriate; not a production-scale choice)
- **Watch app**: Native watchOS (Swift), paired with an iPhone relay app
- **Phone app**: for this demo, built as a mobile-styled web app (HTML/CSS/JS) served by the same FastAPI backend, so it's runnable and demoable without an Xcode build. A native Swift/SwiftUI version is the eventual target (see "Native phone app" below) but is not required for this demo to function.
- **Speech-to-text**: Apple's on-device Speech framework on the watch; the phone app's demo build uses the browser's Web Speech API (Chrome) as a stand-in for on-device dictation, since it's running as a web app for now. Both are free and don't depend on a cloud STT service.
- **AI narrative generation**: Claude API (Haiku) generates the structured narrative (chief complaint / assessment / treatment) from all captured assets. Falls back to a template-based split if the API is unavailable or fails, so the demo never visibly breaks.
- **Auth**: None for this demo (single-user, no login flow)

## Core Features (Demo 2 Scope)

### Watch app (capture-only, minimal UI — few buttons, large tap targets)
- Voice dictation: single tap to start/stop recording; transcribed on-device via Apple's Speech framework
- One-tap event timestamps: dispatch, on-scene, patient contact, transport, hospital arrival
- Vitals quick-entry: BP, HR, SpO2, RR, GCS, blood glucose — fast tap/Digital Crown entry, not typing
- Offline-first: all captures queue locally on the paired iPhone and sync to the backend once connectivity is available

### Phone app (five-screen flow, mockup-driven)
1. **Dashboard** — list of past field reports/calls with status (Draft / In Review / Signed), "+ New Field Interaction" button.
2. **Field Recording (empty)** — four capture buttons (Voice, Scribble, Vitals, Photo); "Generate PCR Narrative" stays visible but disabled until at least one asset exists.
3. **Field Recording (populated)** — every captured asset listed individually and chronologically (e.g. "Voice memo 1," "Vitals 1," "Scribble 1 — injury diagram," "Photo 1"); each capture type can be added more than once per call.
4. **Prelim Report (review & edit)** — AI-generated narrative structured into three sections (Chief Complaint / Assessment / Treatment), each flagged "AI-drafted, tap to edit" so the EMT knows what to double-check before editing. Falls back to a template-based split if AI generation fails.
5. **Approve & Sign** — draw-to-sign signature pad plus an explicit accountability statement ("By signing, I confirm this report accurately reflects care provided") before final submission. The EMT, not the model, is accountable for the final record.

Capture types on the phone app:
- **Voice**: dictation (Web Speech API in this demo build; on-device Speech framework in the eventual native app)
- **Scribble**: freehand drawing capture (e.g. injury diagrams) via a canvas-based drawing tool
- **Vitals**: quick-entry form (BP, HR, SpO2, RR, GCS, glucose)
- **Photo**: image capture (e.g. monitor strips) via the device camera/file picker

## Native Phone App (future direction, not required for this demo)

The mockup implies a native iOS app eventually. When that's pursued, the same
five-screen flow and capture types apply, built in SwiftUI, using:
- `Speech` framework for on-device voice dictation (same as the watch)
- `PencilKit` or a custom `UIView`/Canvas for the scribble/injury-diagram capture
- `UIImagePickerController` / `PHPickerViewController` for photo capture
- `PKCanvasView` or a custom drawing view for the signature pad
- The same FastAPI backend and endpoints used by this demo's web-based phone app, so no backend changes would be needed to swap the frontend for a native one.

## Deferred to Later Phases (explicitly out of scope for this demo)

- EHR/CAD system integration
- NEMSIS compliance / real EMS agency data standards
- Barcode capture (medication barcodes specifically)
- Per-EMT narrative style personalization (the mockup's "Formatted to match Jordan Ramirez's usual narrative style")
- Cloud medical-grade speech-to-text (Deepgram Nova-3 Medical)
- Multi-user auth, roles, permissions
- Production-scale database (Postgres, etc.)
- Native iOS/SwiftUI build of the phone app (web-based demo build is the current target; see "Native Phone App" above)
- Standalone web app for desk/office review (dropped from this demo's scope; the phone app is now the sole review/sign-off surface)

## Demo Scenario (reference walkthrough)

A single end-to-end EMS call, used to demo every core feature in one story:

1. **Dispatch received** — EMT taps "Dispatch" timestamp on watch.
2. **On scene** — taps "On Scene" timestamp.
3. **Patient contact** — EMT dictates via voice on the watch: "58-year-old male, chief complaint chest pain, onset 20 minutes ago." Watch transcribes on-device, syncs text to the backend via the iPhone relay.
4. **Vitals entered** on watch: BP 150/95, HR 110, SpO2 94%, RR 20.
5. **Treatment** — EMT switches to the phone app to add a Scribble (injury diagram) and a Photo (monitor strip), and dictates additional treatment notes via Voice on the phone: oxygen administered, aspirin given, IV established.
6. **Transport / hospital arrival** — timestamps tapped on watch.
7. **Phone app review** — EMT opens the phone app's Dashboard, opens the call, taps "Generate PCR Narrative" to see the AI-structured report (Chief Complaint / Assessment / Treatment), edits a sentence, then proceeds to Approve & Sign, draws a signature, and submits.

This scenario should be the basis for any demo build, sample data, or walkthrough script.

## Design Principles

- **Minimal watch UI**: as few buttons/screens as possible. The watch is for capture in the field under time pressure, not data review.
- **Phone app is both capture and review**: unlike the watch, the phone app is where the EMT can also review, edit, and finalize the report — it's the sole review surface in this demo scope.
- **Demo reliability over completeness**: prefer approaches that work offline and don't depend on live APIs during a presentation (on-device/browser STT, fallback narrative template) over more "accurate" but fragile cloud-dependent approaches.
- **EMT accountability, not AI authority**: AI-drafted content is always visually flagged and editable; the EMT signs off, not the model.
- **HIPAA-minded, not HIPAA-certified**: use reasonable data handling practices (avoid unnecessary exposure of patient data, don't hardcode real PHI in samples) without treating this as a compliant production system.
