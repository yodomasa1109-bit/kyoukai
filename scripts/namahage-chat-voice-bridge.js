"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const { spawn } = require("child_process");

const SESSION = process.env.NAMAHAGE_SESSION || "main";
const API_BASE = process.env.NAMAHAGE_API_BASE || "http://127.0.0.1:8000";
const OBS_INPUT_NAME = process.env.NAMAHAGE_CHAT_VOICE_INPUT || "Namahage Chat Voice Audio";
const OBS_SCENE_NAME = process.env.NAMAHAGE_OBS_SCENE || "";
const VOICE_NAME = process.env.NAMAHAGE_CHAT_VOICE_NAME || "Microsoft Haruka Desktop";
const RATE = Number(process.env.NAMAHAGE_CHAT_VOICE_RATE || -1);
const VOLUME = Number(process.env.NAMAHAGE_CHAT_VOICE_VOLUME || 100);
const POLL_MS = Number(process.env.NAMAHAGE_CHAT_VOICE_POLL_MS || 900);
const RECONNECT_MS = Number(process.env.NAMAHAGE_CHAT_VOICE_RECONNECT_MS || 2000);
const REPLAY_EXISTING = process.env.NAMAHAGE_CHAT_VOICE_REPLAY === "1";
const MOUTH_PULSE_MS = Number(process.env.NAMAHAGE_CHAT_VOICE_MOUTH_PULSE_MS || 70);
const WORK_DIR = path.join(os.tmpdir(), "kyoukai-namahage-chat-voice");

let ws = null;
let nextRequestId = 1;
let sourceReady = false;
let currentSceneName = "";
let lastId = 0;
let polling = false;
let speaking = false;
let shuttingDown = false;
const pending = new Map();
const queue = [];

fs.mkdirSync(WORK_DIR, { recursive: true });

function loadObsConfig() {
  const configPath = `${process.env.APPDATA}\\obs-studio\\plugin_config\\obs-websocket\\config.json`;
  const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  return {
    port: config.server_port || 4455,
    password: config.server_password || config.password || "",
  };
}

function sha256Base64(value) {
  return crypto.createHash("sha256").update(value).digest("base64");
}

function request(type, data = {}) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return "";
  const requestId = String(nextRequestId++);
  pending.set(requestId, { type, data });
  ws.send(JSON.stringify({
    op: 6,
    d: {
      requestType: type,
      requestId,
      requestData: data,
    },
  }));
  return requestId;
}

function escapeSpeechText(value) {
  return String(value || "")
    .replace(/https?:\/\/\\S+/gi, "URL")
    .replace(/[\\r\\n\\t]+/g, " ")
    .replace(/\\s{2,}/g, " ")
    .trim()
    .slice(0, 260);
}

function formatMessage(message) {
  const author = escapeSpeechText(message.author || "コメント");
  const text = escapeSpeechText(message.text || "");
  return `${author}さん。${text}`;
}

function runPowerShell(script) {
  return new Promise((resolve, reject) => {
    const encoded = Buffer.from(script, "utf16le").toString("base64");
    const child = spawn("powershell.exe", [
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-EncodedCommand",
      encoded,
    ], {
      windowsHide: true,
    });

    let stderr = "";
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(stderr.trim() || `PowerShell exited ${code}`));
    });
  });
}

async function synthesize(message) {
  const wavPath = path.join(WORK_DIR, `chat-voice-${Date.now()}-${message.id}.wav`);
  const payload = {
    text: formatMessage(message),
    file: wavPath,
    voice: VOICE_NAME,
    rate: Math.max(-10, Math.min(10, RATE)),
    volume: Math.max(0, Math.min(100, VOLUME)),
  };
  const json = JSON.stringify(payload).replace(/'/g, "''");
  const script = `
$payload = '${json}' | ConvertFrom-Json
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try { $synth.SelectVoice($payload.voice) } catch {}
$synth.Rate = [int]$payload.rate
$synth.Volume = [int]$payload.volume
$synth.SetOutputToWaveFile($payload.file)
$synth.Speak($payload.text)
$synth.Dispose()
`;
  await runPowerShell(script);
  return wavPath;
}

async function sendMouthLevel(volume) {
  try {
    await fetch(`${API_BASE}/api/namahage-avatar/audio-level`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        session: SESSION,
        source: "chat-voice",
        volume: Math.max(0, Math.min(1, volume)),
      }),
    });
  } catch {}
}

function startMouthPulse(durationMs) {
  const started = Date.now();
  const timer = setInterval(() => {
    const elapsed = Date.now() - started;
    if (elapsed >= durationMs || shuttingDown) {
      clearInterval(timer);
      sendMouthLevel(0);
      return;
    }
    const wave = 0.45 + (Math.sin(elapsed / 95) + 1) * 0.22;
    const jitter = Math.random() * 0.22;
    sendMouthLevel(Math.min(1, wave + jitter));
  }, MOUTH_PULSE_MS);
}

function ensureMediaSource(inputs) {
  if (inputs.some((input) => input.inputName === OBS_INPUT_NAME)) {
    sourceReady = true;
    configureAudio();
    console.log(`[namahage-chat-voice] using OBS media input: ${OBS_INPUT_NAME}`);
    return;
  }

  const sceneName = OBS_SCENE_NAME || currentSceneName;
  if (!sceneName) {
    console.error("[namahage-chat-voice] OBS scene is unknown");
    return;
  }
  console.log(`[namahage-chat-voice] creating OBS media input: ${OBS_INPUT_NAME}`);
  request("CreateInput", {
    sceneName,
    inputName: OBS_INPUT_NAME,
    inputKind: "ffmpeg_source",
    inputSettings: {
      is_local_file: true,
      local_file: "",
      looping: false,
      restart_on_activate: true,
      close_when_inactive: false,
    },
    sceneItemEnabled: true,
  });
}

function configureAudio() {
  const inputAudioTracks = {
    "1": true,
    "2": false,
    "3": false,
    "4": false,
    "5": false,
    "6": false,
  };
  request("SetInputAudioTracks", { inputName: OBS_INPUT_NAME, inputAudioTracks });
  request("SetInputMute", { inputName: OBS_INPUT_NAME, inputMuted: false });
  request("SetInputVolume", { inputName: OBS_INPUT_NAME, inputVolumeMul: 1 });
  request("SetInputAudioMonitorType", {
    inputName: OBS_INPUT_NAME,
    monitorType: "OBS_MONITORING_TYPE_MONITOR_AND_OUTPUT",
  });
}

function playWav(wavPath) {
  request("SetInputSettings", {
    inputName: OBS_INPUT_NAME,
    inputSettings: {
      is_local_file: true,
      local_file: wavPath,
      looping: false,
      restart_on_activate: true,
      close_when_inactive: false,
    },
    overlay: true,
  });
  setTimeout(() => {
    request("TriggerMediaInputAction", {
      inputName: OBS_INPUT_NAME,
      mediaAction: "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART",
    });
  }, 180);
}

async function speakNext() {
  if (speaking || !sourceReady || queue.length === 0) return;
  speaking = true;
  const message = queue.shift();
  const delay = Math.max(1800, Math.min(12000, String(message.text || "").length * 180));
  try {
    console.log(`[namahage-chat-voice] speaking #${message.id}: ${message.text}`);
    const wavPath = await synthesize(message);
    playWav(wavPath);
    startMouthPulse(delay);
    setTimeout(() => {
      fs.unlink(wavPath, () => {});
    }, 60000);
  } catch (error) {
    console.error(`[namahage-chat-voice] speak failed: ${error.message}`);
  } finally {
    setTimeout(() => {
      speaking = false;
      speakNext();
    }, delay);
  }
}

async function pollMessages() {
  if (polling) return;
  polling = true;
  try {
    const response = await fetch(`${API_BASE}/api/namahage-avatar/chat-voice?session=${encodeURIComponent(SESSION)}&since=${lastId}`, {
      cache: "no-store",
    });
    if (response.ok) {
      const payload = await response.json();
      const messages = Array.isArray(payload.messages) ? payload.messages : [];
      if (!REPLAY_EXISTING && lastId === 0 && messages.length > 0) {
        lastId = Number(payload.latestId || messages[messages.length - 1].id || 0);
      } else {
        messages.forEach((message) => {
          const id = Number(message.id || 0);
          if (id > lastId) lastId = id;
          queue.push(message);
        });
      }
      speakNext();
    }
  } catch (error) {
    console.error(`[namahage-chat-voice] poll failed: ${error.message}`);
  } finally {
    polling = false;
    if (!shuttingDown) setTimeout(pollMessages, POLL_MS);
  }
}

function handleResponse(message) {
  const meta = pending.get(message.d.requestId) || {};
  pending.delete(message.d.requestId);
  const requestType = meta.type || message.d.requestType;

  if (!message.d.requestStatus || !message.d.requestStatus.result) {
    console.error(`[namahage-chat-voice] ${requestType} failed: ${message.d.requestStatus?.comment || "unknown error"}`);
    return;
  }

  const data = message.d.responseData || {};
  if (requestType === "GetCurrentProgramScene") {
    currentSceneName = data.currentProgramSceneName || data.sceneName || "";
    request("GetInputList");
  }
  if (requestType === "GetInputList") {
    ensureMediaSource(data.inputs || []);
  }
  if (requestType === "CreateInput") {
    sourceReady = true;
    configureAudio();
    console.log(`[namahage-chat-voice] created OBS media input: ${OBS_INPUT_NAME}`);
  }
}

function connect() {
  const { port, password } = loadObsConfig();
  ws = new WebSocket(`ws://127.0.0.1:${port}`);

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.op === 0) {
      const auth = message.d.authentication;
      let authentication;
      if (auth && password) {
        const secret = sha256Base64(password + auth.salt);
        authentication = sha256Base64(secret + auth.challenge);
      }
      ws.send(JSON.stringify({
        op: 1,
        d: {
          rpcVersion: 1,
          authentication,
        },
      }));
    }

    if (message.op === 2) {
      console.log(`[namahage-chat-voice] connected. session=${SESSION}`);
      request("GetCurrentProgramScene");
      pollMessages();
    }

    if (message.op === 7) handleResponse(message);
  };

  ws.onclose = () => {
    sourceReady = false;
    pending.clear();
    if (!shuttingDown) {
      console.log(`[namahage-chat-voice] disconnected. reconnecting in ${RECONNECT_MS}ms`);
      setTimeout(connect, RECONNECT_MS);
    }
  };

  ws.onerror = (error) => {
    console.error(`[namahage-chat-voice] websocket error: ${error.message || "unknown error"}`);
  };
}

process.on("SIGINT", () => {
  shuttingDown = true;
  if (ws) ws.close();
  process.exit(0);
});

connect();
