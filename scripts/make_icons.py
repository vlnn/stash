"""Draws stash.png, the 📒 emoji on a tile like icon.png: uv run --with pillow python scripts/make_icons.py"""

import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
EMOJI_SIZE = 109
STASH_EMOJI = "📒"
SIZE = 256
TILE = (43, 68, 87)


def tile(side):
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ImageDraw.Draw(image).rounded_rectangle((0, 0, side - 1, side - 1), radius=side * 0.22, fill=TILE)
    return image


def emoji(glyph):
    font = ImageFont.truetype(EMOJI_FONT, EMOJI_SIZE)
    left, top, right, bottom = font.getbbox(glyph)
    image = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
    ImageDraw.Draw(image).text((-left, -top), glyph, font=font, embedded_color=True)
    return image


def centered(background, foreground, scale):
    side = background.width
    target = int(side * scale)
    glyph = foreground.resize((target, int(target * foreground.height / foreground.width)), Image.LANCZOS)
    offset = ((side - glyph.width) // 2, (side - glyph.height) // 2)
    background.alpha_composite(glyph, offset)
    return background


def stash_icon():
    return centered(tile(SIZE), emoji(STASH_EMOJI), 0.72)


if __name__ == "__main__":
    stash_icon().save(os.path.join(ROOT, "stash.png"))
