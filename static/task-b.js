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
        <p class="text-sm font-black uppercase text-slate-400">Recommendation agent</p>
        <h2 class="mt-2 text-2xl font-black text-slate-950">Tell me what you need and I will reason before ranking.</h2>
        <p class="mt-3 leading-7 text-slate-600">Try a cold-start prompt, a cross-domain request, or a constraint like budget, family use, mood, or location.</p>
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
  const visibleMessages = conversation.slice(-6);
  $("recommend-result").innerHTML = `
    <div class="chat-thread">
      ${visibleMessages.map(renderChatMessage).join("")}
    </div>
  `;
  $("recommend-result").scrollTop = $("recommend-result").scrollHeight;
}

function renderChatMessage(message) {
  const avatar = message.role === "user" ? "U" : "A";
  return `
    <div class="chat-message ${message.role}">
      <div class="chat-avatar">${avatar}</div>
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
    <div class="agent-progress">
      <p class="text-sm font-black uppercase text-slate-400">Agent workflow running</p>
      <div class="mt-4 progress-steps">
        <span>Parsing intent</span>
        <span>Retrieving candidates</span>
        <span>Reranking with reasoning</span>
      </div>
    </div>
  `;
}

function renderClarificationMessage(result) {
  const questions = (result.follow_up_questions || [])
    .map((question) => `<li>${escapeHtml(question)}</li>`)
    .join("");
  return `
    <p class="text-sm font-black uppercase text-slate-400">Cold-start bootstrap</p>
    <h2 class="mt-2 text-2xl font-black text-slate-950">I need two quick answers before ranking.</h2>
    <p class="mt-3 leading-7 text-slate-600">Reply in the message box. I will keep this session and use your answer in the next turn.</p>
    <ul class="mt-5 space-y-3 text-slate-700">${questions}</ul>
    ${renderReasoningTrace(result.reasoning_trace)}
  `;
}

function renderRecommendationsMessage(result) {
  const rows = (result.items || [])
    .map((item) => {
      const matches = (item.matched_preferences || [])
        .map((match) => `<span class="tag">${escapeHtml(match)}</span>`)
        .join("");
      const score = Number(item.score || 0).toFixed(3);
      return `
        <div class="recommendation-row">
          <div class="rank-badge">${escapeHtml(item.rank)}</div>
          <div>
            <h3 class="text-xl font-black text-slate-950">${escapeHtml(item.title)}</h3>
            <p class="mt-1 text-sm font-bold text-slate-500">${escapeHtml(item.category.replaceAll("_", " "))} &middot; $${escapeHtml(item.price ?? "n/a")}</p>
            <p class="mt-3 leading-7 text-slate-700">${escapeHtml(item.reason)}</p>
            <div class="mt-3 flex flex-wrap gap-2">${matches || '<span class="tag">cold-start quality</span>'}</div>
          </div>
          <div class="score rounded-2xl bg-slate-50 px-4 py-3 text-right">
            <p class="text-xs font-black uppercase text-slate-400">Score</p>
            <p class="text-2xl font-black">${escapeHtml(score)}</p>
          </div>
        </div>
      `;
    })
    .join("");

  latestRankingText = `${result.reasoning || "Personalized ranking ready."} Top picks: ${(result.items || [])
    .slice(0, 5)
    .map((item) => `${item.rank}. ${item.title}: ${item.reason}`)
    .join(" ")}`;
  $("generate-yarn").disabled = false;
  $("yarn-result").innerHTML = "Ready. Choose a voice style and click Yarn It.";

  return `
    <p class="text-sm font-black uppercase text-emerald-700">Ranked response</p>
    <p class="mt-2 leading-7 text-emerald-950">${escapeHtml(result.reasoning || "I ranked the best matching candidates for this turn.")}</p>
    <div class="mt-5">${rows || '<p class="text-slate-600">No candidates were returned. Try a broader request.</p>'}</div>
    ${renderReasoningTrace(result.reasoning_trace)}
  `;
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

  addMessage("user", `<p class="leading-7 text-slate-800">${escapeHtml(text)}</p>`);
  input.value = "";
  const loadingId = addMessage("agent", progressMessage());
  $("generate-recommendations").disabled = true;

  try {
    const result = await api("/api/v1/recommend", {
      method: "POST",
      body: JSON.stringify({
        user_persona: state.activePersona.persona,
        context: text,
        top_k: 10,
        session_id: activeSessionId,
        conversational: true,
      }),
    });
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

async function generateYarn() {
  if (!latestRankingText) return;
  $("yarn-result").innerHTML = "Preparing local voice script...";
  const payload = await api("/api/v1/yarn", {
    method: "POST",
    body: JSON.stringify({
      user_persona: state.activePersona.persona,
      source_text: latestRankingText,
      mode: $("yarn-mode").value,
      task: "recommendation ranking",
    }),
  });
  latestYarnText = payload.voice_script;
  renderYarnResult($("yarn-result"), payload);
  $("speak-yarn").disabled = false;
}

async function init() {
  bindNavigation();
  await loadBaseData();
  bindPersonaSelect(renderPersona);
  document.querySelectorAll("[data-context]").forEach((button) => {
    button.addEventListener("click", () => {
      $("recommend-context").value = button.dataset.context;
      $("recommend-context").focus();
    });
  });
  createVoiceInput({
    button: $("speak-context"),
    target: $("recommend-context"),
    status: $("context-voice-status"),
  });
  $("recommend-context").addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      generateRecommendations();
    }
  });
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
}

init().catch((error) => {
  $("recommend-result").innerHTML = `<div class="panel p-6 text-red-700">${escapeHtml(error.message)}</div>`;
});
})();
