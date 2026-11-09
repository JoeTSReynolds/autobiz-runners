"""Safe margins for 1080x1920 Shorts (some phones crop or zoom a little, YouTube draws its own overlay at the bottom) and a text fitter.

    SAFE_X: keep text this far from the left and right edge; SAFE_TOP: from the top; SAFE_BOTTOM: nothing important in the last N px.
    fit_lines(text, size, max_w, max_lines, floor=44) -> (lines, size): the whole text, never cut.
"""
from PIL import Image, ImageDraw
from .. import captions as C

SAFE_X, SAFE_TOP, SAFE_BOTTOM = 70, 110, 260
_D = ImageDraw.Draw(Image.new("RGBA", (1, 1)))


def _wrap(text, f, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if cur and _D.textlength(t, font=f) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + [cur] if cur else lines


def fit_lines(text, size, max_w, max_lines, floor=44):
    """Wrap text to max_w px; shrink the font 4 px at a time until it fits max_lines. At the floor it wraps onto more lines rather than drop a word."""
    size = max(size, floor)
    while True:
        lines = _wrap(text, C.font(size), max_w)
        if len(lines) <= max_lines or size == floor:
            return lines, size
        size = max(size - 4, floor)
