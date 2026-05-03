# Creating Widgets

Drop a `w_yourwidget.py` file in `src/widgets/` and it's auto-discovered on next restart.

## Template

```python
"""Short description of your widget."""

import json
import time
import pygame

# Required
name = "YourWidget"       # Display name (shown in settings)
priority = 50             # 0=highest, 99=lowest
view_time = 6             # Seconds before rotating away

# Optional
show_every = 0            # Cooldown: 0=always, 60=once per minute
requires_online = False   # Skip when no internet connection


def is_active(hud, music):
    """Return True if this widget has content to show right now.

    Called every 2 seconds (cached). Return False to hide the widget
    entirely from rotation.

    Args:
        hud: CarHUD instance
        music: Current music data dict (from /tmp/car-hud-music-data)
    """
    return True


def urgency(hud, music):
    """Return priority adjustment. Negative = promote.

    Called alongside is_active(). Use this to temporarily boost
    priority when something important happens.

    Returns:
        0 for normal, -100 to jump to front, -200 for critical alerts.
    """
    return 0


def draw(hud, x, y, w, h, music):
    """Render the widget within the given rectangle.

    Args:
        hud: CarHUD instance — access hud.surf, hud.t (theme), hud.font_*
        x, y: Top-left corner of available area
        w, h: Width and height available (adapts to screen layout)
        music: Current music data dict

    Returns:
        True if content was drawn, False to skip this frame.
    """
    s = hud.surf           # pygame.Surface to draw on
    t = hud.t              # theme dict (colors)

    # Panel background (standard widget look)
    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    # Your content
    title = hud.font_md.render("Hello World", True, t["text_bright"])
    s.blit(title, (x + 10, y + h // 2 - 8))

    return True
```

## Available Resources

### Fonts
Access via `hud.font_*`:

| Font | Size | Use For |
|------|------|---------|
| `font_xxl` | 54px | Speed, big numbers |
| `font_xl` | 38px | Clock time |
| `font_lg` | 28px | Temperature, headers |
| `font_md` | 17px | Primary text |
| `font_sm` | 14px | Secondary text |
| `font_xs` | 12px | Labels, details |
| `font_mono` | 11px | Status indicators |
| `font_cjk` | 14px | Japanese/Korean/Chinese |

### Theme Colors
Access via `hud.t["key"]`:

| Key | Purpose |
|-----|---------|
| `primary` | Accent color (gauges, active) |
| `primary_dim` | Dimmed accent |
| `bg` | Background |
| `panel` | Widget panel fill |
| `border` | Gauge tracks, borders |
| `text_bright` | Primary text |
| `text_med` | Secondary text |
| `text_dim` | Tertiary / labels |

### Reading Data

```python
# Read any service's data file
import json
try:
    with open("/tmp/car-hud-obd-data") as f:
        obd = json.load(f)
    speed = obd.get("data", {}).get("SPEED", 0)
except Exception:
    speed = 0
```

### Drawing Helpers

```python
# Glow text (cached, with shadow)
hud.draw_glow_text("Hello", hud.font_md, t["text_bright"], (x, y))

# Horizontal progress bar
hud.draw_hbar(x, y, width, height, percentage, color, "LABEL", "VALUE")

# Arc gauge
hud.draw_arc_gauge(cx, cy, radius, thickness, pct, color, ticks=True)
```

## Tips

- **Height adapts** — your widget may get 40px (compact on OBD page) or 120px (full on system page). Check `h` and adapt layout.
- **Cache heavy operations** — use module-level variables to cache file reads, subprocess calls, etc.
- **Don't block** — `draw()` is called 15+ times per second. Keep it fast.
- **Use `try/except`** — if your widget crashes, it takes down the whole HUD. Always catch exceptions.
