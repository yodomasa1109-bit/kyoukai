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

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
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

  async function send(visible) {
    const response = await fetch("/api/namahage-avatar/consult", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload(visible)),
    });
    if (!response.ok) throw new Error(`status ${response.status}`);
    setStatus(visible ? "表示しました" : "隠しました");
  }

  document.getElementById("consultShow").addEventListener("click", () => {
    send(true).catch(() => setStatus("送信エラー"));
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
})();
