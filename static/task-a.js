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
  enhanceSelect,
  playYarnAudio,
  renderYarnResult,
  renderReasoningTrace,
} = window.AgentApp;

let latestReviewText = "";
let latestYarnText = "";

function fillProduct(product) {
  $("product-title").value = product.title;
  $("product-category").dataset.rawCategory = product.category;
  $("product-category").value = formatCategory(product.category);
  $("product-price").value = product.price ?? "";
  $("product-brand").value = product.brand ?? "";
  $("product-description").value = product.description;
}

function currentProduct() {
  const selected = state.products.find((item) => item.title === $("product-select").value);
  const categoryInput = $("product-category");
  const rawCategory = categoryInput.dataset.rawCategory;
  return {
    title: $("product-title").value,
    category: rawCategory && categoryInput.value === formatCategory(rawCategory) ? rawCategory : categoryInput.value,
    description: $("product-description").value,
    price: Number($("product-price").value || selected?.price || 0),
    brand: $("product-brand").value || selected?.brand || null,
    attributes: selected?.attributes ?? {},
  };
}

function formatCategory(category) {
  return String(category || "")
    .replaceAll("_", " ")
    .replace(/\s+/g, " ")
    .trim();
}

function renderPersona(selected) {
  const persona = selected.persona;
  $("persona-card").innerHTML = `
    <div class="task-a-persona-summary">
      <div>
        <p class="task-a-section-label">Selected persona</p>
        <h2>${escapeHtml(persona.name)}</h2>
        <p>${escapeHtml(persona.occupation)} &middot; ${escapeHtml(persona.location)}</p>
      </div>
      <div class="task-a-persona-rows">
        <div>
          <span>Budget</span>
          <p>${escapeHtml(persona.budget_level)}</p>
        </div>
        <div>
          <span>Likes</span>
          <p>${escapeHtml(persona.likes.join(", "))}</p>
        </div>
        <div>
          <span>Context</span>
          <p>${escapeHtml(persona.cultural_context)}</p>
        </div>
      </div>
    </div>
  `;
}

function renderReview(result) {
  const evidence = result.evidence
    .map((item) => `<span class="task-a-evidence-chip">${escapeHtml(evidenceLabel(item.source))} &middot; ${escapeHtml(item.rating)}/5</span>`)
    .join("");
  $("review-result").innerHTML = `
    <div class="task-a-review-stack">
      <div class="task-a-rating-row">
        <div class="task-a-rating-card">
          <p class="task-a-section-label">Predicted rating</p>
          <strong>${escapeHtml(result.rating)}/5</strong>
        </div>
        <div class="task-a-confidence-pill">
          <span>Confidence</span>
          <strong>${Math.round(result.confidence * 100)}%</strong>
        </div>
      </div>
      <div>
        <p class="task-a-section-label">Generated review</p>
        <p class="task-a-review-copy">${escapeHtml(result.review_text)}</p>
      </div>
      <div>
        <p class="task-a-section-label">Reference examples</p>
        <div class="task-a-evidence-row">${evidence}</div>
      </div>
      <div class="task-a-explanation-box">
        <p class="task-a-section-label">Review explanation</p>
        <p>${escapeHtml(result.reasoning)}</p>
      </div>
    </div>
  `;
  $("task-a-trace").innerHTML = renderReasoningTrace(result.reasoning_trace).replace(" open>", ">");
  $("task-a-results").classList.remove("is-loading");
  $("task-a-side-column").hidden = false;
  latestReviewText = `${result.rating}/5. ${result.review_text} Reasoning: ${result.reasoning}`;
  $("generate-yarn").disabled = false;
  $("yarn-result").innerHTML = "Ready. Choose a voice style and click Yarn It.";
}

function evidenceLabel(source) {
  if (source === "own_history") return "Past review";
  if (source === "similar_user") return "Similar shopper";
  return "Reference";
}

async function generateReview() {
  $("task-a-results").hidden = false;
  $("task-a-results").classList.add("is-loading");
  $("task-a-side-column").hidden = true;
  $("task-a-trace").innerHTML = "";
  $("generate-yarn").disabled = true;
  $("speak-yarn").disabled = true;
  $("yarn-audio").hidden = true;
  $("yarn-result").innerHTML = "Generate a review first.";
  $("review-result").innerHTML = `
    <div class="loading task-a-loading">
      <p class="text-lg font-black text-slate-500">Preparing the review...</p>
    </div>
  `;
  const result = await api("/api/v1/generate-review", {
    method: "POST",
    body: JSON.stringify({
      user_persona: state.activePersona.persona,
      product: currentProduct(),
    }),
  });
  renderReview(result);
}

async function generateYarn() {
  if (!latestReviewText) return;
  $("yarn-result").innerHTML = "Preparing local voice script...";
  const payload = await api("/api/v1/yarn", {
    method: "POST",
    body: JSON.stringify({
      user_persona: state.activePersona.persona,
      source_text: latestReviewText,
      mode: $("yarn-mode").value,
      task: "review simulation",
    }),
  });
  latestYarnText = payload.voice_script;
  renderYarnResult($("yarn-result"), payload);
  $("speak-yarn").disabled = false;
}

async function init() {
  bindNavigation();
  const { products } = await loadBaseData();
  bindPersonaSelect(renderPersona);
  $("product-select").innerHTML = products
    .map((item) => `<option value="${escapeHtml(item.title)}">${escapeHtml(item.title)}</option>`)
    .join("");
  fillProduct(products[0]);
  $("product-select").addEventListener("change", (event) => {
    fillProduct(products.find((item) => item.title === event.target.value));
  });
  $("product-category").addEventListener("input", () => {
    delete $("product-category").dataset.rawCategory;
  });
  enhanceSelect($("product-select"));
  enhanceAllSelects();
  $("generate-review").addEventListener("click", generateReview);
  createVoiceInput({
    button: $("speak-description"),
    target: $("product-description"),
    status: $("description-voice-status"),
  });
  $("generate-yarn").addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    generateYarn();
  });
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
  $("review-result").innerHTML = `<div class="panel p-6 text-red-700">${escapeHtml(error.message)}</div>`;
});
})();
