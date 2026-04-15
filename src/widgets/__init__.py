"""Car-HUD Widget System
Auto-discovers and loads widget modules from this directory.
Each widget module must have:
  - name: str — display name
  - priority: int — lower = shown first (0=highest)
  - def is_active(hud, music) -> bool — whether widget has content
  - def draw(hud, x, y, w, h, music) -> bool — render widget, return True if drawn
"""

import os
import json
import importlib
import glob

_widgets = []
_loaded = False
CONFIG_FILE = "/home/chrismslist/car-hud/.widget-config.json"


def _load_widgets():
    """Auto-discover widget modules in this directory."""
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
    """Load widget visibility config."""
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config):
    """Save widget visibility config."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
    except Exception:
        pass


def get_active(hud, music):
    """Return list of (name, module) for enabled widgets that have content."""
    _load_widgets()
    config = _load_config()
    active = []
    for mod in _widgets:
        wname = mod.name.lower()
        # Check if widget is disabled in config (enabled by default)
        if not config.get(wname, {}).get("enabled", True):
            continue
        try:
            if mod.is_active(hud, music):
                active.append((mod.name, mod))
        except Exception:
            pass
    return active


def get_all():
    """Return all loaded widget modules with their config state."""
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
    """Enable or disable a widget by name."""
    config = _load_config()
    config[widget_name.lower()] = {"enabled": enabled}
    save_config(config)
