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
  document.documentElement.dataset.serviceStatus = health.status || "unknown";
}

function personaSummary(persona) {
  return `
    <div class="space-y-4">
      <div>
        <p class="text-xs font-black uppercase tracking-wider text-slate-400">Selected persona</p>
        <h2 class="mt-1 text-2xl font-black text-slate-950">${escapeHtml(persona.name)}</h2>
        <p class="mt-1 text-sm font-semibold text-slate-500">${escapeHtml(persona.occupation)} &middot; ${escapeHtml(persona.location)}</p>
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
  enhanceSelect(select);
  onChange?.(state.activePersona);
}

function enhanceAllSelects(root = document) {
  root.querySelectorAll("select.select").forEach((select) => enhanceSelect(select));
}

function enhanceSelect(select) {
  if (!select || select.dataset.enhancedSelect === "true") {
    updateEnhancedSelect(select);
    return;
  }
  const wrapper = document.createElement("div");
  wrapper.className = "custom-select";
  wrapper.dataset.selectFor = select.id || "";
  wrapper.innerHTML = `
    <button class="custom-select-trigger" type="button" aria-haspopup="listbox" aria-expanded="false">
      <span></span>
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="m6 9 6 6 6-6"></path>
      </svg>
    </button>
    <div class="custom-select-menu" role="listbox"></div>
  `;
  select.classList.add("native-select-hidden");
  select.dataset.enhancedSelect = "true";
  select.insertAdjacentElement("afterend", wrapper);
  const trigger = wrapper.querySelector(".custom-select-trigger");
  trigger.addEventListener("click", () => toggleSelectMenu(wrapper));
  trigger.addEventListener("keydown", (event) => handleSelectKeydown(event, select, wrapper));
  select.addEventListener("change", () => updateEnhancedSelect(select));
  updateEnhancedSelect(select);
}

function updateEnhancedSelect(select) {
  if (!select) return;
  const wrapper = select.nextElementSibling?.classList?.contains("custom-select")
    ? select.nextElementSibling
    : null;
  if (!wrapper) return;
  const triggerText = wrapper.querySelector(".custom-select-trigger span");
  const menu = wrapper.querySelector(".custom-select-menu");
  const options = Array.from(select.options);
  const active = options.find((option) => option.value === select.value) || options[0];
  triggerText.textContent = active?.textContent || "";
  menu.innerHTML = options
    .map((option) => {
      const selected = option.value === select.value;
      return `
        <button class="custom-select-option${selected ? " selected" : ""}" type="button" role="option" aria-selected="${selected}" data-value="${escapeHtml(option.value)}">
          ${escapeHtml(option.textContent)}
        </button>
      `;
    })
    .join("");
  menu.querySelectorAll(".custom-select-option").forEach((button) => {
    button.addEventListener("click", () => {
      select.value = button.dataset.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      closeSelectMenu(wrapper);
    });
  });
}

function toggleSelectMenu(wrapper) {
  const isOpen = wrapper.classList.contains("open");
  closeAllSelectMenus();
  if (!isOpen) {
    wrapper.classList.add("open");
    wrapper.querySelector(".custom-select-trigger").setAttribute("aria-expanded", "true");
  }
}

function closeSelectMenu(wrapper) {
  wrapper.classList.remove("open");
  wrapper.querySelector(".custom-select-trigger").setAttribute("aria-expanded", "false");
}

function closeAllSelectMenus() {
  document.querySelectorAll(".custom-select.open").forEach(closeSelectMenu);
}

function handleSelectKeydown(event, select, wrapper) {
  const options = Array.from(select.options);
  const currentIndex = Math.max(0, options.findIndex((option) => option.value === select.value));
  if (event.key === "Escape") {
    closeSelectMenu(wrapper);
    return;
  }
  if (!["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) return;
  event.preventDefault();
  if (event.key === "Enter" || event.key === " ") {
    toggleSelectMenu(wrapper);
    return;
  }
  const direction = event.key === "ArrowDown" ? 1 : -1;
  const nextIndex = Math.min(options.length - 1, Math.max(0, currentIndex + direction));
  select.value = options[nextIndex].value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

document.addEventListener("click", (event) => {
  if (!event.target.closest(".custom-select")) {
    closeAllSelectMenus();
  }
});

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

function createVoiceInput({ button, target, status, append = false }) {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    button.disabled = true;
    status.textContent = "Voice input is not supported in this browser. Type instead.";
    return null;
  }

  const recognition = new Recognition();
  recognition.lang = "en-NG";
  recognition.interimResults = true;
  recognition.continuous = false;
  let finalTranscript = "";
  let isListening = false;
  const hasIconButton = button.classList.contains("composer-icon-button");
  const idleHtml = button.innerHTML;
  const idleLabel = button.textContent;

  recognition.onstart = () => {
    finalTranscript = "";
    isListening = true;
    if (hasIconButton) {
      button.classList.add("listening");
      button.setAttribute("aria-label", "Listening");
    } else {
      button.textContent = "Listening...";
    }
    status.textContent = "Listening. Speak naturally.";
    status.classList.add("recording");
  };

  recognition.onresult = (event) => {
    let interim = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const transcript = event.results[index][0].transcript;
      if (event.results[index].isFinal) {
        finalTranscript += transcript;
      } else {
        interim += transcript;
      }
    }
    const current = `${finalTranscript} ${interim}`.trim();
    if (current) {
      target.value = append && target.value.trim() ? `${target.value.trim()} ${current}` : current;
    }
  };

  recognition.onerror = (event) => {
    status.textContent = `Voice input stopped: ${event.error}. You can type instead.`;
    status.classList.remove("recording");
    if (hasIconButton) {
      button.classList.remove("listening");
      button.innerHTML = idleHtml;
      button.setAttribute("aria-label", "Speak");
    } else {
      button.textContent = idleLabel;
    }
    isListening = false;
  };

  recognition.onend = () => {
    status.classList.remove("recording");
    if (hasIconButton) {
      button.classList.remove("listening");
      button.innerHTML = idleHtml;
      button.setAttribute("aria-label", "Speak");
    } else {
      button.textContent = idleLabel;
    }
    isListening = false;
    if (target.value.trim()) {
      status.textContent = "Voice captured. You can edit the text before generating.";
    } else {
      status.textContent = "No speech captured. Try again or type manually.";
    }
  };

  button.addEventListener("click", () => {
    if (!isListening) {
      recognition.start();
    }
  });
  status.textContent = "Voice input ready.";
  return recognition;
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

function renderReasoningTrace(trace) {
  const steps = trace?.steps || [];
  if (!steps.length) {
    return "";
  }
  const rows = steps
    .map((step, index) => {
      const notes = humanTraceNotes(step)
        .map((note) => `<p class="trace-note">${escapeHtml(note)}</p>`)
        .join("");
      return `
        <div class="trace-step">
          <div class="trace-index">${index + 1}</div>
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <p class="font-black text-slate-950">${escapeHtml(traceStepTitle(step.name))}</p>
            </div>
            <div class="mt-2 grid gap-1.5">${notes}</div>
          </div>
        </div>
      `;
    })
    .join("");
  return `
    <details class="trace-panel mt-5" open>
      <summary>How this result was prepared</summary>
      <div class="mt-4">${rows}</div>
    </details>
  `;
}

function traceStepTitle(name) {
  const titles = {
    ResolveUserProfileStep: "User preference review",
    RetrieveEvidenceStep: "Reference review selection",
    PredictSentimentStep: "Likely reaction estimate",
    CalibrateRatingStep: "Rating choice",
    GenerateReviewStep: "Review writing",
    ConsistencyCheckStep: "Final review check",
    FormalizeReviewReasoningStep: "Explanation polish",
    ParseIntentStep: "Request understanding",
    CrossDomainBridgeStep: "Interest connection",
    ColdStartGateStep: "Readiness check",
    CandidateShortlistStep: "Option filtering",
    LLMRerankStep: "Best option selection",
    DiversityStep: "List balance",
    BuildRecommendationResponseStep: "Final response",
  };
  return titles[name] || name.replaceAll("_", " ").replace(/Step$/, "");
}

function humanTraceNotes(step) {
  const outputs = step.outputs || {};
  const name = step.name;
  const notes = [];

  if (name === "ResolveUserProfileStep") {
    notes.push("It reviewed the selected persona and the user's past preferences.");
    if (outputs.nigerian_register) notes.push(`It kept the user's preferred communication style as ${outputs.nigerian_register}.`);
    if (outputs.top_taste_tokens?.length || outputs.taste_tokens?.length) {
      notes.push(`It noted interests such as ${friendlyList(outputs.top_taste_tokens || outputs.taste_tokens, 4)}.`);
    }
    return notes;
  }

  if (name === "RetrieveEvidenceStep") {
    notes.push(`It selected ${plural(outputs.evidence_count, "reference review")} to guide the generated review.`);
    if (outputs.top_evidence?.length) notes.push(`The most relevant references included ${friendlyList(outputs.top_evidence, 3)}.`);
    return notes;
  }

  if (name === "PredictSentimentStep") {
    notes.push(`It estimated that the user would have a ${reactionLabel(outputs.sentiment)} reaction to the product.`);
    if (outputs.base_reasoning) notes.push(cleanTraceSentence(outputs.base_reasoning));
    return notes;
  }

  if (name === "CalibrateRatingStep") {
    notes.push(`It chose a ${outputs.calibrated_rating}/5 rating after comparing the product fit with the user's usual rating style.`);
    return notes;
  }

  if (name === "GenerateReviewStep") {
    notes.push("It wrote the review in the user's likely tone.");
    if (outputs.fallback_used === false) notes.push("It used the hosted language service for the final wording.");
    if (outputs.fallback_used === true) notes.push("It used the local backup writer for this result.");
    return notes;
  }

  if (name === "ConsistencyCheckStep") {
    notes.push(cleanTraceSentence(outputs.consistency_check || "It checked that the review and rating agree."));
    return notes;
  }

  if (name === "FormalizeReviewReasoningStep" || name === "BuildRecommendationResponseStep") {
    notes.push("It rewrote the visible explanation so it reads clearly for a person reviewing the result.");
    if (outputs.presentation_llm_configured === true) notes.push("It used the hosted language service for the final explanation.");
    if (outputs.presentation_fallback_used === true) notes.push("It used a local backup explanation because the hosted service was unavailable.");
    return notes;
  }

  if (name === "ParseIntentStep") {
    if (outputs.target_categories?.length) notes.push(`It understood the requested area as ${friendlyCategories(outputs.target_categories)}.`);
    if (outputs.excluded_categories?.length) notes.push(`It treated ${friendlyCategories(outputs.excluded_categories)} as excluded from the result.`);
    if (outputs.max_price) notes.push(`It treated ${pricePhrase(outputs)} as a firm price rule.`);
    if (outputs.constraints?.length) notes.push(`It also noticed conditions such as ${friendlyList(outputs.constraints, 5)}.`);
    if (!notes.length) notes.push("It read the message and identified what kind of recommendation was needed.");
    return notes;
  }

  if (name === "CrossDomainBridgeStep") {
    if (outputs.is_cross_domain) notes.push("It connected the user's interests from one area to another before recommending.");
    if (outputs.taste_descriptors?.length) notes.push(`It used preference ideas such as ${friendlyList(outputs.taste_descriptors, 5)}.`);
    if (!notes.length) notes.push("It checked whether the request needed ideas to be connected across categories.");
    return notes;
  }

  if (name === "ColdStartGateStep") {
    if (outputs.follow_up_questions?.length) {
      notes.push("It decided that more information was needed before making a recommendation.");
      notes.push(`It asked: ${friendlyList(outputs.follow_up_questions, 2)}.`);
    } else {
      notes.push("It had enough information to continue with the recommendation.");
    }
    return notes;
  }

  if (name === "CandidateShortlistStep") {
    notes.push(`It found ${plural(outputs.candidate_count, "possible option")} after applying the request rules.`);
    if (outputs.top_candidates?.length) notes.push(`The first options considered were ${friendlyList(outputs.top_candidates, 4)}.`);
    if (outputs.excluded_categories?.length) notes.push(`It removed options from ${friendlyCategories(outputs.excluded_categories)}.`);
    return notes;
  }

  if (name === "LLMRerankStep") {
    notes.push("It compared the remaining options and placed the strongest matches first.");
    if (outputs.top_reranked?.length) notes.push(`The leading choices after comparison were ${friendlyList(outputs.top_reranked, 4)}.`);
    if (outputs.fallback_used === true) notes.push("It used the local backup comparison for this step.");
    return notes;
  }

  if (name === "DiversityStep") {
    notes.push("It checked the list so the final result was not too repetitive.");
    if (outputs.selected_categories?.length) notes.push(`The final mix included ${friendlyCategories(outputs.selected_categories)}.`);
    return notes;
  }

  return [cleanTraceSentence(step.summary || "This step was completed.")];
}

function friendlyCategories(categories) {
  return friendlyList(
    [...new Set(categories || [])].map((category) => String(category).replaceAll("_", " and ")),
    5,
  );
}

function friendlyList(items, limit = 4) {
  const clean = (items || [])
    .filter((item) => item !== null && item !== undefined && String(item).trim())
    .map((item) => String(item).replaceAll("_", " ").trim())
    .slice(0, limit);
  if (!clean.length) return "none";
  if (clean.length === 1) return clean[0];
  return `${clean.slice(0, -1).join(", ")} and ${clean[clean.length - 1]}`;
}

function plural(count, label) {
  const number = Number(count || 0);
  return `${number} ${label}${number === 1 ? "" : "s"}`;
}

function reactionLabel(sentiment) {
  const value = Number(sentiment);
  if (Number.isNaN(value)) return "balanced";
  if (value >= 0.75) return "strongly positive";
  if (value >= 0.58) return "positive";
  if (value >= 0.42) return "mixed";
  return "critical";
}

function pricePhrase(outputs) {
  const limit = Number(outputs.max_price);
  const amount = Number.isInteger(limit) ? `$${limit}` : `$${limit.toFixed(2)}`;
  return outputs.max_price_exclusive ? `below ${amount}` : `at or below ${amount}`;
}

function cleanTraceSentence(text) {
  const value = String(text || "")
    .replace(/^passed:\s*/i, "It confirmed that ")
    .replace(/^warning:\s*/i, "It noted that ")
    .replaceAll("_", " ")
    .trim();
  return value ? value[0].toUpperCase() + value.slice(1) : "It completed this check.";
}

function formatTraceValue(value) {
  if (Array.isArray(value)) {
    return value
      .map((item) => (typeof item === "object" && item !== null ? JSON.stringify(item) : String(item)))
      .join(", ");
  }
  if (typeof value === "object" && value !== null) {
    return Object.entries(value)
      .slice(0, 4)
      .map(([key, item]) => `${key}: ${item}`)
      .join(", ");
  }
  return String(value ?? "");
}

window.AgentApp = {
  $,
  api,
  state,
  escapeHtml,
  renderBrandStatus,
  loadBaseData,
  bindPersonaSelect,
  enhanceAllSelects,
  enhanceSelect,
  bindNavigation,
  personaSummary,
  readAloud,
  createVoiceInput,
  generateYarnAudio,
  playYarnAudio,
  renderYarnResult,
  renderReasoningTrace,
};
