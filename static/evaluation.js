(() => {
const { api, escapeHtml, bindNavigation } = window.AgentApp;

function renderMetrics(metrics) {
  const cards = [
    ["Task A RMSE", metrics.task_a_rmse, "Rating error on fixture holdout"],
    ["ROUGE-L", metrics.task_a_rouge_l, "Fixture text overlap score"],
    ["NDCG@10", metrics.task_b_ndcg_at_10, "Ranking quality at ten"],
    ["Hit Rate@10", metrics.task_b_hit_rate_at_10, "Held-out item recovered"],
  ];
  $("metrics-result").innerHTML = `
    ${cards
      .map(
        ([label, value, note]) => `
          <article class="metric-tile">
            <p class="text-sm font-black uppercase text-slate-400">${escapeHtml(label)}</p>
            <p class="mt-4 text-5xl font-black text-slate-950">${escapeHtml(value)}</p>
            <p class="mt-3 text-sm font-semibold text-slate-500">${escapeHtml(note)}</p>
          </article>
        `,
      )
      .join("")}
    <article class="panel p-6 md:col-span-4">
      <p class="text-sm font-black uppercase text-slate-400">Notes</p>
      <ul class="mt-3 grid gap-2 text-slate-700">
        ${metrics.notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}
      </ul>
    </article>
  `;
}

async function loadMetrics() {
  $("metrics-result").innerHTML = `
    <div class="loading panel p-8 md:col-span-4">
      <p class="text-lg font-black text-slate-500">Loading evaluation metrics...</p>
    </div>
  `;
  renderMetrics(await api("/api/v1/evaluation"));
}

async function init() {
  bindNavigation();
  api("/health").then(window.AgentApp.renderBrandStatus).catch(() => {});
  $("load-metrics").addEventListener("click", loadMetrics);
  await loadMetrics();
}

init().catch((error) => {
  $("metrics-result").innerHTML = `<div class="panel p-6 text-red-700 md:col-span-4">${escapeHtml(error.message)}</div>`;
});
})();
