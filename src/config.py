"""Car-HUD Shared Configuration
Central constants, paths, and utility functions used across all services.
Import this instead of hardcoding paths or duplicating helper functions.

Usage:
    from config import PROJECT_DIR, TMP, log, write_signal
"""

import os
import json
import time

# ── Project paths ──
PROJECT_DIR = "/home/chrismslist/car-hud"
TMP = "/tmp"

# Signal/data files (read by HUD, written by services)
OBD_DATA = f"{TMP}/car-hud-obd-data"
MUSIC_DATA = f"{TMP}/car-hud-music-data"
WIFI_DATA = f"{TMP}/car-hud-wifi-data"
DASHCAM_DATA = f"{TMP}/car-hud-dashcam-data"
COBRA_DATA = f"{TMP}/car-hud-cobra-data"
BATTERY_DATA = f"{TMP}/car-hud-battery-data"
DISPLAY_DATA = f"{TMP}/car-hud-display-data"
GPS_DATA = f"{TMP}/car-hud-gps"
VOICE_SIGNAL = f"{TMP}/car-hud-voice-signal"
MIC_LEVEL = f"{TMP}/car-hud-mic-level"
TRANSCRIPT = f"{TMP}/car-hud-transcript"
SCREENSHOT_REQ = "/dev/shm/car-hud-screenshot-request"
SCREENSHOT_BMP = "/dev/shm/car-hud-screenshot.bmp"

# Config files (persistent across reboots)
THEME_FILE = f"{PROJECT_DIR}/.theme"
BRIGHTNESS_FILE = f"{PROJECT_DIR}/.brightness"
WIDGET_CONFIG = f"{PROJECT_DIR}/.widget-config.json"
PINNED_WIDGETS = f"{PROJECT_DIR}/.pinned-widgets.json"
OBD_ADAPTER_FILE = f"{PROJECT_DIR}/.obd_adapter"
COBRA_ADAPTER_FILE = f"{PROJECT_DIR}/.cobra_adapter"
PAIRED_PHONE_FILE = f"{PROJECT_DIR}/.paired_phone"
SPOTIFY_TOKEN = f"{PROJECT_DIR}/.spotify_token"
SPOTIFY_KEYS = f"{PROJECT_DIR}/.keys.json"
BATTERY_DB = f"{PROJECT_DIR}/battery_history.db"

# Asset paths
HONDA_LOGO = f"{PROJECT_DIR}/honda_logo.png"
SPLASH_IMAGE = f"{PROJECT_DIR}/splash.png"
ART_FILE = f"{PROJECT_DIR}/current_art.jpg"
ART_CACHE_DIR = f"{PROJECT_DIR}/art_cache"
DASHCAM_DIR = f"{PROJECT_DIR}/dashcam"
VOSK_MODEL = f"{PROJECT_DIR}/vosk-model"

# ── Display constants ──
TARGET_W = 480
TARGET_H = 320
TARGET_FPS = 30

# ── Font sizes ──
FONT_XXL = 54
FONT_XL = 38
FONT_LG = 28
FONT_MD = 17
FONT_SM = 14
FONT_XS = 12
FONT_MONO = 11

# ── Theme / time ──
DAY_START_HOUR = 7
DAY_END_HOUR = 19

# ── OBD ──
OBD_STALE_SECONDS = 10
MUSIC_STALE_SECONDS = 30

# ── Vehicle specs (2014 Honda Accord Hybrid) ──
PACK_CELLS = 72
CELL_NOMINAL_V = 3.6
PACK_NOMINAL_V = PACK_CELLS * CELL_NOMINAL_V  # ~259.2V
MAX_SPEED_MPH = 140
MAX_RPM = 7000

# ── Status colors (same across all themes) ──
GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)

# ── OBD adapter names ──
OBD_BLE_NAMES = ["ios-vlink", "android-vlink", "vlink", "icar"]
COBRA_BLE_NAMES = ["rad 700", "rad700", "cobra rad"]


def log(msg: str, log_file: str = None) -> None:
    """Print timestamped log message. Optionally write to log file.

    Args:
        msg: Message to log.
        log_file: Optional path to append message to.
    """
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if log_file:
        try:
            with open(log_file, "a") as f:
                f.write(line + "\n")
        except Exception:
            pass


def write_signal(path: str, data: dict) -> None:
    """Write a JSON signal/data file atomically with timestamp.

    Args:
        path: File path to write to.
        data: Dictionary to serialize as JSON. Timestamp is added automatically.
    """
    data["timestamp"] = time.time()
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def read_signal(path: str, max_age: float = 30) -> dict:
    """Read a JSON signal/data file, return empty dict if stale or missing.

    Args:
        path: File path to read.
        max_age: Maximum age in seconds before data is considered stale.

    Returns:
        Parsed dictionary, or empty dict if file is missing/stale/invalid.
    """
    try:
        with open(path) as f:
            data = json.load(f)
        if time.time() - data.get("timestamp", 0) < max_age:
            return data
    except Exception:
        pass
    return {}
