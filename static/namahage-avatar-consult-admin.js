(function () {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const session = params.get("session") || "main";
  const sourceEl = document.getElementById("consultSource");
  const titleEl = document.getElementById("consultTitle");
  const summaryEl = document.getElementById("consultSummary");
  const answerEl = document.getElementById("consultAnswer");
  const namahageEl = document.getElementById("consultNamahage");
  const statusEl = document.getElementById("consultStatus");
  const queueCountEl = document.getElementById("consultQueueCount");

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function updateQueueCount(queueLength) {
    if (queueCountEl) queueCountEl.textContent = `待機 ${Number(queueLength) || 0}件`;
  }

  function fillForm(consult) {
    if (!consult) return;
    sourceEl.value = consult.source || "";
    titleEl.value = consult.title || "";
    summaryEl.value = consult.summary || "";
    answerEl.value = consult.answer || "";
    namahageEl.value = consult.namahage || "";
  }

  function payload(visible) {
    return {
      session,
      visible,
      source: sourceEl.value,
      title: titleEl.value,
      summary: summaryEl.value,
      answer: answerEl.value,
      namahage: namahageEl.value,
    };
  }

  async function readJson(response) {
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data.error || `status ${response.status}`);
      error.data = data;
      throw error;
    }
    return data;
  }

  async function send(visible) {
    const response = await fetch("/api/namahage-avatar/consult", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload(visible)),
    });
    const data = await readJson(response);
    updateQueueCount(data.queueLength);
    setStatus(visible ? "表示しました" : "隠しました");
  }

  async function enqueue() {
    const response = await fetch("/api/namahage-avatar/consult", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload(true), enqueue: true }),
    });
    const data = await readJson(response);
    updateQueueCount(data.queueLength);
    setStatus(`待機列に追加しました（${data.queueLength}件）`);
  }

  async function showNext() {
    const response = await fetch("/api/namahage-avatar/consult/next", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session }),
    });
    if (response.status === 409) {
      const data = await response.json();
      updateQueueCount(data.queueLength);
      setStatus("待機中の相談はありません");
      return;
    }
    const data = await readJson(response);
    fillForm(data.consult);
    updateQueueCount(data.queueLength);
    setStatus(`次の相談を表示しました（残り${data.queueLength}件）`);
  }

  async function loadCurrent() {
    const response = await fetch(`/api/namahage-avatar/consult?session=${encodeURIComponent(session)}`, {
      cache: "no-store",
    });
    const data = await readJson(response);
    const consult = data.consult || {};
    if (consult.title || consult.summary) fillForm(consult);
    updateQueueCount(data.queueLength);
  }

  document.getElementById("consultShow").addEventListener("click", () => {
    send(true).catch(() => setStatus("送信エラー"));
  });
  document.getElementById("consultEnqueue").addEventListener("click", () => {
    enqueue().catch((error) => {
      setStatus(error.message === "title and summary required" ? "タイトルと相談要約を入力してください" : "追加エラー");
    });
  });
  document.getElementById("consultNext").addEventListener("click", () => {
    showNext().catch(() => setStatus("切替エラー"));
  });
  document.getElementById("consultHide").addEventListener("click", () => {
    send(false).catch(() => setStatus("送信エラー"));
  });
  document.getElementById("consultSample").addEventListener("click", () => {
    sourceEl.value = "相談サイトより / 匿名化済み";
    titleEl.value = "家族に本音を言えず、ずっと我慢している";
    summaryEl.value = "相手を傷つけたくなくて黙っていたが、限界が近い。どう切り出せばいいか悩んでいる。";
    answerEl.value = "黙って耐えるのは優しさではなく、問題の先送りだ。短く事実を言え。責めるな、お願いとして出せ。";
    namahageEl.value = "我慢しすぎは悪い子だ。今日は一つだけ本音を言え。泣く子はいねが、黙って壊れる子もいねが。";
    setStatus("例を入れました");
  });

  loadCurrent().catch(() => setStatus("読込エラー"));
})();
