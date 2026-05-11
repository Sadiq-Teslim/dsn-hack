const state = {
  personas: [],
  products: [],
  activePersona: null,
};

const byId = (id) => document.getElementById(id);

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

function renderPersona() {
  const persona = state.activePersona.persona;
  byId("persona-card").innerHTML = `
    <h3>${persona.name}</h3>
    <p>${persona.occupation} · ${persona.location}</p>
    <p><strong>Budget:</strong> ${persona.budget_level}</p>
    <p><strong>Likes:</strong> ${persona.likes.join(", ")}</p>
    <p><strong>Tone:</strong> ${persona.tone}</p>
  `;
}

function fillProduct(product) {
  byId("product-title").value = product.title;
  byId("product-category").value = product.category;
  byId("product-price").value = product.price ?? "";
  byId("product-description").value = product.description;
}

function currentProduct() {
  const selected = state.products.find((item) => item.title === byId("product-select").value);
  return {
    title: byId("product-title").value,
    category: byId("product-category").value,
    description: byId("product-description").value,
    price: Number(byId("product-price").value || selected?.price || 0),
    brand: selected?.brand ?? null,
    attributes: selected?.attributes ?? {},
  };
}

function setLoading(targetId, label) {
  byId(targetId).innerHTML = `<p class="empty-state">${label}</p>`;
}

function renderReview(result) {
  const evidence = result.evidence
    .map((item) => `<span class="pill">${item.title} · ${item.rating}/5</span>`)
    .join("");
  byId("review-result").innerHTML = `
    <div class="rating">${result.rating}/5</div>
    <div class="pill-row">
      <span class="pill">${Math.round(result.confidence * 100)}% confidence</span>
      <span class="pill">${result.fallback_used ? "Local fallback" : "Groq"}</span>
    </div>
    <h3>Simulated review</h3>
    <p class="reasoning">${result.review_text}</p>
    <h3>Behavioral reasoning</h3>
    <p class="reasoning">${result.reasoning}</p>
    <div class="pill-row">${evidence}</div>
  `;
}

function renderRecommendations(result) {
  const rows = result.items
    .map(
      (item) => `
        <div class="recommendation">
          <div class="rank">${item.rank}</div>
          <div>
            <h3>${item.title}</h3>
            <p>${item.reason}</p>
            <div class="pill-row">
              <span class="pill">${item.category.replaceAll("_", " ")}</span>
              <span class="pill">$${item.price ?? "n/a"}</span>
              ${(item.matched_preferences || []).map((match) => `<span class="pill">${match}</span>`).join("")}
            </div>
          </div>
          <div class="score">${item.score.toFixed(3)}</div>
        </div>
      `,
    )
    .join("");
  byId("recommend-result").innerHTML = `
    <p class="reasoning">${result.reasoning}</p>
    <div class="pill-row"><span class="pill">${result.fallback_used ? "Local fallback" : "Groq"}</span></div>
    ${rows}
  `;
}

function renderMetrics(metrics) {
  byId("metrics-result").innerHTML = `
    <div class="metric-card"><span>Task A RMSE</span><strong>${metrics.task_a_rmse}</strong></div>
    <div class="metric-card"><span>ROUGE-L</span><strong>${metrics.task_a_rouge_l}</strong></div>
    <div class="metric-card"><span>NDCG@10</span><strong>${metrics.task_b_ndcg_at_10}</strong></div>
    <div class="metric-card"><span>Hit Rate@10</span><strong>${metrics.task_b_hit_rate_at_10}</strong></div>
    <p class="metric-note">${metrics.notes.join(" ")}</p>
  `;
}

async function generateReview() {
  setLoading("review-result", "Generating review...");
  const result = await api("/api/v1/generate-review", {
    method: "POST",
    body: JSON.stringify({
      user_persona: state.activePersona.persona,
      product: currentProduct(),
    }),
  });
  renderReview(result);
}

async function generateRecommendations() {
  setLoading("recommend-result", "Ranking recommendations...");
  const result = await api("/api/v1/recommend", {
    method: "POST",
    body: JSON.stringify({
      user_persona: state.activePersona.persona,
      context: byId("recommend-context").value,
      top_k: 10,
    }),
  });
  renderRecommendations(result);
}

async function loadMetrics() {
  renderMetrics(await api("/api/v1/evaluation"));
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((item) => item.classList.remove("active"));
      tab.classList.add("active");
      byId(tab.dataset.tab).classList.add("active");
    });
  });
}

async function init() {
  bindTabs();
  const health = await api("/health");
  byId("health-dot").classList.toggle("ok", health.status === "ok");
  byId("health-text").textContent = health.groq_configured ? "Groq connected" : "Local fallback ready";

  state.personas = await api("/api/v1/demo-personas");
  state.products = await api("/api/v1/products");
  byId("persona-select").innerHTML = state.personas
    .map((item) => `<option value="${item.id}">${item.label}</option>`)
    .join("");
  byId("product-select").innerHTML = state.products
    .map((item) => `<option value="${item.title}">${item.title}</option>`)
    .join("");

  state.activePersona = state.personas[0];
  renderPersona();
  fillProduct(state.products[0]);
  await loadMetrics();

  byId("persona-select").addEventListener("change", (event) => {
    state.activePersona = state.personas.find((item) => item.id === event.target.value);
    renderPersona();
  });
  byId("product-select").addEventListener("change", (event) => {
    fillProduct(state.products.find((item) => item.title === event.target.value));
  });
  byId("generate-review").addEventListener("click", generateReview);
  byId("generate-recommendations").addEventListener("click", generateRecommendations);
  byId("load-metrics").addEventListener("click", loadMetrics);
}

init().catch((error) => {
  byId("health-text").textContent = error.message;
});
