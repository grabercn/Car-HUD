#!/usr/bin/env python3
"""Generate premium Honda Accord boot splash screen for 2.5-inch TFT."""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import math

W, H = 480, 320
img = Image.new("RGB", (W, H), (0, 0, 0))
draw = ImageDraw.Draw(img)

# -- Premium dark gradient background --
# Subtle radial gradient: deep black center fading to very dark charcoal
cx, cy = W // 2, H // 2 - 20
max_r = math.sqrt(cx**2 + cy**2)
for r in range(int(max_r), 0, -2):
    ratio = r / max_r
    # Very subtle warm dark gradient
    base = int(12 * (1 - ratio * ratio))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(base, base, base + 2))

# -- Load and place Honda logo --
logo = Image.open("/home/chrismslist/car-hud/honda_logo.png").convert("RGBA")

# Resize logo to fit nicely on a small screen
logo_h = 100
aspect = logo.width / logo.height
logo_w = int(logo_h * aspect)
logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

# Create a subtle glow behind the logo
glow = Image.new("RGBA", (logo_w + 60, logo_h + 60), (0, 0, 0, 0))
glow_draw = ImageDraw.Draw(glow)
# Draw soft white ellipse for glow effect
for i in range(30, 0, -1):
    alpha = int(18 * (1 - i / 30))
    glow_draw.ellipse(
        [30 - i, 30 - i, logo_w + 30 + i, logo_h + 30 + i],
        fill=(160, 200, 240, alpha)
    )

# Composite glow then logo
logo_x = (W - logo_w) // 2
logo_y = H // 2 - logo_h // 2 - 30

glow_x = logo_x - 30
glow_y = logo_y - 30
img.paste(Image.new("RGB", (glow.width, glow.height), (0, 0, 0)),
          (glow_x, glow_y),
          glow.split()[3])

# Blend the glow
glow_rgb = Image.new("RGB", img.size, (0, 0, 0))
glow_full = Image.new("RGBA", img.size, (0, 0, 0, 0))
glow_full.paste(glow, (glow_x, glow_y))
for px in range(glow_x, glow_x + glow.width):
    for py in range(glow_y, glow_y + glow.height):
        if 0 <= px < W and 0 <= py < H:
            gr, gg, gb, ga = glow_full.getpixel((px, py))
            if ga > 0:
                or_, og, ob = img.getpixel((px, py))
                blend = ga / 255.0
                nr = min(255, int(or_ + gr * blend))
                ng = min(255, int(og + gg * blend))
                nb = min(255, int(ob + gb * blend))
                img.putpixel((px, py), (nr, ng, nb))

# Paste the Honda logo
img.paste(logo, (logo_x, logo_y), logo.split()[3])

# -- Text: "ACCORD" in clean automotive style --
draw = ImageDraw.Draw(img)

# Use Liberation Sans which is clean and geometric like Honda's font
try:
    font_accord = ImageFont.truetype("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf", 32)
except Exception:
    try:
        font_accord = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 32)
    except Exception:
        font_accord = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)

# "A C C O R D" with letter spacing for that premium OEM feel
accord_text = "A C C O R D"
accord_y = logo_y + logo_h + 15

# Draw with subtle chrome-like color
bbox = draw.textbbox((0, 0), accord_text, font=font_accord)
tw = bbox[2] - bbox[0]
tx = (W - tw) // 2

# Subtle shadow
draw.text((tx + 1, accord_y + 1), accord_text, fill=(20, 20, 25), font=font_accord)
# Main text - silver/chrome color
draw.text((tx, accord_y), accord_text, fill=(210, 215, 225), font=font_accord)

# -- Thin elegant separator line --
line_y = accord_y + 35
line_w = 140
line_x = (W - line_w) // 2
# Gradient line effect
for i in range(line_w):
    ratio = 1 - abs(i - line_w // 2) / (line_w // 2)
    c = int(80 * ratio)
    draw.line([(line_x + i, line_y), (line_x + i, line_y)], fill=(c, c, c + 10))

img.save("/home/chrismslist/car-hud/splash.png", quality=95)
print("Premium 480x320 Honda Accord splash generated!")
