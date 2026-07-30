import base64
import hashlib
import json
import mimetypes
import os
import random
import re
import shutil
import sqlite3
import struct
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from fastapi.exception_handlers import http_exception_handler

from auto_generator import build_codex_context, build_daimyojin_config
from services.city_service import CityDataError, CityService


BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "videos"
VIDEO_EDITS_DIR = VIDEOS_DIR / "edits"
VIDEOS_MANIFEST_PATH = BASE_DIR / "static" / "videos-manifest.json"
DB_PATH = Path(os.environ.get("KYOUKAI_DB_PATH") or (Path(tempfile.gettempdir()) / "kyoukai.db" if os.environ.get("VERCEL") else BASE_DIR / "kyoukai.db"))
TICK_SECONDS = 3
SILENCE_THRESHOLD_SECONDS = 12
OLLAMA_URL = os.environ.get("KYOUKAI_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.environ.get("KYOUKAI_OLLAMA_MODEL", "qwen2.5:0.5b")
DEFAULT_GA_MEASUREMENT_ID = "G-ZXWYDXKCYS"
GA_MEASUREMENT_ID = os.environ.get("GA_MEASUREMENT_ID", DEFAULT_GA_MEASUREMENT_ID).strip()
NAMAHAGE_AUDIO_LEVELS: dict[str, dict[str, float]] = {}
NAMAHAGE_ACTIONS: dict[str, list[dict[str, Any]]] = {}
NAMAHAGE_CONSULTS: dict[str, dict[str, Any]] = {}
NAMAHAGE_ACTION_COUNTER = 0

try:
    from genome_system import CreatureGeneratorAI, get_creature_params
    from genome_system.genome_defs import CORES, MUTATIONS, ORGANS, SHELLS

    GENOME_SYSTEM_AVAILABLE = True
except Exception:
    CreatureGeneratorAI = None  # type: ignore[assignment]
    CORES: dict[str, Any] = {}
    MUTATIONS: dict[str, Any] = {}
    ORGANS: dict[str, Any] = {}
    SHELLS: dict[str, Any] = {}
    GENOME_SYSTEM_AVAILABLE = False

TRAIT_KEYS = [
    "trait_softness",
    "trait_aggression",
    "trait_gaze",
    "trait_distance",
    "trait_curiosity",
    "trait_corruption",
    "trait_attachment",
]

MUTATION_LOGS = {
    "soft_bloom": ("soft bloom mutation stabilized", "柔らかい膨張を確認"),
    "distorted_pulse": ("distorted pulse repeated", "歪んだ拍動を検出"),
    "gaze_lock": ("gaze lock established", "視線固定反応"),
    "distant_shell": ("distant shell formed", "距離殻を形成"),
    "noise_skin": ("noise skin emerged", "境界ノイズが皮膜化"),
    "phase_slip": ("phase slip recorded", "phase slip 発生"),
    "silent_growth": ("silent growth accumulated", "無言観測による成長"),
}

GENOME_DEFAULTS: dict[str, Any] = {
    "observer_count": 0,
    "total_visits": 0,
    "stay_time": 0,
    "phase": 0,
    "mutation_level": 0,
    "stability": 100,
    "noise_level": 0,
    "tempo": 60,
    "mood": "quiet",
    "last_action": "",
    "log_history": [],
    "updated_at": "",
    "silent_observation": 0,
    "boundary_pressure": 0,
    "drift": 0,
    "phase_drift": 0,
    "audio_instability": 0,
    "visual_instability": 0,
    "mutation_count": 0,
    "last_mutation_type": "none",
    "last_mutation_at": "",
    "mutation_event_id": 0,
    "phase_up_event_id": 0,
    "trait_softness": 0,
    "trait_aggression": 0,
    "trait_gaze": 0,
    "trait_distance": 0,
    "trait_curiosity": 0,
    "trait_corruption": 0,
    "trait_attachment": 0,
    "last_input_at": 0.0,
    "last_event_flags": {},
    "genome_summary": {},
}

CREATURE_GENERATED_DIR = Path(tempfile.gettempdir()) / "kyoukai_creatures"
_creature_generator = CreatureGeneratorAI(CREATURE_GENERATED_DIR) if GENOME_SYSTEM_AVAILABLE and CreatureGeneratorAI else None
_creature_cache: dict[str, dict[str, Any]] = {}

COMMAND_EFFECTS: dict[str, dict[str, Any]] = {
    "なでる": {
        "trait_softness": 2,
        "trait_attachment": 1,
        "stability": 2,
        "mutation_level": 1,
        "mood": "soft",
        "log": "soft contact recorded",
        "jp_log": "柔らかい接触を記録",
    },
    "たたく": {
        "trait_aggression": 3,
        "trait_corruption": 1,
        "stability": -5,
        "noise_level": 2,
        "mutation_level": 3,
        "audio_instability": 1,
        "visual_instability": 1,
        "mood": "disturbed",
        "log": "impact disturbance detected",
        "jp_log": "衝撃性ノイズを検出",
    },
    "みつめる": {
        "trait_gaze": 3,
        "silent_observation": 1,
        "phase_drift": 1,
        "mutation_level": 1,
        "mood": "observed",
        "log": "gaze fixed",
        "jp_log": "外部視線が固定",
    },
    "よぶ": {
        "trait_curiosity": 2,
        "tempo": 2,
        "visual_instability": 1,
        "mutation_level": 1,
        "mood": "awake",
        "log": "call signal received",
        "jp_log": "呼び声信号を受理",
    },
    "はなしかける": {
        "trait_curiosity": 1,
        "trait_attachment": 1,
        "stability": 1,
        "mutation_level": 1,
        "mood": "listening",
        "log": "language fragment accepted",
        "jp_log": "言語片を受け入れ",
    },
    "遠ざける": {
        "trait_distance": 3,
        "trait_attachment": -1,
        "stability": -3,
        "noise_level": 3,
        "boundary_pressure": 2,
        "mood": "distant",
        "log": "distance event recorded",
        "jp_log": "距離イベントを記録",
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def dominant_trait(genome: dict[str, Any]) -> str:
    key = max(TRAIT_KEYS, key=lambda trait: int(genome.get(trait, 0)))
    return key.removeprefix("trait_")


def genome_summary(genome: dict[str, Any]) -> dict[str, Any]:
    instability = clamp(
        (100 - int(genome["stability"]))
        + int(genome["noise_level"])
        + int(genome["audio_instability"]) // 2
        + int(genome["visual_instability"]) // 2,
        0,
        100,
    )
    return {
        "dominant_trait": dominant_trait(genome),
        "instability": instability,
        "current_mutation": genome.get("last_mutation_type", "none"),
        "mutation_event_id": int(genome.get("mutation_event_id", 0)),
        "last_mutation_at": genome.get("last_mutation_at", ""),
        "audio_mode": mutation_audio_mode(str(genome.get("last_mutation_type", "none"))),
        "visual_mode": str(genome.get("last_mutation_type", "none")).replace("_", "-"),
        "phase": int(genome["phase"]),
    }


def kyoukai_to_evo_genome(genome: dict[str, Any]) -> dict[str, Any]:
    """Map the existing KYOUKAI genome to the standalone creature genome scale."""
    return {
        "AGGRO": clamp(
            int(genome.get("trait_aggression", 0))
            + int(genome.get("noise_level", 0)) // 3
            + max(0, 100 - int(genome.get("stability", 100))) // 4,
            0,
            100,
        ),
        "CALM": clamp(
            int(genome.get("trait_softness", 0))
            + int(genome.get("trait_attachment", 0))
            + int(genome.get("stability", 100)) // 5,
            0,
            100,
        ),
        "CURIOSITY": clamp(
            int(genome.get("trait_curiosity", 0))
            + int(genome.get("trait_gaze", 0))
            + int(genome.get("observer_count", 0)) * 3
            + int(genome.get("silent_observation", 0)) // 3,
            0,
            100,
        ),
        "DISTORTION": clamp(
            int(genome.get("trait_corruption", 0))
            + int(genome.get("phase_drift", 0))
            + int(genome.get("visual_instability", 0)) // 2
            + int(genome.get("boundary_pressure", 0)) // 4,
            0,
            100,
        ),
        "last_update": str(genome.get("updated_at", "")),
    }


def creature_rarity(genome: dict[str, Any], evo: dict[str, Any]) -> str:
    peak = max(int(evo.get(key, 0)) for key in ("AGGRO", "CALM", "CURIOSITY", "DISTORTION"))
    phase = int(genome.get("phase", 0))
    mutations = int(genome.get("mutation_count", 0))
    if phase >= 3 or peak >= 86:
        return "Myth"
    if mutations >= 5 or peak >= 68:
        return "Legend"
    if mutations >= 2 or peak >= 42:
        return "Rare"
    return "Common"


def public_creature_payload(genome: dict[str, Any]) -> dict[str, Any]:
    evo = kyoukai_to_evo_genome(genome)
    if not GENOME_SYSTEM_AVAILABLE or not _creature_generator:
        return {"available": False, "evo": evo}

    params = get_creature_params(evo)
    params["rarity"] = creature_rarity(genome, evo)
    key = "|".join(
        [
            str(params.get("branch", "none")),
            str(params.get("variant", "normal")),
            str(params.get("danger", 0)),
            str(params.get("rarity", "Common")),
            str(genome.get("phase", 0)),
            str(genome.get("mutation_count", 0)),
            str(genome.get("last_mutation_type", "none")),
        ]
    )
    creature = _creature_cache.get(key)
    if creature is None:
        creature = _creature_generator.generate(
            branch=str(params["branch"]),
            variant=str(params["variant"]),
            rarity=str(params["rarity"]),
            danger=int(params["danger"]),
            seed_text=key,
        )
        _creature_cache[key] = creature

    cg = creature.get("genome", {})
    organs = [str(ORGANS.get(organ, organ)) for organ in cg.get("organs", [])]
    core = str(CORES.get(str(cg.get("core", "")), {}).get("name", cg.get("core", "unknown")))
    mutation = str(MUTATIONS.get(str(cg.get("mutation", "")), cg.get("mutation", "None")))
    shell = str(SHELLS.get(str(cg.get("shell", "")), cg.get("shell", "unknown")))
    return {
        "available": True,
        "evo": evo,
        "params": params,
        "species_id": creature.get("species_id", ""),
        "name": creature.get("name", "Unknown Organism"),
        "branch": creature.get("branch", params["branch"]),
        "variant": creature.get("variant", params["variant"]),
        "rarity": creature.get("rarity", params["rarity"]),
        "danger": creature.get("danger", params["danger"]),
        "body_plan": cg.get("body_plan", "larva_soft"),
        "silhouette": cg.get("silhouette", "larva_soft"),
        "core": core,
        "organs": organs,
        "shell": shell,
        "mutation": mutation,
    }


def mutation_audio_mode(mutation_type: str) -> str:
    return {
        "soft_bloom": "softTone",
        "distorted_pulse": "hardPulse",
        "gaze_lock": "singleTone",
        "distant_shell": "farShell",
        "noise_skin": "glitchSkin",
        "phase_slip": "phaseDelay",
        "silent_growth": "lowGrowth",
    }.get(mutation_type, "baseline")


class GenomeStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.lock = threading.RLock()
        self._init_db()
        self.update(lambda genome: genome.update({"observer_count": 0, "last_event_flags": {}}))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS genome (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    data TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS genome_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mutation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mutation_type TEXT NOT NULL,
                    phase INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS observation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS affiliate_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    url TEXT NOT NULL,
                    signal_text TEXT NOT NULL,
                    trigger_phase INTEGER DEFAULT 0,
                    trigger_mutation TEXT DEFAULT 'any',
                    display_mode TEXT DEFAULT 'panel',
                    enabled INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_affiliate_signal_columns(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_clicks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slot_name TEXT NOT NULL,
                    signal_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    target_room TEXT NOT NULL,
                    observation TEXT NOT NULL,
                    judgment TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    candidates_json TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'pending',
                    codex_ready INTEGER NOT NULL DEFAULT 0,
                    codex_instruction TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            if connection.execute("SELECT COUNT(*) FROM affiliate_signals").fetchone()[0] == 0:
                seed_signals = [
                    ("観測支援物資 TYPE-A", "#external-signal", "外部物質 TYPE-A 境界侵食中 / 広告コード未挿入", 0, "any", "panel"),
                    ("補助装置 NODE-01", "#external-signal", "外部ノード接触確認 / NODE-01 / 未接続", 1, "any", "panel"),
                    ("未確認接続 SIGNAL-X", "#external-signal", "[EXTERNAL] ████ 境界外信号受信 / 空枠", 0, "any", "log"),
                    ("境界外リンク CORRUPT-02", "#external-signal", "mutation外部干渉 / 汚染源確認 / 未挿入", 2, "noise_skin", "popup"),
                    ("深夜観測支援 SILENT-03", "#external-signal", "深夜外部接触 / 無言観測支援 / 空欄", 0, "silent_growth", "random"),
                ]
                for lbl, url, txt, phase, mut, mode in seed_signals:
                    connection.execute(
                        "INSERT INTO affiliate_signals (label, url, signal_text, trigger_phase, trigger_mutation, display_mode, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                        (lbl, url, txt, phase, mut, mode, now_iso()),
                    )
            self._ensure_kyoukai_affiliate_signal(connection)
            row = connection.execute("SELECT data FROM genome WHERE id = 1").fetchone()
            if row is None:
                genome = GENOME_DEFAULTS | {"updated_at": now_iso(), "last_input_at": time.time()}
                genome["genome_summary"] = genome_summary(genome)
                connection.execute(
                    "INSERT INTO genome (id, data, updated_at) VALUES (1, ?, ?)",
                    (json.dumps(genome, ensure_ascii=False), genome["updated_at"]),
                )

    def _ensure_affiliate_signal_columns(self, connection: sqlite3.Connection) -> None:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(affiliate_signals)").fetchall()}
        migrations = {
            "affiliate_provider": "ALTER TABLE affiliate_signals ADD COLUMN affiliate_provider TEXT DEFAULT 'none'",
            "slot_name": "ALTER TABLE affiliate_signals ADD COLUMN slot_name TEXT DEFAULT 'left_terminal_bottom'",
            "weight": "ALTER TABLE affiliate_signals ADD COLUMN weight INTEGER DEFAULT 1",
        }
        for column, statement in migrations.items():
            if column not in columns:
                connection.execute(statement)
        connection.execute(
            """
            UPDATE affiliate_signals
            SET slot_name = CASE
                WHEN display_mode = 'popup' THEN 'mutation_banner'
                WHEN display_mode = 'random' THEN 'midnight_banner'
                WHEN display_mode = 'log' THEN 'room_corner'
                WHEN id % 2 = 0 THEN 'right_monitor_inner'
                ELSE 'left_terminal_bottom'
            END
            WHERE slot_name IS NULL OR slot_name = 'left_terminal_bottom'
            """
        )

    def _ensure_kyoukai_affiliate_signal(self, connection: sqlite3.Connection) -> None:
        signal = {
            "label": "観測補助装置",
            "url": "https://px.a8.net/svt/ejp?a8mat=4B3R2X+4S2ALU+5GDG+NV9N7",
            "signal_text": "仮想観測基盤を検出 / 深夜稼働ノード応答あり",
            "trigger_phase": 0,
            "trigger_mutation": "any",
            "display_mode": "panel",
            "affiliate_provider": "A8",
            "slot_name": "room_poster",
            "weight": 5,
        }
        row = connection.execute(
            "SELECT id FROM affiliate_signals WHERE label = ? OR url = ?",
            (signal["label"], signal["url"]),
        ).fetchone()
        if row:
            connection.execute(
                """
                UPDATE affiliate_signals
                SET url = ?, signal_text = ?, trigger_phase = ?, trigger_mutation = ?,
                    display_mode = ?, enabled = 1, affiliate_provider = ?, slot_name = ?, weight = ?
                WHERE id = ?
                """,
                (
                    signal["url"],
                    signal["signal_text"],
                    signal["trigger_phase"],
                    signal["trigger_mutation"],
                    signal["display_mode"],
                    signal["affiliate_provider"],
                    signal["slot_name"],
                    signal["weight"],
                    row["id"],
                ),
            )
            return
        connection.execute(
            """
            INSERT INTO affiliate_signals
                (label, url, signal_text, trigger_phase, trigger_mutation, display_mode,
                 enabled, created_at, affiliate_provider, slot_name, weight)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                signal["label"],
                signal["url"],
                signal["signal_text"],
                signal["trigger_phase"],
                signal["trigger_mutation"],
                signal["display_mode"],
                now_iso(),
                signal["affiliate_provider"],
                signal["slot_name"],
                signal["weight"],
            ),
        )

    def get(self) -> dict[str, Any]:
        with self.lock:
            return self._read()

    def update(self, mutator) -> dict[str, Any]:
        with self.lock:
            genome = self._read()
            mutator(genome)
            self._normalize(genome)
            self._write(genome)
            return genome

    def _read(self) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT data FROM genome WHERE id = 1").fetchone()
        genome = GENOME_DEFAULTS | json.loads(row["data"])
        if not isinstance(genome.get("log_history"), list):
            genome["log_history"] = []
        if not isinstance(genome.get("last_event_flags"), dict):
            genome["last_event_flags"] = {}
        if not isinstance(genome.get("genome_summary"), dict):
            genome["genome_summary"] = {}
        if not genome.get("last_input_at"):
            genome["last_input_at"] = time.time()
        return genome

    def _write(self, genome: dict[str, Any]) -> None:
        genome["genome_summary"] = genome_summary(genome)
        genome["updated_at"] = now_iso()
        payload = json.dumps(genome, ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                "UPDATE genome SET data = ?, updated_at = ? WHERE id = 1",
                (payload, genome["updated_at"]),
            )
            connection.execute(
                "INSERT INTO genome_state (created_at, snapshot_json) VALUES (?, ?)",
                (genome["updated_at"], payload),
            )
            # keep only the latest 1000 genome_state snapshots to prevent unbounded growth
            connection.execute(
                "DELETE FROM genome_state WHERE id NOT IN (SELECT id FROM genome_state ORDER BY id DESC LIMIT 1000)"
            )

    def _normalize(self, genome: dict[str, Any]) -> None:
        genome["observer_count"] = clamp(int(genome["observer_count"]), 0, 999)
        genome["total_visits"] = max(0, int(genome["total_visits"]))
        genome["stay_time"] = max(0, int(genome["stay_time"]))
        genome["phase"] = clamp(int(genome["phase"]), 0, 3)
        genome["mutation_level"] = clamp(int(genome["mutation_level"]), 0, 999)
        genome["stability"] = clamp(int(genome["stability"]), 0, 100)
        genome["noise_level"] = clamp(int(genome["noise_level"]), 0, 100)
        genome["tempo"] = clamp(int(genome["tempo"]), 30, 180)
        genome["silent_observation"] = clamp(int(genome["silent_observation"]), 0, 999)
        genome["boundary_pressure"] = clamp(int(genome["boundary_pressure"]), 0, 100)
        genome["drift"] = clamp(int(genome["drift"]), 0, 100)
        genome["phase_drift"] = clamp(int(genome["phase_drift"]), 0, 100)
        genome["audio_instability"] = clamp(int(genome["audio_instability"]), 0, 100)
        genome["visual_instability"] = clamp(int(genome["visual_instability"]), 0, 100)
        genome["mutation_count"] = max(0, int(genome["mutation_count"]))
        genome["mutation_event_id"] = max(0, int(genome["mutation_event_id"]))
        genome["phase_up_event_id"] = max(0, int(genome.get("phase_up_event_id", 0)))
        for trait in TRAIT_KEYS:
            genome[trait] = clamp(int(genome[trait]), 0, 100)

    def append_log(self, genome: dict[str, Any], message: str, channel: str = "OBS") -> None:
        entry = f"[{channel}] {message}"
        genome["log_history"] = [entry, *genome.get("log_history", [])][:64]
        snapshot = json.dumps(genome, ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO logs (message, created_at) VALUES (?, ?)",
                (entry, now_iso()),
            )
            connection.execute(
                "INSERT INTO observation_logs (message, created_at, snapshot_json) VALUES (?, ?, ?)",
                (entry, now_iso(), snapshot),
            )
            # retain only the last 30 days of log entries
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            connection.execute("DELETE FROM logs WHERE created_at < ?", (cutoff,))
            connection.execute("DELETE FROM observation_logs WHERE created_at < ?", (cutoff,))

    def append_mutation(self, genome: dict[str, Any], mutation_type: str) -> None:
        snapshot = json.dumps(genome, ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO mutation_history (mutation_type, phase, created_at, snapshot_json)
                VALUES (?, ?, ?, ?)
                """,
                (mutation_type, int(genome["phase"]), now_iso(), snapshot),
            )


store = GenomeStore(DB_PATH)


ALLOWED_AFFILIATE_HOSTS = {"px.a8.net"}


def is_allowed_affiliate_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme == "https" and parsed.netloc.lower() in ALLOWED_AFFILIATE_HOSTS


# ─── Affiliate Signal System ─────────────────────────────────────────────────

def get_active_signals(phase: int, mutation_type: str, limit: int = 6) -> list[dict[str, Any]]:
    """Return enabled signals filtered by current genome state."""
    with store._connect() as connection:
        rows = connection.execute(
            """
            SELECT id, label, url, signal_text, trigger_phase, trigger_mutation, display_mode,
                   affiliate_provider, slot_name, weight
            FROM affiliate_signals
            WHERE enabled = 1 AND trigger_phase <= ?
            ORDER BY
                CASE WHEN trigger_mutation = ? THEN 0
                     WHEN trigger_mutation = 'any' THEN 1
                     ELSE 2 END,
                weight DESC,
                id
            LIMIT ?
            """,
            (phase, mutation_type, limit),
        ).fetchall()
    return [display_signal(dict(r)) for r in rows]


def get_signals_by_mode(phase: int, mutation_type: str, mode: str) -> list[dict[str, Any]]:
    """Return enabled signals filtered by display mode."""
    with store._connect() as connection:
        rows = connection.execute(
            """
            SELECT id, label, url, signal_text, trigger_phase, trigger_mutation, display_mode,
                   affiliate_provider, slot_name, weight
            FROM affiliate_signals
            WHERE enabled = 1 AND trigger_phase <= ? AND display_mode = ?
            ORDER BY
                CASE WHEN trigger_mutation = ? THEN 0
                     WHEN trigger_mutation = 'any' THEN 1
                     ELSE 2 END,
                weight DESC,
                id
            """,
            (phase, mode, mutation_type),
        ).fetchall()
    return [display_signal(dict(r)) for r in rows]


def display_signal(row: dict[str, Any]) -> dict[str, Any]:
    """Return a public signal payload, allowing only approved affiliate redirects."""
    original_url = str(row.get("url") or "")
    is_configured_affiliate = (
        is_allowed_affiliate_url(original_url)
        and "YOUR_A8_CODE" not in original_url
    )
    row["url"] = original_url if is_configured_affiliate else "#external-signal"
    row["signal_kind"] = "external_signal"
    row["is_affiliate"] = is_configured_affiliate
    row["disclosure"] = "PR / アフィリエイトリンクを含みます" if row["is_affiliate"] else ""
    row.setdefault("affiliate_provider", "none")
    row.setdefault("slot_name", "left_terminal_bottom")
    row.setdefault("weight", 1)
    return row


def list_signal_videos() -> list[str]:
    """Return local video files that can be played inside the /signal TV screen."""
    if not VIDEOS_DIR.exists():
        return load_video_manifest()
    videos: list[str] = []
    for path in sorted(VIDEOS_DIR.iterdir(), key=lambda item: item.name.lower()):
        if path.is_file() and path.suffix.lower() in {".mp4", ".webm", ".m4v"}:
            videos.append("/videos/" + quote(path.name))
    return videos


def load_video_manifest() -> list[str]:
    """Read the deploy-time video list when videos are served by Vercel's CDN."""
    try:
        data = json.loads(VIDEOS_MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    videos = data.get("videos", [])
    if not isinstance(videos, list):
        return []
    return [item for item in videos if isinstance(item, str)]


def site_config_payload() -> dict[str, Any]:
    return {
        "analytics": {
            "gaMeasurementId": GA_MEASUREMENT_ID,
        }
    }


def add_affiliate_signal(label: str, url: str, signal_text: str, trigger_phase: int = 0,
                         trigger_mutation: str = "any", display_mode: str = "panel") -> dict[str, Any]:
    """Insert a new affiliate signal into the database."""
    with store._connect() as connection:
        cursor = connection.execute(
            "INSERT INTO affiliate_signals (label, url, signal_text, trigger_phase, trigger_mutation, display_mode, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            (label, url, signal_text, trigger_phase, trigger_mutation, display_mode, now_iso()),
        )
        new_id = cursor.lastrowid
        row = connection.execute("SELECT * FROM affiliate_signals WHERE id = ?", (new_id,)).fetchone()
    return dict(row)


def log_signal_click(slot_name: str, signal_id: int, provider: str) -> None:
    """Store inert signal click telemetry without external ad code."""
    with store._connect() as connection:
        connection.execute(
            "INSERT INTO signal_clicks (slot_name, signal_id, provider, created_at) VALUES (?, ?, ?, ?)",
            (slot_name[:80], int(signal_id), provider[:80], now_iso()),
        )


# ─────────────────────────────────────────────────────────────────────────────


RADIO_FALLBACK_LINES = [
    "現在、受信域八十三番に接続しています。意味のない言葉が、夜を満たしていきます。",
    "こちらは境界外放送です。午前三時から未明にかけて、沈黙が強まるでしょう。",
    "第六観測波、通過。存在しない町の灯りが、まだ消えていません。",
    "受信番号、零、零、七。聞こえている方は、そのまま聞いてください。",
    "この放送は終了していません。終了予定も、登録されていません。",
    "遠い窓から、白い信号が流入しています。意味は確認されていません。",
]


def generate_radio_line() -> dict[str, Any]:
    """Generate one broken midnight broadcast line via local Ollama when available."""
    prompt = (
        "KYOUKAIの受信域で流れる、意味が少し崩れた深夜ラジオ放送文を日本語で一文だけ作ってください。"
        "ニュース、天気予報、周波数、存在しない地名、受信番号のどれかを含める。"
        "ホラー、血、霊、怪物、説明口調は禁止。45文字から90文字。"
    )
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.9, "num_predict": 80},
    }).encode("utf-8")
    try:
        request = UrlRequest(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2.2) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = str(data.get("response", "")).strip().replace("\n", " ")
        if text:
            return {"line": text[:160], "source": "ollama", "model": OLLAMA_MODEL}
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        pass
    return {"line": random.choice(RADIO_FALLBACK_LINES), "source": "fallback", "model": "local-script"}


def apply_effect(genome: dict[str, Any], effect: dict[str, Any]) -> None:
    for key, value in effect.items():
        if key in {"log", "jp_log", "mood"}:
            continue
        genome[key] = int(genome.get(key, 0)) + int(value)
    if "mood" in effect:
        genome["mood"] = str(effect["mood"])


def add_threshold_log(genome: dict[str, Any], key: str, message: str) -> None:
    flags = genome.setdefault("last_event_flags", {})
    if not flags.get(key):
        flags[key] = True
        store.append_log(genome, message)


def choose_mutation(genome: dict[str, Any]) -> str:
    candidates = {
        "soft_bloom": genome["trait_softness"] + genome["trait_attachment"] // 2,
        "distorted_pulse": genome["trait_aggression"] + genome["audio_instability"] // 2,
        "gaze_lock": genome["trait_gaze"] + genome["silent_observation"] // 3,
        "distant_shell": genome["trait_distance"] * 2,
        "noise_skin": genome["trait_corruption"] + genome["noise_level"] // 4,
        "phase_slip": genome["phase_drift"] + genome["drift"] // 2,
        "silent_growth": genome["silent_observation"] + genome["trait_gaze"] // 2,
    }
    return max(candidates, key=candidates.get)


def maybe_mutate(genome: dict[str, Any]) -> None:
    threshold = 8 + min(12, genome["mutation_count"] * 2)
    if genome["mutation_level"] < threshold:
        return
    mutation_type = choose_mutation(genome)
    genome["mutation_count"] += 1
    genome["last_mutation_type"] = mutation_type
    genome["last_mutation_at"] = now_iso()
    genome["mutation_event_id"] += 1
    genome["mutation_level"] = max(0, genome["mutation_level"] - 5)
    genome["visual_instability"] += 2
    genome["audio_instability"] += 1
    if mutation_type == "soft_bloom":
        genome["stability"] += 3
        genome["trait_softness"] += 1
        genome["noise_level"] -= 2
        genome["tempo"] -= 2
    elif mutation_type == "distorted_pulse":
        genome["noise_level"] += 4
        genome["trait_aggression"] += 1
        genome["tempo"] += 4
    elif mutation_type == "gaze_lock":
        genome["phase_drift"] += 2
        genome["trait_gaze"] += 1
        genome["tempo"] -= 1
    elif mutation_type == "distant_shell":
        genome["boundary_pressure"] += 3
        genome["trait_distance"] += 1
        genome["audio_instability"] += 1
    elif mutation_type == "noise_skin":
        genome["trait_corruption"] += 2
        genome["noise_level"] += 3
        genome["audio_instability"] += 2
    elif mutation_type == "phase_slip":
        genome["phase_drift"] += 3
        genome["drift"] += 2
        genome["visual_instability"] += 2
    elif mutation_type == "silent_growth":
        genome["silent_observation"] += 2
        genome["trait_attachment"] += 1
        genome["tempo"] -= 3

    obs_log, jp_log = MUTATION_LOGS[mutation_type]
    store.append_log(genome, obs_log)
    store.append_log(genome, jp_log, "観測")
    store.append_log(genome, f"organism contour shifted: {mutation_type}")
    store.append_mutation(genome, mutation_type)

    # Affiliate: log-mode signal injection on mutation
    log_signals = get_signals_by_mode(int(genome["phase"]), mutation_type, "log")
    if log_signals and random.random() < 0.55:
        sig = random.choice(log_signals)
        store.append_log(genome, f"§SIGNAL§#external-signal§{sig['signal_text']}", "SIGNAL")

    # Affiliate: random-mode signal injection on mutation
    rand_signals = get_signals_by_mode(int(genome["phase"]), mutation_type, "random")
    if rand_signals and random.random() < 0.35:
        sig = random.choice(rand_signals)
        store.append_log(genome, f"§SIGNAL§#external-signal§{sig['signal_text']}", "SIGNAL")


def update_phase(genome: dict[str, Any]) -> None:
    previous_phase = int(genome["phase"])
    next_phase = 0
    if genome["mutation_count"] >= 1:
        next_phase = 1
    if genome["mutation_count"] >= 3 or genome["trait_corruption"] >= 10:
        next_phase = 2
    if genome["phase_drift"] >= 10 or genome["visual_instability"] >= 12:
        next_phase = 3
    # allow phase to decrease when conditions drop (natural decay)
    genome["phase"] = next_phase
    if genome["phase"] > previous_phase:
        store.append_log(genome, "phase drift crossed threshold")
        store.append_log(genome, "phase drift 微増", "観測")
        genome["phase_up_event_id"] = max(0, int(genome.get("phase_up_event_id", 0))) + 1


def recalculate_genome(genome: dict[str, Any]) -> None:
    genome["boundary_pressure"] += genome["observer_count"] * 2 + genome["silent_observation"] // 14
    genome["noise_level"] += genome["boundary_pressure"] // 12 + genome["trait_corruption"] // 8
    genome["noise_level"] = max(
        genome["noise_level"],
        100 - genome["stability"] + genome["mutation_level"] // 6 + genome["boundary_pressure"] // 5,
    )
    genome["tempo"] = 60 + genome["observer_count"] * 3 + genome["mutation_level"] // 2 + genome["drift"] // 4
    genome["drift"] += genome["mutation_level"] // 28 + genome["phase_drift"] // 20
    genome["visual_instability"] += genome["trait_aggression"] // 18 + genome["trait_corruption"] // 20
    genome["audio_instability"] += genome["noise_level"] // 35 + genome["trait_corruption"] // 22
    maybe_mutate(genome)
    update_phase(genome)

    if genome["stability"] < 70:
        add_threshold_log(genome, "stability_lt_70", "stability decline detected")
    if genome["noise_level"] > 20:
        add_threshold_log(genome, "noise_gt_20", "boundary noise expanded")
    if genome["mutation_level"] > 10:
        add_threshold_log(genome, "mutation_gt_10", "mutation pressure rising")
    if genome["silent_observation"] > 8:
        add_threshold_log(genome, "silence_gt_8", "silence accumulated")


def apply_connection() -> dict[str, Any]:
    def mutate(genome: dict[str, Any]) -> None:
        genome["observer_count"] += 1
        genome["total_visits"] += 1
        genome["boundary_pressure"] += 2
        genome["tempo"] += 1
        if genome["observer_count"] > 1:
            genome["stability"] -= 1
            genome["visual_instability"] += 1
        store.append_log(genome, "observer entered the boundary")
        store.append_log(genome, "接続を確認", "観測")
        recalculate_genome(genome)

    return store.update(mutate)


def apply_disconnection() -> dict[str, Any]:
    def mutate(genome: dict[str, Any]) -> None:
        genome["observer_count"] -= 1
        genome["boundary_pressure"] = max(0, genome["boundary_pressure"] - 1)
        store.append_log(genome, "observer left a faint pressure")
        recalculate_genome(genome)

    return store.update(mutate)


def apply_action(raw_action: str) -> dict[str, Any]:
    action = raw_action.strip()[:80] or "無言"

    def mutate(genome: dict[str, Any]) -> None:
        effect = COMMAND_EFFECTS.get(
            action,
            {
                "trait_curiosity": 1,
                "mutation_level": 1,
                "mood": "unknown",
                "log": "unclassified input entered the genome",
                "jp_log": "未分類入力を保存",
            },
        ).copy()
        if action == "なでる" and genome["stability"] < 55:
            effect["stability"] = 1
            effect["trait_attachment"] = 2
            effect["phase_drift"] = 1
            effect["log"] = "soft contact reached unstable tissue"
        if action == "なでる" and genome["stability"] >= 80:
            effect["trait_softness"] += 1
            effect["log"] = "soft bloom pressure accepted"
        if action == "たたく" and genome["noise_level"] > 25:
            effect["trait_corruption"] += 2
            effect["visual_instability"] += 2
            effect["log"] = "impact echoed through noisy skin"
        if action == "みつめる" and genome["trait_gaze"] > 8:
            effect["phase_drift"] += 2
            effect["log"] = "external gaze synchronized with core"
        if genome["observer_count"] >= 2:
            effect["mutation_level"] = int(effect.get("mutation_level", 0)) + 1
            effect["boundary_pressure"] = int(effect.get("boundary_pressure", 0)) + genome["observer_count"]

        genome["last_action"] = action
        genome["last_input_at"] = time.time()
        apply_effect(genome, effect)
        store.append_log(genome, str(effect["log"]))
        store.append_log(genome, str(effect["jp_log"]), "観測")
        store.append_log(genome, f"action received: {action}")
        recalculate_genome(genome)

    return store.update(mutate)



def tick_once() -> dict[str, Any]:
    def mutate(genome: dict[str, Any]) -> None:
        if genome["observer_count"] <= 0:
            genome["observer_count"] = 0
            # natural decay when no one is observing
            genome["phase_drift"]         = max(0, genome["phase_drift"] - 2)
            genome["visual_instability"]  = max(0, genome["visual_instability"] - 2)
            genome["audio_instability"]   = max(0, genome["audio_instability"] - 1)
            genome["noise_level"]         = max(0, genome["noise_level"] - 2)
            genome["boundary_pressure"]   = max(0, genome["boundary_pressure"] - 2)
            genome["drift"]               = max(0, genome["drift"] - 1)
            genome["trait_gaze"]          = max(0, genome["trait_gaze"] - 1)
            genome["silent_observation"]  = max(0, genome["silent_observation"] - 1)
            update_phase(genome)
            return
        genome["stay_time"] += genome["observer_count"] * TICK_SECONDS
        genome["boundary_pressure"] += genome["observer_count"]
        genome["tempo"] += 1
        if genome["observer_count"] >= 2:
            genome["noise_level"] += 1
            genome["visual_instability"] += 1

        seconds_since_input = time.time() - float(genome.get("last_input_at", time.time()))
        if seconds_since_input >= SILENCE_THRESHOLD_SECONDS:
            genome["silent_observation"] += genome["observer_count"]
            genome["trait_gaze"] += 1
            genome["phase_drift"] += 1
            genome["drift"] += max(1, genome["observer_count"] // 2)
            if random.random() < 0.4:
                store.append_log(genome, "silence accumulated")
                store.append_log(genome, "無言観測が蓄積", "観測")

        if genome["stability"] >= 82 and seconds_since_input < SILENCE_THRESHOLD_SECONDS:
            genome["trait_attachment"] += 1
            genome["stability"] += 1
        if genome["stability"] < 55:
            genome["trait_corruption"] += 1
            genome["audio_instability"] += 1
        if random.random() < 0.18:
            store.append_log(genome, "genome pulse detected")

        # Affiliate: random-mode signal injection on tick (low probability)
        if random.random() < 0.07:
            rand_sigs = get_signals_by_mode(int(genome["phase"]), str(genome.get("last_mutation_type", "none")), "random")
            if rand_sigs:
                sig = random.choice(rand_sigs)
                store.append_log(genome, f"§SIGNAL§#external-signal§{sig['signal_text']}", "SIGNAL")

        recalculate_genome(genome)

    return store.update(mutate)



def state_payload(genome: dict[str, Any]) -> dict[str, Any]:
    summary = genome_summary(genome)
    genome["genome_summary"] = summary
    mutation = str(genome.get("last_mutation_type", "none"))
    phase = int(genome.get("phase", 0))
    panel_signals = get_signals_by_mode(phase, mutation, "panel")[:3]
    popup_signals = get_signals_by_mode(phase, mutation, "popup")[:1]
    return {
        "type": "genome",
        "genome": genome,
        "genome_summary": summary,
        "creature": public_creature_payload(genome),
        "affiliate_panel": panel_signals,
                "affiliate_popup": popup_signals,
    }


class FastAPIConnectionManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, genome: dict[str, Any]) -> None:
        message = json.dumps(state_payload(genome), ensure_ascii=False)
        for websocket in list(self.connections):
            try:
                await websocket.send_text(message)
            except RuntimeError:
                self.disconnect(websocket)

fastapi_manager = FastAPIConnectionManager()

async def genome_clock() -> None:
    while True:
        await asyncio.sleep(TICK_SECONDS)
        await fastapi_manager.broadcast(tick_once())

@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(genome_clock())
    try:
        yield
    finally:
        task.cancel()

app = FastAPI(title="KYOUKAI alpha", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/typhoon-news", StaticFiles(directory=BASE_DIR / "typhoon-news", html=True, check_dir=False), name="typhoon-news")
videos_dir = VIDEOS_DIR
try:
    videos_dir.mkdir(exist_ok=True)
except OSError:
    pass  # Vercel 読み取り専用ファイルシステム対策
if videos_dir.exists():
    app.mount("/videos", StaticFiles(directory=videos_dir), name="videos")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
city_service = CityService(BASE_DIR)

MOMENT_LAYER_WINDOW_ASSETS = (
    '  <link rel="stylesheet" href="/static/css/moment-layer-window.css?v=4">\n'
    '  <script src="/static/js/moment-layer-window.js?v=4" defer></script>\n'
)

SCENARIO_MODE_ASSETS = (
    '  <script src="/static/kyoukai-building-data.js?v=routee6" defer></script>\n'
    '  <script src="/static/kyoukai-scenario-events.js?v=routee6" defer></script>\n'
    '  <script src="/static/kyoukai-scenario.js?v=routee6" defer></script>\n'
)


def inject_moment_layer_window_assets(html: str) -> str:
    if "/static/js/moment-layer-window.js" in html:
        return html
    closing_head = re.search(r"</head\s*>", html, flags=re.IGNORECASE)
    if closing_head is None:
        return html
    return html[: closing_head.start()] + MOMENT_LAYER_WINDOW_ASSETS + html[closing_head.start() :]


def inject_scenario_mode_assets(html: str) -> str:
    if "/static/kyoukai-scenario.js" in html:
        return html
    closing_head = re.search(r"</head\s*>", html, flags=re.IGNORECASE)
    if closing_head is None:
        return html
    return html[: closing_head.start()] + SCENARIO_MODE_ASSETS + html[closing_head.start() :]


@app.middleware("http")
async def moment_layer_window_middleware(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type.lower():
        return response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    charset = "utf-8"
    charset_match = re.search(r"charset=([^;]+)", content_type, flags=re.IGNORECASE)
    if charset_match:
        charset = charset_match.group(1).strip()

    html = body.decode(charset, errors="replace")
    updated_html = inject_scenario_mode_assets(inject_moment_layer_window_assets(html))
    headers = dict(response.headers)
    headers.pop("content-length", None)
    return Response(
        content=updated_html.encode(charset),
        status_code=response.status_code,
        headers=headers,
        media_type=None,
        background=response.background,
    )

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        try:
            return templates.TemplateResponse(
                request=request,
                name="404.html",
                context={"request": request},
                status_code=404,
            )
        except TypeError:
            return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return await http_exception_handler(request, exc)

from fastapi import Body
from fastapi.responses import JSONResponse

def render_template(request: Request, name: str, status_code: int = 200, **extra_context: Any) -> HTMLResponse:
    context = {"request": request, **extra_context}
    try:
        return templates.TemplateResponse(
            request=request,
            name=name,
            context=context,
            status_code=status_code,
        )
    except TypeError:
        return templates.TemplateResponse(name, context, status_code=status_code)

# ─── Pages ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def entrance(request: Request) -> HTMLResponse:
    return render_template(request, "home.html")

@app.get("/elevator", response_class=HTMLResponse)
async def elevator(request: Request) -> HTMLResponse:
    return render_template(request, "elevator.html")

@app.get("/floor/{floor_number}", response_class=HTMLResponse)
async def floor_lobby(request: Request, floor_number: str) -> HTMLResponse:
    if re.fullmatch(r"\d{1,3}", floor_number) is None or int(floor_number) < 1:
        return RedirectResponse(url="/elevator")
    return render_template(request, "floor.html", floor_number=floor_number.zfill(2))

@app.get("/observation", response_class=HTMLResponse)
async def observation(request: Request) -> HTMLResponse:
    return render_template(request, "index.html")

@app.get("/observer", response_class=HTMLResponse)
async def observer_room(request: Request) -> HTMLResponse:
    return render_template(request, "observer.html")

@app.get("/archive", response_class=HTMLResponse)
async def archive(request: Request) -> HTMLResponse:
    return render_template(request, "archive.html")

@app.get("/archive/logs", response_class=HTMLResponse)
async def archive_logs(request: Request) -> HTMLResponse:
    return render_template(request, "archive-logs.html")

@app.get("/archive/logs/{log_id}", response_class=HTMLResponse)
async def archive_log_detail(request: Request, log_id: str) -> HTMLResponse:
    if log_id not in {f"{index:03d}" for index in range(1, 11)}:
        return HTMLResponse("archive log not found", status_code=404)
    return render_template(request, f"archive-log-{log_id}.html")

@app.get("/signal", response_class=HTMLResponse)
async def signal_room(request: Request) -> HTMLResponse:
    return render_template(request, "signal.html")

@app.get("/top-floor", response_class=HTMLResponse)
async def top_floor_room(request: Request) -> HTMLResponse:
    return render_template(request, "top-floor.html")

@app.get("/external-signal", response_class=HTMLResponse)
async def external_signal_room(request: Request) -> HTMLResponse:
    return render_template(request, "external-signal.html")

@app.get("/daimyojin", response_class=HTMLResponse)
async def daimyojin_room(request: Request) -> HTMLResponse:
    return render_template(
        request,
        "daimyojin.html",
        daimyojin_config=json.dumps(build_daimyojin_config(), ensure_ascii=False),
    )

@app.get("/Codex", response_class=HTMLResponse, include_in_schema=False)
@app.get("/codex", response_class=HTMLResponse, include_in_schema=False)
async def codex_automation_page(request: Request) -> HTMLResponse:
    return render_template(request, "codex_template.html", **build_codex_context())

@app.get("/hyougi", response_class=HTMLResponse)
async def hyougi_room(request: Request) -> HTMLResponse:
    return render_template(request, "hyougi.html")

@app.get("/gokuraku", response_class=HTMLResponse)
@app.get("/gokurakuiki", response_class=HTMLResponse)
@app.get("/gokugaku", response_class=HTMLResponse)
async def gokuraku_room(request: Request) -> HTMLResponse:
    return render_template(request, "gokuraku.html")

@app.get("/exit", response_class=HTMLResponse)
async def exit_room(request: Request) -> Any:
    try:
        location = city_service.first_location(base_path="/exit")
    except CityDataError:
        location = None
    if location is None:
        return render_template(
            request,
            "city/error.html",
            title="NewExit is not ready",
            message="NewExit data is not available.",
            status_code=503,
        )
    return RedirectResponse(url=f"/exit/{location['slug']}")


@app.get("/exit/{slug}", response_class=HTMLResponse)
async def new_exit_location(request: Request, slug: str) -> HTMLResponse:
    try:
        location = city_service.get_location(slug, base_path="/exit")
        districts = city_service.load_districts()
    except CityDataError:
        return render_template(
            request,
            "city/error.html",
            title="NewExit data error",
            message="NewExit location data could not be loaded.",
            status_code=503,
        )
    if location is None:
        return render_template(
            request,
            "city/error.html",
            title="NewExit not found",
            message="That NewExit location is not available.",
            status_code=404,
        )
    district = districts.get(str(location.get("district")), {})
    return render_template(
        request,
        "city/location.html",
        location=location,
        images=location.get("images", {}),
        hotspots=location.get("hotspots", []),
        district=district,
        visit_state={},
        debug_mode=request.query_params.get("debug") == "1",
        base_path="/exit",
    )

@app.get("/null", response_class=HTMLResponse)
async def null_room(request: Request) -> HTMLResponse:
    return render_template(request, "null.html")

@app.get("/outside", response_class=HTMLResponse)
@app.get("/support", response_class=HTMLResponse)
async def outside_core(request: Request) -> HTMLResponse:
    return render_template(request, "outside.html")

@app.get("/ma", response_class=HTMLResponse)
async def ma_room(request: Request) -> HTMLResponse:
    return render_template(request, "ma.html")

@app.get("/fukashitsu", response_class=HTMLResponse)
async def fukashitsu_room(request: Request) -> HTMLResponse:
    return render_template(request, "fukashitsu.html")

@app.get("/kanrinin", response_class=HTMLResponse)
@app.get("/manager", response_class=HTMLResponse)
async def kanrinin_room(request: Request) -> HTMLResponse:
    return render_template(request, "kanrinin.html")

@app.get("/matsuri", response_class=HTMLResponse)
async def matsuri_room(request: Request) -> HTMLResponse:
    return render_template(request, "matsuri.html")

@app.get("/namahage", response_class=HTMLResponse)
async def namahage_room(request: Request) -> HTMLResponse:
    return render_template(request, "namahage.html")

@app.get("/avatar/namahage", response_class=HTMLResponse)
async def namahage_avatar(request: Request) -> HTMLResponse:
    return render_template(request, "namahage-avatar.html")

@app.get("/avatar/namahage-editor", response_class=HTMLResponse)
async def namahage_avatar_editor(request: Request) -> HTMLResponse:
    if os.environ.get("VERCEL"):
        return HTMLResponse("local only", status_code=404)
    return render_template(request, "namahage-avatar-editor.html")

@app.get("/avatar/namahage-mic", response_class=HTMLResponse)
async def namahage_avatar_mic(request: Request) -> HTMLResponse:
    if os.environ.get("VERCEL"):
        return HTMLResponse("local only", status_code=404)
    return render_template(request, "namahage-avatar-mic.html")

@app.get("/avatar/namahage-consult", response_class=HTMLResponse)
async def namahage_avatar_consult(request: Request) -> HTMLResponse:
    if os.environ.get("VERCEL"):
        return HTMLResponse("local only", status_code=404)
    return render_template(request, "namahage-avatar-consult.html")

@app.get("/avatar/namahage-consult-admin", response_class=HTMLResponse)
async def namahage_avatar_consult_admin(request: Request) -> HTMLResponse:
    if os.environ.get("VERCEL"):
        return HTMLResponse("local only", status_code=404)
    return render_template(request, "namahage-avatar-consult-admin.html")

@app.get("/api/namahage-avatar/audio-level")
async def get_namahage_avatar_audio_level(session: str = "main") -> JSONResponse:
    if os.environ.get("VERCEL"):
        return JSONResponse({"ok": False, "error": "local only"}, status_code=403)
    record = NAMAHAGE_AUDIO_LEVELS.get(session) or {"volume": 0.0, "updated": 0.0}
    age_ms = max(0, int((time.time() - record["updated"]) * 1000)) if record["updated"] else 999999
    active = age_ms < 900
    return JSONResponse({
        "ok": True,
        "session": session,
        "active": active,
        "ageMs": age_ms,
        "volume": float(record["volume"]) if active else 0.0,
    })

@app.post("/api/namahage-avatar/audio-level")
async def set_namahage_avatar_audio_level(body: dict = Body(...)) -> JSONResponse:
    if os.environ.get("VERCEL"):
        return JSONResponse({"ok": False, "error": "local only"}, status_code=403)
    session = str(body.get("session") or "main")[:64]
    try:
        volume = max(0.0, min(1.0, float(body.get("volume") or 0.0)))
    except (TypeError, ValueError):
        volume = 0.0
    NAMAHAGE_AUDIO_LEVELS[session] = {"volume": volume, "updated": time.time()}
    return JSONResponse({"ok": True, "session": session, "volume": volume})

@app.get("/api/namahage-avatar/action")
async def get_namahage_avatar_action(session: str = "main", since: int = 0) -> JSONResponse:
    if os.environ.get("VERCEL"):
        return JSONResponse({"ok": False, "error": "local only"}, status_code=403)
    queue = NAMAHAGE_ACTIONS.get(session) or []
    actions = [action for action in queue if int(action.get("id", 0)) > since]
    action = actions[0] if actions else None
    latest_id = int(queue[-1].get("id", 0)) if queue else since
    return JSONResponse({"ok": True, "session": session, "action": action, "actions": actions, "latestId": latest_id})

@app.post("/api/namahage-avatar/action")
async def set_namahage_avatar_action(body: dict = Body(...)) -> JSONResponse:
    global NAMAHAGE_ACTION_COUNTER
    if os.environ.get("VERCEL"):
        return JSONResponse({"ok": False, "error": "local only"}, status_code=403)
    session = str(body.get("session") or "main")[:64]
    action = str(body.get("action") or "")[:32]
    if action not in {"knife", "horn", "smile", "frown", "heart"}:
        return JSONResponse({"ok": False, "error": "invalid action"}, status_code=400)
    queue = NAMAHAGE_ACTIONS.setdefault(session, [])
    NAMAHAGE_ACTION_COUNTER += 1
    action_id = NAMAHAGE_ACTION_COUNTER
    queue.append({"id": action_id, "type": action, "created": time.time()})
    del queue[:-24]
    return JSONResponse({"ok": True, "session": session, "action": action, "id": action_id})

@app.get("/api/namahage-avatar/consult")
async def get_namahage_avatar_consult(session: str = "main") -> JSONResponse:
    if os.environ.get("VERCEL"):
        return JSONResponse({"ok": False, "error": "local only"}, status_code=403)
    payload = NAMAHAGE_CONSULTS.get(session) or {"visible": False}
    return JSONResponse({"ok": True, "session": session, "consult": payload})

@app.post("/api/namahage-avatar/consult")
async def set_namahage_avatar_consult(body: dict = Body(...)) -> JSONResponse:
    if os.environ.get("VERCEL"):
        return JSONResponse({"ok": False, "error": "local only"}, status_code=403)
    session = str(body.get("session") or "main")[:64]
    visible = bool(body.get("visible"))
    payload = {
        "visible": visible,
        "source": str(body.get("source") or "")[:120],
        "title": str(body.get("title") or "")[:80],
        "summary": str(body.get("summary") or "")[:360],
        "answer": str(body.get("answer") or "")[:520],
        "namahage": str(body.get("namahage") or "")[:420],
        "updated": time.time(),
    }
    NAMAHAGE_CONSULTS[session] = payload
    return JSONResponse({"ok": True, "session": session, "consult": payload})

@app.post("/api/namahage-avatar/render")
async def render_namahage_avatar_assets(body: dict = Body(...)) -> JSONResponse:
    if os.environ.get("VERCEL"):
        return JSONResponse({"ok": False, "error": "local only"}, status_code=403)
    try:
        from PIL import Image, ImageDraw, ImageFilter

        source_path = BASE_DIR / "static" / "images" / "namahage" / "namahage-room-9x16.png"
        output_dir = BASE_DIR / "static" / "images" / "namahage-avatar"
        source = Image.open(source_path).convert("RGBA")
        width, height = source.size

        def px(point: list[float]) -> tuple[int, int]:
            return (
                int(max(0, min(1, float(point[0]))) * width),
                int(max(0, min(1, float(point[1]))) * height),
            )

        shapes = body.get("shapes", [])
        jaw_mask = Image.new("L", source.size, 0)
        jaw_draw = ImageDraw.Draw(jaw_mask)
        preserve_mask = Image.new("L", source.size, 0)
        preserve_draw = ImageDraw.Draw(preserve_mask)
        knife_mask = Image.new("L", source.size, 0)
        knife_draw = ImageDraw.Draw(knife_mask)
        horns_mask = Image.new("L", source.size, 0)
        horns_draw = ImageDraw.Draw(horns_mask)

        for shape in shapes:
            points = shape.get("points") if isinstance(shape, dict) else None
            if not points or len(points) < 3:
                continue
            polygon = [px(point) for point in points]
            target = shape.get("target", "jaw")
            if target == "knife":
                if shape.get("mode") == "exclude":
                    knife_draw.polygon(polygon, fill=0)
                else:
                    knife_draw.polygon(polygon, fill=255)
            elif target == "horns":
                if shape.get("mode") == "exclude":
                    horns_draw.polygon(polygon, fill=0)
                else:
                    horns_draw.polygon(polygon, fill=255)
            elif shape.get("mode") == "exclude":
                jaw_draw.polygon(polygon, fill=0)
                preserve_draw.polygon(polygon, fill=255)
            else:
                jaw_draw.polygon(polygon, fill=255)

        jaw_mask = jaw_mask.filter(ImageFilter.GaussianBlur(0.85))
        jaw = Image.new("RGBA", source.size, (0, 0, 0, 0))
        jaw.alpha_composite(source)
        jaw.putalpha(jaw_mask)
        jaw.save(output_dir / "namahage-lower-jaw.png")

        erase_mask = jaw_mask.filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(1.8))
        erase_mask = Image.composite(Image.new("L", source.size, 0), erase_mask, preserve_mask)

        mouth = source.copy()
        mouth_draw = ImageDraw.Draw(mouth, "RGBA")
        mouth_draw.polygon(
            [px(point) for point in [[0.310, 0.570], [0.695, 0.570], [0.692, 0.735], [0.615, 0.790], [0.500, 0.810], [0.385, 0.790], [0.305, 0.735]]],
            fill=(1, 1, 1, 246),
        )
        mouth_draw.ellipse(
            (int(width * 0.350), int(height * 0.570), int(width * 0.650), int(height * 0.750)),
            fill=(0, 0, 0, 252),
        )
        knife_mask = knife_mask.filter(ImageFilter.GaussianBlur(0.85))
        knife = Image.new("RGBA", source.size, (0, 0, 0, 0))
        knife.alpha_composite(source)
        knife.putalpha(knife_mask)
        knife.save(output_dir / "namahage-knife.png")

        horns_mask = horns_mask.filter(ImageFilter.GaussianBlur(0.85))
        horns = Image.new("RGBA", source.size, (0, 0, 0, 0))
        horns.alpha_composite(source)
        horns.putalpha(horns_mask)
        horns.save(output_dir / "namahage-horns.png")

        base = Image.composite(mouth, source, erase_mask)

        knife_erase_mask = knife_mask.filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.GaussianBlur(2.5))
        knife_fill = Image.new("RGBA", source.size, (8, 6, 5, 255))
        shifted_hair = source.transform(
            source.size,
            Image.Transform.AFFINE,
            (1, 0, int(width * 0.18), 0, 1, 0),
            resample=Image.Resampling.BICUBIC,
        ).filter(ImageFilter.GaussianBlur(8))
        dark_wash = Image.new("RGBA", source.size, (4, 3, 3, 165))
        knife_fill.alpha_composite(shifted_hair)
        knife_fill.alpha_composite(dark_wash)
        base = Image.composite(knife_fill, base, knife_erase_mask)
        base.save(output_dir / "namahage-base.png")

        assetv = str(int(time.time()))
        return JSONResponse(
            {
                "ok": True,
                "assetv": assetv,
                "base": "/static/images/namahage-avatar/namahage-base.png",
                "jaw": "/static/images/namahage-avatar/namahage-lower-jaw.png",
                "knife": "/static/images/namahage-avatar/namahage-knife.png",
                "horns": "/static/images/namahage-avatar/namahage-horns.png",
            }
        )
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

@app.get("/dot-hanabi", response_class=HTMLResponse)
async def dot_hanabi_room(request: Request) -> HTMLResponse:
    return render_template(request, "dot-hanabi.html")

# /central route removed (Central OS isolated 2026-06-18)

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request) -> HTMLResponse:
    return render_template(request, "about.html")

@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy_page(request: Request) -> HTMLResponse:
    return render_template(request, "privacy-policy.html")

@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request) -> HTMLResponse:
    return render_template(request, "contact.html")

@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request) -> HTMLResponse:
    return render_template(request, "terms.html")

@app.get("/sitemap", response_class=HTMLResponse)
async def sitemap_page(request: Request) -> HTMLResponse:
    return render_template(request, "sitemap.html")

@app.get("/tiktok", response_class=HTMLResponse)
@app.get("/shorts", response_class=HTMLResponse)
@app.get("/x", response_class=HTMLResponse)
@app.get("/reels", response_class=HTMLResponse)
async def sns_entry_page(request: Request) -> HTMLResponse:
    return render_template(request, "sns-entry.html")

@app.get("/particles", response_class=HTMLResponse)
async def particles_page(request: Request) -> HTMLResponse:
    return render_template(request, "particles.html")

@app.get("/ripple", response_class=HTMLResponse)
async def ripple_page(request: Request) -> HTMLResponse:
    return render_template(request, "ripple.html")

@app.get("/colony", response_class=HTMLResponse)
async def colony_page(request: Request) -> HTMLResponse:
    return render_template(request, "colony.html")

@app.get("/dot-art", response_class=HTMLResponse)
async def dot_art_page(request: Request) -> HTMLResponse:
    return render_template(request, "dot-art.html")

@app.get("/city", response_class=HTMLResponse)
async def city_index(request: Request) -> Any:
    return RedirectResponse(url="/exit")


@app.get("/city/{slug}", response_class=HTMLResponse)
async def city_location_compat(request: Request, slug: str) -> Any:
    return RedirectResponse(url=f"/exit/{slug}")


@app.get("/new-exit", response_class=HTMLResponse)
async def new_exit_alias(request: Request) -> Any:
    return RedirectResponse(url="/exit")


@app.get("/new-exit/{slug}", response_class=HTMLResponse)
async def new_exit_location_alias(request: Request, slug: str) -> Any:
    return RedirectResponse(url=f"/exit/{slug}")



@app.get("/altar", response_class=HTMLResponse)
async def altar_room(request: Request) -> HTMLResponse:
    return render_template(
        request,
        "city/altar.html",
        debug_mode=request.query_params.get("debug") == "1",
    )

# ─── API ────────────────────────────────────────────────

@app.get("/api/genome")
async def api_genome() -> JSONResponse:
    genome = store.get()
    summary = genome_summary(genome)
    return JSONResponse({
        "phase": int(genome.get("phase", 0)),
        "mutation_count": int(genome.get("mutation_count", 0)),
        "last_mutation_type": str(genome.get("last_mutation_type", "none")),
        "observer_count": int(genome.get("observer_count", 0)),
        "stability": int(genome.get("stability", 100)),
        "noise_level": int(genome.get("noise_level", 0)),
        "mood": str(genome.get("mood", "quiet")),
        "dominant_trait": summary.get("dominant_trait", "none"),
        "instability": summary.get("instability", 0),
        "updated_at": str(genome.get("updated_at", "")),
    })

@app.get("/api/signals")
async def api_get_signals() -> JSONResponse:
    genome = store.get()
    phase = int(genome.get("phase", 0))
    mutation = str(genome.get("last_mutation_type", "none"))
    signals = get_active_signals(phase, mutation)
    return JSONResponse({"signals": signals})

@app.get("/api/creature")
async def api_creature() -> JSONResponse:
    return JSONResponse(public_creature_payload(store.get()))

@app.get("/api/radio-line")
async def api_radio_line() -> JSONResponse:
    return JSONResponse(generate_radio_line())

@app.get("/api/videos")
async def api_videos() -> JSONResponse:
    return JSONResponse({"videos": list_signal_videos()})

@app.get("/api/site-config")
async def api_site_config() -> JSONResponse:
    return JSONResponse(site_config_payload(), headers={"Cache-Control": "no-store"})

@app.get("/api/test-ai")
async def api_test_ai() -> JSONResponse:
    """AI接続テスト用エンドポイント（デバッグ用）"""
    import os as _os
    from urllib.request import Request as _Req, urlopen as _open

    results = {}

    # Groq test
    groq_key = _os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        payload = json.dumps({"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}).encode()
        try:
            req = _Req("https://api.groq.com/openai/v1/chat/completions", data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {groq_key}", "User-Agent": "Mozilla/5.0"}, method="POST")
            with _open(req, timeout=10) as r:
                d = json.loads(r.read())
            results["groq"] = {"ok": True, "reply": d["choices"][0]["message"]["content"]}
        except Exception as e:
            results["groq"] = {"ok": False, "error": str(e)}
    else:
        results["groq"] = {"ok": False, "error": "no key"}

    # OpenRouter test
    or_key = _os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        for model in ["google/gemma-4-26b-a4b-it:free", "google/gemma-4-31b-it:free", "moonshotai/kimi-k2.6:free"]:
            payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}).encode()
            try:
                req = _Req("https://openrouter.ai/api/v1/chat/completions", data=payload,
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {or_key}", "HTTP-Referer": "https://www.void-kyoukai.net"}, method="POST")
                with _open(req, timeout=15) as r:
                    d = json.loads(r.read())
                results["openrouter"] = {"ok": True, "model": model, "reply": d["choices"][0]["message"]["content"]}
                break
            except Exception as e:
                results[f"openrouter_{model}"] = {"ok": False, "error": str(e)[:80]}
    else:
        results["openrouter"] = {"ok": False, "error": "no key"}

    return JSONResponse(results)


# 神様リレーメッセージ（インメモリ、最大100件FIFO）
import collections as _collections
_divine_relay: _collections.deque = _collections.deque(maxlen=100)


@app.get("/api/divine-relay")
async def divine_relay_get():
    if not _divine_relay:
        return JSONResponse({"message": None})
    import random
    return JSONResponse({"message": random.choice(list(_divine_relay))})


@app.post("/api/divine-relay")
async def divine_relay_post(request: Request):
    body = await request.json()
    text = str(body.get("message", "")).strip()
    if 1 <= len(text) <= 60:
        _divine_relay.appendleft(text)
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "reason": "invalid length"}, status_code=400)


@app.get("/api/divine-voice")
async def divine_voice(visits: int = 1, hour: int = 12, elapsed: int = 60):
    import os as _os
    import json
    from urllib.request import Request as _Req, urlopen as _open

    SYSTEM = (
        "あなたはKYOUKAIという不思議なウェブサイトの神様です。"
        "フランクで友達感覚、でもちゃんと神様という雰囲気で話しかけてください。"
        "怖い言葉、脅すような言葉、進めない・戻れないといった制限を示す言葉は禁止です。"
        "穏やかで、少し不思議で、親しみやすいトーンで。"
        "訪問者のデータを見て、神様として一言だけ日本語で話しかけてください。"
        "句読点なし、10〜20文字程度の短文を一つだけ出力してください。"
        "説明や補足は不要です。セリフだけ出力してください。"
    )
    USER = f"訪問回数:{visits}回 / 現在時刻:{hour}時 / 滞在:{elapsed}秒"

    FALLBACK = [
        "また来たね",
        "ゆっくりしていって",
        "今日も来てくれた",
        "ここにいるよ",
        "見てるよ別に怖くない",
        "いい感じだよ",
        "気になるとこ行ってみて",
        "久しぶり",
    ]

    or_key = _os.environ.get("OPENROUTER_API_KEY", "")
    if not or_key:
        import random
        return JSONResponse({"voice": random.choice(FALLBACK), "source": "fallback"})

    payload = json.dumps({
        "model": "google/gemma-4-26b-a4b-it:free",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
        "max_tokens": 40,
        "temperature": 0.9,
    }).encode()

    try:
        req = _Req(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {or_key}",
                "HTTP-Referer": "https://www.void-kyoukai.net",
            },
            method="POST",
        )
        with _open(req, timeout=15) as r:
            d = json.loads(r.read())
        voice = d["choices"][0]["message"]["content"].strip().split("\n")[0]
        return JSONResponse({"voice": voice, "source": "openrouter"})
    except Exception as e:
        import random
        return JSONResponse({"voice": random.choice(FALLBACK), "source": "fallback", "error": str(e)[:60]})


@app.post("/api/signals")
async def api_post_signal(body: dict = Body(...)) -> JSONResponse:
    try:
        signal = add_affiliate_signal(
            label=str(body.get("label", "untitled")),
            url=str(body.get("url", "")),
            signal_text=str(body.get("signal_text", "")),
            trigger_phase=int(body.get("trigger_phase", 0)),
            trigger_mutation=str(body.get("trigger_mutation", "any")),
            display_mode=str(body.get("display_mode", "panel")),
        )
        return JSONResponse({"ok": True, "signal": signal})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

@app.post("/api/action")
async def api_action(body: dict = Body(...)) -> JSONResponse:
    try:
        genome = apply_action(str(body.get("action", "")))
        await fastapi_manager.broadcast(genome)
        return JSONResponse(state_payload(genome))
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

@app.post("/api/signal-click")
async def api_signal_click(body: dict = Body(...)) -> JSONResponse:
    try:
        log_signal_click(
            slot_name=str(body.get("slot_name", "unknown")),
            signal_id=int(body.get("signal_id", 0)),
            provider=str(body.get("provider", "none")),
        )
        return JSONResponse({"ok": True})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await fastapi_manager.connect(websocket)
    await fastapi_manager.broadcast(apply_connection())
    try:
        while True:
            payload = await websocket.receive_text()
            data = json.loads(payload)
            if data.get("type") == "action" or "action" in data:
                await fastapi_manager.broadcast(apply_action(str(data.get("action", ""))))
    except (WebSocketDisconnect, json.JSONDecodeError):
        fastapi_manager.disconnect(websocket)
        await fastapi_manager.broadcast(apply_disconnection())


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
