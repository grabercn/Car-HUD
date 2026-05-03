#!/usr/bin/env python3
"""Auto-generate README.md files for the Car-HUD project.

Scans the codebase and produces:
  1. README.md           -- main project README with linked TOC
  2. src/README.md       -- all services with docstring descriptions
  3. src/widgets/README.md -- all widgets with stats table
  4. services/README.md  -- all systemd unit files with descriptions

Run from the repo root:
    python3 .github/scripts/generate_readmes.py
"""

import ast
import os
import re
import datetime

# ---------------------------------------------------------------------------
# Resolve repo root (two levels up from this script)
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))

SRC_DIR = os.path.join(REPO_ROOT, "src")
WIDGETS_DIR = os.path.join(SRC_DIR, "widgets")
SERVICES_DIR = os.path.join(REPO_ROOT, "services")
DOCS_URL = "https://grabercn.github.io/Car-HUD/"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_docstring(filepath):
    """Return the module-level docstring from a Python file, or ''."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=filepath)
        ds = ast.get_docstring(tree)
        return ds.strip() if ds else ""
    except Exception:
        return ""


def _first_line(docstring):
    """Return just the first sentence / line of a docstring."""
    if not docstring:
        return ""
    line = docstring.split("\n")[0].strip()
    # Strip trailing period for consistency, we add our own later
    return line.rstrip(".")


def _extract_widget_attrs(filepath):
    """Parse a widget file and return a dict of module-level attributes.

    Looks for: name, priority, view_time, show_every, requires_online.
    Uses AST so we never execute the file.
    """
    attrs = {}
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=filepath)
    except Exception:
        return attrs

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in (
                    "name", "priority", "view_time", "show_every", "requires_online",
                ):
                    val = node.value
                    if isinstance(val, ast.Constant):
                        attrs[target.id] = val.value
    return attrs


def _extract_service_description(filepath):
    """Return the Description= value from a systemd unit file's [Unit] section."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            in_unit = False
            for line in fh:
                line = line.strip()
                if line == "[Unit]":
                    in_unit = True
                    continue
                if line.startswith("[") and line.endswith("]"):
                    in_unit = False
                    continue
                if in_unit and line.startswith("Description="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def _file_size_str(filepath):
    """Human-readable file size."""
    try:
        size = os.path.getsize(filepath)
    except OSError:
        return "?"
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def _last_modified(filepath):
    """Return last-modified date as YYYY-MM-DD."""
    try:
        mtime = os.path.getmtime(filepath)
        return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except OSError:
        return "?"


def _sorted_py_files(directory):
    """Return sorted list of .py files in *directory* (no recursion)."""
    try:
        entries = os.listdir(directory)
    except OSError:
        return []
    return sorted(
        f for f in entries
        if f.endswith(".py") and not f.startswith("__")
    )


def _sorted_files(directory, ext=""):
    """Return sorted list of files in *directory*, optionally filtered by ext."""
    try:
        entries = os.listdir(directory)
    except OSError:
        return []
    if ext:
        return sorted(f for f in entries if f.endswith(ext))
    return sorted(entries)


# ---------------------------------------------------------------------------
# Gather data
# ---------------------------------------------------------------------------

def gather_widgets():
    """Return list of dicts with widget metadata, sorted by priority."""
    widgets = []
    for fname in _sorted_files(WIDGETS_DIR, ".py"):
        if fname.startswith("__"):
            continue
        fpath = os.path.join(WIDGETS_DIR, fname)
        attrs = _extract_widget_attrs(fpath)
        doc = _extract_docstring(fpath)
        widgets.append({
            "file": fname,
            "path": fpath,
            "name": attrs.get("name", fname.replace("w_", "").replace(".py", "").title()),
            "priority": attrs.get("priority", 50),
            "view_time": attrs.get("view_time", "?"),
            "show_every": attrs.get("show_every", 0),
            "requires_online": attrs.get("requires_online", False),
            "docstring": doc,
            "first_line": _first_line(doc),
            "size": _file_size_str(fpath),
            "modified": _last_modified(fpath),
        })
    widgets.sort(key=lambda w: w["priority"])
    return widgets


def gather_src_files():
    """Return list of dicts for every .py file in src/ (non-recursive)."""
    files = []
    for fname in _sorted_py_files(SRC_DIR):
        fpath = os.path.join(SRC_DIR, fname)
        doc = _extract_docstring(fpath)
        files.append({
            "file": fname,
            "path": fpath,
            "docstring": doc,
            "first_line": _first_line(doc),
            "size": _file_size_str(fpath),
            "modified": _last_modified(fpath),
        })
    return files


def gather_services():
    """Return list of dicts for every .service file in services/."""
    services = []
    for fname in _sorted_files(SERVICES_DIR, ".service"):
        fpath = os.path.join(SERVICES_DIR, fname)
        desc = _extract_service_description(fpath)
        services.append({
            "file": fname,
            "path": fpath,
            "description": desc,
            "size": _file_size_str(fpath),
            "modified": _last_modified(fpath),
        })
    return services


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def generate_main_readme(widgets, src_files, services):
    """Generate the root README.md content."""
    today = datetime.date.today().isoformat()

    # Build features list from widget names
    feature_lines = "\n".join(
        f"- **{w['name']}** -- {w['first_line']}" if w["first_line"]
        else f"- **{w['name']}**"
        for w in widgets
    )

    # Widget table
    widget_rows = "\n".join(
        f"| {w['name']} | {w['priority']} | {w['view_time']}s "
        f"| {w['show_every']}s | {'Yes' if w['requires_online'] else 'No'} |"
        for w in widgets
    )

    # Service table
    service_rows = "\n".join(
        f"| `{s['file']}` | {s['description']} |"
        for s in services
    )

    return f"""\
# Car-HUD

A Raspberry Pi-powered heads-up display for the 2014 Honda Accord Hybrid.
Voice-controlled, theme-aware, with live vehicle data, dashcam, and AI assistant.

![Last Commit](https://img.shields.io/github/last-commit/grabercn/Car-HUD)

> Auto-generated on {today} by
> [`.github/scripts/generate_readmes.py`](.github/scripts/generate_readmes.py)

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Hardware Requirements](#hardware-requirements)
- [Quick Start](#quick-start)
- [Widgets](#widgets)
- [Services](#services)
- [Sub-READMEs](#sub-readmes)
- [Documentation](#documentation)
- [Contributing](#contributing)

---

## Features

{feature_lines}

---

## Architecture

```
 Phone (BT)         Cobra RAD 700i (BLE)        Vgate iCar Pro (BLE)
      |                       |                          |
      v                       v                          v
 music_service          cobra_service               obd_service
 spotify_service             |                          |
      |                      v                          v
      |               /tmp/car-hud-cobra     /tmp/car-hud-obd-data
      |                      |                          |
      v                      v                          v
 /tmp/car-hud-music   +-----------+   /tmp/car-hud-battery-data
                      |           |          ^
                      |  hud.py   |<---------+---- battery_monitor
                      |  (pygame) |
                      |           |-----> pages/  -----> widgets/
                      +-----------+
                           |
               +-----------+-----------+
               |           |           |
               v           v           v
          display     web_service   voice_service
         (TFT LCD)   (MJPEG/HTTP)  (Vosk + Gemini)
                                        |
                                        v
                                     brain.py
                                   (NLU + TTS)
```

---

## Hardware Requirements

| Component | Model |
|-----------|-------|
| Compute | Raspberry Pi 3B+ (1 GB RAM) |
| Display | 3.5" TFT 480x320 (1000 nits) |
| OBD-II | Vgate iCar Pro 2S (BT 5.2 LE) |
| Radar | Cobra RAD 700i (BLE + GPS) |
| Camera | Logitech C925e (dashcam + mic) |
| Audio | AB13X USB sound card (lapel mic + speaker) |
| Storage | 64 GB SanDisk Ultra microSD |

---

## Quick Start

```bash
# Clone to Pi
git clone https://github.com/grabercn/Car-HUD.git
cd Car-HUD

# Install everything (services, deps, permissions)
sudo bash scripts/install.sh

# Reboot to start all services
sudo reboot
```

---

## Widgets

| Widget | Priority | View Time | Show Every | Online? |
|--------|----------|-----------|------------|---------|
{widget_rows}

> Lower priority = shown first. See [`src/widgets/README.md`](src/widgets/README.md) for full details.

---

## Services

| Unit File | Description |
|-----------|-------------|
{service_rows}

> See [`services/README.md`](services/README.md) for full details.

---

## Sub-READMEs

| Path | Contents |
|------|----------|
| [`src/README.md`](src/README.md) | All source modules with docstring descriptions |
| [`src/widgets/README.md`](src/widgets/README.md) | Widget files with priority, timing, and stats |
| [`services/README.md`](services/README.md) | Systemd unit files with descriptions |

---

## Documentation

Full project docs are published at **{DOCS_URL}**

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines on code style, testing,
and pull-request workflow.
"""


def generate_src_readme(src_files):
    """Generate src/README.md."""
    today = datetime.date.today().isoformat()

    rows = []
    for f in src_files:
        desc = f["first_line"] if f["first_line"] else "--"
        rows.append(
            f"| [`{f['file']}`]({f['file']}) | {desc} | {f['size']} | {f['modified']} |"
        )
    file_table = "\n".join(rows)

    # Also list subdirectories
    subdirs = []
    for entry in sorted(os.listdir(SRC_DIR)):
        full = os.path.join(SRC_DIR, entry)
        if os.path.isdir(full) and not entry.startswith("__"):
            subdirs.append(entry)

    subdir_lines = "\n".join(f"- [`{d}/`]({d}/)" for d in subdirs)

    return f"""\
# src/

All Python source modules for the Car-HUD system.

[Back to main README](../README.md)

> Auto-generated on {today} by
> [`../.github/scripts/generate_readmes.py`](../.github/scripts/generate_readmes.py)

---

## Modules

| File | Description | Size | Modified |
|------|-------------|------|----------|
{file_table}

---

## Subdirectories

{subdir_lines}

See each subdirectory's README for details.
"""


def generate_widgets_readme(widgets):
    """Generate src/widgets/README.md."""
    today = datetime.date.today().isoformat()

    rows = []
    for w in widgets:
        online = "Yes" if w["requires_online"] else "No"
        desc = w["first_line"] if w["first_line"] else "--"
        rows.append(
            f"| [`{w['file']}`]({w['file']}) | {w['name']} | {desc} "
            f"| {w['priority']} | {w['view_time']}s | {w['show_every']}s "
            f"| {online} | {w['size']} | {w['modified']} |"
        )
    widget_table = "\n".join(rows)

    total = len(widgets)
    online_count = sum(1 for w in widgets if w["requires_online"])
    avg_priority = (
        sum(w["priority"] for w in widgets) / total if total else 0
    )

    return f"""\
# src/widgets/

Widget modules auto-discovered by the HUD at runtime.
Each file (`w_*.py`) exports `name`, `priority`, `draw()`, and `is_active()`.

[Back to main README](../../README.md) | [Back to src/](../README.md)

> Auto-generated on {today} by
> [`../../.github/scripts/generate_readmes.py`](../../.github/scripts/generate_readmes.py)

---

## Stats

- **Total widgets:** {total}
- **Require internet:** {online_count}
- **Average priority:** {avg_priority:.0f}

---

## Widget Reference

| File | Name | Description | Priority | View Time | Show Every | Online? | Size | Modified |
|------|------|-------------|----------|-----------|------------|---------|------|----------|
{widget_table}

---

## How Widgets Work

1. The HUD scans `src/widgets/w_*.py` on startup.
2. Each widget declares a `priority` (lower = shown first).
3. `is_active(hud, music)` determines if the widget has content right now.
4. Active widgets are sorted by effective priority and drawn into the
   scrolling carousel on the current page.
5. `show_every` adds a cooldown (seconds) so low-value widgets don't dominate.
6. `requires_online = True` hides the widget when there is no internet.
"""


def generate_services_readme(services):
    """Generate services/README.md."""
    today = datetime.date.today().isoformat()

    rows = []
    for s in services:
        desc = s["description"] if s["description"] else "--"
        rows.append(
            f"| [`{s['file']}`]({s['file']}) | {desc} | {s['size']} | {s['modified']} |"
        )
    service_table = "\n".join(rows)

    return f"""\
# services/

Systemd unit files that run Car-HUD components as background services on the Pi.

[Back to main README](../README.md)

> Auto-generated on {today} by
> [`../.github/scripts/generate_readmes.py`](../.github/scripts/generate_readmes.py)

---

## Unit Files

| File | Description | Size | Modified |
|------|-------------|------|----------|
{service_table}

---

## Common Commands

```bash
# Check status of all Car-HUD services
systemctl list-units 'car-hud*'

# View logs for a specific service
journalctl -u car-hud-obd.service -f

# Restart a service
sudo systemctl restart car-hud.service

# Enable/disable a service
sudo systemctl enable car-hud-dashcam.service
sudo systemctl disable car-hud-dashcam.service
```
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    widgets = gather_widgets()
    src_files = gather_src_files()
    services = gather_services()

    outputs = {
        os.path.join(REPO_ROOT, "README.md"): generate_main_readme(
            widgets, src_files, services
        ),
        os.path.join(SRC_DIR, "README.md"): generate_src_readme(src_files),
        os.path.join(WIDGETS_DIR, "README.md"): generate_widgets_readme(widgets),
        os.path.join(SERVICES_DIR, "README.md"): generate_services_readme(services),
    }

    for path, content in outputs.items():
        rel = os.path.relpath(path, REPO_ROOT)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        print(f"  wrote {rel}")

    print(f"\nDone -- {len(outputs)} README files generated.")


if __name__ == "__main__":
    main()
