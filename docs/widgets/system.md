# Widget System

Widgets are self-contained display modules that auto-rotate on the HUD.

## How It Works

1. Widget files (`w_*.py`) are auto-discovered from `src/widgets/`
2. Each frame, `get_active()` returns widgets sorted by effective priority
3. System page shows 2 stacked widgets with continuous scroll
4. OBD page shows 1 widget below the gauges
5. Widgets rotate based on `view_time` and `show_every` cooldowns

## Priority System

```
Effective Priority = base priority + urgency()
```

- **Lower number = shown first**
- `urgency()` returns negative to promote (e.g., -100 for new song)
- Pinned widgets get priority -999 (always first)
- `show_every` prevents low-value widgets from hogging rotation

## Cooldown System

Widgets with `show_every > 0` only appear once per cooldown period:

| Widget | `show_every` | Meaning |
|--------|-------------|---------|
| Weather | 180s | Show once every 3 minutes |
| System | 120s | Show once every 2 minutes |
| Camera | 90s | Show once every 90 seconds |
| Connectivity | 60s | Show once every minute |
| Music | 0 | Always in rotation |

Cooldowns are skipped:
- During first 60 seconds of boot
- When fewer than 3 widgets would remain
- When widget has negative urgency (event happening)

## Pinning

Pinned widgets always show first and don't rotate out.

- **Voice:** "Hey Honda, pin battery widget"
- **Touch:** Long-press (1.5s) on widget area
- **Web:** Settings page → Widgets → Pin button
- **API:** `POST /api/widget/pin` with `name=Battery&pinned=true`
