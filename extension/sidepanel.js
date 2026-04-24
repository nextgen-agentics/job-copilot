/**
 * sidepanel.js — JobCopilot AI Side Panel Logic
 *
 * Handles:
 *  - Profile tab: resume upload, GitHub fetch, preferences + model save
 *  - Analyze tab: auto page context, SSE agent streaming, reasoning chain render
 *  - Dashboard tab: populate fit score, company, salary, visa, bullets, cover letter, interview
 */

const API = "http://localhost:8000";

// ── State ──────────────────────────────────────────────────────────────────
let pageContext = null;
let profile = {};
let dashboardData = null;

// ── DOM helpers ────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const setMsg = (id, text, cls = "") => {
  const el = $(id);
  el.textContent = text;
  el.className = `status-msg ${cls}`;
};

// ══════════════════════════════════════════════════════════════════════════
// Tabs
// ══════════════════════════════════════════════════════════════════════════
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    $(`tab-content-${tab}`).classList.add("active");
    if (tab === "dashboard" && dashboardData) renderDashboard(dashboardData);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Health check
// ══════════════════════════════════════════════════════════════════════════
async function checkHealth() {
  try {
    const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      $("status-dot").classList.add("ok");
    } else {
      $("status-dot").classList.add("error");
    }
  } catch {
    $("status-dot").classList.add("error");
  }
}

// ══════════════════════════════════════════════════════════════════════════
// Profile — Load from localStorage
// ══════════════════════════════════════════════════════════════════════════
function loadProfile() {
  const saved = localStorage.getItem("jobcopilot_profile");
  if (saved) {
    try { profile = JSON.parse(saved); } catch { profile = {}; }
  }
  if (profile.preferences) $("prefs-input").value = profile.preferences;
  if (profile.model) {
    const sel = $("model-select");
    const found = Array.from(sel.options).some((o) => o.value === profile.model);
    if (found) sel.value = profile.model;
    else $("model-custom").value = profile.model;
  }
  if (profile.resumeLabel) setMsg("resume-status", `✅ ${profile.resumeLabel}`, "success");
  if (profile.githubUsername) setMsg("github-status", `✅ @${profile.githubUsername}`, "success");
}

function saveProfileLocal() {
  localStorage.setItem("jobcopilot_profile", JSON.stringify(profile));
}

// ══════════════════════════════════════════════════════════════════════════
// Resume Upload
// ══════════════════════════════════════════════════════════════════════════
const dropZone = $("drop-zone");

dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("dragover"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file) uploadResume(file);
});

$("resume-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) uploadResume(file);
});

async function uploadResume(file) {
  if (!file.name.endsWith(".pdf")) {
    setMsg("resume-status", "❌ Only PDF files are supported", "error");
    return;
  }
  setMsg("resume-status", "⏳ Parsing resume...", "info");
  const form = new FormData();
  form.append("file", file);
  try {
    const r = await fetch(`${API}/profile/resume`, { method: "POST", body: form });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "Upload failed");
    profile.resumeLabel = file.name;
    profile.resumeSkills = data.skills_found || [];
    if (data.github_detected) {
      $("github-input").value = data.github_detected;
    }
    saveProfileLocal();
    if (data.llm_used === false) {
      // Fallback regex parse — upload succeeded but LLM was rate-limited
      setMsg("resume-status",
        `⚠️ Parsed (basic mode) · ${data.skills_found?.length || 0} skills · ${data.pages} page(s) · LLM rate-limited, try again later`,
        "info");
    } else {
      setMsg("resume-status",
        `✅ Parsed · ${data.skills_found?.length || 0} skills · ${data.pages} page(s)${data.name ? ` · ${data.name}` : ""}`,
        "success");
    }
  } catch (e) {
    setMsg("resume-status", `❌ ${e.message}`, "error");
  }
}

// ══════════════════════════════════════════════════════════════════════════
// GitHub Fetch
// ══════════════════════════════════════════════════════════════════════════
$("github-btn").addEventListener("click", async () => {
  const url = $("github-input").value.trim();
  if (!url) return;
  setMsg("github-status", "⏳ Fetching GitHub profile...", "info");
  try {
    const r = await fetch(`${API}/profile/github`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ github_url: url }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "GitHub fetch failed");
    profile.githubUsername = data.username;
    profile.githubUrl = url;
    saveProfileLocal();
    setMsg("github-status", `✅ @${data.username} · ${data.repos} repos · ML: ${data.ml_projects?.join(", ") || "none"}`, "success");
  } catch (e) {
    setMsg("github-status", `❌ ${e.message}`, "error");
  }
});

// ══════════════════════════════════════════════════════════════════════════
// Save Profile (preferences + model)
// ══════════════════════════════════════════════════════════════════════════
$("save-profile-btn").addEventListener("click", async () => {
  const prefs = $("prefs-input").value.trim();
  const customModel = $("model-custom").value.trim();
  const model = customModel || $("model-select").value;

  profile.preferences = prefs;
  profile.model = model;
  saveProfileLocal();

  try {
    await fetch(`${API}/profile/prefs`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preferences: prefs, model }),
    });
  } catch { /* backend offline — local save still good */ }

  setMsg("profile-saved-msg", "✅ Profile saved!", "success");
  setTimeout(() => setMsg("profile-saved-msg", "", ""), 2000);
});

// ══════════════════════════════════════════════════════════════════════════
// Page Context (auto from content.js)
// ══════════════════════════════════════════════════════════════════════════
function loadPageContext() {
  chrome.storage.session.get("pageContext", ({ pageContext: ctx }) => {
    if (!ctx) return;
    pageContext = ctx;
    const card = $("job-context-card");
    card.classList.remove("hidden");
    $("context-source-badge").textContent = ctx.source?.toUpperCase() || "JOB PAGE";
    $("context-job-title").textContent = ctx.job_title || ctx.title || "Job Posting";
    $("context-company").textContent = [ctx.company, ctx.location].filter(Boolean).join(" · ") || ctx.url;

    // Auto-fill query if empty
    if (!$("query-input").value && ctx.job_title) {
      $("query-input").value = `Analyze this job posting and help me decide if I should apply. Check fit, salary, company, and visa sponsorship.`;
    }
  });
}

// ══════════════════════════════════════════════════════════════════════════
// Analyze — Run Agent with SSE
// ══════════════════════════════════════════════════════════════════════════
$("analyze-btn").addEventListener("click", runAnalysis);

async function runAnalysis() {
  const query = $("query-input").value.trim();
  if (!query) return;

  // Reset UI
  const stepsEl = $("chain-steps");
  stepsEl.innerHTML = "";
  $("chain-container").classList.remove("hidden");
  dashboardData = null;

  const btn = $("analyze-btn");
  const btnText = $("analyze-btn-text");
  btn.disabled = true;
  btnText.innerHTML = `<span class="spinner"></span>Analyzing…`;

  // Build page context string
  let pageCtxStr = "";
  if (pageContext) {
    pageCtxStr = `Source: ${pageContext.source}\nTitle: ${pageContext.job_title}\nCompany: ${pageContext.company}\nLocation: ${pageContext.location}\n\nDescription:\n${pageContext.description}`;
  }

  // Determine model
  const customModel = $("model-custom").value.trim();
  const model = customModel || $("model-select").value || profile.model || "gemini-2.0-flash";

  try {
    const response = await fetch(`${API}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        page_context: pageCtxStr,
        model,
        profile_override: null, // backend uses its own cached profile
      }),
    });

    if (!response.ok) throw new Error(`Backend error: ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep incomplete line
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const evt = JSON.parse(line.slice(6));
            handleSSEEvent(evt, stepsEl);
          } catch { /* skip malformed */ }
        }
      }
    }
  } catch (e) {
    addChainStep(stepsEl, "error", `Connection error: ${e.message}`);
  } finally {
    btn.disabled = false;
    btnText.textContent = "⚡ Run Analysis";
  }
}

// ── SSE Event Router ──────────────────────────────────────────────────────
function handleSSEEvent(evt, stepsEl) {
  if (evt.type === "llm_call") {
    addLLMCallStep(stepsEl, evt);
  } else if (evt.type === "llm_output") {
    addLLMOutputStep(stepsEl, evt);
  } else if (evt.type === "tool_call") {
    addToolCallStep(stepsEl, evt);
  } else if (evt.type === "tool_result") {
    addToolResultStep(stepsEl, evt);
  } else if (evt.type === "answer") {
    addAnswerStep(stepsEl, evt);
    dashboardData = evt.dashboard || {};
    setTimeout(() => {
      document.querySelector('[data-tab="dashboard"]').click();
    }, 800);
  } else if (evt.type === "error") {
    addChainStep(stepsEl, "error", evt.content);
  } else if (evt.type === "retry") {
    addChainStep(stepsEl, "retry", evt.content);
  }
}

// ── Chain Step Renderers ──────────────────────────────────────────────────
function createStepShell(typeClass, labelText, iteration) {
  const step = document.createElement("div");
  step.className = `chain-step step-${typeClass}`;

  const line = document.createElement("div");
  line.className = "step-line";
  const dot = document.createElement("div");
  dot.className = "step-dot";
  const connector = document.createElement("div");
  connector.className = "step-connector";
  line.appendChild(dot);
  line.appendChild(connector);

  const body = document.createElement("div");
  body.className = "step-body";

  const header = document.createElement("div");
  header.className = "step-header";

  const label = document.createElement("div");
  label.className = "step-label";
  label.textContent = labelText;
  header.appendChild(label);

  if (iteration != null) {
    const badge = document.createElement("span");
    badge.className = "step-iter-badge";
    badge.textContent = `iter ${iteration}`;
    header.appendChild(badge);
  }

  body.appendChild(header);
  step.appendChild(line);
  step.appendChild(body);
  return { step, body };
}

function makeToggleCard(content, previewText) {
  const card = document.createElement("div");
  card.className = "step-card";

  const toggle = document.createElement("button");
  toggle.className = "result-toggle";
  toggle.textContent = `▶ ${previewText}`;
  card.appendChild(toggle);

  const pre = document.createElement("pre");
  pre.className = "result-json hidden";
  pre.textContent = content;
  card.appendChild(pre);

  toggle.addEventListener("click", () => {
    const hidden = pre.classList.toggle("hidden");
    toggle.textContent = hidden ? `▶ ${previewText}` : `▼ Hide`;
  });
  return card;
}

// 🧠 LLM Call — shows model + prompt preview
function addLLMCallStep(stepsEl, evt) {
  const { step, body } = createStepShell("llm-call",
    `🧠 LLM Call · ${evt.model || "gemini"}`, evt.iteration);
  const card = document.createElement("div");
  card.className = "step-card";

  const modelBadge = document.createElement("div");
  modelBadge.className = "tool-name";
  modelBadge.textContent = evt.model || "gemini";
  card.appendChild(modelBadge);

  if (evt.prompt_preview) {
    const previewWrap = document.createElement("div");
    previewWrap.className = "tool-args";
    previewWrap.style.cssText = "max-height:80px;overflow:hidden;mask-image:linear-gradient(to bottom,#fff 60%,transparent);white-space:pre-wrap;font-size:10px;";
    previewWrap.textContent = "…" + evt.prompt_preview;
    card.appendChild(previewWrap);
  }

  body.appendChild(card);
  stepsEl.appendChild(step);
}

// 📤 LLM Output — collapsible raw response
function addLLMOutputStep(stepsEl, evt) {
  const { step, body } = createStepShell("llm-output",
    `📤 LLM Output · iteration ${evt.iteration || ""}`, null);
  const card = makeToggleCard(evt.raw || "", "Show raw LLM response");
  body.appendChild(card);
  stepsEl.appendChild(step);
}

// 🔧 Tool Call
function addToolCallStep(stepsEl, evt) {
  const { step, body } = createStepShell("tool-call",
    `🔧 Tool Call · ${evt.tool}`, evt.iteration);
  const card = document.createElement("div");
  card.className = "step-card";

  const badge = document.createElement("div");
  badge.className = "tool-name";
  badge.textContent = evt.tool;
  card.appendChild(badge);

  const args = document.createElement("div");
  args.className = "tool-args";
  args.textContent = JSON.stringify(evt.args, null, 2);
  card.appendChild(args);

  body.appendChild(card);
  stepsEl.appendChild(step);
}

// 📊 Tool Result
function addToolResultStep(stepsEl, evt) {
  const { step, body } = createStepShell("tool-result",
    `📊 Tool Result · ${evt.tool}`, evt.iteration);
  const card = makeToggleCard(
    JSON.stringify(evt.result, null, 2),
    "Show result"
  );
  body.appendChild(card);
  stepsEl.appendChild(step);
}

// ✅ Final Answer
function addAnswerStep(stepsEl, evt) {
  const { step, body } = createStepShell("answer",
    `✅ Final Answer · ${evt.iterations} iteration${evt.iterations !== 1 ? "s" : ""}`, null);
  const card = document.createElement("div");
  card.className = "step-card";
  card.style.lineHeight = "1.6";
  card.textContent = evt.content;
  body.appendChild(card);
  stepsEl.appendChild(step);
}

// ❌ Error / ℹ️ Retry / Info
function addChainStep(stepsEl, type, content) {
  const icons = { error: "❌", retry: "🔄", info: "ℹ️" };
  const { step, body } = createStepShell(type, `${icons[type] || "ℹ️"} ${type === "retry" ? "Retry" : type === "error" ? "Error" : "Info"}`, null);
  const card = document.createElement("div");
  card.className = "step-card";
  card.textContent = content;
  body.appendChild(card);
  stepsEl.appendChild(step);
}


// ══════════════════════════════════════════════════════════════════════════
// Dashboard Renderer
// ══════════════════════════════════════════════════════════════════════════
function renderDashboard(data) {
  if (!data || Object.keys(data).length === 0) return;

  $("dashboard-empty").classList.add("hidden");
  $("dashboard-content").classList.remove("hidden");

  // ── Fit Score ────────────────────────────────────────────────────────
  const score = data.fit_score ?? 0;
  $("score-number").textContent = score;

  // Animate ring (circumference = 2π × 50 ≈ 314)
  const circumference = 314;
  const offset = circumference - (score / 100) * circumference;
  setTimeout(() => {
    $("ring-progress").style.strokeDashoffset = offset;
    // Color by score
    const color = score >= 80 ? "#10b981" : score >= 60 ? "#8b5cf6" : "#f59e0b";
    $("ring-progress").style.stroke = color;
  }, 100);

  $("score-verdict").textContent = data.verdict ||
    (score >= 85 ? "Excellent match" : score >= 70 ? "Good match" : score >= 55 ? "Moderate match" : "Low match");

  // Score breakdown bars
  const bars = $("score-bars");
  bars.innerHTML = "";
  const breakdown = data.fit_breakdown || {};
  const barDefs = [
    ["Skills", breakdown.skills_match],
    ["Experience", breakdown.experience_match],
    ["Education", breakdown.education_match],
    ["Preferences", breakdown.preferences_match],
  ];
  barDefs.forEach(([label, pct]) => {
    if (pct == null) return;
    bars.innerHTML += `
      <div class="score-bar-row">
        <div class="score-bar-label">${label}</div>
        <div class="score-bar-track">
          <div class="score-bar-fill" style="width:${pct}%"></div>
        </div>
        <div class="score-bar-pct">${pct}%</div>
      </div>`;
  });

  // ── Company Insights ─────────────────────────────────────────────────
  const ci = data.company_insights || {};
  const companyEl = $("company-content");
  companyEl.innerHTML = "";
  if (ci.description) {
    const desc = document.createElement("p");
    desc.className = "text-muted text-sm";
    desc.textContent = ci.description.slice(0, 300) + (ci.description.length > 300 ? "…" : "");
    companyEl.appendChild(desc);
  }
  if (ci.culture_tags?.length) {
    const tags = document.createElement("div");
    tags.className = "tags mt-2";
    ci.culture_tags.forEach((t) => {
      tags.innerHTML += `<span class="tag">${t}</span>`;
    });
    companyEl.appendChild(tags);
  }
  if (ci.website) {
    const link = document.createElement("a");
    link.href = ci.website;
    link.target = "_blank";
    link.style.cssText = "display:block;margin-top:8px;font-size:11px;color:#8b5cf6;";
    link.textContent = "🔗 " + ci.website;
    companyEl.appendChild(link);
  }

  // ── Salary ───────────────────────────────────────────────────────────
  const sal = data.salary || {};
  const salEl = $("salary-content");
  salEl.innerHTML = "";
  if (sal.median || sal.estimated_average) {
    const median = sal.median || sal.estimated_average;
    const cur = sal.currency || "£";
    salEl.innerHTML = `
      <div class="salary-big">${cur}${median?.toLocaleString()}</div>
      <div class="text-muted text-sm" style="margin-top:2px">median salary</div>`;
    if (sal.salary_min && sal.salary_max) {
      salEl.innerHTML += `
        <div class="salary-range" style="margin-top:10px">
          <span class="text-muted text-sm">${cur}${sal.salary_min?.toLocaleString()}</span>
          <div class="salary-track" style="flex:1">
            <div class="salary-fill" style="width:100%"></div>
            ${sal.median ? `<div class="salary-median-marker" style="left:${Math.round(((median - sal.salary_min) / (sal.salary_max - sal.salary_min)) * 100)}%"></div>` : ""}
          </div>
          <span class="text-muted text-sm">${cur}${sal.salary_max?.toLocaleString()}</span>
        </div>
        <div class="text-sm text-muted" style="margin-top:4px">🟡 Median marker</div>`;
    }
    if (sal.note) {
      salEl.innerHTML += `<div class="text-sm text-muted" style="margin-top:6px">${sal.note}</div>`;
    }
  } else {
    salEl.textContent = "Salary data not available for this role/location.";
    salEl.className = "text-muted text-sm";
  }

  // ── Visa Info ────────────────────────────────────────────────────────
  const visa = data.visa_info || {};
  const visaEl = $("visa-content");
  visaEl.innerHTML = "";
  const sponsors = visa.sponsors_visa;
  const badgeClass = sponsors === true ? "yes" : sponsors === false ? "no" : "unknown";
  const badgeText = sponsors === true ? "✅ Sponsors Visas" : sponsors === false ? "❌ No Visa Sponsorship" : "⚠️ Unknown";
  visaEl.innerHTML = `<span class="visa-badge ${badgeClass}">${badgeText}</span>`;
  if (visa.visa_type) visaEl.innerHTML += `<div class="text-sm text-muted" style="margin-top:4px">Type: ${visa.visa_type}</div>`;
  if (visa.language_requirements) visaEl.innerHTML += `<div class="text-sm text-muted" style="margin-top:4px">Language: ${visa.language_requirements}</div>`;
  if (visa.note) visaEl.innerHTML += `<div class="text-sm text-muted" style="margin-top:6px; font-style:italic">${visa.note}</div>`;

  // ── Resume Bullets ───────────────────────────────────────────────────
  const bulletsEl = $("bullets-list");
  bulletsEl.innerHTML = "";
  (data.resume_bullets || []).forEach((b) => {
    const li = document.createElement("li");
    li.textContent = b;
    bulletsEl.appendChild(li);
  });

  // ── Cover Letter Points ──────────────────────────────────────────────
  const coverEl = $("cover-list");
  coverEl.innerHTML = "";
  (data.cover_letter_points || []).forEach((p) => {
    const li = document.createElement("li");
    li.textContent = p;
    coverEl.appendChild(li);
  });

  // ── Interview Questions ──────────────────────────────────────────────
  const interviewEl = $("interview-list");
  interviewEl.innerHTML = "";
  (data.interview_questions || []).forEach((q) => {
    const li = document.createElement("li");
    li.textContent = q;
    interviewEl.appendChild(li);
  });
}

// ══════════════════════════════════════════════════════════════════════════
// Init
// ══════════════════════════════════════════════════════════════════════════
checkHealth();
loadProfile();
loadPageContext();

// Re-check page context when storage changes (new tab navigated)
chrome.storage.session.onChanged?.addListener((changes) => {
  if (changes.pageContext) loadPageContext();
});
