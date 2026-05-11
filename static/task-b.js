(() => {
const {
  api,
  state,
  escapeHtml,
  loadBaseData,
  bindPersonaSelect,
  bindNavigation,
  personaSummary,
  playYarnAudio,
  renderYarnResult,
} = window.AgentApp;

let latestRankingText = "";
let latestYarnText = "";

function renderPersona(selected) {
  $("persona-card").innerHTML = personaSummary(selected.persona);
}

function renderRecommendations(result) {
  const rows = result.items
    .map((item) => {
      const matches = (item.matched_preferences || [])
        .map((match) => `<span class="tag">${escapeHtml(match)}</span>`)
        .join("");
      return `
        <div class="recommendation-row">
          <div class="rank-badge">${escapeHtml(item.rank)}</div>
          <div>
            <h3 class="text-xl font-black text-slate-950">${escapeHtml(item.title)}</h3>
            <p class="mt-1 text-sm font-bold text-slate-500">${escapeHtml(item.category.replaceAll("_", " "))} · $${escapeHtml(item.price ?? "n/a")}</p>
            <p class="mt-3 leading-7 text-slate-700">${escapeHtml(item.reason)}</p>
            <div class="mt-3 flex flex-wrap gap-2">${matches || '<span class="tag">cold-start quality</span>'}</div>
          </div>
          <div class="score rounded-2xl bg-slate-50 px-4 py-3 text-right">
            <p class="text-xs font-black uppercase text-slate-400">Score</p>
            <p class="text-2xl font-black">${escapeHtml(item.score.toFixed(3))}</p>
          </div>
        </div>
      `;
    })
    .join("");
  $("recommend-result").innerHTML = `
    <div class="mb-6 rounded-3xl bg-emerald-50 p-5">
      <p class="text-sm font-black uppercase text-emerald-700">Ranking explanation</p>
      <p class="mt-2 leading-7 text-emerald-950">${escapeHtml(result.reasoning)}</p>
    </div>
    <div>${rows}</div>
  `;
  latestRankingText = `${result.reasoning} Top picks: ${result.items
    .slice(0, 5)
    .map((item) => `${item.rank}. ${item.title}: ${item.reason}`)
    .join(" ")}`;
  $("generate-yarn").disabled = false;
  $("yarn-result").innerHTML = "Ready. Choose a voice style and click Yarn It.";
}

async function generateRecommendations() {
  $("recommend-result").innerHTML = `
    <div class="loading flex h-full min-h-[360px] items-center justify-center rounded-[22px] bg-white p-8">
      <p class="text-lg font-black text-slate-500">Ranking personalized candidates...</p>
    </div>
  `;
  const result = await api("/api/v1/recommend", {
    method: "POST",
    body: JSON.stringify({
      user_persona: state.activePersona.persona,
      context: $("recommend-context").value,
      top_k: 10,
    }),
  });
  renderRecommendations(result);
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
    });
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
