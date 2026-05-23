(() => {
const {
  api,
  state,
  escapeHtml,
  loadBaseData,
  bindPersonaSelect,
  bindNavigation,
  personaSummary,
  createVoiceInput,
  enhanceAllSelects,
  playYarnAudio,
  renderYarnResult,
  renderReasoningTrace,
} = window.AgentApp;

let latestRankingText = "";
let latestYarnText = "";
let activeSessionId = null;
let conversation = [];
let messageId = 0;

function nextMessageId() {
  messageId += 1;
  return `message-${messageId}`;
}

function renderPersona(selected) {
  $("persona-card").innerHTML = personaSummary(selected.persona);
  activeSessionId = null;
  resetConversation();
}

function resetConversation() {
  latestRankingText = "";
  latestYarnText = "";
  conversation = [
    {
      id: nextMessageId(),
      role: "agent",
      html: `
        <p class="message-label">Recommendation agent</p>
        <h2 class="mt-2 text-2xl font-black text-slate-950">What should I help you choose?</h2>
        <p class="mt-3 leading-7 text-slate-600">Ask naturally. I can help with books, groceries, movies, games, beauty picks, new preferences, and requests that connect different interests.</p>
      `,
    },
  ];
  $("generate-yarn").disabled = true;
  $("speak-yarn").disabled = true;
  $("yarn-audio").hidden = true;
  $("yarn-result").innerHTML = "Generate recommendations first.";
  renderConversation();
}

function renderConversation() {
  $("recommend-result").innerHTML = `
    <div class="chat-thread">
      ${conversation.map(renderChatMessage).join("")}
    </div>
  `;
  scrollToLatestMessage();
}

function scrollToLatestMessage() {
  window.requestAnimationFrame(() => {
    const messages = $("recommend-result").querySelectorAll(".chat-message");
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage) return;
    const targetTop = lastMessage.getBoundingClientRect().top + window.scrollY - 96;
    window.scrollTo({
      top: Math.max(0, targetTop),
      behavior: "smooth",
    });
  });
}

function renderChatMessage(message) {
  return `
    <div class="chat-message ${message.role}">
      <div class="chat-bubble">${message.html}</div>
    </div>
  `;
}

function addMessage(role, html) {
  const message = { id: nextMessageId(), role, html };
  conversation.push(message);
  renderConversation();
  return message.id;
}

function replaceMessage(id, html) {
  const target = conversation.find((message) => message.id === id);
  if (target) {
    target.html = html;
  }
  renderConversation();
}

function progressMessage() {
  return `
    <div class="typing-bubble" aria-label="Agent is thinking">
      <span></span>
      <span></span>
      <span></span>
    </div>
  `;
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function collapsedTrace(trace) {
  return renderReasoningTrace(trace).replace(" open>", ">");
}

function renderClarificationMessage(result) {
  const questions = (result.follow_up_questions || [])
    .map((question) => `<li>${escapeHtml(question)}</li>`)
    .join("");
  return `
    <p class="text-sm font-black uppercase text-slate-400">Preference check</p>
    <h2 class="mt-2 text-2xl font-black text-slate-950">I need a clearer recommendation request.</h2>
    <p class="mt-3 leading-7 text-slate-600">${escapeHtml(result.reasoning || "Reply in the message box with what you want me to recommend.")}</p>
    <ul class="mt-5 space-y-3 text-slate-700">${questions}</ul>
    <div class="agent-trace-bottom">${collapsedTrace(result.reasoning_trace)}</div>
  `;
}

function renderRecommendationsMessage(result) {
  const rows = (result.items || [])
    .map((item, index) => {
      const matches = (item.matched_preferences || [])
        .map((match) => `<span class="tag">${escapeHtml(preferenceLabel(match))}</span>`)
        .join("");
      const fitPercent = `${Math.round(Number(item.score || 0) * 100)}%`;
      return `
        <div class="recommendation-row chat-recommendation-row" style="--stagger: ${index}">
          <div class="rec-card-header">
            <div class="rec-title-wrap">
              <div class="rank-badge">${escapeHtml(item.rank)}</div>
              <div class="min-w-0">
                <h3>${escapeHtml(item.title)}</h3>
                <p class="rec-meta">${escapeHtml(item.category.replaceAll("_", " "))} · $${escapeHtml(item.price ?? "n/a")}</p>
              </div>
            </div>
            <div class="fit-pill">
              <span>Fit</span>
              <strong>${escapeHtml(fitPercent)}</strong>
            </div>
          </div>
          <p class="rec-reason">${escapeHtml(item.reason)}</p>
          <div class="rec-tags">${matches || '<span class="tag">recommended fit</span>'}</div>
        </div>
      `;
    })
    .join("");

  latestRankingText = `${result.reasoning || "Personalized recommendations ready."} Top picks: ${(result.items || [])
    .slice(0, 5)
    .map((item) => `${item.rank}. ${item.title}: ${item.reason}`)
    .join(" ")}`;
  $("generate-yarn").disabled = false;
  $("yarn-result").innerHTML = "Ready. Choose a voice style and click Yarn It.";

  return `
    <p class="message-label text-emerald-700">Recommendation</p>
    <p class="mt-2 leading-7 text-slate-700">${escapeHtml(result.reasoning || "I prepared the best matching options for this request.")}</p>
    <div class="mt-5">${rows || '<p class="text-slate-600">I could not find matching options. Try a broader request.</p>'}</div>
    <div class="agent-trace-bottom">${collapsedTrace(result.reasoning_trace)}</div>
  `;
}

function preferenceLabel(value) {
  const normalized = String(value || "").replaceAll("_", " ").trim().toLowerCase();
  if (!normalized || normalized === "catalog" || normalized === "quality") return "overall fit";
  if (normalized === "local relevance") return "local relevance";
  return normalized;
}

function renderErrorMessage(error) {
  return `
    <p class="text-sm font-black uppercase text-red-700">Request failed</p>
    <p class="mt-3 leading-7 text-slate-700">${escapeHtml(error.message)}</p>
  `;
}

async function generateRecommendations() {
  const input = $("recommend-context");
  const text = input.value.trim();
  if (!text) {
    input.focus();
    return;
  }

  addMessage("user", `<p class="leading-7">${escapeHtml(text)}</p>`);
  input.value = "";
  resizeComposer();
  const loadingId = addMessage("agent", progressMessage());
  $("generate-recommendations").disabled = true;

  try {
    const [result] = await Promise.all([
      api("/api/v1/recommend", {
        method: "POST",
        body: JSON.stringify({
          user_persona: state.activePersona.persona,
          context: text,
          top_k: 10,
          session_id: activeSessionId,
          conversational: true,
        }),
      }),
      sleep(1900),
    ]);
    activeSessionId = result.session_id || activeSessionId;
    replaceMessage(
      loadingId,
      result.status === "needs_clarification"
        ? renderClarificationMessage(result)
        : renderRecommendationsMessage(result),
    );
  } catch (error) {
    replaceMessage(loadingId, renderErrorMessage(error));
  } finally {
    $("generate-recommendations").disabled = false;
    input.focus();
  }
}

function resizeComposer() {
  const input = $("recommend-context");
  input.style.height = "auto";
  input.style.height = `${Math.min(Math.max(input.scrollHeight, 34), 180)}px`;
  input.style.overflowY = input.scrollHeight > 180 ? "auto" : "hidden";
}

async function generateYarn() {
  if (!latestRankingText) return;
  $("yarn-result").innerHTML = "Preparing local voice script...";
  const payload = await api("/api/v1/yarn", {
    method: "POST",
    body: JSON.stringify({
      user_persona: state.activePersona.persona,
      source_text: latestRankingText,
      mode: $("yarn-mode").value,
      task: "recommendation",
    }),
  });
  latestYarnText = payload.voice_script;
  renderYarnResult($("yarn-result"), payload);
  $("speak-yarn").disabled = false;
}

async function init() {
  document.documentElement.dataset.taskBReady = "loading";
  bindNavigation();
  await loadBaseData();
  bindPersonaSelect(renderPersona);
  enhanceAllSelects();
  document.querySelectorAll("[data-context]").forEach((button) => {
    button.addEventListener("click", () => {
      $("recommend-context").value = button.dataset.context;
      resizeComposer();
      $("recommend-context").focus();
    });
  });
  createVoiceInput({
    button: $("speak-context"),
    target: $("recommend-context"),
    status: $("context-voice-status"),
  });
  $("recommend-context").addEventListener("input", resizeComposer);
  $("recommend-context").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      generateRecommendations();
    }
  });
  resizeComposer();
  $("generate-recommendations").addEventListener("click", generateRecommendations);
  $("generate-yarn").addEventListener("click", generateYarn);
  $("speak-yarn").addEventListener("click", () => {
    const played = playYarnAudio(
      latestYarnText,
      $("yarngpt-voice").value,
      $("yarn-audio"),
      $("yarn-result"),
    );
    Promise.resolve(played).then((ok) => {
      if (!ok) {
        $("yarn-result").innerHTML += `<p class="mt-3 text-red-700">This browser does not support speech synthesis.</p>`;
      }
    });
  });
  document.documentElement.dataset.taskBReady = "true";
}

init().catch((error) => {
  document.documentElement.dataset.taskBReady = "error";
  const message = escapeHtml(error.message || "The recommendation workspace could not finish loading. Please refresh the page.");
  const personaCard = $("persona-card");
  if (personaCard) {
    personaCard.innerHTML = `<div class="panel p-4 text-red-700">${message}</div>`;
  }
  $("recommend-result").innerHTML = `<div class="panel p-6 text-red-700">${escapeHtml(error.message)}</div>`;
});
})();
