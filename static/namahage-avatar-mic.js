(function () {
  "use strict";

  const button = document.getElementById("namahageMicStart");
  const statusEl = document.getElementById("namahageMicStatus");
  const meterEl = document.getElementById("namahageMicMeter");
  const actionButtons = document.querySelectorAll("[data-action]");
  const params = new URLSearchParams(window.location.search);
  const session = params.get("session") || "main";

  let audioContext = null;
  let analyser = null;
  let audioData = null;
  let animationId = 0;
  let lastSentAt = 0;

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function calculateRms(data) {
    let sum = 0;
    for (let i = 0; i < data.length; i += 1) {
      const normalized = (data[i] - 128) / 128;
      sum += normalized * normalized;
    }
    return Math.sqrt(sum / data.length);
  }

  function updateMeter(volume) {
    if (!meterEl) return;
    meterEl.style.width = `${Math.min(100, Math.round(volume * 780))}%`;
  }

  function postVolume(volume) {
    return fetch("/api/namahage-avatar/audio-level", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session, volume }),
      keepalive: true,
    });
  }

  function postAction(action) {
    return fetch("/api/namahage-avatar/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session, action }),
      keepalive: true,
    });
  }

  function loop() {
    analyser.getByteTimeDomainData(audioData);
    const volume = calculateRms(audioData);
    updateMeter(volume);
    const now = performance.now();
    if (now - lastSentAt > 45) {
      lastSentAt = now;
      postVolume(volume).catch(() => setStatus("送信エラー"));
    }
    animationId = window.requestAnimationFrame(loop);
  }

  async function start() {
    if (animationId) return;
    try {
      setStatus("マイク確認中");
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(stream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);
      audioData = new Uint8Array(analyser.fftSize);
      setStatus("接続中。このページは開いたままにしてください。");
      if (button) button.textContent = "接続中";
      loop();
    } catch (error) {
      setStatus(error && error.message ? error.message : "マイク接続に失敗");
    }
  }

  if (button) button.addEventListener("click", start);
  actionButtons.forEach((actionButton) => {
    actionButton.addEventListener("click", () => {
      const action = actionButton.getAttribute("data-action");
      postAction(action).then(() => setStatus("送信しました")).catch(() => setStatus("送信エラー"));
    });
  });
  if (params.get("autostart") === "1") setTimeout(start, 250);

  window.addEventListener("pagehide", () => {
    if (animationId) window.cancelAnimationFrame(animationId);
    if (audioContext) audioContext.close().catch(() => {});
    postVolume(0).catch(() => {});
  });
})();
