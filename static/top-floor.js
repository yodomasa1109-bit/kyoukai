(function () {
  "use strict";

  const scenario = window.KYOUKAI_SCENARIO;
  const room = document.querySelector("[data-top-floor-room]");
  const keyholeButton = document.querySelector("[data-top-floor-keyhole]");
  const messageEl = document.querySelector("[data-top-floor-message]");
  const returnLink = document.querySelector("[data-top-floor-return]");
  const MESSAGE_MS = 2600;
  const REPEAT_COOLDOWN_MS = 1300;
  const USE_PRELUDE_MS = 1600;
  const INSERT_MS = 650;
  const TURN_MS = 1250;
  const COMPLETE_MS = 2050;
  const OBSERVER_TRANSITION_MS = 1700;
  let messageTimer = 0;
  let interactionLock = false;
  let lastRepeatAt = 0;
  let pendingUseStart = false;
  let keyUseTimerIds = [];

  function showMessage(text, duration = MESSAGE_MS) {
    if (!messageEl || !text) return;
    window.clearTimeout(messageTimer);
    messageEl.textContent = text;
    messageEl.classList.add("is-visible");
    messageTimer = window.setTimeout(() => {
      messageEl.classList.remove("is-visible");
    }, duration);
  }

  function clearKeyUseTimers() {
    keyUseTimerIds.forEach((timerId) => window.clearTimeout(timerId));
    keyUseTimerIds = [];
  }

  function queueKeyUseTimer(callback, delay) {
    const timerId = window.setTimeout(callback, delay);
    keyUseTimerIds.push(timerId);
    return timerId;
  }

  function canUseTopFloor(state) {
    return Boolean(
      state &&
      state.mode === "scenario" &&
      state.active_route_id === "route_e" &&
      state.route_status?.route_e === "active" &&
      state.route_e_phone_completed === true &&
      state.top_floor_unlocked === true &&
      state.ending_completed !== true
    );
  }

  function canVisitCompletedTopFloor(state) {
    return Boolean(state && state.mode === "scenario" && state.ending_completed === true && state.top_floor_unlocked === true);
  }

  function canUseAnnihilationKey(state) {
    return Boolean(
      canUseTopFloor(state) &&
      state.top_floor_entered === true &&
      hasAnnihilationKey(state) &&
      state.annihilation_key_obtained === true &&
      state.annihilation_key_used !== true &&
      state.top_floor_keyhole_completed !== true &&
      state.ending_completed !== true
    );
  }

  function hasAnnihilationKey(state) {
    return Boolean(scenario?.hasAnnihilationKey?.(state));
  }

  function saveState(mutator) {
    if (!scenario) return null;
    const state = scenario.getState();
    mutator(state);
    return scenario.saveState(state);
  }

  function ensureKeyholeState(state) {
    if (state.top_floor_keyhole_completed === true) return "completed";
    if (state.keyhole_state === "processing") return hasAnnihilationKey(state) ? "ready" : "waiting_for_key";
    if (hasAnnihilationKey(state)) return "ready";
    if (["available", "waiting_for_key", "ready"].includes(state.keyhole_state)) return state.keyhole_state;
    return "available";
  }

  function syncVisuals(state) {
    if (!room || !keyholeButton) return;
    const active = canUseTopFloor(state) || canVisitCompletedTopFloor(state);
    const keyholeState = active ? ensureKeyholeState(state) : "inactive";
    room.dataset.routeE = active ? "active" : "locked";
    room.dataset.keyholeState = keyholeState;
    room.classList.toggle("route-e-active", active && !canVisitCompletedTopFloor(state));
    room.classList.toggle("route-e-completed", canVisitCompletedTopFloor(state));
    ["inactive", "available", "waiting_for_key", "ready", "processing", "completed"].forEach((name) => {
      room.classList.toggle(`keyhole--${name}`, keyholeState === name);
    });
    keyholeButton.disabled = !active || state.keyhole_state === "processing" || (state.top_floor_keyhole_completed === true && !canVisitCompletedTopFloor(state)) || state.annihilation_key_use_lock === true;
    keyholeButton.setAttribute("aria-disabled", keyholeButton.disabled ? "true" : "false");
  }

  function enterTopFloor() {
    if (!scenario) return null;
    let state = scenario.getState();
    if (!canUseTopFloor(state) && !canVisitCompletedTopFloor(state)) {
      syncVisuals(state);
      return state;
    }
    if (canVisitCompletedTopFloor(state)) {
      syncVisuals(state);
      return state;
    }

    if (state.top_floor_entered !== true) {
      scenario.completeScenarioEvent("route_e_top_floor_enter_001", { sequenceEventId: "route_e_top_floor_enter_001" });
      state = scenario.getState();
    }

    state = saveState((next) => {
      next.top_floor_entered = true;
      next.route_e_stage = next.route_e_stage === "route_e_top_floor_unlocked" ? "top_floor_entered" : next.route_e_stage;
      next.top_floor_keyhole_active = true;
      next.keyhole_interaction_lock = false;
      next.keyhole_state = ensureKeyholeState(next);
    });

    showMessage("最上階", 2200);
    syncVisuals(state);
    return state;
  }

  function markReady() {
    const state = saveState((next) => {
      next.keyhole_state = "ready";
      next.top_floor_keyhole_active = true;
      next.keyhole_interaction_lock = false;
    });
    scenario?.completeScenarioEvent("route_e_keyhole_ready_001", { interactionTarget: "top-floor-keyhole" });
    scenario?.completeScenarioEvent("route_e_annihilation_key_ready_001", { interactionTarget: "top-floor-keyhole" });
    syncVisuals(state || scenario?.getState());
    startAnnihilationKeyUse();
  }

  function markWaitingWithoutKey(state) {
    scenario?.completeScenarioEvent("route_e_keyhole_touch_without_key_001", {
      interactionTarget: "top-floor-keyhole",
    });
    const next = saveState((current) => {
      current.keyhole_touched = true;
      current.keyhole_touched_without_key = true;
      current.keyhole_state = "waiting_for_key";
      current.top_floor_keyhole_active = true;
      current.keyhole_interaction_lock = false;
    });
    syncVisuals(next || state);
  }

  function touchKeyhole() {
    if (!scenario || interactionLock) return;
    let state = scenario.getState();
    if (canVisitCompletedTopFloor(state)) {
      showMessage("閉じています。", 1800);
      window.setTimeout(() => showMessage("反応はありません。", 1800), 850);
      return;
    }
    if (!canUseTopFloor(state) || state.top_floor_keyhole_completed === true) return;
    if (state.keyhole_state === "processing") return;
    interactionLock = true;

    if (hasAnnihilationKey(state)) {
      markReady();
      interactionLock = false;
      return;
    }

    if (state.keyhole_touched_without_key === true) {
      const now = Date.now();
      if (now - lastRepeatAt > REPEAT_COOLDOWN_MS) {
        lastRepeatAt = now;
        showMessage("反応はありません。", 1800);
      }
      interactionLock = false;
      return;
    }

    showMessage("形は合っている。", 2100);
    window.setTimeout(() => {
      showMessage("ここには、まだ何もありません。", 2400);
      state = scenario.getState();
      markWaitingWithoutKey(state);
      interactionLock = false;
    }, 850);
  }

  function ensureUseKeyElement() {
    if (!room) return null;
    let keyEl = room.querySelector("[data-annihilation-key-visual]");
    if (keyEl) return keyEl;
    keyEl = document.createElement("span");
    keyEl.className = "top-floor-room__use-key";
    keyEl.setAttribute("data-annihilation-key-visual", "");
    keyEl.setAttribute("aria-hidden", "true");
    room.append(keyEl);
    return keyEl;
  }

  function removeUseStartListeners() {
    document.removeEventListener("click", beginAnnihilationKeyUse, true);
    document.removeEventListener("keydown", beginAnnihilationKeyUseByKey, true);
  }

  function finalizeAnnihilationKeyUse() {
    scenario?.completeScenarioEvent("route_e_annihilation_key_use_001", {
      interactionTarget: "top-floor-keyhole",
      sequenceEventId: "route_e_annihilation_key_use_001",
    });
    const completed = scenario?.completeScenarioEvent("route_e_annihilation_key_complete_001", {
      interactionTarget: "top-floor-keyhole",
      sequenceEventId: "route_e_annihilation_key_complete_001",
    });
    saveState((next) => {
      next.annihilation_key_obtained = true;
      next.annihilation_key_used = true;
      next.annihilation_key_used_at = next.annihilation_key_used_at || new Date().toISOString();
      next.annihilation_key_consumed = true;
      next.top_floor_keyhole_completed = true;
      next.top_floor_event_completed = true;
      next.keyhole_state = "completed";
      next.route_e_stage = "keyhole_completed";
      next.current_target_room_id = "observer";
      next.annihilation_key_use_lock = false;
      next.items = (next.items || []).filter((item) => item !== "annihilation_key");
    });
    room?.classList.remove("is-using-key");
    room?.classList.add("has-used-key");
    showMessage("消滅したものはありません。", 2200);
    queueKeyUseTimer(() => {
      showMessage("続いていた状態だけが、\n終了しました。", 0);
      queueKeyUseTimer(transitionToFinalObserver, OBSERVER_TRANSITION_MS);
    }, 1100);
    interactionLock = false;
    syncVisuals(completed || scenario?.getState());
  }

  function transitionToFinalObserver() {
    if (!scenario || !room) return;
    const state = scenario.getState();
    if (
      state.mode !== "scenario" ||
      state.active_route_id !== "route_e" ||
      state.route_status?.route_e !== "active" ||
      state.annihilation_key_used !== true ||
      state.top_floor_keyhole_completed !== true ||
      state.top_floor_event_completed !== true ||
      state.observer_final_event_completed === true ||
      state.ending_completed === true
    ) {
      return;
    }
    room.classList.add("is-observer-transitioning");
    scenario.completeScenarioEvent("route_e_observer_transition_001", {
      sequenceEventId: "route_e_observer_transition_001",
    });
    queueKeyUseTimer(() => {
      window.location.href = "/observer";
    }, 1250);
  }

  function runAnnihilationKeyAnimation() {
    if (!scenario || !room) return;
    const state = scenario.getState();
    if (!canUseAnnihilationKey(state) || state.keyhole_state !== "ready") {
      interactionLock = false;
      syncVisuals(state);
      return;
    }
    clearKeyUseTimers();
    const keyEl = ensureUseKeyElement();
    keyEl?.classList.remove("is-inserted", "is-turned");
    room.classList.add("is-using-key");
    scenario.completeScenarioEvent("route_e_annihilation_key_insert_001", {
      interactionTarget: "top-floor-keyhole",
      sequenceEventId: "route_e_annihilation_key_insert_001",
    });
    syncVisuals(scenario.getState());
    queueKeyUseTimer(() => keyEl?.classList.add("is-inserted"), INSERT_MS);
    queueKeyUseTimer(() => {
      keyEl?.classList.add("is-turned");
      scenario.completeScenarioEvent("route_e_annihilation_key_turn_001", {
        interactionTarget: "top-floor-keyhole",
        sequenceEventId: "route_e_annihilation_key_turn_001",
      });
    }, TURN_MS);
    queueKeyUseTimer(finalizeAnnihilationKeyUse, COMPLETE_MS);
  }

  function beginAnnihilationKeyUse(event) {
    if (!pendingUseStart) return;
    if (event) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
    }
    pendingUseStart = false;
    removeUseStartListeners();
    runAnnihilationKeyAnimation();
  }

  function beginAnnihilationKeyUseByKey(event) {
    if (!pendingUseStart) return;
    if (!["Enter", " "].includes(event.key)) return;
    beginAnnihilationKeyUse(event);
  }

  function startAnnihilationKeyUse() {
    const state = scenario?.getState();
    if (!canUseAnnihilationKey(state) || pendingUseStart) {
      interactionLock = false;
      syncVisuals(state);
      return;
    }
    document.dispatchEvent(new CustomEvent("kyoukai:route-e-keyhole-ready", {
      detail: { room_id: "top-floor", event_id: "route_e_annihilation_key_ready_001" },
    }));
    if (typeof window.onKeyholeReady === "function") window.onKeyholeReady();
    showMessage("鍵穴の奥で、\n何かが待っている。", USE_PRELUDE_MS);
    queueKeyUseTimer(() => {
      showMessage("消滅の鍵を差し込みます。", 0);
      pendingUseStart = true;
      document.addEventListener("click", beginAnnihilationKeyUse, true);
      document.addEventListener("keydown", beginAnnihilationKeyUseByKey, true);
    }, USE_PRELUDE_MS);
  }

  window.KYOUKAI_ROUTE_E_TOP_FLOOR = {
    enterTopFloor,
    touchKeyhole,
    startAnnihilationKeyUse,
    transitionToFinalObserver,
  };

  keyholeButton?.addEventListener("click", touchKeyhole);
  returnLink?.addEventListener("click", (event) => {
    const state = scenario?.getState();
    if (state?.keyhole_state !== "processing") return;
    event.preventDefault();
  });

  document.addEventListener("kyoukai:scenario-state", (event) => {
    syncVisuals(event.detail || scenario?.getState());
  });

  const initialState = scenario?.getState?.();
  if (
    initialState?.mode === "scenario" &&
    initialState.active_route_id === "route_e" &&
    initialState.route_status?.route_e === "active" &&
    initialState.annihilation_key_used === true &&
    initialState.top_floor_keyhole_completed === true &&
    initialState.observer_final_event_completed !== true &&
    initialState.ending_completed !== true
  ) {
    window.location.replace("/observer");
    return;
  }

  enterTopFloor();
})();
