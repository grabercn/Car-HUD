"""Car-HUD Widget System
Auto-discovers and loads widget modules from this directory.
Each widget module must have:
  - name: str — display name
  - priority: int — lower = shown first (0=highest)
  - def is_active(hud, music) -> bool — whether widget has content
  - def draw(hud, x, y, w, h, music) -> bool — render widget, return True if drawn
"""

import os
import importlib
import glob

_widgets = []
_loaded = False


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


def get_active(hud, music):
    """Return list of (name, module) for widgets that have content right now."""
    _load_widgets()
    active = []
    for mod in _widgets:
        try:
            if mod.is_active(hud, music):
                active.append((mod.name, mod))
        except Exception:
            pass
    return active


def get_all():
    """Return all loaded widget modules."""
    _load_widgets()
    return list(_widgets)
