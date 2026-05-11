const state = {
  personas: [],
  products: [],
  activePersona: null,
};

const $ = (id) => document.getElementById(id);
window.$ = $;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status}: ${text}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderBrandStatus(health) {
  document.querySelectorAll("[data-health-text]").forEach((node) => {
    node.textContent = health.groq_configured ? "Live Groq connection" : "Local demo mode";
  });
  document.querySelectorAll("[data-health-dot]").forEach((node) => {
    node.classList.toggle("ok", health.status === "ok");
  });
}

function personaSummary(persona) {
  return `
    <div class="space-y-4">
      <div>
        <p class="text-xs font-black uppercase tracking-wider text-slate-400">Selected persona</p>
        <h2 class="mt-1 text-2xl font-black text-slate-950">${escapeHtml(persona.name)}</h2>
        <p class="mt-1 text-sm font-semibold text-slate-500">${escapeHtml(persona.occupation)} · ${escapeHtml(persona.location)}</p>
      </div>
      <div class="grid gap-3 text-sm">
        <div class="rounded-2xl bg-slate-50 p-4">
          <span class="font-black text-slate-950">Budget</span>
          <p class="mt-1 text-slate-600">${escapeHtml(persona.budget_level)}</p>
        </div>
        <div class="rounded-2xl bg-slate-50 p-4">
          <span class="font-black text-slate-950">Likes</span>
          <p class="mt-1 text-slate-600">${escapeHtml(persona.likes.join(", "))}</p>
        </div>
        <div class="rounded-2xl bg-slate-50 p-4">
          <span class="font-black text-slate-950">Context</span>
          <p class="mt-1 text-slate-600">${escapeHtml(persona.cultural_context)}</p>
        </div>
      </div>
    </div>
  `;
}

async function loadBaseData() {
  const [health, personas, products] = await Promise.all([
    api("/health"),
    api("/api/v1/demo-personas"),
    api("/api/v1/products"),
  ]);
  renderBrandStatus(health);
  state.personas = personas;
  state.products = products;
  state.activePersona = personas[0];
  return { health, personas, products };
}

function bindPersonaSelect(onChange) {
  const select = $("persona-select");
  if (!select) return;
  select.innerHTML = state.personas
    .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`)
    .join("");
  select.addEventListener("change", (event) => {
    state.activePersona = state.personas.find((item) => item.id === event.target.value);
    onChange?.(state.activePersona);
  });
  onChange?.(state.activePersona);
}

function bindNavigation() {
  const current = window.location.pathname;
  document.querySelectorAll("[data-nav]").forEach((link) => {
    const href = link.getAttribute("href");
    const active = href === current || (href !== "/" && current.startsWith(href));
    link.classList.toggle("active", active);
  });
}

function readAloud(text) {
  if (!("speechSynthesis" in window)) {
    return false;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-NG";
  utterance.rate = 0.92;
  utterance.pitch = 1.02;
  window.speechSynthesis.speak(utterance);
  return true;
}

async function generateYarnAudio(text, voice) {
  return api("/api/v1/yarn-tts", {
    method: "POST",
    body: JSON.stringify({
      text,
      voice,
      response_format: "mp3",
    }),
  });
}

async function playYarnAudio(text, voice, audioElement, statusElement) {
  statusElement.innerHTML += `<p class="mt-3 text-slate-500">Generating hosted YarnGPT audio...</p>`;
  let payload;
  try {
    payload = await generateYarnAudio(text, voice);
  } catch (error) {
    statusElement.innerHTML += `<p class="mt-3 text-slate-500">YarnGPT audio request failed. Falling back to browser speech.</p>`;
    return readAloud(text);
  }
  if (payload.audio_data_url) {
    audioElement.src = payload.audio_data_url;
    audioElement.hidden = false;
    await audioElement.play().catch(() => {});
    statusElement.innerHTML += `<p class="mt-3 text-emerald-700">YarnGPT audio ready with ${escapeHtml(payload.voice)}.</p>`;
    return true;
  }
  statusElement.innerHTML += `<p class="mt-3 text-slate-500">${escapeHtml(payload.message)} Falling back to browser speech.</p>`;
  return readAloud(text);
}

function renderYarnResult(container, payload) {
  container.innerHTML = `
    <p class="text-sm font-black uppercase text-slate-500">${escapeHtml(payload.mode)}</p>
    <p class="mt-3 text-xl font-semibold leading-8 text-slate-800">${escapeHtml(payload.voice_script)}</p>
    <div class="mt-4 rounded-2xl bg-slate-50 p-4">
      <p class="text-sm font-black uppercase text-slate-400">Judge note</p>
      <p class="mt-2 text-slate-600">${escapeHtml(payload.judge_note)}</p>
    </div>
  `;
}

window.AgentApp = {
  $,
  api,
  state,
  escapeHtml,
  renderBrandStatus,
  loadBaseData,
  bindPersonaSelect,
  bindNavigation,
  personaSummary,
  readAloud,
  generateYarnAudio,
  playYarnAudio,
  renderYarnResult,
};
