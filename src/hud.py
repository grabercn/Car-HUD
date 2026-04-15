#!/usr/bin/env python3
"""Car-HUD - Visual Dashboard
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
from pages import vehicle as vehicle_page, system as system_page

# ── Theme Presets (2014 Car-HUD style) ──
# Themes modeled on 2014 Car-HUD iMID color options
# Each theme completely transforms the entire display
THEMES = {
    "blue": {  # Default Car-HUD blue
        "primary":    (0, 180, 255),     # Bright cyan-blue gauges
        "primary_dim":(0, 110, 180),     # Dim gauge backgrounds (brighter for TFT)
        "accent":     (0, 130, 220),     # Secondary elements
        "bg":         (2, 4, 12),        # Deep blue-black
        "panel":      (5, 10, 25),
        "border":     (10, 30, 60),
        "border_lite":(8, 22, 45),
        "text_bright":(220, 240, 255),   # Blue-white text
        "text_med":   (140, 190, 240),   # Boosted for 2.5" TFT
        "text_dim":   (80, 140, 200),    # Readable on small TFT
    },
    "red": {  # Honda Sport red
        "primary":    (255, 30, 30),     # Vivid red gauges
        "primary_dim":(180, 20, 20),     # Brighter red backgrounds
        "accent":     (220, 20, 20),
        "bg":         (12, 2, 2),        # Deep red-black
        "panel":      (25, 5, 5),
        "border":     (60, 12, 12),
        "border_lite":(45, 10, 10),
        "text_bright":(255, 210, 200),   # Warm white
        "text_med":   (240, 150, 140),   # Boosted
        "text_dim":   (180, 90, 80),     # Readable
    },
    "green": {  # Honda Eco green
        "primary":    (0, 230, 100),     # Vivid green gauges
        "primary_dim":(0, 150, 65),      # Brighter green backgrounds
        "accent":     (0, 200, 80),
        "bg":         (2, 10, 4),        # Deep green-black
        "panel":      (4, 22, 10),
        "border":     (10, 50, 20),
        "border_lite":(8, 38, 16),
        "text_bright":(210, 255, 220),   # Green-white
        "text_med":   (130, 220, 150),   # Boosted
        "text_dim":   (80, 170, 100),    # Readable
    },
    "amber": {  # Classic amber instruments
        "primary":    (255, 180, 0),     # Bright amber gauges
        "primary_dim":(160, 110, 0),     # Brighter amber backgrounds
        "accent":     (230, 150, 0),
        "bg":         (10, 7, 2),        # Deep amber-black
        "panel":      (22, 16, 5),
        "border":     (55, 40, 10),
        "border_lite":(40, 30, 8),
        "text_bright":(255, 240, 190),   # Warm amber-white
        "text_med":   (230, 180, 90),    # Boosted
        "text_dim":   (170, 130, 50),    # Readable
    },
    "day": {  # High-contrast daylight mode
        "primary":    (0, 0, 0),         # Black gauges on white
        "primary_dim":(130, 130, 130),
        "accent":     (40, 40, 40),
        "bg":         (240, 240, 235),   # Bright white
        "panel":      (225, 225, 220),
        "border":     (180, 180, 175),
        "border_lite":(200, 200, 195),
        "text_bright":(0, 0, 0),         # Pure black text
        "text_med":   (40, 40, 40),
        "text_dim":   (80, 80, 80),
    },
    "night": {  # Ultra-dim night driving
        "primary":    (0, 120, 160),     # Very dim blue
        "primary_dim":(0, 60, 80),       # Slightly brighter for TFT
        "accent":     (0, 80, 110),
        "bg":         (1, 2, 4),         # Nearly black
        "panel":      (3, 5, 10),
        "border":     (6, 14, 25),
        "border_lite":(5, 10, 18),
        "text_bright":(120, 160, 190),   # Slightly brighter
        "text_med":   (80, 120, 155),    # Boosted
        "text_dim":   (50, 80, 110),     # Readable
    },
}

# Fixed status colors (same across all themes)
GREEN  = (0, 180, 85)
AMBER  = (220, 160, 0)
RED    = (220, 45, 45)

THEME_FILE = "/home/chrismslist/car-hud/.theme"
HONDA_LOGO_PATH = "/home/chrismslist/car-hud/honda_logo.png"


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
        # Simple init — same as working test
        pygame.init()
        info = pygame.display.Info()
        self.display_w = info.current_w if info.current_w > 0 else 480
        self.display_h = info.current_h if info.current_h > 0 else 320
        self.screen = pygame.display.set_mode(
            (self.display_w, self.display_h), pygame.FULLSCREEN | pygame.NOFRAME)

        self.width = self.TARGET_W
        self.height = self.TARGET_H
        self.surf = pygame.Surface((self.width, self.height))
        pygame.mouse.set_visible(False)

        # Use bold fonts everywhere for 2.5" TFT visibility
        fs_bold = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
        dv_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        dv_mono = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
        dv_mono_reg = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
        bold = fs_bold if os.path.exists(fs_bold) else dv_bold
        mono = dv_mono if os.path.exists(dv_mono) else dv_mono_reg

        # All bold, slightly larger for 2.5" TFT readability
        self.font_xxl  = pygame.font.Font(bold, 54)
        self.font_xl   = pygame.font.Font(bold, 38)
        self.font_lg   = pygame.font.Font(bold, 28)
        self.font_md   = pygame.font.Font(bold, 17)
        self.font_sm   = pygame.font.Font(bold, 14)
        self.font_xs   = pygame.font.Font(bold, 12)
        self.font_mono = pygame.font.Font(mono, 11)

        # CJK font for Japanese/Korean/Chinese text (bold)
        cjk_paths = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-DemiLight.ttc",
        ]
        self.font_cjk = None
        for cp in cjk_paths:
            if os.path.exists(cp):
                self.font_cjk = pygame.font.Font(cp, 14)
                self.font_cjk_sm = pygame.font.Font(cp, 12)
                break

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
        self.camera_idx = 0
        self.camera_frame = None
        self.camera_cap = None

        # Touch support
        self.touch_start = None  # (x, y, time) for swipe detection
        self.force_page = None   # None=auto, "vehicle", "system"
        self.page_names = ["system", "vehicle"]
        self.page_idx = 0

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

        # Smoothed data for animations
        self.smooth_data = {}
        self.last_update = time.time()

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

    def draw_glow_text(self, text, font, color, pos, glow_color=None, glow_dist=1):
        """Draw text with a subtle glow/shadow for better readability."""
        if glow_color is None:
            glow_color = (0, 0, 0, 150)
        
        # Draw shadow/glow offset
        st = font.render(text, True, glow_color)
        for dx, dy in [(-glow_dist, 0), (glow_dist, 0), (0, -glow_dist), (0, glow_dist)]:
            self.surf.blit(st, (pos[0] + dx, pos[1] + dy))
        
        # Main text
        mt = font.render(text, True, color)
        self.surf.blit(mt, pos)

    def draw_arc_gauge(self, cx, cy, radius, thickness, pct, color, bg_color=None, 
                       start=math.pi, end=0, ticks=False):
        s = self.surf
        bg = bg_color or self.t["border"]
        start_angle = start
        end_angle = end
        steps = 50

        # Draw background track
        for i in range(steps):
            t = i / steps
            a1 = start_angle + (end_angle - start_angle) * t
            a2 = start_angle + (end_angle - start_angle) * (t + 1/steps)
            x1 = cx + radius * math.cos(a1)
            y1 = cy - radius * math.sin(a1)
            x2 = cx + radius * math.cos(a2)
            y2 = cy - radius * math.sin(a2)
            pygame.draw.line(s, bg, (int(x1), int(y1)), (int(x2), int(y2)), thickness)

        # Draw progress arc
        fill_steps = max(1, int(steps * min(pct, 1.0)))
        for i in range(fill_steps):
            t = i / steps
            t2 = (i + 1) / steps
            # Logic for color transitions based on progress
            if pct > 0.85 and t > 0.85: c = RED
            elif pct > 0.7 and t > 0.7: c = AMBER
            else: c = color
            
            a1 = start_angle + (end_angle - start_angle) * t
            a2 = start_angle + (end_angle - start_angle) * t2
            x1 = cx + radius * math.cos(a1)
            y1 = cy - radius * math.sin(a1)
            x2 = cx + radius * math.cos(a2)
            y2 = cy - radius * math.sin(a2)
            pygame.draw.line(s, c, (int(x1), int(y1)), (int(x2), int(y2)), thickness)

        if ticks:
            # Draw scale ticks every 10%
            tick_len = thickness + 3
            for i in range(11):
                a = start_angle + (end_angle - start_angle) * (i / 10)
                x1 = cx + (radius - thickness//2) * math.cos(a)
                y1 = cy - (radius - thickness//2) * math.sin(a)
                x2 = cx + (radius + thickness//2 + 3) * math.cos(a)
                y2 = cy - (radius + thickness//2 + 3) * math.sin(a)
                pygame.draw.line(s, self.t["border_lite"], (int(x1), int(y1)), (int(x2), int(y2)), 1)

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
        vehicle_page.draw(self, obd, music)

    def draw_system_page(self, stats, music):
        system_page.draw(self, stats, music)

    def draw_lower_section(self, y, music, vd):
        W = self.width
        s = self.surf
        t = self.t
        now = datetime.datetime.now()

        if music.get("playing"):
            track = music.get("track", "")
            artist = music.get("artist", "")
            album = music.get("album", "")
            device = music.get("device", "")

            # Album art (left side) — bigger for 2.5" TFT
            art_x = 4
            art_size = 55
            art_loaded = False
            try:
                art_file = "/home/chrismslist/car-hud/current_art.jpg"
                if os.path.exists(art_file) and os.path.getsize(art_file) > 100:
                    from PIL import Image as PILImage
                    pil = PILImage.open(art_file).convert("RGB")
                    pil = pil.resize((art_size, art_size), PILImage.LANCZOS)
                    art_surf = pygame.image.fromstring(pil.tobytes(), (art_size, art_size), "RGB")
                    s.blit(art_surf, (art_x, y))
                    art_loaded = True
            except Exception:
                pass

            if not art_loaded:
                # Fallback: centered music note icon in bordered square
                pygame.draw.rect(s, t["border"], (art_x, y, art_size, art_size), border_radius=4)
                ncx, ncy = art_x + art_size // 2, y + art_size // 2
                # Note head
                pygame.draw.ellipse(s, t["primary"], (ncx - 8, ncy + 2, 10, 8))
                # Note stem
                pygame.draw.line(s, t["primary"], (ncx + 1, ncy + 5), (ncx + 1, ncy - 14), 2)
                # Note flag
                pygame.draw.line(s, t["primary"], (ncx + 1, ncy - 14), (ncx + 7, ncy - 10), 2)

            # Track info (right of art)
            tx = art_x + art_size + 6
            tw = W - tx - 4
            max_c = tw // 7

            # Use CJK font if text contains non-ASCII
            has_cjk = any(ord(c) > 0x2E80 for c in track)
            track_font = self.font_cjk if has_cjk and self.font_cjk else self.font_md
            tt = track_font.render(track[:max_c], True, t["text_bright"])
            s.blit(tt, (tx, y))

            has_cjk_a = any(ord(c) > 0x2E80 for c in artist)
            artist_font = self.font_cjk_sm if has_cjk_a and hasattr(self, "font_cjk_sm") and self.font_cjk_sm else self.font_sm
            at = artist_font.render(artist[:max_c], True, t["text_med"])
            s.blit(at, (tx, y + 18))

            # Progress bar — estimate from timestamp if API returns 0
            prog = max(0, music.get("progress", 0))
            dur = max(0, music.get("duration", 0))
            if prog == 0 and dur > 0 and music.get("timestamp"):
                elapsed = time.time() - music["timestamp"]
                prog = min(elapsed, dur)
            if dur > 0:
                pbar_y = y + 36
                pygame.draw.rect(s, t["border"], (tx, pbar_y, tw, 4), border_radius=2)
                fw = int(tw * min(prog / dur, 1))
                if fw > 0:
                    pygame.draw.rect(s, t["primary"], (tx, pbar_y, fw, 4), border_radius=2)

                # Time — bigger font, left aligned
                prog_m, prog_s = int(prog) // 60, int(prog) % 60
                dur_m, dur_s = int(dur) // 60, int(dur) % 60
                time_t = self.font_sm.render(f"{prog_m}:{prog_s:02d} / {dur_m}:{dur_s:02d}", True, t["text_med"])
                s.blit(time_t, (tx, pbar_y + 6))

            # Device source — bigger, right aligned below progress
            dev_name = music.get("device", "")
            if dev_name:
                dt = self.font_sm.render(dev_name, True, t["text_dim"])
                s.blit(dt, (tx + tw - dt.get_width(), pbar_y + 6 if dur > 0 else y + 36))

        elif music.get("paired"):
            phone = music.get("phone", "Phone")
            pygame.draw.circle(s, t["primary_dim"], (15, y + 12), 3)
            pt = self.font_sm.render(f"Connected: {phone}", True, t["text_dim"])
            s.blit(pt, (28, y + 5))

        elif vd:
            ts = self.font_md.render(now.strftime("%I:%M %p"), True, t["text_med"])
            s.blit(ts, (10, y + 2))
            amb = vd.get("AMBIANT_AIR_TEMP")
            if amb:
                at = self.font_md.render(f"{amb:.0f}C", True, t["text_dim"])
                s.blit(at, (W - at.get_width() - 10, y + 2))

    def draw_status_strip(self, obd):
        W, H = self.width, self.height
        s = self.surf
        t = self.t
        sy = H - 26

        # Strip background
        pygame.draw.rect(s, (0, 0, 0, 80), (0, sy, W, 26))
        pygame.draw.line(s, t["border_lite"], (0, sy), (W, sy))

        # Audio detection
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

        # OBD — primary=connected, amber=service running, dim=off
        if obd["connected"] and obd.get("data"):
            oc = t["primary"]
        elif obd.get("status") and obd["status"] not in ("offline", ""):
            oc = AMBER
        else:
            oc = t["text_dim"]

        # Music
        music = self.get_music_data()
        # Phone/BT indicator
        phone_c = t["text_dim"]
        try:
            import subprocess as _sp
            bt_info = _sp.run(["bluetoothctl", "info"], capture_output=True, text=True, timeout=3)
            if "Connected: yes" in bt_info.stdout:
                phone_c = t["primary"]  # connected
            elif bt_info.returncode == 0 and "Device" in bt_info.stdout:
                phone_c = AMBER  # paired but not connected
            else:
                bt_state = _sp.run(["bluetoothctl", "show"], capture_output=True, text=True, timeout=3)
                if "Powered: yes" in bt_state.stdout:
                    phone_c = AMBER  # BT on, searching
        except Exception:
            pass

        # Network
        nc = t["text_dim"]
        net_ssid = ""
        try:
            with open("/tmp/car-hud-wifi-data") as f:
                wd = json.load(f)
                ws = wd.get("state", "")
                net_ssid = wd.get("ssid", "")
                if ws == "connected" or ws == "tethered":
                    nc = t["primary"]
                elif ws == "connecting":
                    nc = AMBER
                elif ws == "failed":
                    nc = RED
        except Exception:
            pass

        # AUD (Mic)
        voice_running = False
        try:
            with open("/tmp/car-hud-mic-level") as f:
                lvl_age = time.time() - os.path.getmtime("/tmp/car-hud-mic-level")
                voice_running = lvl_age < 15
        except Exception:
            pass

        if has_in and voice_running:
            ac = t["primary"]
        elif has_in:
            ac = AMBER
        elif has_out:
            ac = AMBER

        # CAM
        cam_c = t["text_dim"]
        cam_count = 0
        try:
            with open("/tmp/car-hud-dashcam-data") as f:
                cd = json.load(f)
                if time.time() - cd.get("timestamp", 0) < 60:
                    cam_count = cd.get("cam_count", 0)
                    if cd.get("recording"):
                        cam_c = RED if int(time.time() * 2) % 2 == 0 else (120, 0, 0) # Blinking
                    else:
                        cam_c = t["primary"] if cam_count > 0 else t["text_dim"]
        except Exception:
            pass
        if cam_count == 0 and os.path.exists("/dev/video0"):
            cam_count = 1
            if cam_c == t["text_dim"]: cam_c = AMBER

        modules = [("AUD", ac), ("OBD", oc), ("PHN", phone_c),
                   ("NET", nc), ("CAM", cam_c)]
        mw = W // len(modules)
        my = sy + 2

        for i, (name, color) in enumerate(modules):
            mx = i * mw

            # Icon
            if name == "CAM":
                if cam_count == 1:
                    pygame.draw.arc(s, color, (mx + mw // 2 - 4, my, 8, 8), 0, math.pi, 2)
                elif cam_count >= 2:
                    pygame.draw.circle(s, color, (mx + mw // 2, my + 4), 3)
                else:
                    pygame.draw.circle(s, color, (mx + mw // 2, my + 4), 3, 1)
            else:
                pygame.draw.circle(s, color, (mx + mw // 2, my + 4), 3)

            # Label
            mt = self.font_xs.render(name, True, color)
            s.blit(mt, (mx + (mw - mt.get_width()) // 2, my + 10))

        # Mic level bar — draw BEHIND the AUD text
        self._read_voice_signal()
        aud_x = 0 * mw + 4
        mic_w = mw - 8
        mic_y = my + 8
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

        # Keyboard shortcuts hint only when keyboard is connected (above strip)
        if self.has_keyboard:
            sc = self.font_xs.render("C:Cam 1-6:Theme", True, t["text_dim"])
            s.blit(sc, (W - sc.get_width() - 4, sy - 12))

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
            # Show results for a few seconds
            s.fill(t["bg"])
            pygame.draw.line(s, GREEN, (0, 0), (W, 0), 2)
            self.draw_glow_text("CALIBRATION COMPLETE", self.font_lg, GREEN, ((W - self.font_lg.size("CALIBRATION COMPLETE")[0]) // 2, H // 2 - 30))
            detail = cal.get("detail", "")
            self.draw_glow_text(detail, self.font_sm, t["text_bright"], ((W - self.font_sm.size(detail)[0]) // 2, H // 2 + 10))
            return True

        s.fill(t["bg"])
        pygame.draw.line(s, AMBER, (0, 0), (W, 0), 2)

        # Title
        self.draw_glow_text("VOICE CALIBRATION", self.font_lg, AMBER, ((W - self.font_lg.size("VOICE CALIBRATION")[0]) // 2, 8))

        mic = cal.get("mic", "").upper()
        rnd = cal.get("round", 0)
        total = cal.get("total", 1)
        progress = cal.get("progress", 0)
        cur_gain = cal.get("gain", 0)
        detail = cal.get("detail", "").upper()

        # Mic + round
        if mic:
            self.draw_glow_text(f"TESTING: {mic}", self.font_md, t["text_bright"], ((W - self.font_md.size(f"TESTING: {mic}")[0]) // 2, 38))
            rnd_str = f"ROUND {rnd} OF {total}"
            self.draw_glow_text(rnd_str, self.font_sm, t["text_med"], ((W - self.font_sm.size(rnd_str)[0]) // 2, 58))

        # Progress bar
        bar_w = W - 60
        bar_h = 12
        bar_x = 30
        bar_y = 85
        pygame.draw.rect(s, t["border"], (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        fill = max(0, min(int(bar_w * progress / 100), bar_w))
        if fill > 1:
            pygame.draw.rect(s, AMBER, (bar_x, bar_y, fill, bar_h), border_radius=4)

        # Current action
        if status == "recording":
            pulse = int(time.time() * 3) % 2
            color = RED if pulse else (150, 0, 0)
            self.draw_glow_text("RECORDING...", self.font_sm, color, ((W - self.font_sm.size("RECORDING...")[0]) // 2, bar_y + 18))
            
            prompt = "SAY: 'HEY HONDA, WHAT'S THE WEATHER?'"
            self.draw_glow_text(prompt, self.font_md, t["text_bright"], ((W - self.font_md.size(prompt)[0]) // 2, bar_y + 45))
        elif status == "testing":
            act = f"ANALYZING {cur_gain}X GAIN..."
            self.draw_glow_text(act, self.font_sm, AMBER, ((W - self.font_sm.size(act)[0]) // 2, bar_y + 18))
        else:
            self.draw_glow_text(detail, self.font_sm, t["text_med"], ((W - self.font_sm.size(detail)[0]) // 2, bar_y + 18))

        # Gain visualization
        gains = [2, 4, 6, 8]
        gy = bar_y + 80
        gw = (W - 80) // len(gains)

        for i, g in enumerate(gains):
            gx = 40 + i * gw
            # Highlight current gain being tested
            if g == cur_gain and status == "testing":
                pygame.draw.rect(s, AMBER, (gx + 4, gy, gw - 8, 30), 1, border_radius=3)

            gl = self.font_xs.render(f"{g}X", True, t["text_med"])
            s.blit(gl, (gx + (gw - gl.get_width()) // 2, gy + 35))
            
            # Simple placeholder for gain bars
            pygame.draw.rect(s, t["border"], (gx + 8, gy + 4, gw - 16, 22), border_radius=2)
            if g < cur_gain or (g == cur_gain and status != "testing"):
                pygame.draw.rect(s, t["primary_dim"], (gx + 8, gy + 4, gw - 16, 22), border_radius=2)

        # Bottom status with ETA
        eta = cal.get("eta", "")
        if eta:
            self.draw_glow_text(f"ESTIMATED: {eta}", self.font_sm, t["text_dim"], ((W - self.font_sm.size(f"ESTIMATED: {eta}")[0]) // 2, H - 32))

        hint = "KEEP CAR INTERIOR QUIET FOR BEST RESULTS"
        self.draw_glow_text(hint, self.font_xs, t["text_dim"], ((W - self.font_xs.size(hint)[0]) // 2, H - 16))
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
        
        # Start persistent camera capture if not running or wrong index
        if self.camera_cap is None or self.camera_cap.poll() is not None:
            try:
                # Find the requested camera device
                cam_dev = f"/dev/video{self.camera_idx*2}" # common mapping on Pi
                try:
                    r = subprocess.run(["v4l2-ctl", "--list-devices"],
                                       capture_output=True, text=True, timeout=3)
                    lines = r.stdout.split("\n")
                    found_devs = []
                    current_bus = ""
                    for line in lines:
                        if ":" in line and not line.startswith("\t"):
                            current_bus = line.lower()
                        elif line.strip().startswith("/dev/video"):
                            dev = line.strip()
                            if "bcm2835" in current_bus or "unicam" in current_bus:
                                continue
                            # Check caps
                            res = subprocess.run(["v4l2-ctl", "--device", dev, "--all"],
                                                 capture_output=True, text=True, timeout=2)
                            if "Device Caps      : 0x04200001" in res.stdout:
                                found_devs.append(dev)
                    
                    found_devs = sorted(list(set(found_devs)))
                    if self.camera_idx < len(found_devs):
                        cam_dev = found_devs[self.camera_idx]
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
                self.camera_frame = None # clear old frame
            except Exception:
                s.fill(t["bg"])
                msg = self.font_md.render("Camera unavailable", True, AMBER)
                s.blit(msg, ((W - msg.get_width()) // 2, H // 2))
                return

        # Label for which camera we are seeing
        cam_label = f"CAMERA {self.camera_idx}"
        cam_frame_size = self._cam_w * self._cam_h * 3
        try:
            raw = self.camera_cap.stdout.read(cam_frame_size)
            if raw and len(raw) == cam_frame_size:
                small = pygame.image.fromstring(raw, (self._cam_w, self._cam_h), "RGB")
                frame = pygame.transform.scale(small, (W, H))
                s.blit(frame, (0, 0))
                self.camera_frame = frame
                
                # Draw camera label
                lt = self.font_sm.render(f"CAMERA {self.camera_idx}", True, (255, 255, 255))
                pygame.draw.rect(s, (0, 0, 0, 150), (10, 10, lt.get_width() + 10, lt.get_height() + 4))
                s.blit(lt, (15, 12))
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
        print("     Car-HUD - Terminal")
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

        # Screenshot on request (for HTTP server) — BMP for speed in RAM disk
        try:
            req_path = "/dev/shm/car-hud-screenshot-request"
            if os.path.exists(req_path):
                pygame.image.save(self.surf, "/dev/shm/car-hud-screenshot.bmp")
                os.remove(req_path)
        except Exception:
            pass

    def run(self):
        theme_check_timer = 0

        while self.running:
            # Process touch events from touch_service
            try:
                with open("/tmp/car-hud-touch") as tf:
                    td = json.load(tf)
                    if time.time() - td.get("time", 0) < 0.5 and td["time"] != getattr(self, '_last_touch_time', 0):
                        self._last_touch_time = td["time"]
                        g = td.get("gesture", "")
                        ty = td.get("y", 0)
                        if g == "tap":
                            if ty < self.height - 30:
                                self.page_idx = (self.page_idx + 1) % len(self.page_names)
                                self.force_page = self.page_names[self.page_idx]
                            else:
                                themes = list(THEMES.keys())
                                ci = themes.index(self.theme_name) if self.theme_name in themes else 0
                                self.set_theme(themes[(ci + 1) % len(themes)])
                        elif g in ("swipe_left", "swipe_right"):
                            if g == "swipe_right":
                                self.page_idx = (self.page_idx - 1) % len(self.page_names)
                            else:
                                self.page_idx = (self.page_idx + 1) % len(self.page_names)
                            self.force_page = self.page_names[self.page_idx]
            except Exception:
                pass

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
                        if not self.show_camera:
                            # Start showing camera 0
                            self.show_camera = True
                            self.camera_idx = 0
                            # Stop dashcam to free the webcam device
                            subprocess.run(["sudo", "systemctl", "stop", "car-hud-dashcam"],
                                           capture_output=True, timeout=5)
                            time.sleep(0.5)
                        else:
                            # Already showing a camera, try to move to next or turn off
                            # Check how many cameras are available
                            cam_count = 1
                            try:
                                with open("/tmp/car-hud-dashcam-data") as f:
                                    cd = json.load(f)
                                    cam_count = cd.get("cam_count", 1)
                            except Exception:
                                pass
                            
                            self.camera_idx += 1
                            if self.camera_idx >= cam_count:
                                # Wrap around to off
                                self.show_camera = False
                                if self.camera_cap:
                                    self.camera_cap.kill()
                                    self.camera_cap = None
                                subprocess.run(["sudo", "systemctl", "start", "car-hud-dashcam"],
                                               capture_output=True, timeout=5)
                            else:
                                # Switch to next camera
                                if self.camera_cap:
                                    self.camera_cap.kill()
                                    self.camera_cap = None
                                # draw_camera_view will pick up the new self.camera_idx
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
                            ["python3", "/home/chrismslist/car-hud/calibrate.py"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    elif event.key == K_SLASH or event.key == K_QUESTION:
                        # Show keyboard shortcuts
                        signal_hud_file("show", "keys")

            self.surf.fill(self.t["bg"])
            stats = self.get_system_stats()
            obd = self.get_obd_data()
            music = self.get_music_data()

            # Smooth OBD data for animations
            target_data = obd.get("data", {})
            for k, v in target_data.items():
                if k not in self.smooth_data:
                    self.smooth_data[k] = v
                else:
                    # Faster smoothing for RPM/Speed, slower for temps
                    factor = 0.25 if k in ["RPM", "SPEED", "ENGINE_LOAD", "THROTTLE_POS"] else 0.08
                    self.smooth_data[k] = self.smooth_data[k] + (v - self.smooth_data[k]) * factor

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

            # Page selection: touch override or auto-detect from OBD
            show_vehicle = obd["connected"] and obd.get("data")
            if self.force_page == "vehicle":
                show_vehicle = True
            elif self.force_page == "system":
                show_vehicle = False

            if show_vehicle:
                self.draw_vehicle_page(obd, music)
            else:
                self.draw_system_page(stats, music)

            self.draw_status_strip(obd)

            # Check voice signal for overlays (help, keys, camera, save)
            try:
                with open("/tmp/car-hud-voice-signal") as vs:
                    vsig = json.load(vs)
                    if time.time() - vsig.get("time", 0) < 10:
                        if vsig.get("action") == "save" and vsig.get("target") == "dashcam":
                            # Draw 'CLIP SAVED' overlay
                            self.draw_glow_text("CLIP SAVED", self.font_lg, GREEN, 
                                               ((self.width - self.font_lg.size("CLIP SAVED")[0]) // 2, 40))
                        elif vsig.get("action") == "show" and vsig.get("target") == "help":
                            self.draw_help_overlay()
                            self.present()
                            self.clock_t.tick(30)
                            continue
                        elif vsig.get("action") == "show" and vsig.get("target") == "keys":
                            self.draw_keys_overlay()
                            self.present()
                            self.clock_t.tick(30)
                            continue
                        elif vsig.get("action") == "widget":
                            # Voice widget control: "show/hide <name> widget"
                            raw = vsig.get("raw", "").lower()
                            import widgets as _widgets
                            for wmod in _widgets.get_all():
                                wn = wmod["name"].lower()
                                if wn in raw:
                                    enable = vsig.get("target") == "show"
                                    _widgets.set_enabled(wn, enable)
                                    break
                        elif vsig.get("action") == "system" and vsig.get("target") == "calibrate":
                            subprocess.Popen(
                                ["python3", "/home/chrismslist/car-hud/calibrate.py"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        elif vsig.get("action") == "show" and vsig.get("target") == "camera":
                            if not self.show_camera:
                                # Start showing camera 0
                                subprocess.run(["sudo", "systemctl", "stop", "car-hud-dashcam"],
                                               capture_output=True, timeout=5)
                                time.sleep(0.5)
                                self.show_camera = True
                                self.camera_idx = 0
                            else:
                                # Already showing, cycle to next
                                cam_count = 1
                                try:
                                    with open("/tmp/car-hud-dashcam-data") as f:
                                        cd = json.load(f)
                                        cam_count = cd.get("cam_count", 1)
                                except Exception:
                                    pass
                                
                                self.camera_idx += 1
                                if self.camera_idx >= cam_count:
                                    self.show_camera = False
                                    if self.camera_cap:
                                        self.camera_cap.kill()
                                        self.camera_cap = None
                                    subprocess.run(["sudo", "systemctl", "start", "car-hud-dashcam"],
                                                   capture_output=True, timeout=5)
                                else:
                                    if self.camera_cap:
                                        self.camera_cap.kill()
                                        self.camera_cap = None
                                    # draw_camera_view will pick up the new self.camera_idx
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
