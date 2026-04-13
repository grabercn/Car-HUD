#!/usr/bin/env python3
"""Honda Accord Boot Splash
Animated progress bar calibrated to real boot time.
Each boot measures how long splash is displayed, saves rolling average.
Progress bar gets more accurate over time.
"""

import os
import sys
import time
import math
import json
import signal
import warnings
import subprocess

warnings.filterwarnings("ignore")
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
os.environ["SDL_FBDEV"] = "/dev/fb0"

import pygame
from pygame.locals import *
from PIL import Image

BOOT_DATA_FILE = "/home/chrismslist/northstar/.boot_times.json"
DEFAULT_BOOT_TIME = 22.0
MAX_HISTORY = 10


def load_boot_data():
    try:
        with open(BOOT_DATA_FILE) as f:
            data = json.load(f)
            return data.get("times", []), data.get("avg", DEFAULT_BOOT_TIME)
    except Exception:
        return [], DEFAULT_BOOT_TIME


def save_boot_data(elapsed, times):
    """Rolling window of last N boot splash durations."""
    times.append(round(elapsed, 2))
    times = times[-MAX_HISTORY:]
    avg = sum(times) / len(times)
    try:
        with open(BOOT_DATA_FILE, "w") as f:
            json.dump({"times": times, "avg": round(avg, 2),
                        "last": round(elapsed, 2), "boots": len(times)}, f)
    except Exception:
        pass


def check_critical_errors():
    errors = []
    try:
        result = subprocess.run(
            ["systemctl", "--failed", "--no-legend", "--plain"],
            capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                svc = line.split()[0] if line.split() else ""
                if svc and "northstar" not in svc and "car-hud" not in svc:
                    errors.append(svc)
    except Exception:
        pass
    return errors[:3]


def hud_is_active():
    try:
        r = subprocess.run(["systemctl", "is-active", "northstar-hud"],
                           capture_output=True, text=True, timeout=2)
        return r.stdout.strip() == "active"
    except Exception:
        return False


def ease_out_cubic(t):
    """Easing function — fast start, slow finish (feels premium)."""
    return 1 - (1 - t) ** 3


def main():
    # Retry display init — DRM may not be ready during early boot
    screen = None
    for attempt in range(20):
        try:
            pygame.init()
            info = pygame.display.Info()
            dw = info.current_w if info.current_w > 0 else 480
            dh = info.current_h if info.current_h > 0 else 320
            screen = pygame.display.set_mode((dw, dh),
                                             pygame.FULLSCREEN | pygame.NOFRAME)
            break
        except Exception:
            pygame.quit()
            time.sleep(1)

    if screen is None:
        os.system("fbi -d /dev/fb0 --noverbose -a -T 1 "
                  "/home/chrismslist/northstar/splash.png 2>/dev/null")
        time.sleep(25)
        return

    pygame.mouse.set_visible(False)

    # Load splash image
    splash_path = "/home/chrismslist/northstar/splash.png"
    try:
        pil_img = Image.open(splash_path).convert("RGB")
        pil_img = pil_img.resize((dw, dh), Image.LANCZOS)
        splash_surf = pygame.image.fromstring(pil_img.tobytes(), (dw, dh), "RGB")
    except Exception:
        splash_surf = pygame.Surface((dw, dh))
        splash_surf.fill((0, 0, 0))

    # Fonts
    lib_bold = "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
    lib_reg = "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    dv_reg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    dv_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    f_reg = lib_reg if os.path.exists(lib_reg) else dv_reg
    f_bold = lib_bold if os.path.exists(lib_bold) else dv_bold

    font_sm = pygame.font.Font(f_reg, max(10, dh // 32))
    font_xs = pygame.font.Font(f_reg, max(8, dh // 45))
    font_bold_xs = pygame.font.Font(f_bold, max(8, dh // 45))

    # Boot time calibration
    boot_times, avg_boot = load_boot_data()
    start_time = time.monotonic()
    clock = pygame.time.Clock()

    # Save boot data on any signal (SIGHUP from HUD taking over tty)
    def save_and_exit(signum, frame):
        actual = time.monotonic() - start_time
        save_boot_data(actual, boot_times)
        pygame.quit()
        sys.exit(0)

    signal.signal(signal.SIGHUP, save_and_exit)
    signal.signal(signal.SIGTERM, save_and_exit)

    # Bar geometry — wider, more substantial
    bar_w = int(dw * 0.60)
    bar_h = max(4, dh // 80)
    bar_x = (dw - bar_w) // 2
    bar_y = dh - int(dh * 0.10)

    # Glow bar (taller, drawn behind for bloom effect)
    glow_h = bar_h + max(10, dh // 25)
    glow_y = bar_y - (glow_h - bar_h) // 2

    # Pre-render EVERYTHING expensive once at startup
    r = bar_h // 2

    # Track (dark background bar)
    track_surf = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
    pygame.draw.rect(track_surf, (18, 20, 25, 200), (0, 0, bar_w, bar_h),
                     border_radius=r)

    # Full gradient fill bar (pre-rendered, we clip it each frame)
    full_fill = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
    for i in range(bar_w):
        t = i / max(bar_w - 1, 1)
        cg = int(55 + 95 * t)
        cb = int(95 + 85 * t)
        pygame.draw.line(full_fill, (0, cg, cb, 240), (i, 0), (i, bar_h - 1))
    # Apply rounded mask
    fill_mask = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
    pygame.draw.rect(fill_mask, (255, 255, 255, 255), (0, 0, bar_w, bar_h),
                     border_radius=r)
    full_fill.blit(fill_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

    # Leading edge bloom
    bloom_w = max(30, dw // 20)
    bloom_h = bar_h + max(24, dh // 12)
    bloom_surf = pygame.Surface((bloom_w, bloom_h), pygame.SRCALPHA)
    for bx in range(bloom_w):
        for by in range(bloom_h):
            dx = abs(bx - bloom_w // 2) / (bloom_w / 2)
            dy = abs(by - bloom_h // 2) / (bloom_h / 2)
            d = min(1.0, math.sqrt(dx**2 + dy**2))
            a = int(120 * (1 - d)**2)
            if a > 0:
                bloom_surf.set_at((bx, by), (0, 180, 255, a))

    # Background glow surface
    glow_base = pygame.Surface((bar_w + 20, glow_h), pygame.SRCALPHA)
    glow_base.fill((0, 70, 140, 50))

    # Pre-render comet tail
    tail_len = max(40, dw // 15)
    tail_surf = pygame.Surface((tail_len, bar_h + 6), pygame.SRCALPHA)
    for tx in range(tail_len):
        t = tx / tail_len
        a = int(140 * (t ** 2.5))
        cg = int(120 + 100 * t)
        cb = int(160 + 70 * t)
        pygame.draw.line(tail_surf, (0, cg, cb, a), (tx, 0), (tx, bar_h + 5))

    # Pre-render shimmer highlight
    shimmer_sw = max(20, dw // 30)
    shimmer_surf = pygame.Surface((shimmer_sw, bar_h), pygame.SRCALPHA)
    for sx in range(shimmer_sw):
        dist = abs(sx - shimmer_sw // 2) / (shimmer_sw / 2)
        a = int(30 * (1 - dist))
        for sy in range(bar_h):
            dy = abs(sy - bar_h // 2) / max(bar_h / 2, 1)
            shimmer_surf.set_at((sx, sy), (100, 180, 220, int(a * (1 - dy * 0.5))))

    errors_cache = []
    errors_check_time = 0
    hud_check_time = 0
    hud_ready = False
    final_anim_start = 0

    # Smooth animation state
    display_pos = 0.0      # what's actually shown (0-1), moves silkily
    last_frame_time = time.monotonic()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN and event.key == K_ESCAPE:
                running = False

        now = time.monotonic()
        dt = min(now - last_frame_time, 0.05)
        last_frame_time = now
        elapsed = now - start_time

        # Target moves continuously based on time
        raw_t = min(elapsed / avg_boot, 1.0)
        target = ease_out_cubic(raw_t) * 0.92

        # Check HUD ready every 2 seconds after 5s
        if elapsed > 5 and now - hud_check_time > 2:
            hud_check_time = now
            if hud_is_active():
                hud_ready = True
                if final_anim_start == 0:
                    final_anim_start = now

        # When HUD is ready, glide to 100%
        if hud_ready:
            fill_time = now - final_anim_start
            target = 1.0
            if fill_time > 1.5 and display_pos > 0.998:
                running = False

        # Smooth exponential interpolation — silky fluid motion
        # display_pos chases target, closing 92% of the gap each second
        # This creates beautiful acceleration/deceleration naturally
        smoothing = 1.0 - math.exp(-3.5 * dt)
        display_pos += (target - display_pos) * smoothing

        # Ensure it actually reaches the target
        if abs(display_pos - target) < 0.001:
            display_pos = target

        progress = max(0.0, min(display_pos, 1.0))

        # Phase labels
        phase_text = ""
        if progress < 0.3:
            phase_text = "System Initialization..."
        elif progress < 0.6:
            phase_text = "Loading Northstar Modules..."
        elif progress < 0.85:
            phase_text = "Connecting to OBD..."
        elif hud_ready:
            phase_text = "Starting Dashboard..."
        else:
            phase_text = "Finalizing Services..."

        if phase_text:
            pt = font_xs.render(phase_text, True, (60, 100, 130))
            screen.blit(pt, ((dw - pt.get_width()) // 2, bar_y - pt.get_height() - 6))

        # --- Draw ---
        screen.blit(splash_surf, (0, 0))

        # Background Track (dark background bar)
        screen.blit(track_surf, (bar_x, bar_y))
        
        # Center marker (subtle tick)
        pygame.draw.line(screen, (30, 35, 45), (dw // 2, bar_y), (dw // 2, bar_y + bar_h), 1)

        # Fill bar — clip from pre-rendered gradient
        if fill_w > r * 2:
            screen.blit(full_fill, (bar_x, bar_y),
                        area=pygame.Rect(0, 0, fill_w, bar_h))

            # Comet tail — pre-rendered fading trail behind leading edge
            edge_x = bar_x + fill_w
            screen.blit(tail_surf, (edge_x - tail_len, bar_y - 3))

            # Shimmer — pre-rendered highlight sweeps across filled area
            shimmer_pos = (elapsed * 0.3) % 1.0
            shimmer_x = bar_x + int(fill_w * shimmer_pos)
            screen.blit(shimmer_surf, (shimmer_x - shimmer_sw // 2, bar_y),
                        special_flags=pygame.BLEND_ADD)

            # Leading edge bloom
            screen.blit(bloom_surf, (edge_x - bloom_w // 2 - 2,
                                     bar_y - (bloom_h - bar_h) // 2))

            # Hot bright core at leading edge
            pygame.draw.line(screen, (0, 230, 255),
                             (edge_x - 2, bar_y - 2),
                             (edge_x - 2, bar_y + bar_h + 1), 3)
            pygame.draw.line(screen, (200, 245, 255),
                             (edge_x - 1, bar_y),
                             (edge_x - 1, bar_y + bar_h - 1), 1)

        # Check for errors periodically (not every frame)
        if elapsed > 8 and now - errors_check_time > 5:
            errors_check_time = now
            errors_cache = check_critical_errors()

        # Error display — Honda-style amber warning panel
        if errors_cache:
            row_h = font_xs.get_height() + 5
            panel_h = row_h * len(errors_cache) + font_bold_xs.get_height() + 16
            panel_w = int(dw * 0.5)
            panel_x = (dw - panel_w) // 2
            panel_y = bar_y + bar_h + max(8, dh // 50)

            # Panel background
            panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            panel.fill((8, 6, 4, 190))
            screen.blit(panel, (panel_x, panel_y))

            # Top accent — thin amber line with fade at edges
            for i in range(panel_w):
                edge = min(i, panel_w - 1 - i)
                fade = min(1.0, edge / (panel_w * 0.1))
                c = int(160 * fade)
                screen.set_at((panel_x + i, panel_y), (c, int(c * 0.7), 0))

            # "SYSTEM" header
            hdr = font_bold_xs.render("SYSTEM", True, (160, 115, 0))
            screen.blit(hdr, (panel_x + 10, panel_y + 5))

            # Error entries
            ey = panel_y + hdr.get_height() + 10
            for err in errors_cache:
                # Amber indicator dash
                dash_y = ey + font_xs.get_height() // 2
                pygame.draw.rect(screen, (110, 75, 0),
                                 (panel_x + 10, dash_y - 1, 3, 3))
                name = err.replace(".service", "").replace(".socket", "")
                et = font_xs.render(name, True, (130, 95, 30))
                screen.blit(et, (panel_x + 20, ey))
                ey += row_h

        pygame.display.flip()
        clock.tick(60)

    # Save this boot's splash duration
    actual = time.monotonic() - start_time
    save_boot_data(actual, boot_times)
    pygame.quit()


if __name__ == "__main__":
    main()
