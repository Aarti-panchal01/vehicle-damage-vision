const form = document.querySelector("#claim-form");
const photosInput = document.querySelector("#photos");
const policyInput = document.querySelector("#policy-pdf");
const preview = document.querySelector("#photo-preview");
const healthBanner = document.querySelector("#health-banner");
const progress = document.querySelector("#progress");
const errorPanel = document.querySelector("#error-panel");
const results = document.querySelector("#results");
const submitButton = document.querySelector("#submit-button");
const MAX_UPLOAD_BYTES = 4_000_000;
let previewUrls = [];

function showError(message) {
  errorPanel.textContent = message;
  errorPanel.classList.remove("hidden");
  errorPanel.scrollIntoView({ behavior: "smooth", block: "center" });
}

function clearError() {
  errorPanel.textContent = "";
  errorPanel.classList.add("hidden");
}

function releasePreviewUrls() {
  previewUrls.forEach((url) => URL.revokeObjectURL(url));
  previewUrls = [];
}

function canvasBlob(canvas, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("The browser could not resize one of the photos."));
    }, "image/jpeg", quality);
  });
}

async function compressPhoto(file) {
  const image = await createImageBitmap(file);
  const scale = Math.min(1, 1280 / Math.max(image.width, image.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(image.width * scale));
  canvas.height = Math.max(1, Math.round(image.height * scale));
  const context = canvas.getContext("2d");
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  image.close();

  let blob = await canvasBlob(canvas, 0.78);
  if (blob.size > 900_000) blob = await canvasBlob(canvas, 0.62);
  return new File([blob], file.name.replace(/\.[^.]+$/, ".jpg"), { type: "image/jpeg" });
}

function renderPreviews(files) {
  releasePreviewUrls();
  preview.replaceChildren();
  if (!files.length) return;

  const label = document.createElement("span");
  label.textContent = `${files.length} photo${files.length === 1 ? "" : "s"} selected`;
  preview.append(label);
  files.forEach((file) => {
    const url = URL.createObjectURL(file);
    previewUrls.push(url);
    const image = document.createElement("img");
    image.src = url;
    image.alt = `Preview of ${file.name}`;
    preview.append(image);
  });
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    const config = await response.json();
    if (config.ready) {
      healthBanner.classList.add("hidden");
      return;
    }

    healthBanner.textContent = "Claim drafting is temporarily unavailable. Please try again later.";
    healthBanner.classList.remove("hidden");
    healthBanner.classList.add("warning");
  } catch {
    healthBanner.textContent = "Unable to check service availability. Please try again later.";
    healthBanner.classList.remove("hidden");
    healthBanner.classList.add("warning");
  }
}

function getErrorMessage(payload, status) {
  const detail = payload && payload.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail.message === "string") return detail.message;
  return `Request failed (${status}). Check the files and server configuration, then try again.`;
}

function textNode(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text == null ? "" : String(text);
  if (className) node.className = className;
  return node;
}

function money(value, currency) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "—";
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: currency || "INR",
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency || "INR"} ${amount.toFixed(2)}`;
  }
}

function humanize(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function makeCard(title) {
  const card = document.createElement("section");
  card.className = "results-card";
  card.append(textNode("h3", title));
  return card;
}

function renderEstimate(payload) {
  const contractB = payload.contract_b;
  const contractC = payload.contract_c;
  const card = makeCard("Repair estimate");
  const incomplete = contractB.unpriced_parts && contractB.unpriced_parts.length > 0;
  const pill = textNode("span", incomplete ? "Incomplete estimate" : "Estimate prepared", `status-pill${incomplete ? " incomplete" : ""}`);
  card.append(pill);

  const wrapper = document.createElement("div");
  wrapper.className = "table-wrap";
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headerRow = document.createElement("tr");
  ["Part", "Action", "Material", "Part", "Labour", "Paint", "After deduction*"].forEach((label) => {
    headerRow.append(textNode("th", label));
  });
  head.append(headerRow);
  const body = document.createElement("tbody");
  (contractB.line_items || []).forEach((item) => {
    const row = document.createElement("tr");
    [
      humanize(item.part),
      humanize(item.action),
      humanize(item.material),
      money(item.part_cost, contractB.currency),
      money(item.labour_cost, contractB.currency),
      money(item.paint_cost, contractB.currency),
      money(item.claimable_amount, contractB.currency),
    ].forEach((value) => row.append(textNode("td", value)));
    body.append(row);
  });
  if (!contractB.line_items || !contractB.line_items.length) {
    const row = document.createElement("tr");
    row.append(textNode("td", "No visible damage was priced.", ""));
    row.firstChild.colSpan = 7;
    body.append(row);
  }
  table.append(head, body);
  wrapper.append(table);
  card.append(wrapper);

  const totals = document.createElement("div");
  totals.className = "totals-grid";
  [
    ["Gross estimate", contractB.totals.gross],
    ["Depreciation", contractB.totals.depreciation],
    ["After-deduction estimate", contractB.totals.claimable],
  ].forEach(([label, amount]) => {
    const item = document.createElement("div");
    item.className = "total-item";
    item.append(textNode("span", label), textNode("strong", money(amount, contractB.currency)));
    totals.append(item);
  });
  card.append(totals);
  card.append(textNode(
    "p",
    "The deductions use a Shriram policy reference, not a verified rate for the selected policy. Treat after-deduction figures as illustrative, not claimable or payable amounts.",
    "estimate-assumption",
  ));

  if (incomplete) {
    const note = document.createElement("p");
    note.className = "unpriced-list";
    note.textContent = `Missing prices or rates for: ${contractB.unpriced_parts.map(humanize).join(", ")}. Totals are incomplete and are not a payable claim amount.`;
    card.append(note);
  }
  if (contractC.totals && contractC.totals.unpriced_parts && contractC.totals.unpriced_parts.length && !incomplete) {
    card.append(textNode("p", "Role 3 marked the estimate as incomplete.", "unpriced-list"));
  }
  return card;
}

function renderEvidence(contractC) {
  const card = makeCard("Policy evidence and explanation");
  card.append(textNode("p", contractC.summary, "summary-text"));
  const list = document.createElement("div");
  list.className = "evidence-list";
  (contractC.policy_justification || []).forEach((item) => {
    const evidence = document.createElement("div");
    evidence.className = "evidence-item";
    evidence.append(
      textNode("p", item.statement),
      textNode("small", `${item.source}, page ${item.page}`),
    );
    list.append(evidence);
  });
  if (list.childElementCount) card.append(list);

  if (contractC.exclusions_flagged && contractC.exclusions_flagged.length) {
    const exclusions = document.createElement("ul");
    exclusions.className = "exclusion-list";
    contractC.exclusions_flagged.forEach((item) => exclusions.append(textNode("li", item)));
    card.append(textNode("h3", "Potential exclusions to review"), exclusions);
  }
  card.append(textNode("p", contractC.disclaimer, "disclaimer-text"));
  return card;
}

function renderQuality(contractA) {
  const card = makeCard("Photo assessment");
  if (contractA.damages && contractA.damages.length) {
    const wrapper = document.createElement("div");
    wrapper.className = "table-wrap";
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const row = document.createElement("tr");
    ["Part", "Damage", "Severity", "Confidence", "Photo"].forEach((label) => row.append(textNode("th", label)));
    head.append(row);
    const body = document.createElement("tbody");
    contractA.damages.forEach((damage) => {
      const damageRow = document.createElement("tr");
      [
        humanize(damage.part),
        humanize(damage.damage_type),
        humanize(damage.severity),
        `${Math.round(Number(damage.confidence) * 100)}%`,
        String(Number(damage.image_index) + 1),
      ].forEach((value) => damageRow.append(textNode("td", value)));
      body.append(damageRow);
    });
    table.append(head, body);
    wrapper.append(table);
    card.append(wrapper);
  } else {
    card.append(textNode("p", "No visible damage was reported. This does not rule out hidden damage.", "summary-text"));
  }

  if (contractA.image_quality_flags && contractA.image_quality_flags.length) {
    const flags = document.createElement("div");
    flags.className = "quality-flags";
    contractA.image_quality_flags.forEach((flag) => {
      const match = /^image_(\d+)_(.+)$/.exec(flag);
      const label = match ? `Photo ${Number(match[1]) + 1}: ${humanize(match[2]).toLowerCase()}` : flag;
      flags.append(textNode("span", label));
    });
    card.append(flags);
  }
  card.append(textNode("p", `Vision model: ${contractA.model_used} · Prompt: ${contractA.prompt_strategy}`, "form-footnote"));
  return card;
}

function renderResults(payload) {
  results.replaceChildren();
  const header = document.createElement("div");
  header.className = "results-heading";
  const title = document.createElement("div");
  title.append(
    textNode("h2", "Claim draft ready"),
    textNode("p", `Claim ID ${payload.claim_id} · Review all evidence and estimates before use.`),
  );
  const actions = document.createElement("div");
  actions.className = "result-actions";
  const download = textNode("button", "Download JSON", "button button-secondary");
  download.type = "button";
  download.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${payload.claim_id}_claim_draft.json`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  const print = textNode("button", "Print / Save PDF", "button button-secondary");
  print.type = "button";
  print.addEventListener("click", () => window.print());
  actions.append(download, print);
  header.append(title, actions);
  results.append(header, renderQuality(payload.contract_a), renderEstimate(payload), renderEvidence(payload.contract_c));

  const raw = document.createElement("details");
  raw.className = "results-card";
  raw.append(textNode("summary", "View complete Contract A, B, and C JSON"));
  raw.append(textNode("pre", JSON.stringify(payload, null, 2)));
  results.append(raw);
  results.classList.remove("hidden");
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

photosInput.addEventListener("change", () => {
  clearError();
  const files = Array.from(photosInput.files || []);
  if (files.length > 5) {
    photosInput.value = "";
    renderPreviews([]);
    showError("Choose no more than five photos.");
    return;
  }
  renderPreviews(files);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  results.replaceChildren();
  results.classList.add("hidden");

  const rawPhotos = Array.from(photosInput.files || []);
  const policyFile = (policyInput.files || [])[0];
  if (!rawPhotos.length || !policyFile) {
    showError("Upload at least one vehicle photo and the matching policy PDF.");
    return;
  }
  if (policyFile.size > 2_500_000) {
    showError("The policy PDF must be 2.5 MB or smaller.");
    return;
  }

  submitButton.disabled = true;
  progress.classList.remove("hidden");
  try {
    const compressedPhotos = await Promise.all(rawPhotos.map(compressPhoto));
    const totalBytes = compressedPhotos.reduce((total, file) => total + file.size, policyFile.size);
    if (totalBytes > MAX_UPLOAD_BYTES - 64_000) {
      throw new Error("The compressed photos and policy exceed Vercel's 4 MB upload budget. Use fewer photos or a smaller PDF.");
    }

    const formData = new FormData(form);
    formData.delete("photos");
    compressedPhotos.forEach((file) => formData.append("photos", file, file.name));
    formData.set("policy_pdf", policyFile, policyFile.name);
    const response = await fetch("/api/claims", { method: "POST", body: formData });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(getErrorMessage(payload, response.status));
    renderResults(payload);
  } catch (error) {
    showError(error instanceof Error ? error.message : "The claim request failed.");
  } finally {
    progress.classList.add("hidden");
    submitButton.disabled = false;
  }
});

checkHealth();
