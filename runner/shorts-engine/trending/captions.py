"""Text layers for 1080x1920 shorts (Pillow). Every layer has:

    layer.frame(t) -> list of (RGBA PIL.Image, (x, y))   # top-left paste position on the canvas, [] if nothing visible
    layer.active(t) -> bool

Layers: GoldCaptions(items), PopupCards(items), StatSlams(items); items are {text, start, end} (seconds).
Draw with draw(base_rgb_image, layer, t) (RGB paste using the RGBA as mask).
chunks(words, max_words, max_chars) -> [{text, start, end, words}], the grouping every renderer uses; group_words([{w, s, e}]) wraps it for GoldCaptions.
Fonts: Montserrat Black (variable font instance, trending/fonts) by default; pass font_path=captions.LILITA (the engine's fonts/ folder) to GoldCaptions/StatSlams to swap.
"""
import math, os, re, textwrap
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from .sensitive import caption_text, caption_word

HERE = os.path.dirname(os.path.abspath(__file__))
MONTSERRAT = os.path.join(HERE, "fonts", "Montserrat-VF.ttf")
LILITA = os.path.join(os.path.dirname(HERE), "fonts", "LilitaOne-Regular.ttf")
W, H = 1080, 1920
GOLD_TOP, GOLD_BOT, OUTLINE, GLOW = (255, 194, 26), (255, 240, 122), (107, 78, 0), (255, 216, 74)

_fonts = {}


def font(size, path=MONTSERRAT):
    k = (path, size)
    if k not in _fonts:
        f = ImageFont.truetype(path, size)
        if path == MONTSERRAT:
            f.set_variation_by_name("Black")
        _fonts[k] = f
    return _fonts[k]


def _font_for_cap(cap, path):
    """Font whose capital 'H' is `cap` px tall."""
    f = font(100, path)
    b = f.getbbox("H")
    return font(max(8, round(100 * cap / (b[3] - b[1]))), path)


# ------------------------------------------------------------------ word grouping
# The swear list, in one place. Stems match anywhere in a word (bullshit, motherfucker, dipshit); the ones that
# hide inside innocent words only match at the start of a word, with their false friends excluded:
# ass/arse whole word (class, pass, glass, assume, Essex stay), cock (peacock, Hitchcock, cocktail, cockpit),
# dick (Dickens), cunt (Scunthorpe), wank (swank), twat, slut, whore, prick.
_SWEAR = re.compile(
    r"fuck|shit|bitch|(?<!s)cunt|bastard|piss|bollock"
    r"|(?<![a-z])(?:dick(?!ens|inson)|wank|twat|prick|slut|whore|cock(?!tail|pit|roach|atoo|erel))"
    r"|(?<![a-z])(?:(?:jack|dumb|bad|smart|fat)?ass|arse)(?:es|holes?|heads?|hats?)?(?![a-z])", re.I)


def _mask(m):
    s = m.group(0)  # one vowel (never the first letter) becomes *: sh*t, ass -> a*s
    i = next((j for j, c in enumerate(s) if j > 0 and c.lower() in "aeiou"), 1)
    return s[:i] + "*" + s[i + 1:]


def censor(word):
    return _SWEAR.sub(_mask, caption_word(word))  # demonetisation-safe form first (sensitive.py), then swear-word masking


# Spoken filler, in one place: um/uh/er/erm/ah/eh/hmm/mm and their stretched spellings (umm, uhhh, hmmm). Never "like", "so", "you know" or a
# single "but": those carry meaning. A word repeated at once with no punctuation ("but but", "I I", "the the") is a stutter: the first is dropped.
FILLER = re.compile(r"^(?:u+m+|u+h+|e+r+m*|e+h+|a+h+|h+m+|m+h*m*)$")


def filler_idx(toks):
    """Indices of tokens to drop: fillers, and the first of an immediate stutter repeat."""
    n = [re.sub(r"[^a-z']", "", t.lower()) if not re.search(r"[.?!,;:]$", t) else None for t in toks]
    f = [re.sub(r"[^a-z']", "", t.lower()) for t in toks]
    return {i for i, t in enumerate(f) if FILLER.match(t)} | {i for i in range(len(toks) - 1) if n[i] and n[i] == f[i + 1]}


def chunks(words, max_words, max_chars, max_gap=0.5, hold=0.4, min_dur=0.35, soft_chars=0):
    """[{w, s, e, cap?, b?}] -> [{text, start, end, words}], the one caption grouping every renderer uses.
    Cleaned (no >> or [tag] words; cap when present, no filler or stutter repeat) and censored. Splits at a pause > max_gap, at . ? ! (and , ; : once the group has
    2+ words and soft_chars), at a b flag, and at max_words/max_chars. A caption runs from its first word to its last word's end + hold,
    never past the next caption's start, never across a silence."""
    out, cur, items = [], [], []
    for o in words:
        t = censor(o.get("cap", o["w"]).replace(">>", "").strip())
        if t and not t.startswith("["):
            items.append((t, o))
    skip = filler_idx([t for t, _ in items])
    for i, (t, o) in enumerate(items):
        if i in skip:
            continue
        # shortcut: a word lasts at most 0.3 s + 0.1 s per letter; ASR stretches a word over the silence after it. Upgrade if a real slow word is cut short.
        w = {**{k: v for k, v in o.items() if k != "cap"}, "w": t, "e": min(o["e"], o["s"] + 0.3 + 0.1 * len(t))}
        if cur and (len(cur) >= max_words or len(" ".join(x["w"] for x in cur + [w])) > max_chars or w["s"] - cur[-1]["e"] > max_gap):
            out.append(cur)
            cur = []
        cur.append(w)
        if (re.search(r"[.?!]$", t) or (len(cur) >= 2 and re.search(r"[,;:]$", t) and len(" ".join(x["w"] for x in cur)) >= soft_chars) or w.get("b")):
            out.append(cur)
            cur = []
    out += [cur] if cur else []
    res = []
    for i, g in enumerate(out):
        s = g[0]["s"]
        e = max(g[-1]["e"] + hold, s + min_dur if min_dur else 0)
        e = min(e, out[i + 1][0]["s"]) if i + 1 < len(out) else e
        res.append({"text": " ".join(x["w"] for x in g), "start": s, "end": max(e, s), "words": g})
    return res


def group_words(words, max_words=2, max_chars=14, max_gap=0.5):
    """[{w, s, e}] -> [{text, start, end}] for GoldCaptions: chunks without the hold, so a caption ends with its last word."""
    return [{k: c[k] for k in ("text", "start", "end")} for c in chunks(words, max_words, max_chars, max_gap, hold=0, min_dur=0)]


# ------------------------------------------------------------------ rendering
def render_gold(text, cap=95, max_w=900, path=MONTSERRAT, outline=7, glow_r=16, glow_a=0.55):
    """Gold gradient text with olive outline and soft glow, as one RGBA image (full scale). '\\n' = line break."""
    text = caption_text(text).upper()
    for _ in range(12):  # shrink to fit
        f = _font_for_cap(cap, path)
        o = max(2, round(outline * cap / 95))
        lines = text.split("\n")
        boxes = [f.getbbox(l, stroke_width=o) for l in lines]
        tw = max(b[2] - b[0] for b in boxes)
        if tw <= max_w:
            break
        cap = cap * max_w / tw * 0.99
    lh = round(cap * 1.45)
    pad = int(glow_r * 3 + o)
    w_, h_ = tw + 2 * pad, lh * (len(lines) - 1) + (boxes[0][3] - boxes[0][1]) + 2 * pad
    mask_fill, mask_all = Image.new("L", (w_, h_), 0), Image.new("L", (w_, h_), 0)
    capb = f.getbbox("H")
    for i, l in enumerate(lines):
        b = f.getbbox(l)
        x = (w_ - (b[2] - b[0])) // 2 - b[0]
        y = pad + i * lh - capb[1]
        ImageDraw.Draw(mask_fill).text((x, y), l, font=f, fill=255)
        ImageDraw.Draw(mask_all).text((x, y), l, font=f, fill=255, stroke_width=o)
    glow = mask_all.filter(ImageFilter.GaussianBlur(glow_r)).point(lambda v: int(v * glow_a))
    img = Image.new("RGBA", (w_, h_), GLOW + (0,))
    img.putalpha(glow)
    img.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (w_, h_), c) for c in OUTLINE], mask_all)))
    top, bot = pad, h_ - pad
    grad = Image.new("RGB", (1, h_))
    for y in range(h_):
        u = min(max((y - top) / max(bot - top, 1), 0), 1)
        grad.putpixel((0, y), tuple(round(a + (b - a) * u) for a, b in zip(GOLD_TOP, GOLD_BOT)))
    img.alpha_composite(Image.merge("RGBA", (*grad.resize((w_, h_)).split(), mask_fill)))
    return img


def _scaled(img, s, alpha=1.0):
    if abs(s - 1) > 1e-3:
        img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    if alpha < 0.999:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    return img


def _at(img, cx, cy):
    return (img, (round(cx - img.width / 2), round(cy - img.height / 2)))


def draw(base, layer, t):
    for im, pos in layer.frame(t):
        base.paste(im, pos, im)
    return base


def _out(u):
    return 1 - (1 - min(max(u, 0), 1)) ** 3


# ------------------------------------------------------------------ a) gold pop captions
POP_T, POP_FROM, SHRINK_TO = 0.07, 0.55, 1 / 3


def gold_scale(t, d):
    """Scale at time t of a caption shown for d seconds: pop 0.55->1 in 0.07 s, then accelerating shrink to ~1/3 at d."""
    if t < POP_T:
        return POP_FROM + (1 - POP_FROM) * _out(t / POP_T)
    dp = d - POP_T
    if dp <= 1e-3:
        return 1.0
    tau = dp / 3
    return 1 - (1 - SHRINK_TO) * (math.exp(min(t - POP_T, dp) / tau) - 1) / (math.exp(dp / tau) - 1)


class GoldCaptions:
    """Main word captions. A caption that is followed within 0.4 s by another is stretched to the next one's start
    (so it reaches 1/3 exactly then); otherwise it shrinks over its own duration, holds 0.2 s, fades over 0.1 s.
    scale multiplies the text size and the width limit (person edits use 0.8)."""
    HOLD, FADE, GAP = 0.2, 0.1, 0.4

    def __init__(self, items, cy=0.52, font_path=MONTSERRAT, cap=95, max_w=900, scale=1.0):
        self.cy, self.cache = cy * H, {}
        self.font_path, self.cap, self.max_w = font_path, cap * scale, max_w * scale
        items = sorted(items, key=lambda i: i["start"])
        self.items = []
        for k, it in enumerate(items):
            nxt = items[k + 1]["start"] if k + 1 < len(items) else None
            if nxt is not None and nxt - it["end"] <= self.GAP:
                self.items.append((it["text"], it["start"], nxt, nxt))
            else:
                self.items.append((it["text"], it["start"], it["end"], it["end"] + self.HOLD + self.FADE))

    def _img(self, text):
        if text not in self.cache:
            self.cache[text] = render_gold(text, self.cap, self.max_w, self.font_path)
        return self.cache[text]

    def active(self, t):
        return any(s <= t < v for _, s, _, v in self.items)

    def frame(self, t):
        for text, s, e, vis in self.items:
            if s <= t < vis:
                tt = t - s
                sc = gold_scale(min(tt, e - s), e - s)
                a = 1.0 if t < e + self.HOLD else max(0.0, 1 - (t - e - self.HOLD) / self.FADE)
                return [_at(_scaled(self._img(text), sc, a), W / 2, self.cy)]
        return []


# ------------------------------------------------------------------ b) pop-up cards
class PopupCards:
    """White-on-near-black rounded card, gold border, tilted -3 deg, centred at y=24%. Pop 0->1.08->1 in 0.18 s, out in 0.15 s."""
    IN, OUT = 0.18, 0.15

    def __init__(self, items, cy=0.24, size=64, wrap=22):
        self.items, self.cy, self.cache = items, cy * H, {}
        self.size, self.wrap = size, wrap

    def _img(self, text):
        if text not in self.cache:
            f = font(self.size)
            lines = textwrap.wrap(caption_text(text).upper(), self.wrap)[:2]
            bs = [f.getbbox(l) for l in lines]
            lh = round(self.size * 1.25)
            tw, th = max(b[2] - b[0] for b in bs), lh * (len(lines) - 1) + (f.getbbox("H")[3] - f.getbbox("H")[1])
            bw, bh, m = tw + 56, th + 36, 20
            im = Image.new("RGBA", (bw + 2 * m, bh + 2 * m), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.rounded_rectangle((m, m, m + bw, m + bh), 22, fill=(17, 17, 17, 255), outline=(255, 194, 26, 255), width=4)
            for i, l in enumerate(lines):
                b = f.getbbox(l)
                d.text((m + 28 + (tw - (b[2] - b[0])) // 2 - b[0], m + 18 + i * lh - f.getbbox("H")[1]), l, font=f, fill="white")
            self.cache[text] = im.rotate(3, resample=Image.BICUBIC, expand=True)  # PIL angle is counter-clockwise, same as CSS rotate(-3deg)
        return self.cache[text]

    def active(self, t):
        return any(i["start"] <= t < i["end"] for i in self.items)

    def frame(self, t):
        for it in self.items:
            if it["start"] <= t < it["end"]:
                tt, rem = t - it["start"], it["end"] - t
                if tt < self.IN:
                    u = tt / self.IN
                    sc = 1.08 * _out(u / 0.7) if u < 0.7 else 1.08 - 0.08 * ((u - 0.7) / 0.3)
                else:
                    sc = 1.0
                a = 1.0
                if rem < self.OUT:
                    k = rem / self.OUT
                    sc, a = sc * (0.85 + 0.15 * k), k
                return [_at(_scaled(self._img(it["text"]), sc, a), W / 2, self.cy)]
        return []


# ------------------------------------------------------------------ c) stat slams
class StatSlams:
    """Big gold text at ~2.3x caption size, centred at y=50%. Scales 1.6 -> 1.0 in 0.06 s, holds, cuts out at end.
    Single-line text wider than max_w with several words is split into two lines."""
    def __init__(self, items, cy=0.50, cap=220, max_w=1000, font_path=MONTSERRAT):
        self.items, self.cy, self.cache = items, cy * H, {}
        self.cap, self.max_w, self.font_path = cap, max_w, font_path

    def _img(self, text):
        if text not in self.cache:
            t = caption_text(text).upper()
            f = _font_for_cap(self.cap, self.font_path)
            if "\n" not in t and " " in t and f.getlength(t) > self.max_w:
                words = t.split()
                best = min(range(1, len(words)), key=lambda k: abs(len(" ".join(words[:k])) - len(" ".join(words[k:]))))
                t = " ".join(words[:best]) + "\n" + " ".join(words[best:])
            self.cache[text] = render_gold(t, self.cap, self.max_w, self.font_path, outline=7, glow_r=16)
        return self.cache[text]

    def active(self, t):
        return any(i["start"] <= t < i["end"] for i in self.items)

    def frame(self, t):
        for it in self.items:
            if it["start"] <= t < it["end"]:
                u = (t - it["start"]) / 0.06
                sc = 1.6 - 0.6 * _out(u) if u < 1 else 1.0
                return [_at(_scaled(self._img(it["text"]), sc), W / 2, self.cy)]
        return []
