#!/usr/bin/env python3
"""Honda Accord HUD - Visual Dashboard
3.5" TFT (480x320). Full-screen visual gauges.
Theme system with voice commands: "Hey Honda change color to blue/red/green/amber"
Auto day/night mode based on clock (+ light sensor when available).
"""

import os
import sys
import time
import json
import math
import datetime
import glob
import subprocess

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
# Try kmsdrm (real display), fall back to dummy (headless for screenshot server)
os.environ["SDL_FBDEV"] = "/dev/fb0"
_headless = False

import pygame
from pygame.locals import *

# ── Theme Presets (2014 Honda Accord Hybrid style) ──
# Themes modeled on 2014 Honda Accord Hybrid iMID color options
# Each theme completely transforms the entire display
THEMES = {
    "blue": {  # Default Honda Accord blue
        "primary":    (0, 180, 255),     # Bright cyan-blue gauges
        "primary_dim":(0, 70, 120),      # Dim gauge backgrounds
        "accent":     (0, 130, 220),     # Secondary elements
        "bg":         (2, 4, 12),        # Deep blue-black
        "panel":      (5, 10, 25),
        "border":     (10, 30, 60),
        "border_lite":(8, 22, 45),
        "text_bright":(200, 230, 255),   # Blue-white text
        "text_med":   (80, 130, 190),
        "text_dim":   (30, 55, 90),
    },
    "red": {  # Honda Sport red
        "primary":    (255, 30, 30),     # Vivid red gauges
        "primary_dim":(120, 10, 10),     # Dark red backgrounds
        "accent":     (220, 20, 20),
        "bg":         (12, 2, 2),        # Deep red-black
        "panel":      (25, 5, 5),
        "border":     (60, 12, 12),
        "border_lite":(45, 10, 10),
        "text_bright":(255, 200, 190),   # Warm white
        "text_med":   (200, 100, 90),
        "text_dim":   (100, 40, 35),
    },
    "green": {  # Honda Eco green
        "primary":    (0, 230, 100),     # Vivid green gauges
        "primary_dim":(0, 90, 40),       # Dark green backgrounds
        "accent":     (0, 200, 80),
        "bg":         (2, 10, 4),        # Deep green-black
        "panel":      (4, 22, 10),
        "border":     (10, 50, 20),
        "border_lite":(8, 38, 16),
        "text_bright":(200, 255, 210),   # Green-white
        "text_med":   (80, 180, 100),
        "text_dim":   (30, 80, 40),
    },
    "amber": {  # Classic amber instruments
        "primary":    (255, 180, 0),     # Bright amber gauges
        "primary_dim":(100, 65, 0),      # Dark amber backgrounds
        "accent":     (230, 150, 0),
        "bg":         (10, 7, 2),        # Deep amber-black
        "panel":      (22, 16, 5),
        "border":     (55, 40, 10),
        "border_lite":(40, 30, 8),
        "text_bright":(255, 235, 180),   # Warm amber-white
        "text_med":   (190, 140, 60),
        "text_dim":   (90, 65, 25),
    },
    "day": {  # High-contrast daylight mode
        "primary":    (0, 0, 0),         # Black gauges on white
        "primary_dim":(160, 160, 160),
        "accent":     (40, 40, 40),
        "bg":         (240, 240, 235),   # Bright white
        "panel":      (225, 225, 220),
        "border":     (180, 180, 175),
        "border_lite":(200, 200, 195),
        "text_bright":(0, 0, 0),         # Pure black text
        "text_med":   (50, 50, 50),
        "text_dim":   (120, 120, 120),
    },
    "night": {  # Ultra-dim night driving
        "primary":    (0, 120, 160),     # Very dim blue
        "primary_dim":(0, 30, 45),
        "accent":     (0, 80, 110),
        "bg":         (1, 2, 4),         # Nearly black
        "panel":      (3, 5, 10),
        "border":     (6, 14, 25),
        "border_lite":(5, 10, 18),
        "text_bright":(100, 140, 170),   # Dim blue-white
        "text_med":   (50, 80, 105),
        "text_dim":   (20, 35, 50),
    },
}

# Fixed status colors (same across all themes)
GREEN  = (0, 180, 85)
AMBER  = (220, 160, 0)
RED    = (220, 45, 45)

THEME_FILE = "/home/chrismslist/northstar/.theme"
HONDA_LOGO_PATH = "/home/chrismslist/northstar/honda_logo.png"


def keyboard_connected():
    for path in glob.glob("/sys/class/input/event*/device/name"):
        try:
            with open(path) as f:
                if "keyboard" in f.read().strip().lower():
                    return True
        except Exception:
            pass
    return False


def signal_hud_file(action, target):
    """Write a command to the voice signal file (for keyboard shortcuts)."""
    try:
        with open("/tmp/car-hud-voice-signal", "w") as f:
            json.dump({"action": action, "target": target, "time": time.time()}, f)
    except Exception:
        pass


def get_auto_theme():
    """Determine day/night based on clock. 7AM-7PM = day, else night."""
    hour = datetime.datetime.now().hour
    # TODO: integrate BH1750 lux sensor for real ambient detection
    if 7 <= hour < 19:
        return "day"
    return "night"


class CarHUD:
    TARGET_W = 480
    TARGET_H = 320

    def __init__(self):
        global _headless

        # Try real display first, fall back to headless
        for driver in ["kmsdrm", "dummy"]:
            os.environ["SDL_VIDEODRIVER"] = driver
            try:
                pygame.init()
                info = pygame.display.Info()
                self.display_w = info.current_w if info.current_w > 0 else 480
                self.display_h = info.current_h if info.current_h > 0 else 320
                self.screen = pygame.display.set_mode(
                    (self.display_w, self.display_h), pygame.FULLSCREEN | pygame.NOFRAME)
                _headless = (driver == "dummy")
                break
            except Exception:
                pygame.quit()
                continue

        if _headless:
            self.display_w = self.TARGET_W
            self.display_h = self.TARGET_H
            self.screen = pygame.display.set_mode((self.display_w, self.display_h))

        self.width = self.TARGET_W
        self.height = self.TARGET_H
        self.surf = pygame.Surface((self.width, self.height))
        pygame.mouse.set_visible(False)

        lib_bold = "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        lib_reg = "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
        dv_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        dv_reg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        dv_mono = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
        bold = lib_bold if os.path.exists(lib_bold) else dv_bold
        reg = lib_reg if os.path.exists(lib_reg) else dv_reg

        # Bigger fonts for 3.5" readability
        self.font_xxl  = pygame.font.Font(bold, 52)
        self.font_xl   = pygame.font.Font(bold, 36)
        self.font_lg   = pygame.font.Font(bold, 26)
        self.font_md   = pygame.font.Font(reg, 16)
        self.font_sm   = pygame.font.Font(reg, 13)
        self.font_xs   = pygame.font.Font(reg, 11)
        self.font_mono = pygame.font.Font(dv_mono, 10)

        self.clock_t = pygame.time.Clock()
        self.running = True
        self.show_terminal = False
        self.has_keyboard = keyboard_connected()
        self.kb_check_timer = 0
        self.mic1_level = 0.0  # USB mic (near user)
        self.mic2_level = 0.0  # Webcam mic (on dash)
        self.voice_status = ""
        self.terminal_lines = ["Car-HUD Terminal [ESC close]", "$ "]
        self.show_camera = False
        self.camera_frame = None
        self.camera_cap = None

        # Theme
        self.auto_theme = True
        self.theme_name = self._load_theme()
        self.t = THEMES[self.theme_name]

        # Honda logo for idle screen — tinted to theme color
        self.honda_logo_pil = None
        self.honda_logo = None
        self._logo_theme = None
        try:
            from PIL import Image as PILImage
            self.honda_logo_pil = PILImage.open(HONDA_LOGO_PATH).convert("RGBA")
        except Exception:
            pass
        self._build_tinted_logo()

    def _build_tinted_logo(self):
        """Tint the Honda logo to match current theme color."""
        if not self.honda_logo_pil or self._logo_theme == self.theme_name:
            return
        self._logo_theme = self.theme_name
        try:
            from PIL import Image as PILImage, ImageEnhance
            pil = self.honda_logo_pil.copy()
            # Scale to fit
            aspect = pil.width / pil.height
            lh = 60
            lw = int(lh * aspect)
            pil = pil.resize((lw, lh), PILImage.LANCZOS)

            # Tint: convert to grayscale then colorize with theme primary
            r_tint, g_tint, b_tint = self.t["primary"]
            pixels = pil.load()
            for py in range(pil.height):
                for px in range(pil.width):
                    r, g, b, a = pixels[px, py]
                    if a < 10:
                        continue
                    # Get luminance of original pixel
                    lum = (r * 0.299 + g * 0.587 + b * 0.114) / 255.0
                    # Apply theme tint based on luminance
                    nr = int(r_tint * lum)
                    ng = int(g_tint * lum)
                    nb = int(b_tint * lum)
                    pixels[px, py] = (nr, ng, nb, a)

            raw = pil.tobytes()
            self.honda_logo = pygame.image.fromstring(raw, (lw, lh), "RGBA")
        except Exception:
            pass

    def _load_theme(self):
        try:
            with open(THEME_FILE) as f:
                data = json.load(f)
                name = data.get("theme", "blue")
                self.auto_theme = data.get("auto", True)
                if name in THEMES:
                    return name
        except Exception:
            pass
        return "blue"

    def _save_theme(self, name):
        try:
            with open(THEME_FILE, "w") as f:
                json.dump({"theme": name, "auto": self.auto_theme}, f)
        except Exception:
            pass

    def set_theme(self, name):
        if name == "auto":
            self.auto_theme = True
            name = get_auto_theme()
        elif name in THEMES:
            self.auto_theme = False
        else:
            return
        self.theme_name = name
        self.t = THEMES[name]
        self._save_theme(name)
        self._build_tinted_logo()

    def get_obd_data(self):
        try:
            with open("/tmp/car-hud-obd-data") as f:
                data = json.load(f)
                if time.time() - data.get("timestamp", 0) < 10:
                    return data
        except Exception:
            pass
        return {"connected": False, "status": "offline", "data": {},
                "warnings": [], "dtcs": []}

    def get_music_data(self):
        try:
            with open("/tmp/car-hud-music-data") as f:
                data = json.load(f)
                if time.time() - data.get("timestamp", 0) < 30:
                    return data
        except Exception:
            pass
        return {"playing": False}

    def get_system_stats(self):
        stats = {}
        try:
            with open("/proc/uptime") as f:
                stats["uptime"] = float(f.read().split()[0])
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                stats["cpu_temp"] = int(f.read().strip()) / 1000.0
            with open("/proc/loadavg") as f:
                stats["load"] = f.read().split()[0]
            with open("/proc/meminfo") as f:
                lines = f.readlines()
                total = int(lines[0].split()[1])
                avail = int(lines[2].split()[1])
                stats["mem_used_pct"] = int((1 - avail / total) * 100)
        except Exception:
            stats.setdefault("cpu_temp", 0)
            stats.setdefault("mem_used_pct", 0)
            stats.setdefault("uptime", 0)
        return stats

    def _read_voice_signal(self):
        try:
            with open("/tmp/car-hud-voice-signal") as f:
                data = json.load(f)
                if time.time() - data.get("time", 0) < 5:
                    self.voice_status = data.get("target", "")
                    action = data.get("action", "")
                    target = data.get("target", "")
                    # Theme change — check action field (from brain/Gemini)
                    if action == "theme" and target in THEMES:
                        self.set_theme(target)
                    elif action == "theme" and target == "auto":
                        self.set_theme("auto")
                else:
                    self.voice_status = ""
        except Exception:
            self.voice_status = ""
        try:
            with open("/tmp/car-hud-mic-level") as f:
                parts = f.read().strip().split(",")
                self.mic1_level = float(parts[0])
                self.mic2_level = float(parts[1]) if len(parts) > 1 else 0.0
        except Exception:
            pass

    def draw_arc_gauge(self, cx, cy, radius, thickness, pct, color, bg_color=None):
        s = self.surf
        bg = bg_color or self.t["border"]
        start_angle = math.pi
        end_angle = 0
        steps = 50

        for i in range(steps):
            t = i / steps
            a1 = start_angle + (end_angle - start_angle) * t
            a2 = start_angle + (end_angle - start_angle) * (t + 1/steps)
            x1 = cx + radius * math.cos(a1)
            y1 = cy - radius * math.sin(a1)
            x2 = cx + radius * math.cos(a2)
            y2 = cy - radius * math.sin(a2)
            pygame.draw.line(s, bg, (int(x1), int(y1)), (int(x2), int(y2)), thickness)

        fill_steps = max(1, int(steps * min(pct, 1.0)))
        for i in range(fill_steps):
            t = i / steps
            t2 = (i + 1) / steps
            if pct > 0.75 and t > 0.75:
                c = RED
            elif pct > 0.5 and t > 0.5:
                c = AMBER
            else:
                c = color
            a1 = start_angle + (end_angle - start_angle) * t
            a2 = start_angle + (end_angle - start_angle) * t2
            x1 = cx + radius * math.cos(a1)
            y1 = cy - radius * math.sin(a1)
            x2 = cx + radius * math.cos(a2)
            y2 = cy - radius * math.sin(a2)
            pygame.draw.line(s, c, (int(x1), int(y1)), (int(x2), int(y2)), thickness)

    def draw_hbar(self, x, y, w, h, pct, color, label=None, value=None):
        s = self.surf
        pygame.draw.rect(s, self.t["border"], (x, y, w, h), border_radius=2)
        fw = max(0, min(int(w * pct), w))
        if fw > 1:
            pygame.draw.rect(s, color, (x, y, fw, h), border_radius=2)
        if label:
            lt = self.font_xs.render(label, True, self.t["text_dim"])
            s.blit(lt, (x, y - lt.get_height() - 1))
        if value:
            vt = self.font_xs.render(value, True, color)
            s.blit(vt, (x + w - vt.get_width(), y - vt.get_height() - 1))

    def draw_vehicle_page(self, obd, music):
        W, H = self.width, self.height
        s = self.surf
        t = self.t
        vd = obd.get("data", {})

        pygame.draw.line(s, t["primary_dim"], (0, 0), (W, 0), 1)

        # Warnings banner
        warn_h = 0
        if obd.get("warnings"):
            for wt in obd["warnings"][:2]:
                txt = self.font_sm.render(wt, True, RED)
                pygame.draw.rect(s, (25, 5, 5), (0, warn_h, W, txt.get_height() + 6))
                s.blit(txt, ((W - txt.get_width()) // 2, warn_h + 3))
                warn_h += txt.get_height() + 6

        # Speed gauge (BIG left)
        speed = vd.get("SPEED", 0)
        speed_pct = min(speed / 140.0, 1.0)
        gcx = W // 4 + 5
        gcy = 100 + warn_h
        gr = 75
        self.draw_arc_gauge(gcx, gcy, gr, 8, speed_pct, t["primary"])
        self.draw_arc_gauge(gcx, gcy, gr - 12, 3, speed_pct, t["primary_dim"])

        sp = self.font_xxl.render(f"{int(speed)}", True, t["primary"])
        s.blit(sp, (gcx - sp.get_width() // 2, gcy - sp.get_height() + 4))
        mph = self.font_xs.render("MPH", True, t["text_dim"])
        s.blit(mph, (gcx - mph.get_width() // 2, gcy + 12))

        # RPM gauge (right)
        rpm = vd.get("RPM", 0)
        rpm_pct = min(rpm / 7000.0, 1.0)
        rc = t["primary"] if rpm < 4000 else AMBER if rpm < 6000 else RED
        rcx = W * 3 // 4 - 5
        rcy = gcy
        self.draw_arc_gauge(rcx, rcy, gr, 8, rpm_pct, rc)
        self.draw_arc_gauge(rcx, rcy, gr - 12, 3, rpm_pct, t["primary_dim"])

        rp = self.font_lg.render(f"{int(rpm)}", True, t["text_bright"])
        s.blit(rp, (rcx - rp.get_width() // 2, rcy - rp.get_height() + 4))
        rl = self.font_xs.render("RPM", True, t["text_dim"])
        s.blit(rl, (rcx - rl.get_width() // 2, rcy + 12))

        # Gauge bars
        by = gcy + 28
        bh = 8
        pad = 6
        hw = W // 2 - pad * 2 - 2

        # Fuel + Hybrid Battery (most important for hybrid)
        fuel = vd.get("FUEL_LEVEL", 0)
        fc = GREEN if fuel > 20 else AMBER if fuel > 10 else RED
        self.draw_hbar(pad, by + 16, hw, bh, fuel / 100.0, fc, "FUEL", f"{fuel:.0f}%")

        hv_bat = vd.get("HYBRID_BATTERY_REMAINING", 0)
        bc = GREEN if hv_bat > 30 else AMBER if hv_bat > 15 else RED
        self.draw_hbar(W//2 + 2 + pad, by + 16, hw, bh,
                       hv_bat / 100.0, bc, "HV BATT", f"{hv_bat:.0f}%")

        # Coolant + Load
        cool = vd.get("COOLANT_TEMP", 0)
        cc = t["primary"] if cool < 100 else AMBER if cool < 110 else RED
        self.draw_hbar(pad, by + 42, hw, bh, min(cool/130, 1), cc, "COOLANT", f"{cool:.0f}C")

        load = vd.get("ENGINE_LOAD", 0)
        lc = t["primary"] if load < 70 else AMBER if load < 90 else RED
        self.draw_hbar(W//2 + 2 + pad, by + 42, hw, bh, load/100, lc, "LOAD", f"{load:.0f}%")

        # Lower: music or time
        ly = by + 60
        pygame.draw.line(s, t["border_lite"], (4, ly), (W - 4, ly))
        self.draw_lower_section(ly + 3, music, vd)

    def draw_system_page(self, stats, music):
        W, H = self.width, self.height
        s = self.surf
        t = self.t
        now = datetime.datetime.now()

        pygame.draw.line(s, t["primary_dim"], (0, 0), (W, 0), 1)

        # Time (bigger)
        time_str = now.strftime("%I:%M")
        ampm = now.strftime("%p")
        ts = self.font_xl.render(time_str, True, t["primary"])
        ap = self.font_md.render(ampm, True, t["accent"])
        tx = (W - ts.get_width() - ap.get_width() - 6) // 2
        s.blit(ts, (tx, 8))
        s.blit(ap, (tx + ts.get_width() + 6,
                    8 + ts.get_height() - ap.get_height() - 2))

        ds = self.font_sm.render(now.strftime("%A, %B %d"), True, t["text_med"])
        s.blit(ds, ((W - ds.get_width()) // 2, 8 + ts.get_height() + 2))

        dy = 8 + ts.get_height() + ds.get_height() + 8
        pygame.draw.line(s, t["primary_dim"], (4, dy), (W - 4, dy))

        # System bars
        ry = dy + 8
        hw = W // 2 - 14
        pad = 6

        temp = stats.get("cpu_temp", 0)
        tc = t["primary"] if temp < 60 else AMBER if temp < 75 else RED
        self.draw_hbar(pad, ry + 16, hw, 7, temp/85, tc, "CPU", f"{temp:.0f}C")

        mp = stats.get("mem_used_pct", 0)
        mc = t["primary"] if mp < 70 else AMBER if mp < 85 else RED
        self.draw_hbar(W//2 + pad, ry + 16, hw, 7, mp/100, mc, "MEM", f"{mp}%")

        # Lower: Honda logo or music
        ly = ry + 40
        pygame.draw.line(s, t["border_lite"], (4, ly), (W - 4, ly))

        if music.get("playing"):
            self.draw_lower_section(ly + 3, music, None)
        elif self.honda_logo:
            # Center Honda H badge exactly between divider and status strip
            strip_y = H - 26
            avail_h = strip_y - ly - 4
            target_h = min(55, avail_h - 4)  # bigger, with margin
            logo = self.honda_logo
            scale = target_h / logo.get_height()
            logo = pygame.transform.smoothscale(
                logo, (int(logo.get_width() * scale), target_h))
            lx = (W - logo.get_width()) // 2
            logo_y = ly + (avail_h - target_h) // 2 + 2
            s.blit(logo, (lx, logo_y))
        else:
            ht = self.font_sm.render("Honda Accord", True, t["primary_dim"])
            s.blit(ht, ((W - ht.get_width()) // 2, ly + 20))

    def draw_lower_section(self, y, music, vd):
        W = self.width
        s = self.surf
        t = self.t
        now = datetime.datetime.now()

        if music.get("playing"):
            track = music.get("track", "Unknown")
            artist = music.get("artist", "Unknown")
            max_c = W // 8
            if len(track) > max_c:
                track = track[:max_c-2] + ".."
            if len(artist) > max_c:
                artist = artist[:max_c-2] + ".."

            # Music note
            pygame.draw.circle(s, t["primary"], (12, y + 14), 4)
            pygame.draw.line(s, t["primary"], (16, y + 14), (16, y + 4), 2)

            tt = self.font_sm.render(track, True, t["text_bright"])
            at = self.font_xs.render(artist, True, t["text_med"])
            s.blit(tt, (24, y + 2))
            s.blit(at, (24, y + 3 + tt.get_height()))

            prog = music.get("progress", 0)
            dur = music.get("duration", 0)
            if dur > 0:
                pbar_y = y + 4 + tt.get_height() + at.get_height() + 3
                pygame.draw.rect(s, t["border"], (8, pbar_y, W-16, 3), border_radius=1)
                fw = int((W-16) * min(prog/dur, 1))
                if fw > 0:
                    pygame.draw.rect(s, t["primary"], (8, pbar_y, fw, 3), border_radius=1)
        elif vd:
            ts = self.font_md.render(now.strftime("%I:%M %p"), True, t["text_med"])
            s.blit(ts, (8, y + 4))
            amb = vd.get("AMBIANT_AIR_TEMP")
            if amb:
                at = self.font_md.render(f"{amb:.0f}C", True, t["text_dim"])
                s.blit(at, (W - at.get_width() - 8, y + 4))

    def draw_status_strip(self, obd):
        W, H = self.width, self.height
        s = self.surf
        t = self.t
        sy = H - 26

        pygame.draw.line(s, t["border_lite"], (0, sy), (W, sy))

        # Audio detection — check for USB audio device (input+output)
        ac = t["text_dim"]
        has_in = False
        has_out = False
        for i in range(5):
            p = f"/proc/asound/card{i}/id"
            if os.path.exists(p):
                try:
                    with open(p) as f:
                        card_id = f.read().strip()
                        if card_id in ("Audio", "Card"):  # AB13X or Razer
                            has_in = True
                            has_out = True
                        elif card_id == "Headphones":
                            has_out = True
                except Exception:
                    pass
        if has_in and has_out:
            ac = t["primary"]  # theme color when fully active
        elif has_in or has_out:
            ac = AMBER

        # OBD
        if obd["connected"] and obd.get("data"):
            oc = t["primary"]
        elif obd.get("timestamp", 0) > 0 and time.time() - obd["timestamp"] < 30:
            oc = AMBER
        else:
            oc = t["text_dim"]

        # Music
        music = self.get_music_data()
        mc = t["primary"] if music.get("playing") else AMBER if music.get("paired") else t["text_dim"]

        # Network
        nc = t["text_dim"]
        try:
            with open("/tmp/car-hud-wifi-data") as f:
                wd = json.load(f)
                ws = wd.get("state", "")
                if ws == "connected":
                    nc = t["primary"]
                elif ws == "connecting":
                    nc = AMBER
                elif ws == "failed":
                    nc = RED
        except Exception:
            pass

        # AUD: combine hardware + voice service status
        # Green = hardware + service running, Amber = hardware only (service starting), Dim = nothing
        voice_running = False
        try:
            with open("/tmp/car-hud-mic-level") as f:
                lvl_age = time.time() - os.path.getmtime("/tmp/car-hud-mic-level")
                voice_running = lvl_age < 15  # generous — Gemini calls take a few seconds
        except Exception:
            pass

        if has_in and voice_running:
            ac = t["primary"]  # fully active
        elif has_in:
            ac = AMBER  # hardware present but service not ready
        elif has_out:
            ac = AMBER

        # CAM status — read dashcam data
        cam_c = t["text_dim"]
        try:
            with open("/tmp/car-hud-dashcam-data") as f:
                cd = json.load(f)
                if cd.get("recording") and time.time() - cd.get("timestamp", 0) < 30:
                    cam_c = t["primary"]
                elif time.time() - cd.get("timestamp", 0) < 30:
                    cam_c = AMBER
        except Exception:
            pass

        modules = [("AUD", ac), ("OBD", oc), ("MUS", mc),
                   ("NET", nc), ("CAM", cam_c), ("LUX", t["text_dim"])]
        mw = (W - 12) // len(modules)
        my = sy + 3

        for i, (name, color) in enumerate(modules):
            mx = 6 + i * mw
            pygame.draw.circle(s, color, (mx + mw // 2, my + 3), 3)
            mt = self.font_xs.render(name, True, color)
            s.blit(mt, (mx + (mw - mt.get_width()) // 2, my + 9))

        # Split mic bar: left half = USB mic, right half = webcam mic
        self._read_voice_signal()
        aud_x = 6 + 0 * mw + 2
        mic_w = mw - 4
        mic_y = my + 19
        half = mic_w // 2

        # Background
        pygame.draw.rect(s, t["border"], (aud_x, mic_y, mic_w, 3), border_radius=1)

        # Left side: USB mic (fills left to center)
        if self.mic1_level > 0.01:
            lc = t["primary"] if self.mic1_level < 0.3 else GREEN if self.mic1_level < 0.6 else AMBER
            fw = max(1, int(half * self.mic1_level))
            pygame.draw.rect(s, lc, (aud_x + half - fw, mic_y, fw, 3), border_radius=1)

        # Right side: webcam mic (fills center to right)
        if self.mic2_level > 0.01:
            rc = AMBER if self.mic2_level < 0.3 else GREEN if self.mic2_level < 0.6 else t["primary"]
            fw = max(1, int(half * self.mic2_level))
            pygame.draw.rect(s, rc, (aud_x + half, mic_y, fw, 3), border_radius=1)

        # Center divider tick
        pygame.draw.line(s, t["text_dim"], (aud_x + half, mic_y), (aud_x + half, mic_y + 2))

        if self.has_keyboard:
            sc = self.font_xs.render("C:Cam H:Help 1-6:Theme F1:Calibrate ?:Keys", True, t["text_dim"])
            s.blit(sc, (4, H - 10))

    def get_voice_state(self):
        """Read transcript and determine voice UI state."""
        try:
            with open("/tmp/car-hud-transcript") as tf:
                tr = json.load(tf)
                age = time.time() - tr.get("time", 0)
                if age < 6:
                    return tr
        except Exception:
            pass
        return None

    def draw_voice_overlay(self, tr):
        """Full-screen voice assistant overlay — theme-matched."""
        W, H = self.width, self.height
        s = self.surf
        t = self.t

        # Overlay: dark tinted bg + bright accent that's visible on ANY theme
        pr, pg, pb = t["primary"]
        brightness = max(pr, pg, pb)
        if brightness < 80:
            accent = (0, 160, 220)
            accent_dim = (0, 80, 110)
        else:
            accent = t["primary"]
            accent_dim = t["primary_dim"]

        # Background — visibly tinted, not just black
        overlay_bg = (max(15, pr // 3), max(15, pg // 3), max(15, pb // 3))
        s.fill(overlay_bg)

        # Thick accent line at top
        pygame.draw.line(s, accent, (0, 0), (W, 0), 3)
        pygame.draw.line(s, accent_dim, (0, H - 1), (W, H - 1), 2)

        # Pulsing circle — center
        cx, cy = W // 2, H // 2 - 20
        pulse = 0.5 + 0.5 * math.sin(time.time() * 3)

        # Bright rings — full accent color, thick lines
        ar, ag, ab = accent
        for ring in range(3):
            r = int(35 + 12 * pulse) + ring * 12
            thickness = max(2, 4 - ring)
            fade = 1.0 - ring * 0.25
            c = (min(255, int(ar * fade)), min(255, int(ag * fade)), min(255, int(ab * fade)))
            pygame.draw.circle(s, c, (cx, cy), r, thickness)

        # Filled center circle — full accent color
        inner_r = int(16 + 8 * pulse)
        pygame.draw.circle(s, accent, (cx, cy), inner_r)
        # White hot core
        pygame.draw.circle(s, (255, 255, 255), (cx, cy), int(5 + 3 * pulse))

        # "Hey Honda" above the circle — always bright
        hh = self.font_md.render("Hey Honda", True, accent)
        s.blit(hh, ((W - hh.get_width()) // 2, cy - 65))

        # What's being heard — per-word confidence coloring
        text = tr.get("partial", tr.get("text", ""))
        is_final = "text" in tr

        if text:
            ar, ag, ab = accent
            words = text.split()
            max_w = W - 20

            # Score each word's confidence
            # Common English words = high confidence, unusual/short = low
            _common = {"the","a","to","is","it","i","you","what","how","can",
                       "do","my","me","we","show","change","make","set","turn",
                       "color","camera","music","home","system","map","help",
                       "red","blue","green","amber","night","day","dark","light",
                       "hey","honda","please","and","or","not","this","that",
                       "on","off","up","down","brightness","connect","phone",
                       "wifi","network","weather","time","speed","fuel"}

            word_scores = []
            for w in words:
                wl = w.lower()
                if wl in _common:
                    word_scores.append(1.0)
                elif len(wl) <= 2:
                    word_scores.append(0.3)
                elif len(wl) <= 4:
                    word_scores.append(0.5 if is_final else 0.35)
                else:
                    word_scores.append(0.7 if is_final else 0.45)

            # Word-wrap into lines of (word, score) tuples
            lines = []
            current_line = []
            current_w = 0
            for i, word in enumerate(words):
                ww = self.font_md.size(word + " ")[0]
                if current_w + ww > max_w and current_line:
                    lines.append(current_line)
                    current_line = []
                    current_w = 0
                current_line.append((word, word_scores[i]))
                current_w += ww
            if current_line:
                lines.append(current_line)

            # Render word by word with per-word brightness
            ty = cy + 50
            for line in lines[-3:]:
                # Center the line
                line_w = sum(self.font_md.size(w + " ")[0] for w, _ in line)
                tx = max(6, (W - line_w) // 2)
                for word, score in line:
                    if is_final:
                        c = (int(ar * 0.3 + 200 * score),
                             int(ag * 0.3 + 200 * score),
                             int(ab * 0.3 + 200 * score))
                    else:
                        c = (int(ar * score * 0.8),
                             int(ag * score * 0.8),
                             int(ab * score * 0.8))
                    c = (min(255, c[0]), min(255, c[1]), min(255, c[2]))
                    wt = self.font_md.render(word, True, c)
                    s.blit(wt, (tx, ty))
                    tx += wt.get_width() + self.font_md.size(" ")[0]
                ty += self.font_md.get_height() + 3

        # Source indicator + listening
        source = ""
        try:
            with open("/tmp/car-hud-voice-signal") as vs:
                vsig = json.load(vs)
                if time.time() - vsig.get("time", 0) < 8:
                    source = vsig.get("source", "")
                    reply = vsig.get("reply", "")
                    if reply:
                        rt = self.font_sm.render(reply, True, accent)
                        rx = max(6, (W - rt.get_width()) // 2)
                        s.blit(rt, (rx, H - 45))
        except Exception:
            pass

        dots = "." * (int(time.time() * 2) % 4)
        lt = self.font_xs.render(f"Listening{dots}", True, accent_dim)
        s.blit(lt, (6, H - 18))

        if source:
            if source.startswith("ai:"):
                tag = source.split(":")[1]
            elif source == "cache":
                tag = "Cached"
            elif source == "learned":
                tag = "Learned"
            elif source == "local":
                tag = "Local"
            else:
                tag = source
            it = self.font_xs.render(tag, True, accent_dim)
            s.blit(it, (W - it.get_width() - 6, H - 18))

    def draw_help_overlay(self):
        """Full-screen help with available commands."""
        W, H = self.width, self.height
        s = self.surf
        t = self.t

        s.fill(t["bg"])
        pygame.draw.line(s, t["primary_dim"], (0, 0), (W, 0), 1)

        title = self.font_md.render("Voice Commands", True, t["primary"])
        s.blit(title, ((W - title.get_width()) // 2, 6))

        commands = [
            ("Show camera / music / map", "Views"),
            ("Color blue / red / green", "Theme"),
            ("Night mode / day mode", "Theme"),
            ("Scan networks", "WiFi"),
            ("Connect my phone", "Bluetooth"),
            ("What's playing", "Music"),
            ("How much gas", "Vehicle"),
            ("Go home / go back", "Navigation"),
            ("Make it brighter", "Display"),
            ("Help / what can you do", "Info"),
        ]

        y = 28
        for cmd_text, category in commands:
            cat = self.font_xs.render(category, True, t["primary_dim"])
            s.blit(cat, (8, y + 1))
            ct = self.font_sm.render(cmd_text, True, t["text_bright"])
            s.blit(ct, (65, y))
            y += ct.get_height() + 4

        hint = self.font_xs.render("Say 'Hey Honda' then a command", True, t["text_dim"])
        s.blit(hint, ((W - hint.get_width()) // 2, H - 18))

    def draw_calibration_overlay(self):
        """Full-page calibration progress with gain scores."""
        W, H = self.width, self.height
        s = self.surf
        t = self.t

        try:
            with open("/tmp/car-hud-calibration-status") as f:
                cal = json.load(f)
        except Exception:
            return False

        if time.time() - cal.get("time", 0) > 30:
            return False

        status = cal.get("status", "")
        if status == "done":
            # Show results for 10 seconds
            s.fill(t["bg"])
            pygame.draw.line(s, GREEN, (0, 0), (W, 0), 2)
            done = self.font_lg.render("Calibration Complete", True, GREEN)
            s.blit(done, ((W - done.get_width()) // 2, H // 2 - 30))
            detail = self.font_sm.render(cal.get("detail", ""), True, t["text_bright"])
            s.blit(detail, ((W - detail.get_width()) // 2, H // 2 + 10))
            return True

        s.fill(t["bg"])
        pygame.draw.line(s, AMBER, (0, 0), (W, 0), 2)

        # Title
        title = self.font_lg.render("Voice Calibration", True, AMBER)
        s.blit(title, ((W - title.get_width()) // 2, 8))

        mic = cal.get("mic", "")
        rnd = cal.get("round", 0)
        total = cal.get("total", 1)
        progress = cal.get("progress", 0)
        cur_gain = cal.get("gain", 0)
        detail = cal.get("detail", "")

        # Mic + round
        info = self.font_md.render(f"{mic}", True, t["text_bright"])
        s.blit(info, ((W - info.get_width()) // 2, 38))

        rnd_text = self.font_sm.render(f"Round {rnd}/{total}", True, t["text_med"])
        s.blit(rnd_text, ((W - rnd_text.get_width()) // 2, 58))

        # Progress bar
        bar_w = W - 40
        bar_h = 8
        bar_x = 20
        bar_y = 80
        pygame.draw.rect(s, t["border"], (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        fill = max(0, min(int(bar_w * progress / 100), bar_w))
        if fill > 1:
            pygame.draw.rect(s, AMBER, (bar_x, bar_y, fill, bar_h), border_radius=3)

        # Current action
        if status == "recording":
            # Pulsing dot to show recording
            pulse = int(time.time() * 3) % 2
            if pulse:
                pygame.draw.circle(s, RED, (bar_x + fill - 2, bar_y + 4), 4)
            act = self.font_sm.render("Recording...", True, RED)
        elif status == "testing":
            act = self.font_sm.render(f"Testing gain {cur_gain}x...", True, AMBER)
        else:
            act = self.font_sm.render(detail, True, t["text_med"])
        s.blit(act, ((W - act.get_width()) // 2, bar_y + 14))

        # Gain visualization — show bars for tested gains
        gains = [1, 2, 3, 4, 5, 6, 8]
        gy = bar_y + 40
        gw = (W - 40) // len(gains)

        for i, g in enumerate(gains):
            gx = 20 + i * gw
            # Highlight current gain being tested
            if g == cur_gain and status == "testing":
                pygame.draw.rect(s, AMBER, (gx + 2, gy, gw - 4, 60), 1, border_radius=3)

            # Gain label
            gl = self.font_xs.render(f"{g}x", True, t["text_med"])
            s.blit(gl, (gx + (gw - gl.get_width()) // 2, gy + 48))

            # Score bar (grows upward) — visual indicator
            # We don't have live scores here but show which is being tested
            bar_h_inner = 40
            pygame.draw.rect(s, t["border"], (gx + 6, gy + 4, gw - 12, bar_h_inner), border_radius=2)

        # Bottom status with ETA
        eta = cal.get("eta", "")
        if eta:
            eta_t = self.font_sm.render(eta, True, AMBER)
            s.blit(eta_t, ((W - eta_t.get_width()) // 2, H - 35))

        pct = self.font_xs.render(f"{progress}%", True, AMBER)
        s.blit(pct, (W - pct.get_width() - 10, H - 16))

        hint = self.font_xs.render("Testing voice recognition at each gain...", True, t["text_dim"])
        s.blit(hint, (10, H - 16))

        return True

    def draw_keys_overlay(self):
        """Keyboard shortcuts reference."""
        W, H = self.width, self.height
        s = self.surf
        t = self.t
        s.fill(t["bg"])
        pygame.draw.line(s, t["primary"], (0, 0), (W, 0), 1)

        title = self.font_md.render("Keyboard Shortcuts", True, t["primary"])
        s.blit(title, ((W - title.get_width()) // 2, 6))

        keys = [
            ("C", "Camera view"),
            ("H", "Help / commands"),
            ("1-6", "Themes: blue red green amber day night"),
            ("F1", "Run voice calibration"),
            ("ESC", "Close overlay"),
            ("Ctrl+T", "Drop to terminal"),
            ("Ctrl+Q", "Quit HUD"),
            ("?", "This screen"),
        ]

        y = 30
        for key, desc in keys:
            kt = self.font_sm.render(key, True, t["primary"])
            dt = self.font_sm.render(desc, True, t["text_bright"])
            s.blit(kt, (12, y))
            s.blit(dt, (70, y))
            y += dt.get_height() + 5

        hint = self.font_xs.render("Press any key to close", True, t["text_dim"])
        s.blit(hint, ((W - hint.get_width()) // 2, H - 16))

    def draw_terminal_overlay(self):
        overlay = pygame.Surface((self.width, self.height // 2), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))
        self.surf.blit(overlay, (0, 0))
        header = self.font_sm.render("Terminal [ESC close]", True, self.t["primary"])
        self.surf.blit(header, (4, 2))
        pygame.draw.line(self.surf, self.t["primary_dim"],
                         (0, header.get_height() + 4), (self.width, header.get_height() + 4))
        y = header.get_height() + 8
        for line in self.terminal_lines[-12:]:
            txt = self.font_mono.render(line, True, GREEN)
            self.surf.blit(txt, (4, y))
            y += self.font_mono.get_height() + 1

    def draw_camera_view(self):
        """Full-screen camera feed from webcam using persistent ffmpeg stream."""
        W, H = self.width, self.height
        s = self.surf
        t = self.t
        frame_size = W * H * 3

        # Start persistent camera capture if not running
        if self.camera_cap is None or self.camera_cap.poll() is not None:
            try:
                # Auto-detect webcam device
                cam_dev = "/dev/video0"
                try:
                    r = subprocess.run(["v4l2-ctl", "--list-devices"],
                                       capture_output=True, text=True, timeout=3)
                    lines = r.stdout.split("\n")
                    for i, line in enumerate(lines):
                        if "Webcam" in line or "C925" in line or "USB" in line:
                            if i + 1 < len(lines):
                                dev = lines[i + 1].strip()
                                if dev.startswith("/dev/video"):
                                    cam_dev = dev
                                    break
                except Exception:
                    pass

                # Use 320x240 for speed — pygame scales it up
                self._cam_w, self._cam_h = 320, 240
                self.camera_cap = subprocess.Popen([
                    "ffmpeg", "-f", "v4l2",
                    "-video_size", f"{self._cam_w}x{self._cam_h}",
                    "-framerate", "15", "-i", cam_dev,
                    "-f", "rawvideo", "-pix_fmt", "rgb24",
                    "-an", "-"
                ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            except Exception:
                s.fill(t["bg"])
                msg = self.font_md.render("Camera unavailable", True, AMBER)
                s.blit(msg, ((W - msg.get_width()) // 2, H // 2))
                return

        # Read one frame at 320x240, scale to fill screen
        cam_frame_size = self._cam_w * self._cam_h * 3
        try:
            raw = self.camera_cap.stdout.read(cam_frame_size)
            if raw and len(raw) == cam_frame_size:
                small = pygame.image.fromstring(raw, (self._cam_w, self._cam_h), "RGB")
                frame = pygame.transform.scale(small, (W, H))
                s.blit(frame, (0, 0))
                self.camera_frame = frame
            elif self.camera_frame:
                s.blit(self.camera_frame, (0, 0))
            else:
                s.fill(t["bg"])
                msg = self.font_md.render("Camera starting...", True, t["primary"])
                s.blit(msg, ((W - msg.get_width()) // 2, H // 2))
        except Exception:
            if self.camera_frame:
                s.blit(self.camera_frame, (0, 0))

        # REC indicator
        pulse = int(time.time() * 2) % 2
        if pulse:
            pygame.draw.circle(s, RED, (16, 14), 5)
        rec = self.font_xs.render("LIVE", True, RED)
        s.blit(rec, (24, 8))

        hint = self.font_xs.render("ESC: close  C: toggle", True, (150, 150, 150))
        s.blit(hint, ((W - hint.get_width()) // 2, H - 14))

    def drop_to_terminal(self):
        pygame.quit()
        os.system("clear")
        print("\033[38;2;0;140;210m" + "=" * 36)
        print("     Honda Accord - Terminal")
        print("  Type 'car-hud' to return")
        print("=" * 36 + "\033[0m\n")
        os.execvp("/bin/bash", ["/bin/bash", "--login"])

    def present(self):
        if self.display_w == self.width and self.display_h == self.height:
            self.screen.blit(self.surf, (0, 0))
        else:
            scaled = pygame.transform.smoothscale(self.surf,
                                                  (self.display_w, self.display_h))
            self.screen.blit(scaled, (0, 0))
        pygame.display.flip()

        # Screenshot on request (for HTTP server) — BMP for speed
        try:
            if os.path.exists("/tmp/car-hud-screenshot-request"):
                pygame.image.save(self.surf, "/tmp/car-hud-screenshot.bmp")
                os.remove("/tmp/car-hud-screenshot-request")
        except Exception:
            pass

    def run(self):
        theme_check_timer = 0

        while self.running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    self.running = False
                elif event.type == KEYDOWN:
                    mods = pygame.key.get_mods()
                    if event.key == K_q and (mods & KMOD_CTRL):
                        self.running = False
                    elif event.key == K_t and (mods & KMOD_CTRL):
                        self.drop_to_terminal()
                    elif event.key == K_ESCAPE:
                        # ESC closes any overlay, or toggles terminal
                        if self.show_camera:
                            self.show_camera = False
                            if self.camera_cap:
                                self.camera_cap.kill()
                                self.camera_cap = None
                            subprocess.run(["sudo", "systemctl", "start", "car-hud-dashcam"],
                                           capture_output=True, timeout=5)
                        elif self.show_terminal:
                            self.show_terminal = False
                        else:
                            self.show_terminal = True
                    # Keyboard shortcuts (when keyboard connected)
                    elif event.key == K_c:
                        self.show_camera = not self.show_camera
                        if self.show_camera:
                            # Stop dashcam to free the webcam device
                            subprocess.run(["sudo", "systemctl", "stop", "car-hud-dashcam"],
                                           capture_output=True, timeout=5)
                            subprocess.run(["pkill", "-f", "ffmpeg.*video0"],
                                           capture_output=True, timeout=3)
                            time.sleep(0.5)
                        else:
                            # Close camera and restart dashcam
                            if self.camera_cap:
                                self.camera_cap.kill()
                                self.camera_cap = None
                            subprocess.run(["sudo", "systemctl", "start", "car-hud-dashcam"],
                                           capture_output=True, timeout=5)
                    elif event.key == K_h:
                        # Simulate help command
                        signal_hud_file("show", "help")
                    elif event.key == K_1:
                        self.set_theme("blue")
                    elif event.key == K_2:
                        self.set_theme("red")
                    elif event.key == K_3:
                        self.set_theme("green")
                    elif event.key == K_4:
                        self.set_theme("amber")
                    elif event.key == K_5:
                        self.set_theme("day")
                    elif event.key == K_6:
                        self.set_theme("night")
                    elif event.key == K_F1:
                        # Run voice calibration
                        subprocess.Popen(
                            ["python3", "/home/chrismslist/northstar/calibrate.py"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    elif event.key == K_SLASH or event.key == K_QUESTION:
                        # Show keyboard shortcuts
                        signal_hud_file("show", "keys")

            self.surf.fill(self.t["bg"])
            stats = self.get_system_stats()
            obd = self.get_obd_data()
            music = self.get_music_data()

            # Reload theme from file every 2 seconds (for voice commands)
            theme_check_timer += 1
            if theme_check_timer >= 60:  # 30fps * 2s
                theme_check_timer = 0
                new_theme = self._load_theme()
                if self.auto_theme:
                    new_theme = get_auto_theme()
                if new_theme != self.theme_name:
                    self.theme_name = new_theme
                    self.t = THEMES[self.theme_name]
                    self._build_tinted_logo()

            self.kb_check_timer += 1
            if self.kb_check_timer >= 150:
                self.has_keyboard = keyboard_connected()
                self.kb_check_timer = 0

            if obd["connected"] and obd.get("data"):
                self.draw_vehicle_page(obd, music)
            else:
                self.draw_system_page(stats, music)

            self.draw_status_strip(obd)

            # Calibration overlay — takes over everything
            if self.draw_calibration_overlay():
                self.present()
                self.clock_t.tick(15)
                continue

            # Check voice signal for overlays (help, keys, camera)
            try:
                with open("/tmp/car-hud-voice-signal") as vs:
                    vsig = json.load(vs)
                    if time.time() - vsig.get("time", 0) < 10:
                        if vsig.get("action") == "show" and vsig.get("target") == "help":
                            self.draw_help_overlay()
                            self.present()
                            self.clock_t.tick(30)
                            continue
                        elif vsig.get("action") == "show" and vsig.get("target") == "keys":
                            self.draw_keys_overlay()
                            self.present()
                            self.clock_t.tick(30)
                            continue
                        elif vsig.get("action") == "system" and vsig.get("target") == "calibrate":
                            subprocess.Popen(
                                ["python3", "/home/chrismslist/northstar/calibrate.py"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        elif vsig.get("action") == "show" and vsig.get("target") == "camera":
                            if not self.show_camera:
                                subprocess.run(["sudo", "systemctl", "stop", "car-hud-dashcam"],
                                               capture_output=True, timeout=5)
                                subprocess.run(["pkill", "-f", "ffmpeg.*video0"],
                                               capture_output=True, timeout=3)
                                time.sleep(0.5)
                            self.show_camera = True
            except Exception:
                pass

            # Camera full-screen view
            if self.show_camera:
                self.draw_camera_view()
                self.present()
                self.clock_t.tick(10)  # lower FPS for camera to save CPU
                continue

            # Voice assistant overlay — takes over screen when wake detected
            voice_tr = self.get_voice_state()
            if voice_tr and voice_tr.get("wake"):
                self.draw_voice_overlay(voice_tr)
            elif voice_tr:
                # Not wake mode — show small transcript above status strip
                text = voice_tr.get("partial", voice_tr.get("text", ""))
                if text:
                    age = time.time() - voice_tr.get("time", 0)
                    if age < 3:
                        max_c = self.width // 7
                        if len(text) > max_c:
                            text = text[-max_c:]
                        color = self.t["text_dim"] if "partial" in voice_tr else self.t["text_med"]
                        tt = self.font_xs.render(text, True, color)
                        self.surf.blit(tt, (16, self.height - 40))

            if self.show_terminal:
                self.draw_terminal_overlay()

            self.present()
            self.clock_t.tick(30)

        pygame.quit()


if __name__ == "__main__":
    hud = CarHUD()
    hud.run()
