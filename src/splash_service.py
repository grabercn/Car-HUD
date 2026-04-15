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

BOOT_DATA_FILE = "/home/chrismslist/car-hud/.boot_times.json"
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
                if svc and "car-hud" not in svc and "car-hud" not in svc:
                    errors.append(svc)
    except Exception:
        pass
    return errors[:3]


def hud_is_active():
    try:
        r = subprocess.run(["systemctl", "is-active", "car-hud"],
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
                  "/home/chrismslist/car-hud/splash.png 2>/dev/null")
        time.sleep(25)
        return

    pygame.mouse.set_visible(False)

    # Play startup chime (Unique chime if just updated)
    UPDATE_FLAG = "/home/chrismslist/car-hud/.update_pending"
    VERSION_FILE = "/home/chrismslist/car-hud/.version"
    updated = False
    if os.path.exists(UPDATE_FLAG):
        updated = True
        subprocess.Popen(["aplay", "-D", "default", "-q",
                         "/home/chrismslist/car-hud/chime_update_ok.wav"],
                         stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        try: os.remove(UPDATE_FLAG)
        except: pass
    else:
        subprocess.Popen(["aplay", "-D", "default", "-q", "/home/chrismslist/car-hud/chime_startup.wav"],
                         stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    # Load splash image
    splash_path = "/home/chrismslist/car-hud/splash.png"
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

    # Scale fonts to display resolution
    scale = max(dw / 480, 1.0)
    font_xl = pygame.font.Font(f_bold, int(42 * scale))
    font_lg = pygame.font.Font(f_bold, int(32 * scale))
    font_md = pygame.font.Font(f_bold, int(24 * scale))
    font_sm = pygame.font.Font(f_reg, int(18 * scale))
    font_xs = pygame.font.Font(f_reg, int(14 * scale))
    font_bold_xs = pygame.font.Font(f_bold, int(14 * scale))

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

    # Bar geometry — scaled to display
    bar_w = int(dw * 0.65)
    bar_h = max(4, int(6 * scale))
    bar_x = (dw - bar_w) // 2
    bar_y = dh - int(50 * scale)

    def get_update_status():
        try:
            with open("/tmp/car-hud-update-status") as f:
                data = json.load(f)
                if time.time() - data.get("time", 0) < 30:
                    return data
        except Exception:
            pass
        return None

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

        # Check for live update status
        upd = get_update_status()
        
        if upd and upd.get("status") != "done":
            # UPDATE MODE: Remove loading bar, show prominent update text
            screen.fill((0, 5, 15)) # Dark blue-black
            
            # Pulsing update icon
            pulse = (math.sin(now * 4) + 1) / 2
            pygame.draw.circle(screen, (0, 150, 255), (dw // 2, dh // 2 - 60), 15 + 5 * pulse, 2)
            pygame.draw.circle(screen, (0, 150, 255), (dw // 2, dh // 2 - 60), 5)
            
            # Massive "UPDATING"
            ut = font_xl.render("UPDATING", True, (0, 200, 255))
            screen.blit(ut, ((dw - ut.get_width()) // 2, dh // 2 - 30))
            
            # Detail text (Truncated version/date)
            detail = upd.get("detail", "").upper()
            if len(detail) > 24: detail = detail[:21] + "..."
            dt_t = font_md.render(detail, True, (150, 200, 255))
            screen.blit(dt_t, ((dw - dt_t.get_width()) // 2, dh // 2 + 20))
            
            # Large Progress %
            prog = upd.get("progress", 0)
            pt = font_lg.render(f"{prog}%", True, (255, 255, 255))
            screen.blit(pt, ((dw - pt.get_width()) // 2, dh // 2 + 60))
            
            pygame.display.flip()
            clock.tick(30)
            continue

        # Standard Boot Mode — splash image + progress bar
        raw_t = min(elapsed / avg_boot, 1.0)

        # Smooth the progress bar
        display_pos += (raw_t - display_pos) * 0.1

        # Draw splash background
        screen.blit(splash_surf, (0, 0))

        # Update banner if just updated
        if updated:
            ver = ""
            try:
                with open(VERSION_FILE) as vf:
                    ver = vf.read().strip()[:8]
            except Exception:
                pass
            banner = f"UPDATED TO {ver}" if ver else "SYSTEM UPDATED"
            bt = font_sm.render(banner, True, (0, 200, 100))
            screen.blit(bt, ((dw - bt.get_width()) // 2, bar_y - 24))

        # Progress bar
        pygame.draw.rect(screen, (20, 20, 30), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
        fill_w = int(bar_w * display_pos)
        if fill_w > 0:
            pygame.draw.rect(screen, (0, 150, 255), (bar_x, bar_y, fill_w, bar_h), border_radius=2)

        pygame.display.flip()
        clock.tick(30)

    # Save this boot's splash duration
    actual = time.monotonic() - start_time
    save_boot_data(actual, boot_times)
    pygame.quit()


if __name__ == "__main__":
    main()
