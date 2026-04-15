"""Car-HUD Widget System
Auto-discovers widget modules (w_*.py). Each widget can:
  - name: str — display name
  - priority: int — base priority (lower = shown first)
  - def is_active(hud, music) -> bool — has content to show?
  - def draw(hud, x, y, w, h, music) -> bool — render, return True if drawn
  - def urgency(hud, music) -> int (optional) — 0=normal, negative=promote above priority
    Widget returns negative urgency to temporarily jump ahead of others.
    e.g. music widget returns -100 when a new song starts, so it shows first.
"""

import os
import json
import importlib
import glob
import time

_widgets = []
_loaded = False
CONFIG_FILE = "/home/chrismslist/car-hud/.widget-config.json"


def _load_widgets():
    global _widgets, _loaded
    if _loaded:
        return
    _loaded = True

    widget_dir = os.path.dirname(os.path.abspath(__file__))
    for path in sorted(glob.glob(os.path.join(widget_dir, "w_*.py"))):
        mod_name = os.path.basename(path)[:-3]
        try:
            mod = importlib.import_module(f"widgets.{mod_name}")
            if hasattr(mod, "draw") and hasattr(mod, "name"):
                _widgets.append(mod)
        except Exception as e:
            print(f"Widget load error {mod_name}: {e}")

    _widgets.sort(key=lambda m: getattr(m, "priority", 50))


def _load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
    except Exception:
        pass


def get_active(hud, music):
    """Return active widgets sorted by effective priority (base + urgency)."""
    _load_widgets()
    config = _load_config()
    active = []
    for mod in _widgets:
        wname = mod.name.lower()
        if not config.get(wname, {}).get("enabled", True):
            continue
        try:
            if mod.is_active(hud, music):
                # Effective priority = base priority + urgency adjustment
                urg = 0
                if hasattr(mod, "urgency"):
                    urg = mod.urgency(hud, music)
                eff = getattr(mod, "priority", 50) + urg
                active.append((eff, mod.name, mod))
        except Exception:
            pass

    active.sort(key=lambda x: x[0])
    return [(name, mod) for _, name, mod in active]


def get_all():
    _load_widgets()
    config = _load_config()
    result = []
    for mod in _widgets:
        wname = mod.name.lower()
        result.append({
            "name": mod.name,
            "priority": getattr(mod, "priority", 50),
            "enabled": config.get(wname, {}).get("enabled", True),
        })
    return result


def set_enabled(widget_name, enabled):
    config = _load_config()
    config[widget_name.lower()] = {"enabled": enabled}
    save_config(config)
