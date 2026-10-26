"""Draws docs/gifs/<scenario>-<theme>.gif, one frame per keystroke of each docs/scenarios.py scenario, dark and light:

    uv run --with pillow python scripts/make_gifs.py

Every frame is what Alfred would show, rendered from the Script Filter JSON that run.py search prints.
"""

import os
import sys
from typing import NamedTuple

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from docs.scenarios import GIFS_DIR, SCENARIOS, keystrokes, search_items  # noqa: E402

WIDTH, PADDING, QUERY_HEIGHT, ROW_HEIGHT, CAPTION_HEIGHT, MAX_ROWS = 720, 16, 56, 52, 28, 4
KEYWORD = "st "
KEYSTROKE_MS, LANDING_MS = 280, 2600
FONTS = ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial Unicode.ttf")


class Theme(NamedTuple):
    background: str
    selected: str
    divider: str
    text: str
    selected_text: str
    dim: str
    caption: str


THEMES = {
    "dark": Theme("#1f2125", "#2f5fd0", "#33363c", "#f2f2f2", "#f2f2f2", "#9a9ea6", "#6f7580"),
    "light": Theme("#f7f7f8", "#3b6fe0", "#d9dadf", "#1c1d21", "#ffffff", "#6b7079", "#8a8f99"),
}


def font(size):
    for path in FONTS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def frame_height():
    return PADDING * 2 + QUERY_HEIGHT + ROW_HEIGHT * MAX_ROWS + CAPTION_HEIGHT


def frame(query, items, caption, theme):
    image = Image.new("RGB", (WIDTH, frame_height()), theme.background)
    draw = ImageDraw.Draw(image)
    draw_query(draw, query, theme)
    for index, item in enumerate(items[:MAX_ROWS]):
        draw_row(draw, PADDING + QUERY_HEIGHT + ROW_HEIGHT * index, item, index == 0, theme)
    draw.text((PADDING, frame_height() - CAPTION_HEIGHT - 2), caption, font=font(13), fill=theme.caption)
    return image


def draw_query(draw, query, theme):
    draw.text((PADDING, PADDING + 8), KEYWORD + query, font=font(26), fill=theme.text)
    draw.line((0, PADDING + QUERY_HEIGHT - 1, WIDTH, PADDING + QUERY_HEIGHT - 1), fill=theme.divider)


def draw_row(draw, top, item, selected, theme):
    if selected:
        draw.rectangle((0, top, WIDTH, top + ROW_HEIGHT), fill=theme.selected)
    text = theme.selected_text if selected else theme.text
    subtitle = theme.selected_text if selected else theme.dim
    draw.text((PADDING, top + 7), item["title"], font=font(17), fill=text)
    draw.text((PADDING, top + 31), clipped(item.get("subtitle", "")), font=font(12), fill=subtitle)


def clipped(text, limit=96):
    return text if len(text) <= limit else text[: limit - 1] + "…"


def frames_of(scenario, theme):
    queries = ["", *keystrokes(scenario.typed)]
    return [frame(query, search_items(query, scenario.today), scenario.shows, theme) for query in queries]


def save_gif(frames, path):
    durations = [KEYSTROKE_MS] * (len(frames) - 1) + [LANDING_MS]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)


def make_gifs():
    os.makedirs(GIFS_DIR, exist_ok=True)
    for scenario in SCENARIOS:
        for name, theme in THEMES.items():
            path = os.path.join(GIFS_DIR, f"{scenario.name}-{name}.gif")
            save_gif(frames_of(scenario, theme), path)
            print(os.path.relpath(path, ROOT))


if __name__ == "__main__":
    make_gifs()
