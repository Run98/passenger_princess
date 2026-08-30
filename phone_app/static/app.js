// Phone App - demo frontend matching the 5-screen mockup:
// Dashboard -> Field Recording (empty/populated) -> Prelim Report -> Approve & Sign

const state = {
  callId: null,
  recognition: null,
  isRecording: false,
  lastTranscript: "",
  lastPhotoDataUrl: null,
  reportFormat: "standard",
};

const ASSET_ICONS = { voice: "🎙️", vitals: "❤️", scribble: "✏️", photo: "📷" };

const screens = {
  dashboard: document.getElementById("screen-dashboard"),
  recording: document.getElementById("screen-recording"),
  report: document.getElementById("screen-report"),
  sign: document.getElementById("screen-sign"),
};

function showScreen(name, title) {
  Object.values(screens).forEach(s => s.classList.remove("active"));
  screens[name].classList.add("active");
  document.getElementById("header-title").textContent = title;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API error ${res.status} on ${path}`);
  return res.json();
}

// ---------- Dashboard ----------

async function loadDashboard() {
  showScreen("dashboard", "Field Reports");
  const calls = await api("/api/calls");
  const listEl = document.getElementById("call-list");
  listEl.innerHTML = "";
  for (const call of calls) {
    const card = document.createElement("div");
    card.className = "call-card";
    const statusLabel = { draft: "Draft", in_review: "In Review", signed: "Signed" }[call.status] || call.status;
    card.innerHTML = `
      <div>
        <div class="title">Call ${call.id}</div>
        <div class="subtitle">${call.chief_complaint || "no complaint set"}</div>
      </div>
      <span class="status-pill status-${call.status}">${statusLabel}</span>
    `;
    card.addEventListener("click", () => openCall(call.id));
    listEl.appendChild(card);
  }
}

document.getElementById("new-call-btn").addEventListener("click", async () => {
  const { call_id } = await api("/api/calls", {
    method: "POST",
    body: JSON.stringify({ chief_complaint: "chest pain", patient_age: 58, patient_sex: "male" }),
  });
  openCall(call_id);
});

// ---------- Field Recording ----------

async function openCall(callId) {
  state.callId = callId;
  showScreen("recording", `Call #${callId}`);
  await refreshAssets();
}

async function refreshAssets() {
  const assets = await api(`/api/calls/${state.callId}/assets`);
  const listEl = document.getElementById("asset-list");
  const genBtn = document.getElementById("generate-narrative-btn");
  genBtn.disabled = assets.length === 0;

  if (assets.length === 0) {
    listEl.innerHTML = `
      <div class="empty-state">
        <div class="plus-circle">+</div>
        <p>No content yet.</p>
        <p class="hint">Use a button above to add your first voice memo, scribble, vitals reading, or photo.</p>
      </div>`;
    return;
  }

  listEl.innerHTML = assets.map(a => `
    <div class="asset-card">
      <div class="asset-icon ${a.type}">${ASSET_ICONS[a.type]}</div>
      <div>
        <div class="asset-label">${a.label}</div>
        <div class="asset-detail">${(a.detail || "").slice(0, 60)}</div>
      </div>
    </div>
  `).join("");
}

document.getElementById("back-to-dashboard-btn").addEventListener("click", loadDashboard);

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function renderReportSections(format, sections) {
  state.reportFormat = format;
  const container = document.getElementById("report-sections-container");
  container.innerHTML = "";
  for (const [label, text] of Object.entries(sections)) {
    const section = document.createElement("div");
    section.className = "report-section";
    section.innerHTML = `
      <h3>${escapeHtml(label)}</h3>
      <div class="ai-flag">✨ AI-drafted, tap to edit</div>
      <textarea class="report-textarea" data-section-label="${escapeHtml(label)}"></textarea>
    `;
    section.querySelector("textarea").value = text;
    container.appendChild(section);
  }
}

function gatherReportSections() {
  const sections = {};
  document.querySelectorAll("#report-sections-container .report-textarea").forEach(ta => {
    sections[ta.dataset.sectionLabel] = ta.value;
  });
  return sections;
}

document.getElementById("generate-narrative-btn").addEventListener("click", async () => {
  const btn = document.getElementById("generate-narrative-btn");
  const format = document.getElementById("narrative-format-select").value;
  btn.disabled = true;
  btn.textContent = "Generating...";
  try {
    const result = await api(`/api/calls/${state.callId}/generate-narrative?format=${format}`, { method: "POST" });
    renderReportSections(result.format, result.sections);
    showScreen("report", "Prelim Report");
  } finally {
    btn.textContent = "Generate PCR Narrative";
    btn.disabled = false;
  }
});

// ---------- Capture modals ----------

const overlay = document.getElementById("modal-overlay");
const modals = {
  voice: document.getElementById("modal-voice"),
  scribble: document.getElementById("modal-scribble"),
  vitals: document.getElementById("modal-vitals"),
  photo: document.getElementById("modal-photo"),
};

function openModal(name) {
  overlay.classList.add("active");
  Object.values(modals).forEach(m => m.classList.remove("active"));
  modals[name].classList.add("active");
  if (name === "scribble") setupScribbleCanvas();
}

function closeModal() {
  overlay.classList.remove("active");
  Object.values(modals).forEach(m => m.classList.remove("active"));
  resetModals();
}

function resetModals() {
  document.getElementById("voice-transcript").textContent = "";
  document.getElementById("voice-transcript").style.display = "";
  document.getElementById("voice-fallback-input").value = "";
  document.getElementById("voice-fallback-input").style.display = "none";
  document.getElementById("voice-record-btn").style.display = "";
  document.getElementById("voice-status").textContent = "Tap the mic to start speaking.";
  document.getElementById("save-voice-btn").disabled = true;
  document.getElementById("photo-preview").style.display = "none";
  document.getElementById("photo-input").value = "";
  document.getElementById("save-photo-btn").disabled = true;
  ["v-sys", "v-dia", "v-hr", "v-spo2", "v-rr", "v-gcs", "v-glucose"].forEach(id => {
    document.getElementById(id).value = "";
  });
  state.lastTranscript = "";
  state.lastPhotoDataUrl = null;
  if (state.isRecording) stopVoiceRecording();
}

document.querySelectorAll(".capture-btn").forEach(btn => {
  btn.addEventListener("click", () => openModal(btn.dataset.capture));
});
document.querySelectorAll("[data-close-modal]").forEach(btn => {
  btn.addEventListener("click", closeModal);
});

// --- Vitals ---

function numOrNull(id) {
  const raw = document.getElementById(id).value.trim();
  return raw === "" ? null : Number(raw);
}

document.getElementById("save-vitals-btn").addEventListener("click", async () => {
  const sys = document.getElementById("v-sys").value.trim();
  const dia = document.getElementById("v-dia").value.trim();
  await api(`/api/calls/${state.callId}/vitals`, {
    method: "POST",
    body: JSON.stringify({
      bp: (sys || dia) ? `${sys}/${dia}` : null,
      hr: numOrNull("v-hr"),
      spo2: numOrNull("v-spo2"),
      rr: numOrNull("v-rr"),
      gcs: numOrNull("v-gcs"),
      glucose: numOrNull("v-glucose"),
    }),
  });
  closeModal();
  await refreshAssets();
});

// --- Voice (Web Speech API -- browser equivalent of on-device dictation) ---

function getRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return null;
  const recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-US";
  return recognition;
}

function showTypeFallback(message) {
  if (state.isRecording) stopVoiceRecording();
  document.getElementById("voice-status").textContent = message;
  document.getElementById("voice-transcript").style.display = "none";
  document.getElementById("voice-record-btn").style.display = "none";
  document.getElementById("voice-fallback-input").style.display = "block";
}

function startVoiceRecording() {
  const recognition = getRecognition();
  const btn = document.getElementById("voice-record-btn");
  const status = document.getElementById("voice-status");
  const transcriptEl = document.getElementById("voice-transcript");

  if (!recognition) {
    showTypeFallback("Speech recognition isn't supported in this browser (try Chrome). You can type instead:");
    return;
  }

  state.recognition = recognition;
  state.isRecording = true;
  btn.classList.add("recording");
  status.textContent = "Listening...";

  recognition.onresult = (event) => {
    let transcript = "";
    for (let i = 0; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    state.lastTranscript = transcript;
    transcriptEl.textContent = transcript;
    document.getElementById("save-voice-btn").disabled = !transcript.trim();
  };
  recognition.onerror = () => {
    stopVoiceRecording();
    showTypeFallback("Couldn't access the microphone. You can type instead:");
  };
  try {
    recognition.start();
  } catch (e) {
    // start() can throw synchronously (e.g. mic permission denied) --
    // never leave the modal stuck with no way forward.
    state.isRecording = false;
    btn.classList.remove("recording");
    showTypeFallback("Couldn't start speech recognition. You can type instead:");
  }
}

function stopVoiceRecording() {
  if (state.recognition) state.recognition.stop();
  state.isRecording = false;
  document.getElementById("voice-record-btn").classList.remove("recording");
  document.getElementById("voice-status").textContent = "Tap the mic to start speaking.";
}

document.getElementById("voice-record-btn").addEventListener("click", () => {
  if (state.isRecording) stopVoiceRecording();
  else startVoiceRecording();
});

document.getElementById("voice-type-instead-btn").addEventListener("click", () => {
  showTypeFallback("Type your notes:");
});

document.getElementById("voice-fallback-input").addEventListener("input", (e) => {
  state.lastTranscript = e.target.value;
  document.getElementById("save-voice-btn").disabled = !e.target.value.trim();
});

document.getElementById("save-voice-btn").addEventListener("click", async () => {
  if (!state.lastTranscript.trim()) return;
  await api(`/api/calls/${state.callId}/dictations`, {
    method: "POST",
    body: JSON.stringify({ text: state.lastTranscript.trim() }),
  });
  closeModal();
  await refreshAssets();
});

// --- Scribble (canvas drawing) ---

let scribbleCtx, scribbleDrawing = false;

function setupScribbleCanvas() {
  const canvas = document.getElementById("scribble-canvas");
  canvas.width = canvas.clientWidth;
  canvas.height = canvas.clientHeight;
  scribbleCtx = canvas.getContext("2d");
  scribbleCtx.fillStyle = "#fff";
  scribbleCtx.fillRect(0, 0, canvas.width, canvas.height);
  scribbleCtx.strokeStyle = "#7c6bf0";
  scribbleCtx.lineWidth = 3;
  scribbleCtx.lineCap = "round";

  const pos = (e) => {
    const rect = canvas.getBoundingClientRect();
    const point = e.touches ? e.touches[0] : e;
    return { x: point.clientX - rect.left, y: point.clientY - rect.top };
  };

  const start = (e) => { scribbleDrawing = true; const p = pos(e); scribbleCtx.beginPath(); scribbleCtx.moveTo(p.x, p.y); };
  const move = (e) => {
    if (!scribbleDrawing) return;
    e.preventDefault();
    const p = pos(e);
    scribbleCtx.lineTo(p.x, p.y);
    scribbleCtx.stroke();
  };
  const end = () => { scribbleDrawing = false; };

  canvas.onmousedown = start; canvas.onmousemove = move; canvas.onmouseup = end; canvas.onmouseleave = end;
  canvas.ontouchstart = start; canvas.ontouchmove = move; canvas.ontouchend = end;
}

document.getElementById("clear-scribble-btn").addEventListener("click", () => {
  const canvas = document.getElementById("scribble-canvas");
  scribbleCtx.fillStyle = "#fff";
  scribbleCtx.fillRect(0, 0, canvas.width, canvas.height);
});

document.getElementById("save-scribble-btn").addEventListener("click", async () => {
  const canvas = document.getElementById("scribble-canvas");
  const imageData = canvas.toDataURL("image/png");
  await api(`/api/calls/${state.callId}/scribbles`, {
    method: "POST",
    body: JSON.stringify({ image_data: imageData, caption: "injury diagram" }),
  });
  closeModal();
  await refreshAssets();
});

// --- Photo ---

document.getElementById("photo-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    state.lastPhotoDataUrl = reader.result;
    const preview = document.getElementById("photo-preview");
    preview.src = reader.result;
    preview.style.display = "block";
    document.getElementById("save-photo-btn").disabled = false;
  };
  reader.readAsDataURL(file);
});

document.getElementById("save-photo-btn").addEventListener("click", async () => {
  if (!state.lastPhotoDataUrl) return;
  await api(`/api/calls/${state.callId}/photos`, {
    method: "POST",
    body: JSON.stringify({ image_data: state.lastPhotoDataUrl, caption: "field photo" }),
  });
  closeModal();
  await refreshAssets();
});

// ---------- Report review & edit ----------

document.getElementById("save-report-btn").addEventListener("click", async () => {
  await api(`/api/calls/${state.callId}/structured-narrative`, {
    method: "PUT",
    body: JSON.stringify({ format: state.reportFormat, sections: gatherReportSections() }),
  });
});

document.getElementById("continue-to-sign-btn").addEventListener("click", async () => {
  await api(`/api/calls/${state.callId}/structured-narrative`, {
    method: "PUT",
    body: JSON.stringify({ format: state.reportFormat, sections: gatherReportSections() }),
  });
  showScreen("sign", "Approve & Sign");
  setupSignatureCanvas();
});

// ---------- Signature ----------

let sigCtx, sigDrawing = false, sigHasContent = false;

function setupSignatureCanvas() {
  const canvas = document.getElementById("signature-canvas");
  canvas.width = canvas.clientWidth;
  canvas.height = canvas.clientHeight;
  sigCtx = canvas.getContext("2d");
  sigCtx.strokeStyle = "#1c1e21";
  sigCtx.lineWidth = 2.5;
  sigCtx.lineCap = "round";
  sigHasContent = false;
  document.getElementById("signature-placeholder").style.display = "block";

  const pos = (e) => {
    const rect = canvas.getBoundingClientRect();
    const point = e.touches ? e.touches[0] : e;
    return { x: point.clientX - rect.left, y: point.clientY - rect.top };
  };
  const start = (e) => {
    sigDrawing = true;
    document.getElementById("signature-placeholder").style.display = "none";
    const p = pos(e); sigCtx.beginPath(); sigCtx.moveTo(p.x, p.y);
  };
  const move = (e) => {
    if (!sigDrawing) return;
    e.preventDefault();
    sigHasContent = true;
    const p = pos(e);
    sigCtx.lineTo(p.x, p.y);
    sigCtx.stroke();
  };
  const end = () => { sigDrawing = false; };

  canvas.onmousedown = start; canvas.onmousemove = move; canvas.onmouseup = end; canvas.onmouseleave = end;
  canvas.ontouchstart = start; canvas.ontouchmove = move; canvas.ontouchend = end;
}

document.getElementById("clear-signature-btn").addEventListener("click", () => {
  const canvas = document.getElementById("signature-canvas");
  sigCtx.clearRect(0, 0, canvas.width, canvas.height);
  sigHasContent = false;
  document.getElementById("signature-placeholder").style.display = "block";
});

document.getElementById("submit-signature-btn").addEventListener("click", async () => {
  if (!sigHasContent) {
    alert("Please sign before submitting.");
    return;
  }
  const canvas = document.getElementById("signature-canvas");
  const imageData = canvas.toDataURL("image/png");
  await api(`/api/calls/${state.callId}/signature`, {
    method: "POST",
    body: JSON.stringify({ signer_name: "EMT on duty", image_data: imageData }),
  });
  await loadDashboard();
});

// ---------- Init ----------

loadDashboard();
