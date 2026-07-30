(function () {
  "use strict";

  const root = document.getElementById("namahageAvatar");
  const leftCanvas = document.getElementById("namahageAvatarLeftEye");
  const rightCanvas = document.getElementById("namahageAvatarRightEye");
  const micButton = document.getElementById("namahageAvatarMic");
  const knifeButton = document.getElementById("namahageAvatarKnifeButton");
  const debugEl = document.getElementById("namahageAvatarDebug");

  if (!root || !leftCanvas || !rightCanvas) return;

  const params = new URLSearchParams(window.location.search);
  const debug = params.get("debug") === "1" || params.get("debug") === "true";
  const autostart = params.get("autostart") === "1" || params.get("autostart") === "true";
  const audioMode = params.get("audio") || "mic";
  const relaySession = params.get("session") || "main";
  const useAudioRelay = audioMode === "relay";
  const relayGain = Number(params.get("relayGain") || 4.2);
  const relayFloor = Number(params.get("relayFloor") || 0.012);
  const enableMic = params.get("mic") !== "0" && !useAudioRelay;
  const enableKeyboardControls = params.get("keys") !== "0";
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const config = {
    cols: 16,
    rows: 12,
    noiseFloor: 0.018,
    speechThreshold: 0.03,
    attack: 0.62,
    release: 0.62,
    maxJawOpen: reducedMotion ? 20 : 42,
    holdClosedMs: 35,
    shakeMs: [100, 180],
    idleGazeMs: reducedMotion ? [2600, 5600] : [1500, 4000],
    blinkMs: reducedMotion ? [5200, 10000] : [3000, 8000],
  };

  const ctxLeft = leftCanvas.getContext("2d");
  const ctxRight = rightCanvas.getContext("2d");
  const timers = new Set();
  let animationId = 0;
  let stream = null;
  let audioContext = null;
  let analyser = null;
  let audioData = null;
  let relayTimer = 0;
  let actionTimer = 0;
  let smoothedVolume = 0;
  let lastSpeakingAt = 0;
  let micState = useAudioRelay ? "relay" : (enableMic ? "idle" : "disabled");
  let knifeTimer = 0;
  let hornTimer = 0;

  const state = {
    mode: "dot",
    leftPos: { x: 6, y: 4 },
    rightPos: { x: 6, y: 4 },
    lockedUntil: 0,
    speaking: false,
    level: 0,
    jawOpen: 0,
    jawRotate: 0,
    shakeX: 0,
    shakeRotate: 0,
    knifeSwinging: false,
    hornTwitching: false,
  };

  function setT(fn, ms) {
    const id = window.setTimeout(() => {
      timers.delete(id);
      fn();
    }, ms);
    timers.add(id);
    return id;
  }

  function clearTimers() {
    timers.forEach((id) => window.clearTimeout(id));
    timers.clear();
  }

  function rand(min, max) {
    return min + Math.random() * (max - min);
  }

  function pick(items) {
    return items[Math.floor(Math.random() * items.length)];
  }

  function emptyGrid() {
    return Array.from({ length: config.rows }, () => new Array(config.cols).fill(0));
  }

  function setPoints(points) {
    const grid = emptyGrid();
    points.forEach(([r, c]) => {
      if (r >= 0 && r < config.rows && c >= 0 && c < config.cols) grid[r][c] = 1;
    });
    return grid;
  }

  function block(cx, cy, size) {
    const grid = emptyGrid();
    for (let r = 0; r < size; r += 1) {
      for (let c = 0; c < size; c += 1) {
        const gr = cy + r;
        const gc = cx + c;
        if (gr >= 0 && gr < config.rows && gc >= 0 && gc < config.cols) grid[gr][gc] = 1;
      }
    }
    return grid;
  }

  const patterns = {
    blank: () => emptyGrid(),
    dot: (pos) => block(pos.x, pos.y, 2),
    largeDot: (pos) => block(Math.max(0, pos.x - 1), Math.max(0, pos.y - 1), 4),
    line: () => setPoints([[5, 5], [5, 6], [5, 7], [5, 8], [5, 9], [5, 10]]),
    smile: () => setPoints([[7, 4], [8, 5], [9, 6], [9, 7], [9, 8], [9, 9], [8, 10], [7, 11]]),
    frown: () => setPoints([[5, 4], [4, 5], [3, 6], [3, 7], [3, 8], [3, 9], [4, 10], [5, 11]]),
    heart: () => setPoints([[3, 6], [3, 7], [3, 9], [3, 10], [4, 5], [4, 6], [4, 7], [4, 8], [4, 9], [4, 10], [4, 11], [5, 5], [5, 6], [5, 7], [5, 8], [5, 9], [5, 10], [5, 11], [6, 6], [6, 7], [6, 8], [6, 9], [6, 10], [7, 7], [7, 8], [7, 9], [8, 8]]),
    question: () => setPoints([[2, 6], [2, 7], [2, 8], [3, 9], [4, 9], [5, 8], [6, 7], [7, 7], [9, 7]]),
    exclamation: () => setPoints([[2, 7], [2, 8], [3, 7], [3, 8], [4, 7], [4, 8], [5, 7], [5, 8], [6, 7], [6, 8], [9, 7], [9, 8]]),
    cross: () => setPoints([[3, 5], [4, 6], [5, 7], [6, 8], [7, 9], [8, 10], [3, 10], [4, 9], [5, 8], [6, 7], [7, 6], [8, 5]]),
    spiral: () => setPoints([[3, 7], [2, 8], [3, 9], [4, 10], [6, 10], [7, 9], [7, 7], [6, 6], [5, 7], [5, 8]]),
  };

  const gazePositions = [
    { x: 6, y: 4 }, { x: 3, y: 4 }, { x: 9, y: 4 }, { x: 6, y: 2 },
    { x: 6, y: 7 }, { x: 4, y: 3 }, { x: 8, y: 5 }, { x: 2, y: 1 },
  ];

  function drawEye(ctx, mode, pos) {
    ctx.clearRect(0, 0, config.cols, config.rows);
    const grid = (patterns[mode] || patterns.dot)(pos);
    ctx.fillStyle = "#ffffff";
    for (let r = 0; r < config.rows; r += 1) {
      for (let c = 0; c < config.cols; c += 1) {
        if (grid[r][c]) ctx.fillRect(c, r, 1, 1);
      }
    }
  }

  function renderEyes() {
    drawEye(ctxLeft, state.mode, state.leftPos);
    drawEye(ctxRight, state.mode, state.rightPos);
  }

  function setExpression(mode, ms) {
    state.mode = mode;
    state.lockedUntil = Date.now() + ms;
    renderEyes();
    setT(() => {
      if (Date.now() >= state.lockedUntil) {
        state.mode = "dot";
        state.leftPos = { x: 6, y: 4 };
        state.rightPos = { x: 6, y: 4 };
        renderEyes();
      }
    }, ms);
  }

  function triggerKnifeSwing() {
    if (knifeTimer) window.clearTimeout(knifeTimer);
    state.knifeSwinging = true;
    root.classList.remove("is-knife-swinging");
    void root.offsetWidth;
    root.classList.add("is-knife-swinging");
    if (debug) renderDebug();
    knifeTimer = window.setTimeout(() => {
      state.knifeSwinging = false;
      root.classList.remove("is-knife-swinging");
      knifeTimer = 0;
      if (debug) renderDebug();
    }, 3400);
  }

  function triggerHornTwitch(intensity) {
    const amount = intensity || 1;
    if (hornTimer) window.clearTimeout(hornTimer);
    state.hornTwitching = true;
    root.style.setProperty("--horn-twitch-x", `${rand(-2.5, 2.5) * amount}px`);
    root.style.setProperty("--horn-twitch-y", `${rand(-2.2, 1.2) * amount}px`);
    root.style.setProperty("--horn-twitch-rotate", `${rand(-1.4, 1.4) * amount}deg`);
    root.classList.remove("is-horn-twitching");
    void root.offsetWidth;
    root.classList.add("is-horn-twitching");
    if (debug) renderDebug();
    hornTimer = window.setTimeout(() => {
      state.hornTwitching = false;
      root.classList.remove("is-horn-twitching");
      hornTimer = 0;
      if (debug) renderDebug();
    }, 780);
  }

  function scheduleRandomHornTwitch() {
    setT(() => {
      if (!state.speaking && Math.random() < 0.72) triggerHornTwitch(rand(0.65, 1.15));
      scheduleRandomHornTwitch();
    }, rand(4500, 13500));
  }

  function scheduleIdleGaze() {
    setT(() => {
      if (Date.now() >= state.lockedUntil && !state.speaking) {
        const pos = pick(gazePositions);
        state.mode = "dot";
        state.leftPos = pos;
        state.rightPos = Math.random() < 0.15 ? pick(gazePositions) : pos;
        renderEyes();
      }
      scheduleIdleGaze();
    }, rand(config.idleGazeMs[0], config.idleGazeMs[1]));
  }

  function scheduleBlink() {
    setT(() => {
      if (Date.now() >= state.lockedUntil && !state.speaking) {
        const previous = state.mode;
        state.mode = "line";
        renderEyes();
        setT(() => {
          state.mode = "blank";
          renderEyes();
        }, 65);
        setT(() => {
          state.mode = previous === "blank" ? "dot" : previous;
          renderEyes();
        }, 145);
      }
      scheduleBlink();
    }, rand(config.blinkMs[0], config.blinkMs[1]));
  }

  function setJaw(open, rotate) {
    state.jawOpen = Math.min(config.maxJawOpen, open);
    state.jawRotate = rotate;
    root.style.setProperty("--jaw-open", `${state.jawOpen.toFixed(1)}px`);
    root.style.setProperty("--jaw-rotate", `${state.jawRotate.toFixed(2)}deg`);
  }

  function updateShake() {
    if (!state.speaking || reducedMotion) {
      state.shakeX = 0;
      state.shakeRotate = 0;
    } else {
      state.shakeX = rand(-1, 1);
      state.shakeRotate = 0;
    }
    root.style.setProperty("--jaw-shake-x", `${state.shakeX.toFixed(1)}px`);
    root.style.setProperty("--jaw-shake-rotate", `${state.shakeRotate.toFixed(2)}deg`);
    setT(updateShake, rand(config.shakeMs[0], config.shakeMs[1]));
  }

  function calculateRms(data) {
    let sum = 0;
    for (let i = 0; i < data.length; i += 1) {
      const normalized = (data[i] - 128) / 128;
      sum += normalized * normalized;
    }
    return Math.sqrt(sum / data.length);
  }

  function volumeToLevel(volume) {
    if (volume <= config.noiseFloor) return 0;
    if (volume < 0.04) return 1;
    if (volume < 0.065) return 2;
    if (volume < 0.105) return 3;
    return 4;
  }

  function applyVolume(rawVolume) {
    const activeVolume = rawVolume <= config.noiseFloor ? 0 : rawVolume;
    const factor = activeVolume > smoothedVolume ? config.attack : config.release;
    smoothedVolume = smoothedVolume * (1 - factor) + activeVolume * factor;
    const now = Date.now();
    state.speaking = smoothedVolume > config.speechThreshold || now - lastSpeakingAt < config.holdClosedMs;
    if (smoothedVolume > config.speechThreshold) lastSpeakingAt = now;

    const level = state.speaking ? volumeToLevel(smoothedVolume) : 0;
    state.level = level;
    const jawByLevel = [0, 8, 20, 34, 42];
    const rotateByLevel = [0, 0.15, 0.25, 0.35, 0.45];
    setJaw(jawByLevel[level], rotateByLevel[level]);

    if (state.speaking) {
      if (level >= 4) {
        state.mode = "largeDot";
      } else if (level >= 2) {
        state.mode = Math.random() < 0.03 ? "spiral" : "dot";
      } else {
        state.mode = "dot";
      }
      state.leftPos = { x: 6, y: 4 };
      state.rightPos = { x: 6, y: 4 };
      renderEyes();
    }
    if (debug) renderDebug();
  }

  function audioLoop() {
    if (!analyser || !audioData) return;
    analyser.getByteTimeDomainData(audioData);
    applyVolume(calculateRms(audioData));
    if (debug) renderDebug();
    animationId = window.requestAnimationFrame(audioLoop);
  }

  async function readRelayVolume() {
    if (!useAudioRelay) return;
    try {
      const response = await fetch(`/api/namahage-avatar/audio-level?session=${encodeURIComponent(relaySession)}`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`relay ${response.status}`);
      const payload = await response.json();
      micState = payload.active ? "relay" : "relay-wait";
      const relayVolume = Math.max(0, (Number(payload.volume) || 0) - relayFloor) * relayGain;
      applyVolume(Math.min(1, relayVolume));
    } catch (error) {
      micState = "relay-error";
      applyVolume(0);
      if (debug) renderDebug(error && error.message ? error.message : "relay error");
    } finally {
      relayTimer = window.setTimeout(readRelayVolume, 55);
    }
  }

  async function readRelayAction() {
    if (!useAudioRelay) return;
    try {
      const response = await fetch(`/api/namahage-avatar/action?session=${encodeURIComponent(relaySession)}`, {
        cache: "no-store",
      });
      if (response.ok) {
        const payload = await response.json();
        const type = payload && payload.action ? payload.action.type : "";
        if (type === "knife") triggerKnifeSwing();
        if (type === "horn") triggerHornTwitch(1.2);
        if (type === "smile") {
          setExpression("smile", 1200);
          triggerHornTwitch(1.15);
        }
        if (type === "frown") {
          setExpression("frown", 1200);
          triggerKnifeSwing();
          triggerHornTwitch(1.5);
        }
        if (type === "heart") {
          setExpression("heart", 1400);
          triggerHornTwitch(1.25);
        }
      }
    } catch (error) {
      if (debug) renderDebug(error && error.message ? error.message : "action error");
    } finally {
      actionTimer = window.setTimeout(readRelayAction, 120);
    }
  }

  async function startMic() {
    if (!enableMic || micState === "running") return;
    micState = "requesting";
    if (micButton) micButton.textContent = "マイク確認中";
    try {
      stream = await navigator.mediaDevices.getUserMedia({
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
      micState = "running";
      if (micButton) micButton.hidden = true;
      audioLoop();
    } catch (error) {
      micState = "error";
      if (micButton) {
        micButton.hidden = false;
        micButton.textContent = "音声反応を開始";
      }
      if (debug) renderDebug(error && error.message ? error.message : "mic error");
    }
  }

  function stopMic() {
    if (animationId) {
      window.cancelAnimationFrame(animationId);
      animationId = 0;
    }
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
    }
    if (audioContext) {
      audioContext.close().catch(() => {});
      audioContext = null;
    }
    analyser = null;
    audioData = null;
    micState = enableMic ? "idle" : "disabled";
    smoothedVolume = 0;
    applyVolume(0);
    if (micButton && enableMic) micButton.hidden = false;
  }

  function renderDebug(errorText) {
    if (!debugEl) return;
    debugEl.hidden = false;
    debugEl.textContent =
      `mic:${micState}\n` +
      `audio:${audioMode} session:${relaySession}\n` +
      `volume:${smoothedVolume.toFixed(4)}\n` +
      `speaking:${state.speaking}\n` +
      `level:${state.level}\n` +
      `jaw:${state.jawOpen.toFixed(1)}px ${state.jawRotate.toFixed(1)}deg\n` +
      `knife:${state.knifeSwinging}\n` +
      `horn:${state.hornTwitching}\n` +
      `eye:${state.mode}\n` +
      `noise:${config.noiseFloor} threshold:${config.speechThreshold}` +
      (errorText ? `\nerror:${errorText}` : "");
  }

  function handleKey(event) {
    if (!enableKeyboardControls || event.repeat) return;
    const key = event.key.toLowerCase();
    if (key === "1") {
      setExpression("smile", 1200);
      triggerHornTwitch(1.15);
    }
    if (key === "2") {
      setExpression("frown", 1200);
      triggerKnifeSwing();
      triggerHornTwitch(1.5);
    }
    if (key === "3") {
      setExpression("heart", 1400);
      triggerHornTwitch(1.25);
    }
    if (key === "4") setExpression("spiral", 1200);
    if (key === "5") setExpression("blank", 900);
    if (key === "6") setExpression("largeDot", 900);
    if (key === " ") {
      event.preventDefault();
      applyVolume(0.14);
      setT(() => applyVolume(0), 180);
    }
    if (key === "m") {
      if (micState === "running" || micState === "requesting") stopMic();
      else startMic();
    }
    if (key === "d") {
      root.classList.toggle("is-debug");
      if (debugEl) debugEl.hidden = !root.classList.contains("is-debug");
      if (knifeButton) knifeButton.hidden = !root.classList.contains("is-debug");
      renderDebug();
    }
    if (key === "k") triggerKnifeSwing();
    if (key === "h") triggerHornTwitch(1.2);
  }

  if (debug) {
    root.classList.add("is-debug");
    renderDebug();
  }

  renderEyes();
  scheduleIdleGaze();
  scheduleBlink();
  scheduleRandomHornTwitch();
  updateShake();

  if (micButton) {
    micButton.hidden = !enableMic;
    micButton.addEventListener("click", startMic);
  }
  if (knifeButton) {
    knifeButton.hidden = !debug;
    knifeButton.addEventListener("click", triggerKnifeSwing);
  }
  if (enableKeyboardControls) window.addEventListener("keydown", handleKey);
  if (enableMic && autostart) setT(startMic, 250);
  if (useAudioRelay) setT(readRelayVolume, 120);
  if (useAudioRelay) setT(readRelayAction, 180);

  window.addEventListener("pagehide", () => {
    clearTimers();
    if (relayTimer) window.clearTimeout(relayTimer);
    if (actionTimer) window.clearTimeout(actionTimer);
    if (knifeTimer) window.clearTimeout(knifeTimer);
    if (hornTimer) window.clearTimeout(hornTimer);
    stopMic();
  });
})();
