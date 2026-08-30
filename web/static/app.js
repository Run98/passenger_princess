// EMT Report Assistant - demo frontend
// Handles call selection, auto-draft loading, and inline AI ghost-text suggestions.

const state = {
  callId: null,
  currentSuggestion: "",
  suggestTimer: null,
};

const els = {
  callSelect: document.getElementById("call-select"),
  newCallBtn: document.getElementById("new-call-btn"),
  summary: document.getElementById("summary-content"),
  textarea: document.getElementById("narrative-text"),
  ghostOverlay: document.getElementById("ghost-overlay"),
  suggestionSource: document.getElementById("suggestion-source"),
  loadDraftBtn: document.getElementById("load-draft-btn"),
  saveBtn: document.getElementById("save-btn"),
  finalizeBtn: document.getElementById("finalize-btn"),
  saveStatus: document.getElementById("save-status"),
};

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API error ${res.status} on ${path}`);
  return res.json();
}

async function refreshCallList(selectId) {
  const calls = await api("/api/calls");
  els.callSelect.innerHTML = "";
  for (const call of calls) {
    const opt = document.createElement("option");
    opt.value = call.id;
    opt.textContent = `${call.id} — ${call.chief_complaint || "no complaint set"}`;
    els.callSelect.appendChild(opt);
  }
  if (calls.length) {
    els.callSelect.value = selectId || calls[0].id;
    await loadCall(els.callSelect.value);
  }
}

async function loadCall(callId) {
  state.callId = callId;
  const data = await api(`/api/calls/${callId}`);
  renderSummary(data);
  els.textarea.value = data.call.narrative || "";
  renderGhost("");
}

function renderSummary(data) {
  const { call, timestamps, vitals } = data;
  const lastVitals = vitals[vitals.length - 1] || {};
  const tsStr = timestamps.map(t => `${t.label} (${t.recorded_at})`).join(", ") || "none yet";
  const vitalsStr = Object.entries(lastVitals)
    .filter(([k, v]) => v !== null && k !== "recorded_at")
    .map(([k, v]) => `${k.toUpperCase()}: ${v}`)
    .join(", ") || "none yet";

  els.summary.innerHTML = `
    <div class="row"><span class="label">Patient:</span>${call.patient_age || "?"} ${call.patient_sex || ""}</div>
    <div class="row"><span class="label">Chief complaint:</span>${call.chief_complaint || "—"}</div>
    <div class="row"><span class="label">Timeline:</span>${tsStr}</div>
    <div class="row"><span class="label">Latest vitals:</span>${vitalsStr}</div>
  `;
}

async function loadDraft() {
  if (!state.callId) return;
  const format = document.getElementById("narrative-format-select").value;
  const { draft } = await api(`/api/calls/${state.callId}/draft?format=${format}`);
  els.textarea.value = draft;
  renderGhost("");
}

async function saveNarrative(finalize = false) {
  if (!state.callId) return;
  await api(`/api/calls/${state.callId}/narrative`, {
    method: "PUT",
    body: JSON.stringify({ narrative: els.textarea.value, finalized: finalize }),
  });
  els.saveStatus.textContent = finalize
    ? "Report finalized and saved."
    : `Saved at ${new Date().toLocaleTimeString()}.`;
}

// ---- Ghost-text suggestion logic ----

function renderGhost(suggestion) {
  state.currentSuggestion = suggestion;
  const typed = escapeHtml(els.textarea.value);
  const ghost = suggestion ? `<span class="ghost">${escapeHtml(suggestion)}</span>` : "";
  els.ghostOverlay.innerHTML = typed + ghost;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function fetchSuggestion() {
  if (!state.callId) return;
  const currentText = els.textarea.value;
  if (!currentText.trim()) {
    renderGhost("");
    return;
  }
  try {
    const { suggestion, source } = await api("/api/suggest", {
      method: "POST",
      body: JSON.stringify({ call_id: state.callId, current_text: currentText }),
    });
    // Only show if the textarea hasn't changed since the request was made
    if (els.textarea.value === currentText) {
      renderGhost(suggestion);
      els.suggestionSource.textContent = suggestion
        ? (source === "ai" ? "AI suggestion (Tab to accept)" : "Suggested phrase (Tab to accept)")
        : "";
    }
  } catch (e) {
    // Fail silently -- ghost text is a nice-to-have, never block typing
    console.warn("Suggestion fetch failed", e);
  }
}

function onInput() {
  renderGhost(""); // clear stale suggestion immediately on new input
  els.suggestionSource.textContent = "";
  clearTimeout(state.suggestTimer);
  state.suggestTimer = setTimeout(fetchSuggestion, 400); // debounce
}

function onKeydown(e) {
  if (e.key === "Tab" && state.currentSuggestion) {
    e.preventDefault();
    const needsSpace = els.textarea.value && !els.textarea.value.endsWith(" ") && !els.textarea.value.endsWith("\n");
    els.textarea.value += (needsSpace ? " " : "") + state.currentSuggestion;
    renderGhost("");
    els.suggestionSource.textContent = "";
    els.textarea.focus();
  }
}

function syncScroll() {
  els.ghostOverlay.scrollTop = els.textarea.scrollTop;
}

// ---- Wire up events ----

els.textarea.addEventListener("input", onInput);
els.textarea.addEventListener("keydown", onKeydown);
els.textarea.addEventListener("scroll", syncScroll);
els.callSelect.addEventListener("change", (e) => loadCall(e.target.value));
els.loadDraftBtn.addEventListener("click", loadDraft);
els.saveBtn.addEventListener("click", () => saveNarrative(false));
els.finalizeBtn.addEventListener("click", () => saveNarrative(true));
els.newCallBtn.addEventListener("click", async () => {
  const complaint = prompt("Chief complaint for this new call (e.g. diabetic emergency, opioid overdose, heart attack):");
  if (complaint === null) return; // cancelled
  const ageRaw = prompt("Patient age (optional):");
  const sex = prompt("Patient sex (male/female/other, optional):");
  const { call_id } = await api("/api/calls", {
    method: "POST",
    body: JSON.stringify({
      chief_complaint: complaint.trim() || "unspecified complaint",
      patient_age: ageRaw && ageRaw.trim() ? Number(ageRaw.trim()) : null,
      patient_sex: sex && sex.trim() ? sex.trim() : null,
    }),
  });
  await refreshCallList(call_id);
});

refreshCallList();
