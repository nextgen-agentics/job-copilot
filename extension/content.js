/**
 * content.js — Page Context Extractor
 * Auto-extracts job posting content from the current tab.
 * Works on LinkedIn, Indeed, Glassdoor, and generic job pages.
 */

(function extractJobContext() {
  const url = window.location.href;

  let jobData = {
    url,
    title: document.title,
    source: "generic",
    job_title: "",
    company: "",
    location: "",
    description: "",
  };

  // ── LinkedIn ─────────────────────────────────────────────────────────────
  if (url.includes("linkedin.com/jobs")) {
    jobData.source = "linkedin";
    jobData.job_title =
      document.querySelector(".job-details-jobs-unified-top-card__job-title h1")?.innerText ||
      document.querySelector(".jobs-unified-top-card__job-title")?.innerText ||
      document.querySelector("h1.t-24")?.innerText || "";
    jobData.company =
      document.querySelector(".job-details-jobs-unified-top-card__company-name")?.innerText ||
      document.querySelector(".jobs-unified-top-card__company-name")?.innerText || "";
    jobData.location =
      document.querySelector(".job-details-jobs-unified-top-card__bullet")?.innerText ||
      document.querySelector(".jobs-unified-top-card__bullet")?.innerText || "";
    jobData.description =
      document.querySelector(".jobs-description__content")?.innerText ||
      document.querySelector(".job-view-layout")?.innerText || "";
  }

  // ── Indeed ───────────────────────────────────────────────────────────────
  else if (url.includes("indeed.com")) {
    jobData.source = "indeed";
    jobData.job_title = document.querySelector('[data-testid="jobsearch-JobInfoHeader-title"]')?.innerText ||
      document.querySelector("h1.jobsearch-JobInfoHeader-title")?.innerText || "";
    jobData.company = document.querySelector('[data-testid="inlineHeader-companyName"]')?.innerText ||
      document.querySelector(".jobsearch-InlineCompanyRating-companyHeader")?.innerText || "";
    jobData.location = document.querySelector('[data-testid="job-location"]')?.innerText || "";
    jobData.description = document.querySelector("#jobDescriptionText")?.innerText ||
      document.querySelector(".jobsearch-jobDescriptionText")?.innerText || "";
  }

  // ── Glassdoor ────────────────────────────────────────────────────────────
  else if (url.includes("glassdoor.com")) {
    jobData.source = "glassdoor";
    jobData.job_title = document.querySelector('[data-test="job-title"]')?.innerText ||
      document.querySelector("h1")?.innerText || "";
    jobData.company = document.querySelector('[data-test="employer-name"]')?.innerText || "";
    jobData.location = document.querySelector('[data-test="location"]')?.innerText || "";
    jobData.description = document.querySelector('[data-test="description"]')?.innerText ||
      document.querySelector(".jobDescriptionContent")?.innerText || "";
  }

  // ── Generic fallback ─────────────────────────────────────────────────────
  else {
    // Try common patterns
    jobData.job_title =
      document.querySelector("h1")?.innerText ||
      document.querySelector('[class*="job-title"]')?.innerText || "";
    jobData.company =
      document.querySelector('[class*="company"]')?.innerText ||
      document.querySelector('[class*="employer"]')?.innerText || "";

    // Grab meaningful page text (avoid nav/footer noise)
    const main = document.querySelector("main") ||
      document.querySelector("article") ||
      document.querySelector('[class*="content"]') ||
      document.body;
    jobData.description = main?.innerText?.slice(0, 4000) || "";
  }

  // Truncate description to avoid overloading the LLM context
  jobData.description = jobData.description?.trim().slice(0, 3500) || "";

  // Send to background.js for relay to side panel
  if (jobData.description || jobData.job_title) {
    chrome.runtime.sendMessage({ type: "PAGE_CONTEXT", data: jobData });
  }
})();
