"""Music / Now Playing widget."""

import os
import time
import pygame

name = "Music"
priority = 0  # highest — always show first


def is_active(hud, music):
    return music.get("playing", False)


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t
    track = music.get("track", "")
    artist = music.get("artist", "")

    # Album art
    art_size = min(h, 55)
    art_loaded = False
    try:
        art_file = "/home/chrismslist/car-hud/current_art.jpg"
        if os.path.exists(art_file) and os.path.getsize(art_file) > 100:
            from PIL import Image as PILImage
            pil = PILImage.open(art_file).convert("RGB")
            pil = pil.resize((art_size, art_size), PILImage.LANCZOS)
            art_surf = pygame.image.fromstring(pil.tobytes(), (art_size, art_size), "RGB")
            s.blit(art_surf, (x, y))
            art_loaded = True
    except Exception:
        pass

    if not art_loaded:
        pygame.draw.rect(s, t["border"], (x, y, art_size, art_size), border_radius=4)
        ncx, ncy = x + art_size // 2, y + art_size // 2
        pygame.draw.ellipse(s, t["primary"], (ncx - 8, ncy + 2, 10, 8))
        pygame.draw.line(s, t["primary"], (ncx + 1, ncy + 5), (ncx + 1, ncy - 14), 2)
        pygame.draw.line(s, t["primary"], (ncx + 1, ncy - 14), (ncx + 7, ncy - 10), 2)

    tx = x + art_size + 6
    tw = w - art_size - 10
    max_c = max(10, tw // 7)

    has_cjk = any(ord(c) > 0x2E80 for c in track)
    track_font = hud.font_cjk if has_cjk and hud.font_cjk else hud.font_md
    tt = track_font.render(track[:max_c], True, t["text_bright"])
    s.blit(tt, (tx, y))

    has_cjk_a = any(ord(c) > 0x2E80 for c in artist)
    artist_font = hud.font_cjk_sm if has_cjk_a and hasattr(hud, "font_cjk_sm") and hud.font_cjk_sm else hud.font_sm
    at = artist_font.render(artist[:max_c], True, t["text_med"])
    s.blit(at, (tx, y + 18))

    # Progress
    prog = max(0, music.get("progress", 0))
    dur = max(0, music.get("duration", 0))
    if prog == 0 and dur > 0 and music.get("timestamp"):
        prog = min(time.time() - music["timestamp"], dur)

    if dur > 0:
        pbar_y = y + 36
        pygame.draw.rect(s, t["border"], (tx, pbar_y, tw, 4), border_radius=2)
        fw = int(tw * min(prog / dur, 1))
        if fw > 0:
            pygame.draw.rect(s, t["primary"], (tx, pbar_y, fw, 4), border_radius=2)

        prog_m, prog_s = int(prog) // 60, int(prog) % 60
        dur_m, dur_s = int(dur) // 60, int(dur) % 60
        time_t = hud.font_sm.render(f"{prog_m}:{prog_s:02d} / {dur_m}:{dur_s:02d}", True, t["text_med"])
        s.blit(time_t, (tx, pbar_y + 6))

    dev_name = music.get("device", "")
    if dev_name:
        dt = hud.font_sm.render(dev_name, True, t["text_dim"])
        dt_y = y + 36 + 6 if dur > 0 else y + 36
        s.blit(dt, (tx + tw - dt.get_width(), dt_y))

    return True
