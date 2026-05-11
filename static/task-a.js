(() => {
const { api, state, escapeHtml, loadBaseData, bindPersonaSelect, bindNavigation, personaSummary } = window.AgentApp;

function fillProduct(product) {
  $("product-title").value = product.title;
  $("product-category").value = product.category;
  $("product-price").value = product.price ?? "";
  $("product-brand").value = product.brand ?? "";
  $("product-description").value = product.description;
}

function currentProduct() {
  const selected = state.products.find((item) => item.title === $("product-select").value);
  return {
    title: $("product-title").value,
    category: $("product-category").value,
    description: $("product-description").value,
    price: Number($("product-price").value || selected?.price || 0),
    brand: $("product-brand").value || selected?.brand || null,
    attributes: selected?.attributes ?? {},
  };
}

function renderPersona(selected) {
  $("persona-card").innerHTML = personaSummary(selected.persona);
}

function renderReview(result) {
  const evidence = result.evidence
    .map((item) => `<span class="tag">${escapeHtml(item.title)} · ${escapeHtml(item.rating)}/5</span>`)
    .join("");
  $("review-result").innerHTML = `
    <div class="flex flex-col gap-6">
      <div class="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
        <div>
          <p class="text-sm font-black uppercase text-slate-400">Predicted rating</p>
          <div class="review-rating mt-2">${escapeHtml(result.rating)}/5</div>
        </div>
        <div class="rounded-2xl bg-emerald-50 px-5 py-4 text-right">
          <p class="text-sm font-black uppercase text-emerald-700">Confidence</p>
          <p class="mt-1 text-3xl font-black text-emerald-900">${Math.round(result.confidence * 100)}%</p>
        </div>
      </div>
      <div>
        <p class="text-sm font-black uppercase text-[#4285F4]">Generated review</p>
        <p class="mt-3 text-xl font-semibold leading-9 text-slate-800">${escapeHtml(result.review_text)}</p>
      </div>
      <div class="rounded-3xl bg-slate-50 p-5">
        <p class="text-sm font-black uppercase text-slate-500">Behavioral reasoning</p>
        <p class="mt-2 leading-7 text-slate-700">${escapeHtml(result.reasoning)}</p>
      </div>
      <div>
        <p class="mb-3 text-sm font-black uppercase text-slate-500">Retrieved evidence</p>
        <div class="flex flex-wrap gap-2">${evidence}</div>
      </div>
    </div>
  `;
}

async function generateReview() {
  $("review-result").innerHTML = `
    <div class="loading flex h-full min-h-[360px] items-center justify-center rounded-[22px] bg-white p-8">
      <p class="text-lg font-black text-slate-500">Modeling persona behavior...</p>
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
  $("generate-review").addEventListener("click", generateReview);
}

init().catch((error) => {
  $("review-result").innerHTML = `<div class="panel p-6 text-red-700">${escapeHtml(error.message)}</div>`;
});
})();
