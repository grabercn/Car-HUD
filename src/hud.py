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
    "blue": {  # Honda 2014 Default Blue (High Contrast)
        "primary":    (0, 200, 255),     # Vibrant cyan-blue
        "primary_dim":(0, 90, 160),
        "accent":     (0, 150, 240),
        "bg":         (4, 8, 16),
        "panel":      (10, 16, 32),
        "border":     (30, 55, 100),     # Visible gauge tracks
        "border_lite":(22, 42, 75),
        "text_bright":(240, 250, 255),   # Crisp white with blue tint
        "text_med":   (160, 210, 255),   # Legible light blue
        "text_dim":   (100, 150, 200),   # Muted blue
    },
    "red": {  # Honda 2014 Sport Red
        "primary":    (255, 40, 40),     # Glowing crimson red
        "primary_dim":(160, 20, 20),
        "accent":     (220, 30, 30),
        "bg":         (12, 4, 4),        # Deep red-black
        "panel":      (28, 8, 8),
        "border":     (80, 20, 20),
        "border_lite":(60, 15, 15),
        "text_bright":(255, 230, 230),   # Crisp white with red tint
        "text_med":   (255, 160, 160),
        "text_dim":   (200, 100, 100),
    },
    "green": {  # Honda 2014 Eco Green
        "primary":    (30, 240, 120),    # Vibrant eco green
        "primary_dim":(15, 140, 70),
        "accent":     (20, 200, 100),
        "bg":         (4, 12, 6),        # Very dark green-black
        "panel":      (8, 24, 12),
        "border":     (20, 70, 30),
        "border_lite":(15, 50, 25),
        "text_bright":(230, 255, 240),
        "text_med":   (150, 240, 180),
        "text_dim":   (100, 180, 120),
    },
    "amber": {  # Classic Honda Amber
        "primary":    (255, 160, 0),     # Glowing amber
        "primary_dim":(150, 90, 0),
        "accent":     (220, 130, 0),
        "bg":         (12, 8, 2),        # Very dark amber-black
        "panel":      (28, 18, 5),
        "border":     (80, 50, 15),
        "border_lite":(60, 35, 10),
        "text_bright":(255, 245, 210),
        "text_med":   (255, 200, 110),
        "text_dim":   (200, 140, 60),
    },
    "day": {  # Ultra-high contrast for bright sunlight
        "primary":    (0, 120, 255),     # Deep blue on white
        "primary_dim":(150, 150, 150),
        "accent":     (20, 20, 20),
        "bg":         (245, 245, 250),   # Very bright cool white
        "panel":      (230, 230, 235),
        "border":     (140, 140, 155),   # Darker gauge tracks for visibility
        "border_lite":(170, 170, 185),
        "text_bright":(10, 10, 15),
        "text_med":   (60, 60, 70),
        "text_dim":   (100, 100, 110),
    },
    "night": {  # Honda 2014 Night Mode (Minimal glare)
        "primary":    (0, 100, 180),
        "primary_dim":(0, 50, 90),
        "accent":     (0, 80, 140),
        "bg":         (2, 4, 6),
        "panel":      (5, 8, 12),
        "border":     (20, 35, 55),      # Brighter gauge tracks for visibility
        "border_lite":(15, 28, 45),
        "text_bright":(140, 180, 210),   # Dimmed white
        "text_med":   (90, 130, 160),
        "text_dim":   (60, 90, 120),
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

        # Always render at 480x320, scale to display
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
        """Read OBD data — skip re-parse if file hasn't changed."""
        obd_path = "/tmp/car-hud-obd-data"
        try:
            mt = os.path.getmtime(obd_path)
            if hasattr(self, '_obd_cache_mt') and mt == self._obd_cache_mt:
                return self._obd_cache  # file unchanged, reuse
            with open(obd_path) as f:
                data = json.load(f)
            if time.time() - data.get("timestamp", 0) < 10:
                self._obd_cache = data
                self._obd_cache_mt = mt
                return data
        except Exception:
            pass
        return {"connected": False, "status": "offline", "data": {},
                "warnings": [], "dtcs": []}

    def get_music_data(self):
        music_path = "/tmp/car-hud-music-data"
        try:
            mt = os.path.getmtime(music_path)
            if hasattr(self, '_music_cache_mt') and mt == self._music_cache_mt:
                return self._music_cache
            with open(music_path) as f:
                data = json.load(f)
            if time.time() - data.get("timestamp", 0) < 30:
                self._music_cache = data
                self._music_cache_mt = mt
                return data
        except Exception:
            pass
        return {"playing": False}

    def get_system_stats(self):
        """System stats — cached for 2 seconds."""
        now = time.time()
        if hasattr(self, '_stats_cache') and now - self._stats_cache_t < 2:
            return self._stats_cache
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
        self._stats_cache = stats
        self._stats_cache_t = now
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
        """Draw text with shadow — cached for performance."""
        if not hasattr(self, '_text_cache'):
            self._text_cache = {}
        key = (text, id(font), color)
        if key not in self._text_cache:
            if glow_color is None:
                glow_color = (0, 0, 0)
            mt = font.render(text, True, color)
            w, h = mt.get_width() + 2, mt.get_height() + 2
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            st = font.render(text, True, glow_color)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                surf.blit(st, (1 + dx, 1 + dy))
            surf.blit(mt, (1, 1))
            self._text_cache[key] = surf
            # Cap cache at 200 entries
            if len(self._text_cache) > 200:
                self._text_cache.clear()
        self.surf.blit(self._text_cache[key], (pos[0] - 1, pos[1] - 1))

    def draw_arc_gauge(self, cx, cy, radius, thickness, pct, color, bg_color=None,
                       start=math.pi, end=0, ticks=False):
        s = self.surf
        bg = bg_color or self.t["border"]
        start_angle = start
        end_angle = end
        steps = 30  # reduced from 40 — still smooth, fewer draws

        # Pre-computed segments (cached)
        if not hasattr(self, '_arc_cache'):
            self._arc_cache = {}
        arc_key = (cx, cy, radius, start_angle, end_angle, steps)
        if arc_key not in self._arc_cache:
            segs = []
            for i in range(steps):
                t1 = i / steps
                t2 = (i + 1) / steps
                a1 = start_angle + (end_angle - start_angle) * t1
                a2 = start_angle + (end_angle - start_angle) * t2
                segs.append((
                    int(cx + radius * math.cos(a1)), int(cy - radius * math.sin(a1)),
                    int(cx + radius * math.cos(a2)), int(cy - radius * math.sin(a2))
                ))
            tick_segs = []
            if ticks:
                for i in range(11):
                    a = start_angle + (end_angle - start_angle) * (i / 10)
                    tick_segs.append((
                        int(cx + (radius - thickness//2) * math.cos(a)),
                        int(cy - (radius - thickness//2) * math.sin(a)),
                        int(cx + (radius + thickness//2 + 3) * math.cos(a)),
                        int(cy - (radius + thickness//2 + 3) * math.sin(a))
                    ))
            self._arc_cache[arc_key] = (segs, tick_segs)

        segs, tick_segs = self._arc_cache[arc_key]

        # Pre-rendered background surface (bg arcs + ticks — never changes per theme)
        if not hasattr(self, '_arc_bg_cache'):
            self._arc_bg_cache = {}
        bg_key = (arc_key, bg, self.theme_name, ticks)
        if bg_key not in self._arc_bg_cache:
            # Render bg + ticks to a surface once
            # Find bounding box
            all_pts = [(x1, y1) for x1, y1, x2, y2 in segs] + [(x2, y2) for x1, y1, x2, y2 in segs]
            min_x = min(p[0] for p in all_pts) - thickness
            min_y = min(p[1] for p in all_pts) - thickness
            max_x = max(p[0] for p in all_pts) + thickness + 4
            max_y = max(p[1] for p in all_pts) + thickness + 4
            bw, bh = max_x - min_x, max_y - min_y
            bg_surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            for x1, y1, x2, y2 in segs:
                pygame.draw.line(bg_surf, bg, (x1 - min_x, y1 - min_y), (x2 - min_x, y2 - min_y), thickness)
            if ticks:
                for x1, y1, x2, y2 in tick_segs:
                    pygame.draw.line(bg_surf, self.t["border_lite"], (x1 - min_x, y1 - min_y), (x2 - min_x, y2 - min_y), 1)
            self._arc_bg_cache[bg_key] = (bg_surf, min_x, min_y)

        # Blit pre-rendered background (1 blit vs 40+ line draws)
        bg_surf, ox, oy = self._arc_bg_cache[bg_key]
        s.blit(bg_surf, (ox, oy))

        # Draw ONLY the dynamic fill arc (the part that changes)
        fill_steps = max(1, int(steps * min(pct, 1.0)))
        for i in range(fill_steps):
            x1, y1, x2, y2 = segs[i]
            t = i / steps
            if pct > 0.85 and t > 0.85: c = RED
            elif pct > 0.7 and t > 0.7: c = AMBER
            else: c = color
            pygame.draw.line(s, c, (x1, y1), (x2, y2), thickness)

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
        now_t = time.time()

        # Minimalist compact status pill
        sy = H - 30

        # Color scheme: primary=connected, amber=service running, dark=(30,30,30)=off
        OFF = (30, 30, 30)

        # MIC — primary if voice active, amber if hardware present, off otherwise
        ac = OFF
        voice_running = False
        has_mic = False
        for i in range(5):
            p = f"/proc/asound/card{i}/id"
            if os.path.exists(p):
                try:
                    with open(p) as f:
                        cid = f.read().strip()
                        if cid in ("Audio", "Card"):
                            has_mic = True
                except Exception:
                    pass
        try:
            lvl_age = time.time() - os.path.getmtime("/tmp/car-hud-mic-level")
            voice_running = lvl_age < 15
        except Exception:
            pass
        if has_mic and voice_running:
            ac = t["primary"]
        elif has_mic:
            ac = AMBER

        # OBD — primary=data flowing, amber=service running, off=down
        if obd["connected"] and obd.get("data"):
            oc = t["primary"]
        elif obd.get("status") and obd["status"] not in ("offline", ""):
            oc = AMBER
        else:
            oc = OFF

        # PHN — check for PHONE connection (not OBD adapter), cached 5s
        music = self.get_music_data()
        if not hasattr(self, '_bt_cache_time'):
            self._bt_cache_time = 0
            self._bt_state = "off"
        if now_t - self._bt_cache_time > 5:
            self._bt_cache_time = now_t
            try:
                import subprocess as _sp
                r = _sp.run(["bluetoothctl", "devices", "Connected"],
                            capture_output=True, text=True, timeout=3)
                phone_found = False
                for line in r.stdout.splitlines():
                    parts = line.split(" ", 2)
                    if len(parts) < 2:
                        continue
                    name = parts[2] if len(parts) > 2 else ""
                    if any(x in name.lower() for x in ["vlink", "obd", "elm", "icar"]):
                        continue
                    info = _sp.run(["bluetoothctl", "info", parts[1]],
                                   capture_output=True, text=True, timeout=2)
                    if "Icon: phone" in info.stdout:
                        phone_found = True
                        break
                if phone_found:
                    self._bt_state = "connected"
                else:
                    bt_state = _sp.run(["bluetoothctl", "show"],
                                       capture_output=True, text=True, timeout=2)
                    self._bt_state = "on" if "Powered: yes" in bt_state.stdout else "off"
            except Exception:
                pass
        phone_c = t["primary"] if self._bt_state == "connected" else AMBER if self._bt_state == "on" else OFF

        # NET — primary=connected, amber=connecting, off=down
        nc = OFF
        try:
            with open("/tmp/car-hud-wifi-data") as f:
                wd = json.load(f)
                ws = wd.get("state", "")
                if ws in ("connected", "tethered"):
                    nc = t["primary"]
                elif ws == "connecting":
                    nc = AMBER
        except Exception:
            pass

        # CAM — red blink=recording, primary=camera present, amber=service running, off=none
        cam_c = OFF
        try:
            with open("/tmp/car-hud-dashcam-data") as f:
                cd = json.load(f)
                if time.time() - cd.get("timestamp", 0) < 60:
                    if cd.get("recording"):
                        cam_c = RED if int(time.time() * 2) % 2 == 0 else (120, 0, 0)
                    elif cd.get("cam_count", 0) > 0:
                        cam_c = t["primary"]
                    else:
                        cam_c = AMBER
        except Exception:
            pass
        if cam_c == OFF and os.path.exists("/dev/video0"):
            cam_c = t["primary"]  # camera present = blue

        modules = [("mic", ac), ("obd", oc), ("phn", phone_c),
                   ("net", nc), ("cam", cam_c)]

        # ── Icon-only status strip — bold, legible ──
        pygame.draw.line(s, t["border_lite"], (0, sy + 1), (W, sy + 1))
        iw = W // len(modules)
        for i, (icon, color) in enumerate(modules):
            cx_i = i * iw + iw // 2
            cy_i = sy + 14

            if icon == "mic":
                # Microphone — bold pill + base
                pygame.draw.rect(s, color, (cx_i - 3, cy_i - 8, 6, 11), border_radius=3)
                pygame.draw.arc(s, color, (cx_i - 6, cy_i - 5, 12, 12), 3.14, 6.28, 2)
                pygame.draw.line(s, color, (cx_i, cy_i + 6), (cx_i, cy_i + 9), 2)
                pygame.draw.line(s, color, (cx_i - 3, cy_i + 9), (cx_i + 3, cy_i + 9), 2)
            elif icon == "obd":
                # Car — simple side view
                pygame.draw.rect(s, color, (cx_i - 8, cy_i - 2, 16, 7), border_radius=2)
                pygame.draw.rect(s, color, (cx_i - 5, cy_i - 6, 10, 5), border_radius=2)
                pygame.draw.circle(s, color, (cx_i - 5, cy_i + 6), 3)
                pygame.draw.circle(s, color, (cx_i + 5, cy_i + 6), 3)
            elif icon == "phn":
                # Phone — bold rectangle
                pygame.draw.rect(s, color, (cx_i - 4, cy_i - 9, 8, 18), border_radius=3)
                pygame.draw.rect(s, t["bg"], (cx_i - 2, cy_i - 6, 4, 12), border_radius=1)
                pygame.draw.line(s, color, (cx_i - 1, cy_i + 6), (cx_i + 1, cy_i + 6), 2)
            elif icon == "net":
                # WiFi — bold arcs
                for r in [4, 8, 12]:
                    pygame.draw.arc(s, color, (cx_i - r, cy_i - r + 4, r * 2, r * 2), 0.4, 2.7, 2)
                pygame.draw.circle(s, color, (cx_i, cy_i + 4), 2)
            elif icon == "cam":
                # Camera — bold body + lens
                pygame.draw.rect(s, color, (cx_i - 7, cy_i - 5, 14, 10), border_radius=3)
                pygame.draw.circle(s, color, (cx_i - 1, cy_i), 4, 2)
                pygame.draw.rect(s, color, (cx_i + 6, cy_i - 3, 5, 6))

        # Mic level — subtle glow under mic icon
        self._read_voice_signal()
        if self.mic1_level > 0.01 or self.mic2_level > 0.01:
            lvl = max(self.mic1_level, self.mic2_level)
            lc = t["primary"] if lvl < 0.3 else GREEN if lvl < 0.6 else AMBER
            fw = max(2, int(iw * 0.6 * lvl))
            mic_cx = iw // 2
            pygame.draw.rect(s, lc, (mic_cx - fw // 2, sy + 2, fw, 2), border_radius=1)

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
            # Pre-allocated scale target — avoids Surface creation every frame
            if not hasattr(self, '_scale_surf'):
                self._scale_surf = pygame.Surface((self.display_w, self.display_h))
            pygame.transform.scale(self.surf, (self.display_w, self.display_h), self._scale_surf)
            self.screen.blit(self._scale_surf, (0, 0))
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
        theme_check_timer = 55  # check theme almost immediately on boot

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

            # Smooth OBD data — near-instant for driving-critical values
            target_data = obd.get("data", {})
            sd = self.smooth_data
            for k, v in target_data.items():
                if k not in sd:
                    sd[k] = v
                elif k == "SPEED":
                    sd[k] += (v - sd[k]) * 0.85  # ~2 frames to reach target
                elif k == "RPM":
                    sd[k] += (v - sd[k]) * 0.8   # ~2-3 frames
                elif k in ("ENGINE_LOAD", "THROTTLE_POS"):
                    sd[k] += (v - sd[k]) * 0.7   # ~3 frames
                elif k in ("FUEL_LEVEL", "HYBRID_BATTERY_REMAINING"):
                    sd[k] += (v - sd[k]) * 0.15  # slow — fuel doesn't jump
                else:
                    sd[k] += (v - sd[k]) * 0.1   # temps, voltage — gradual

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
                    # Clear render caches on theme change
                    if hasattr(self, '_text_cache'):
                        self._text_cache.clear()
                    if hasattr(self, '_arc_cache'):
                        self._arc_cache.clear()

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
                # No status strip on OBD page — more room for widgets
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


if __name__ == "__main__":
    hud = CarHUD()
    hud.run()
