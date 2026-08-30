// EMT Report Assistant - demo frontend
// Handles call selection, auto-draft loading, and inline AI ghost-text suggestions.

const state = {
  callId: null,
  currentSuggestion: "",
  suggestTimer: null,
  calls: [],
};

const els = {
  callSelect: document.getElementById("call-select"),
  newCallBtn: document.getElementById("new-call-btn"),
  archiveToggleBtn: document.getElementById("archive-toggle-btn"),
  deleteCallBtn: document.getElementById("delete-call-btn"),
  summary: document.getElementById("summary-content"),
  capturedList: document.getElementById("captured-list"),
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

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function formatTimestamp(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

async function refreshCallList(selectId) {
  const calls = await api("/api/calls");
  state.calls = calls;
  els.callSelect.innerHTML = "";
  for (const call of calls) {
    const opt = document.createElement("option");
    opt.value = call.id;
    const prefix = call.archived ? "📌 " : "";
    opt.textContent = `${prefix}${call.id} — ${call.chief_complaint || "no complaint set"}`;
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
  renderCapturedList(data);
  els.textarea.value = data.call.narrative || "";
  renderGhost("");
  updateArchiveButton();
}

function updateArchiveButton() {
  const call = state.calls.find(c => c.id === state.callId);
  const archived = !!(call && call.archived);
  els.archiveToggleBtn.textContent = archived ? "📌" : "☆";
  els.archiveToggleBtn.title = archived ? "Remove from examples" : "Archive as example";
  els.archiveToggleBtn.classList.toggle("archived", archived);
}

function renderSummary(data) {
  const { call, timestamps, vitals } = data;
  const lastVitals = vitals[vitals.length - 1] || {};
  const tsStr = timestamps.map(t => `${t.label} (${formatTimestamp(t.recorded_at)})`).join(", ") || "none yet";
  const vitalsStr = Object.entries(lastVitals)
    .filter(([k, v]) => v !== null && k !== "recorded_at" && k !== "id")
    .map(([k, v]) => `${k.toUpperCase()}: ${v}`)
    .join(", ") || "none yet";

  els.summary.innerHTML = `
    <div class="row"><span class="label">Patient:</span>${call.patient_age || "?"} ${call.patient_sex || ""}</div>
    <div class="row"><span class="label">Chief complaint:</span>${call.chief_complaint || "—"}</div>
    <div class="row"><span class="label">Timeline:</span>${tsStr}</div>
    <div class="row"><span class="label">Latest vitals:</span>${vitalsStr}</div>
  `;
}

function renderCapturedList(data) {
  const { timestamps, vitals, dictations } = data;
  const rows = [];

  for (const t of timestamps) {
    rows.push({ type: "timestamps", id: t.id, label: t.label, detail: "", recorded_at: t.recorded_at, editable: false });
  }
  for (const [i, v] of vitals.entries()) {
    const detail = Object.entries(v)
      .filter(([k, val]) => val !== null && k !== "recorded_at" && k !== "id")
      .map(([k, val]) => `${k.toUpperCase()}: ${val}`)
      .join(", ");
    rows.push({ type: "vitals", id: v.id, label: `Vitals ${i + 1}`, detail, recorded_at: v.recorded_at, editable: true });
  }
  for (const [i, d] of dictations.entries()) {
    rows.push({ type: "dictations", id: d.id, label: `Voice memo ${i + 1}`, detail: d.text, recorded_at: d.recorded_at, editable: true });
  }
  rows.sort((a, b) => new Date(a.recorded_at) - new Date(b.recorded_at));

  if (!rows.length) {
    els.capturedList.innerHTML = "";
    return;
  }

  els.capturedList.innerHTML = `<h3>Captured Data</h3>` + rows.map(r => `
    <div class="captured-row" data-type="${r.type}" data-id="${r.id}">
      <div class="captured-main">
        <span class="captured-label">${escapeHtml(r.label)}</span>
        ${r.detail ? ` — ${escapeHtml(r.detail)}` : ""}
      </div>
      <div class="captured-time">${formatTimestamp(r.recorded_at)}</div>
      <div class="captured-actions">
        ${r.editable ? '<button class="icon-btn captured-edit-btn" title="Edit">✏️</button>' : ""}
        <button class="icon-btn captured-delete-btn" title="Delete">🗑</button>
      </div>
    </div>
  `).join("");

  els.capturedList.querySelectorAll(".captured-row").forEach(row => {
    const type = row.dataset.type;
    const id = row.dataset.id;
    const rowData = rows.find(r => r.type === type && String(r.id) === id);

    row.querySelector(".captured-delete-btn").addEventListener("click", async () => {
      if (!confirm(`Delete "${rowData.label}"? This can't be undone.`)) return;
      await api(`/api/calls/${state.callId}/${type}/${id}`, { method: "DELETE" });
      await loadCall(state.callId);
    });

    const editBtn = row.querySelector(".captured-edit-btn");
    if (editBtn) {
      editBtn.addEventListener("click", async () => {
        if (type === "dictations") {
          const newText = prompt("Edit voice memo text:", rowData.detail);
          if (newText === null || !newText.trim()) return;
          await api(`/api/calls/${state.callId}/dictations/${id}`, {
            method: "PUT",
            body: JSON.stringify({ text: newText.trim() }),
          });
          await loadCall(state.callId);
        } else if (type === "vitals") {
          const v = vitals.find(v => String(v.id) === id);
          if (!v) return;
          const bp = prompt("BP (e.g. 120/80):", v.bp || "");
          if (bp === null) return;
          const hr = prompt("HR:", v.hr ?? "");
          const spo2 = prompt("SpO2:", v.spo2 ?? "");
          const rr = prompt("RR:", v.rr ?? "");
          const gcs = prompt("GCS:", v.gcs ?? "");
          const glucose = prompt("Glucose:", v.glucose ?? "");
          await api(`/api/calls/${state.callId}/vitals/${id}`, {
            method: "PUT",
            body: JSON.stringify({
              bp: bp || null,
              hr: hr ? Number(hr) : null,
              spo2: spo2 ? Number(spo2) : null,
              rr: rr ? Number(rr) : null,
              gcs: gcs ? Number(gcs) : null,
              glucose: glucose ? Number(glucose) : null,
            }),
          });
          await loadCall(state.callId);
        }
      });
    }
  });
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

// ---- New Call modal ----

const modalOverlay = document.getElementById("modal-overlay");
const modalNewcall = document.getElementById("modal-newcall");

function openNewCallModal() {
  document.getElementById("nc-complaint").value = "";
  document.getElementById("nc-age").value = "";
  document.getElementById("nc-sex").value = "";
  modalOverlay.classList.add("active");
  modalNewcall.classList.add("active");
}

function closeNewCallModal() {
  modalOverlay.classList.remove("active");
  modalNewcall.classList.remove("active");
}

document.getElementById("nc-cancel-btn").addEventListener("click", closeNewCallModal);

document.getElementById("nc-create-btn").addEventListener("click", async () => {
  const complaint = document.getElementById("nc-complaint").value.trim();
  const ageRaw = document.getElementById("nc-age").value.trim();
  const sex = document.getElementById("nc-sex").value;
  const { call_id } = await api("/api/calls", {
    method: "POST",
    body: JSON.stringify({
      chief_complaint: complaint || "unspecified complaint",
      patient_age: ageRaw ? Number(ageRaw) : null,
      patient_sex: sex || null,
    }),
  });
  closeNewCallModal();
  await refreshCallList(call_id);
});

// ---- Archive / delete ----

els.archiveToggleBtn.addEventListener("click", async () => {
  const call = state.calls.find(c => c.id === state.callId);
  const nextArchived = !(call && call.archived);
  await api(`/api/calls/${state.callId}/archive`, {
    method: "PUT",
    body: JSON.stringify({ archived: nextArchived }),
  });
  await refreshCallList(state.callId);
});

els.deleteCallBtn.addEventListener("click", async () => {
  const call = state.calls.find(c => c.id === state.callId);
  if (!confirm(`Delete call ${state.callId} (${(call && call.chief_complaint) || "no complaint set"})? This can't be undone.`)) return;
  await api(`/api/calls/${state.callId}`, { method: "DELETE" });
  await refreshCallList();
});

// ---- Wire up events ----

els.textarea.addEventListener("input", onInput);
els.textarea.addEventListener("keydown", onKeydown);
els.textarea.addEventListener("scroll", syncScroll);
els.callSelect.addEventListener("change", (e) => loadCall(e.target.value));
els.loadDraftBtn.addEventListener("click", loadDraft);
els.saveBtn.addEventListener("click", () => saveNarrative(false));
els.finalizeBtn.addEventListener("click", () => saveNarrative(true));
els.newCallBtn.addEventListener("click", openNewCallModal);

// ---- Init ----
// Supports deep-linking from the watch simulator: /report/<call_id>
// selects that specific call instead of just the most recent one.
const pathMatch = window.location.pathname.match(/^\/report\/([^/]+)/);
refreshCallList(pathMatch ? decodeURIComponent(pathMatch[1]) : undefined);
