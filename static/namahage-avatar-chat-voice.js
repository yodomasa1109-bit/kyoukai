(function () {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const session = params.get("session") || "main";
  const autostart = params.get("autostart") === "1";
  const showUi = params.get("ui") !== "0";
  const rate = Number(params.get("rate") || 1.02);
  const pitch = Number(params.get("pitch") || 0.86);
  const volume = Number(params.get("volume") || 1);
  const voiceHint = (params.get("voice") || "Japanese").toLowerCase();
  const root = document.getElementById("chatVoice");
  const startButton = document.getElementById("chatVoiceStart");
  const statusEl = document.getElementById("chatVoiceStatus");
  const lineEl = document.getElementById("chatVoiceLine");

  let enabled = false;
  let lastId = 0;
  let speaking = false;
  let queue = [];
  let pulseTimer = 0;
  let hideTimer = 0;
  let cachedVoice = null;

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function setLine(text) {
    if (lineEl) lineEl.textContent = text;
    if (!root || !showUi) return;
    root.classList.add("is-visible");
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(() => root.classList.remove("is-visible"), 4200);
  }

  function postMouthVolume(value) {
    return fetch("/api/namahage-avatar/audio-level", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session, source: "chat-voice", volume: value }),
      keepalive: true,
    });
  }

  function startMouthPulse(text) {
    const seed = Math.max(8, text.length);
    window.clearInterval(pulseTimer);
    pulseTimer = window.setInterval(() => {
      const wobble = Math.sin(Date.now() / 82) * 0.025 + Math.random() * 0.035;
      const base = Math.min(0.16, 0.055 + seed / 1800);
      postMouthVolume(Math.max(0.025, base + wobble)).catch(() => {});
    }, 70);
  }

  function stopMouthPulse() {
    window.clearInterval(pulseTimer);
    pulseTimer = 0;
    postMouthVolume(0).catch(() => {});
  }

  function chooseVoice() {
    if (cachedVoice) return cachedVoice;
    const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
    cachedVoice = voices.find((voice) => voice.lang && voice.lang.toLowerCase().startsWith("ja"))
      || voices.find((voice) => voice.name.toLowerCase().includes(voiceHint))
      || voices[0]
      || null;
    return cachedVoice;
  }

  function formatMessage(message) {
    const author = message.author ? `${message.author}さん、` : "";
    return `${author}${message.text}`;
  }

  function speakNext() {
    if (!enabled || speaking || queue.length === 0) return;
    if (!("speechSynthesis" in window)) {
      setStatus("このブラウザは読み上げ非対応です");
      return;
    }

    const message = queue.shift();
    const text = formatMessage(message);
    const utterance = new SpeechSynthesisUtterance(text);
    const voice = chooseVoice();
    if (voice) utterance.voice = voice;
    utterance.lang = voice && voice.lang ? voice.lang : "ja-JP";
    utterance.rate = rate;
    utterance.pitch = pitch;
    utterance.volume = volume;

    speaking = true;
    setStatus(`読み上げ中 #${message.id}`);
    setLine(text);
    startMouthPulse(text);

    utterance.onend = () => {
      speaking = false;
      stopMouthPulse();
      setStatus("待機中");
      window.setTimeout(speakNext, 180);
    };
    utterance.onerror = () => {
      speaking = false;
      stopMouthPulse();
      setStatus("読み上げエラー");
      window.setTimeout(speakNext, 400);
    };
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }

  async function poll() {
    if (enabled) {
      try {
        const response = await fetch(`/api/namahage-avatar/chat-voice?session=${encodeURIComponent(session)}&since=${lastId}`, {
          cache: "no-store",
        });
        if (response.ok) {
          const payload = await response.json();
          const messages = Array.isArray(payload.messages) ? payload.messages : [];
          messages.forEach((message) => {
            const id = Number(message.id || 0);
            if (id > lastId) lastId = id;
            queue.push(message);
          });
          speakNext();
        }
      } catch (error) {
        setStatus("受信エラー");
      }
    }
    window.setTimeout(poll, 700);
  }

  function start() {
    enabled = true;
    if (startButton) startButton.hidden = true;
    if (root && !showUi) root.hidden = true;
    setStatus("接続中");
    if ("speechSynthesis" in window) {
      window.speechSynthesis.getVoices();
      window.speechSynthesis.onvoiceschanged = () => {
        cachedVoice = null;
        chooseVoice();
      };
    }
  }

  if (startButton) startButton.addEventListener("click", start);
  if (autostart) window.setTimeout(start, 250);
  poll();

  window.addEventListener("pagehide", () => {
    stopMouthPulse();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  });
})();
