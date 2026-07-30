"use strict";

const fs = require("fs");
const crypto = require("crypto");

const OBS_EVENT_INPUT_VOLUME_METERS = 1 << 16;
const INPUT_NAME = process.env.NAMAHAGE_OBS_MIC_INPUT || "Namahage Mic";
const SESSION = process.env.NAMAHAGE_SESSION || "main";
const API_BASE = process.env.NAMAHAGE_API_BASE || "http://127.0.0.1:8000";
const GAIN = Number(process.env.NAMAHAGE_OBS_MIC_GAIN || 2.2);
const FLOOR = Number(process.env.NAMAHAGE_OBS_MIC_FLOOR || 0.02);
const SEND_INTERVAL_MS = Number(process.env.NAMAHAGE_OBS_MIC_INTERVAL_MS || 25);
const RECONNECT_MS = Number(process.env.NAMAHAGE_OBS_MIC_RECONNECT_MS || 2000);
const DEVICE_ID = process.env.NAMAHAGE_OBS_MIC_DEVICE_ID || "";
const DEVICE_NAME_PATTERNS = (process.env.NAMAHAGE_OBS_MIC_DEVICE_NAME || "WO Mic,マイク,Microphone")
  .split(",")
  .map((item) => item.trim().toLowerCase())
  .filter(Boolean);
DEVICE_NAME_PATTERNS.unshift("cable output");

let ws = null;
let nextRequestId = 1;
let currentVolume = 0;
let lastSentAt = 0;
let sourceReady = false;
let shuttingDown = false;
let currentDeviceId = "";
const pending = new Map();

function loadObsConfig() {
  const path = `${process.env.APPDATA}\\obs-studio\\plugin_config\\obs-websocket\\config.json`;
  const config = JSON.parse(fs.readFileSync(path, "utf8"));
  return {
    port: config.server_port || 4455,
    password: config.server_password || config.password || "",
  };
}

function sha256Base64(value) {
  return crypto.createHash("sha256").update(value).digest("base64");
}

function request(type, data = {}) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const requestId = String(nextRequestId++);
  pending.set(requestId, type);
  ws.send(JSON.stringify({
    op: 6,
    d: {
      requestType: type,
      requestId,
      requestData: data,
    },
  }));
}

function maxNestedNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return Math.max(0, value);
  if (!Array.isArray(value)) return 0;
  return value.reduce((max, item) => Math.max(max, maxNestedNumber(item)), 0);
}

async function postVolume(volume) {
  await fetch(`${API_BASE}/api/namahage-avatar/audio-level`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session: SESSION, volume }),
    keepalive: true,
  });
}

function meterToVolume(inputLevelsMul) {
  const raw = maxNestedNumber(inputLevelsMul);
  return Math.max(0, Math.min(1, (raw - FLOOR) * GAIN));
}

function handleMeters(inputs) {
  const input = inputs.find((item) => item.inputName === INPUT_NAME);
  if (!input) return;

  const meterVolume = meterToVolume(input.inputLevelsMul || []);
  currentVolume = meterVolume < 0.01 ? 0 : meterVolume;

  const now = Date.now();
  if (now - lastSentAt < SEND_INTERVAL_MS) return;
  lastSentAt = now;
  postVolume(currentVolume).catch((error) => {
    console.error(`[namahage-obs-mic] post failed: ${error.message}`);
  });
}

function ensureMicInput(inputs) {
  if (inputs.some((input) => input.inputName === INPUT_NAME)) {
    sourceReady = true;
    console.log(`[namahage-obs-mic] using OBS input: ${INPUT_NAME}`);
    request("GetInputSettings", { inputName: INPUT_NAME });
    request("GetInputPropertiesListPropertyItems", { inputName: INPUT_NAME, propertyName: "device_id" });
    return;
  }

  console.log(`[namahage-obs-mic] creating OBS mic input: ${INPUT_NAME}`);
  request("GetCurrentProgramScene");
}

function chooseDevice(items) {
  if (!Array.isArray(items) || items.length === 0) return null;
  if (DEVICE_ID) {
    return items.find((item) => item.itemValue === DEVICE_ID) || null;
  }

  const namedDevice = items.find((item) => {
    const name = String(item.itemName || "").toLowerCase();
    return DEVICE_NAME_PATTERNS.some((pattern) => name.includes(pattern));
  });
  if (namedDevice) return namedDevice;

  return items.find((item) => String(item.itemValue || "") !== "default") || null;
}

function maybeSetDevice(items) {
  const device = chooseDevice(items);
  if (!device || !device.itemValue || device.itemValue === currentDeviceId) return;
  console.log(`[namahage-obs-mic] selecting OBS mic device: ${device.itemName}`);
  request("SetInputSettings", {
    inputName: INPUT_NAME,
    inputSettings: {
      device_id: device.itemValue,
      use_device_timing: false,
    },
    overlay: true,
  });
}

function handleResponse(message) {
  const requestType = pending.get(message.d.requestId) || message.d.requestType;
  pending.delete(message.d.requestId);

  if (!message.d.requestStatus || !message.d.requestStatus.result) {
    console.error(`[namahage-obs-mic] ${requestType} failed: ${message.d.requestStatus?.comment || "unknown error"}`);
    return;
  }

  const data = message.d.responseData || {};
  if (requestType === "GetInputList") {
    ensureMicInput(data.inputs || []);
  }
  if (requestType === "GetInputSettings") {
    currentDeviceId = data.inputSettings?.device_id || "";
  }
  if (requestType === "GetInputPropertiesListPropertyItems") {
    maybeSetDevice(data.propertyItems || []);
  }
  if (requestType === "GetCurrentProgramScene") {
    request("CreateInput", {
      sceneName: data.currentProgramSceneName,
      inputName: INPUT_NAME,
      inputKind: "wasapi_input_capture",
      inputSettings: {
        device_id: "default",
        use_device_timing: false,
      },
      sceneItemEnabled: true,
    });
  }
  if (requestType === "CreateInput") {
    sourceReady = true;
    console.log(`[namahage-obs-mic] created OBS input: ${INPUT_NAME}`);
    request("GetInputSettings", { inputName: INPUT_NAME });
    request("GetInputPropertiesListPropertyItems", { inputName: INPUT_NAME, propertyName: "device_id" });
  }
  if (requestType === "SetInputSettings") {
    console.log("[namahage-obs-mic] OBS mic device is ready");
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
          eventSubscriptions: OBS_EVENT_INPUT_VOLUME_METERS,
        },
      }));
    }

    if (message.op === 2) {
      console.log(`[namahage-obs-mic] connected. session=${SESSION}`);
      request("GetInputList");
    }

    if (message.op === 5 && message.d.eventType === "InputVolumeMeters" && sourceReady) {
      handleMeters(message.d.eventData.inputs || []);
    }

    if (message.op === 7) {
      handleResponse(message);
    }
  };

  ws.onclose = () => {
    sourceReady = false;
    pending.clear();
    if (!shuttingDown) {
      console.log(`[namahage-obs-mic] disconnected. reconnecting in ${RECONNECT_MS}ms`);
      setTimeout(connect, RECONNECT_MS);
    }
  };

  ws.onerror = (error) => {
    console.error(`[namahage-obs-mic] websocket error: ${error.message || "unknown error"}`);
  };
}

process.on("SIGINT", async () => {
  shuttingDown = true;
  await postVolume(0).catch(() => {});
  if (ws) ws.close();
  process.exit(0);
});

connect();
