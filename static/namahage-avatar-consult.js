(function () {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const session = params.get("session") || "main";
  const root = document.getElementById("namahageConsult");
  const sourceEl = document.getElementById("namahageConsultSource");
  const titleEl = document.getElementById("namahageConsultTitle");
  const summaryEl = document.getElementById("namahageConsultSummary");
  const answerEl = document.getElementById("namahageConsultAnswer");
  const namahageBlockEl = document.getElementById("namahageConsultNamahageBlock");
  const namahageEl = document.getElementById("namahageConsultNamahage");
  let lastUpdated = 0;

  function text(el, value) {
    if (el) el.textContent = value || "";
  }

  async function poll() {
    try {
      const response = await fetch(`/api/namahage-avatar/consult?session=${encodeURIComponent(session)}`, {
        cache: "no-store",
      });
      const payload = await response.json();
      const consult = payload.consult || {};
      if (!consult.visible) {
        root.hidden = true;
      } else if (consult.updated !== lastUpdated || root.hidden) {
        lastUpdated = consult.updated || Date.now();
        text(sourceEl, consult.source);
        text(titleEl, consult.title);
        text(summaryEl, consult.summary);
        text(answerEl, consult.answer);
        text(namahageEl, consult.namahage);
        if (namahageBlockEl) namahageBlockEl.hidden = !consult.namahage;
        root.hidden = false;
      }
    } catch (error) {
      root.hidden = true;
    } finally {
      window.setTimeout(poll, 500);
    }
  }

  if (root) poll();
})();
