"""Auto-generate API reference markdown pages from source code.
Runs during docs build -- scans src/ for Python files and creates
a reference page for each one with mkdocstrings directives.
"""

import os

SRC_DIR = "src"
API_DIR = "docs/api"
WIDGET_DIR = os.path.join(SRC_DIR, "widgets")
PAGES_DIR = os.path.join(SRC_DIR, "pages")

os.makedirs(API_DIR, exist_ok=True)

# Main service files
services = {
    "config": "Shared configuration, constants, and utilities",
    "hud": "Main HUD display engine (pygame rendering, events)",
    "obd_service": "OBD-II BLE adapter communication",
    "cobra_service": "Cobra RAD 700i radar detector BLE service",
    "battery_monitor": "HV battery health tracking and SQLite storage",
    "display_service": "PWM backlight brightness controller",
    "spotify_service": "Spotify Connect and API integration",
    "web_service": "Web server (settings, camera, terminal, APIs)",
    "wifi_service": "WiFi and USB tethering management",
    "voice_service": "Voice control (Vosk STT + wake word)",
    "brain": "Voice command processing (Gemini AI + local matching)",
    "intent": "Voice intent matching (keyword scoring system)",
    "touch_service": "Touchscreen input (evdev to gesture conversion)",
    "splash_service": "Boot splash screen with progress bar",
}

generated = 0
for mod, desc in services.items():
    filepath = os.path.join(SRC_DIR, f"{mod}.py")
    if not os.path.exists(filepath):
        print(f"  SKIP {mod} (file not found)")
        continue

    with open(os.path.join(API_DIR, f"{mod}.md"), "w") as f:
        f.write(f"# {mod}\n\n")
        f.write(f"*{desc}*\n\n")
        f.write(f"**Source:** [`src/{mod}.py`](https://github.com/grabercn/Car-HUD/blob/main/src/{mod}.py)\n\n")
        f.write(f"::: {mod}\n")
        f.write(f"    options:\n")
        f.write(f"      show_source: true\n")
        f.write(f"      members_order: source\n")
    generated += 1

# Widget files
widget_entries = []
if os.path.isdir(WIDGET_DIR):
    for fname in sorted(os.listdir(WIDGET_DIR)):
        if fname.startswith("w_") and fname.endswith(".py"):
            mod_name = fname[:-3]
            widget_entries.append(mod_name)

with open(os.path.join(API_DIR, "widgets.md"), "w") as f:
    f.write("# Widgets\n\n")
    f.write("All widget modules are auto-discovered from `src/widgets/w_*.py`.\n\n")
    f.write("## Widget Interface\n\n")
    f.write("Each widget module must have:\n\n")
    f.write("| Attribute | Type | Description |\n")
    f.write("|-----------|------|-------------|\n")
    f.write("| `name` | `str` | Display name |\n")
    f.write("| `priority` | `int` | Sort order (lower = first) |\n")
    f.write("| `view_time` | `int` | Seconds to display |\n")
    f.write("| `is_active(hud, music)` | `-> bool` | Has content? |\n")
    f.write("| `draw(hud, x, y, w, h, music)` | `-> bool` | Render widget |\n")
    f.write("| `urgency(hud, music)` | `-> int` | Priority boost (optional) |\n\n")
    f.write("## Built-in Widgets\n\n")

    for mod_name in widget_entries:
        filepath = os.path.join(WIDGET_DIR, f"{mod_name}.py")
        # Read the module docstring
        doc = ""
        try:
            with open(filepath) as src:
                first_line = src.readline().strip()
                if first_line.startswith('"""') or first_line.startswith("'''"):
                    doc = first_line.strip('"').strip("'")
        except Exception:
            pass

        f.write(f"### {mod_name}\n\n")
        if doc:
            f.write(f"*{doc}*\n\n")
        f.write(f"**Source:** [`src/widgets/{mod_name}.py`]")
        f.write(f"(https://github.com/grabercn/Car-HUD/blob/main/src/widgets/{mod_name}.py)\n\n")

print(f"Generated API docs for {generated} services + {len(widget_entries)} widgets")
