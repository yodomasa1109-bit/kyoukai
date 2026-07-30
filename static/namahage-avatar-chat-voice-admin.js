(function () {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const session = params.get("session") || "main";
  const authorEl = document.getElementById("chatVoiceAuthor");
  const textEl = document.getElementById("chatVoiceText");
  const statusEl = document.getElementById("chatVoiceAdminStatus");

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  async function send() {
    const response = await fetch("/api/namahage-avatar/chat-voice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session,
        author: authorEl.value,
        text: textEl.value,
      }),
    });
    if (!response.ok) throw new Error(`status ${response.status}`);
    const payload = await response.json();
    setStatus(`送信しました #${payload.message.id}`);
    textEl.value = "";
  }

  document.getElementById("chatVoiceSend").addEventListener("click", () => {
    send().catch(() => setStatus("送信エラー"));
  });

  document.getElementById("chatVoiceSample").addEventListener("click", () => {
    authorEl.value = "視聴者";
    textEl.value = "なまはげさん、今日の相談かなり刺さりました。包丁はしまってください。";
    setStatus("例を入れました");
  });
})();
