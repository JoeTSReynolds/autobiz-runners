"""Case-file renderer: a documentary voice (trending/tts.py) over article screenshot cards, Commons photos, quote/date cards and muted face-cropped
archive clips, with a dated timeline bar, 3-5 word captions with one yellow key word, and a ducked music bed. No footer and no photo labels:
credits go back in the returned `credits` list. Screenshots stay SHOT_MIN-SHOT_MAX s each (the highlight animation ends within ANIM s, then the card holds still) and under
SHOT_SHARE of the runtime where possible; a longer sentence shows its screenshot first, then a photo or quote card. Look generalised from prototypes/trending/casefile/render.py + build.py.

    from trending.formats import casefile; casefile.render(job, cfg, run_dir) -> {short, timeline, credits}

Reads job["plan"] (script[{text, spoken, visual}], timeline[{label, text}], clips, musicOffset), job["clips"], job["assets"]
({screenshots{url: file}, photos[{query, file, credit, licence, page}]}), job["track"] ({file}); cfg voice / elevenVoice / elevenModel (see tts.py).
Paths are relative to `run`; intermediates go to run/cut/, the video to run/short.mp4.
"""
import subprocess
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from .. import captions as C, facecrop, music, tts
from ..sensitive import caption_text
from .safe import SAFE_X, SAFE_TOP, fit_lines
from .tribute import _ff

W, H, FPS = 1080, 1920, 30
CARD_W, CARD_H, CARD_X, CARD_Y = W - 2 * SAFE_X, 950, SAFE_X, 290
YELLOW, DARK = (255, 214, 10), (8, 8, 12)
SHOT_MIN, SHOT_MAX, SHOT_SHARE, RUN_ON, ANIM, MIN_REST, SPLIT_AT, HOLD, FADE = 3.0, 4.0, 0.4, 1.0, 1.0, 0.6, 4.6, 0.5, 0.5
MUSIC_DB, DUCK_DB, VOICE_LUFS, TARGET_LUFS = -14, 12, -15, -14
CAP_Y = 1382
Img = Image.fromarray


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def _cover(a, w=W, h=H):
    s = max(w / a.shape[1], h / a.shape[0])
    a = cv2.resize(a, (round(a.shape[1] * s), round(a.shape[0] * s)), interpolation=cv2.INTER_AREA)
    y, x = (a.shape[0] - h) // 2, (a.shape[1] - w) // 2
    return a[y:y + h, x:x + w]


def _pill(text, size=34):
    f = C.font(size)
    l, t, r, b = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=f)
    im = Image.new("RGBA", (r - l + 44, b - t + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), 14, fill=(200, 30, 30, 235))
    d.text((22 - l, 15 - t), text, font=f, fill=(255, 255, 255))
    return im


def _load(path):
    return np.asarray(Image.open(path).convert("RGB"))


# ------------------------------------------------------------------ shots (frame(t) -> PIL RGB)
class CardSeg:
    """Article screenshot as a rounded card on a blurred backdrop. Full page width always (no horizontal crop, so no word is cut at the sides);
    the page drifts down onto the highlighted line."""
    card = True

    def __init__(self, png, label, s, e):
        self.s, self.e = s, e
        src = _load(png)
        mask = (abs(src[..., 0].astype(int) - 255) < 6) & (abs(src[..., 1].astype(int) - 225) < 10) & (abs(src[..., 2].astype(int) - 77) < 20)
        ys, _ = np.nonzero(mask)
        k = CARD_W / src.shape[1]
        self.big = cv2.resize(src, (CARD_W, max(round(src.shape[0] * k), 1)), interpolation=cv2.INTER_AREA)
        self.ch = min(CARD_H, self.big.shape[0])
        room = self.big.shape[0] - self.ch
        end = min(max(float(np.median(ys)) * k - self.ch * 0.45, 0), room) if len(ys) > 50 else min(160, room)
        self.y0, self.y1 = max(end - 160, 0), end
        self.bg = (cv2.GaussianBlur(_cover(src), (0, 0), 38) * 0.38).astype(np.uint8)
        m = Image.new("L", (CARD_W, self.ch), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, CARD_W - 1, self.ch - 1), 34, fill=255)
        self.mask = np.asarray(m)[..., None] / 255.0
        self.top = CARD_Y + (CARD_H - self.ch) // 2
        self.label = _pill(label)

    def frame(self, t):
        u = min((t - self.s) / min(self.e - self.s, ANIM), 1)   # drift + highlight finish in ANIM s, then the card holds still
        y = int(round(self.y0 + (self.y1 - self.y0) * ease(u)))
        card = self.big[y:y + self.ch].astype(np.float32)
        a, am = ease((t - self.s) / 0.18), self.mask
        k = 0.95 + 0.05 * a                                    # pop-in
        if k < 1:
            M = np.float32([[k, 0, (1 - k) * CARD_W / 2], [0, k, (1 - k) * self.ch / 2]])
            card, am = cv2.warpAffine(card, M, (CARD_W, self.ch)), cv2.warpAffine(am, M, (CARD_W, self.ch))[..., None]
        fr = self.bg.astype(np.float32)
        reg = fr[self.top:self.top + self.ch, CARD_X:CARD_X + CARD_W]
        fr[self.top:self.top + self.ch, CARD_X:CARD_X + CARD_W] = reg * (1 - am * a) + card * am * a
        out = Img(np.clip(fr, 0, 255).astype(np.uint8))
        if a > 0.5:
            out.paste(self.label, (CARD_X, self.top - self.label.height - 14), self.label)
        return out


class PhotoSeg:
    """Photo with a slow 9:16 push (or pull) and a sideways drift; never labelled."""
    card = False

    def __init__(self, path, s, e, zin=True, fy=0.4):
        self.s, self.e, self.zin, self.fy, self.im = s, e, zin, fy, _load(path)

    def frame(self, t):
        u = ease((t - self.s) / (self.e - self.s))
        z = 1.0 + 0.12 * (u if self.zin else 1 - u)
        h, w = self.im.shape[:2]
        ch = min(h, w * 16 / 9) / z
        cw = ch * 9 / 16
        x0, y0 = (w - cw) * (0.35 + 0.3 * u if self.zin else 0.65 - 0.3 * u), (h - ch) * self.fy
        s = W / cw
        return Img(cv2.warpAffine(self.im, np.float32([[s, 0, -x0 * s], [0, s, -y0 * s]]), (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE))


class ClipSeg:
    """Face-cropped archive clip (rendered to cut/ beforehand), muted; holds its last frame if the sentence outlasts it."""
    card = False

    def __init__(self, path, s, e):
        self.s, self.e, self.path, self.proc, self.n, self.last = s, e, path, None, 0, None

    def frame(self, t):
        if self.proc is None:
            self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(self.path), "-an", "-vf", f"fps={FPS},scale={W}:{H}", "-f", "rawvideo",
                                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        while self.n <= round((t - self.s) * FPS):
            b = self.proc.stdout.read(W * H * 3)
            if len(b) < W * H * 3:
                break
            self.last, self.n = np.frombuffer(b, np.uint8).reshape(H, W, 3), self.n + 1
        return Img(self.last if self.last is not None else np.zeros((H, W, 3), np.uint8))

    def close(self):
        if self.proc:
            self.proc.kill()
            self.proc.wait()


class TextSeg:
    """Quote card or date card on a dark gradient: static, drawn once."""
    card = True

    def __init__(self, head, body, foot, s, e, big=False):
        self.s, self.e = s, e
        head, body, foot = caption_text(head), caption_text(body), caption_text(foot or "")
        g = np.linspace(0, 1, H)[:, None, None]
        im = Img((np.array([18, 22, 34]) * (1 - g) + np.array([6, 6, 10]) * g).astype(np.uint8).repeat(W, 1)).convert("RGBA")
        d = ImageDraw.Draw(im)
        size = 52 if big else 88 if len(body) < 45 else 64
        lines, size = fit_lines(body, size, W - 2 * SAFE_X - 20, 7, 40)   # pixel-wrapped inside the safe margins, shrunk before any text is cut
        step = round(size * 1.3)
        hsize, fsize = (fit_lines(t, s, W - 2 * SAFE_X - 20, 1, 44)[1] for t, s in ((head, 150 if big else 220), (foot, 40)))
        y = 740 - (len(lines) * step + (150 if head else 0) + (110 if foot else 0)) // 2   # block centred above the captions
        if head:
            d.text((W / 2, y + 75), head, font=C.font(hsize), fill=YELLOW, anchor="mm", stroke_width=6, stroke_fill=(10, 10, 10))
            y += 170
        for ln in lines:
            d.text((W / 2, y + step / 2), ln, font=C.font(size), fill=(255, 255, 255), anchor="mm", stroke_width=5, stroke_fill=(10, 10, 10))
            y += step
        if foot:
            d.line((W / 2 - 90, y + 20, W / 2 + 90, y + 20), fill=YELLOW, width=6)
            d.text((W / 2, y + 70), foot, font=C.font(fsize), fill=YELLOW, anchor="mm")
        self.im = im.convert("RGB")

    def frame(self, t):
        return self.im


# ------------------------------------------------------------------ overlays
def _gradient():
    g = np.linspace(0, 1, 700) ** 1.6 * 175
    a = np.zeros((H, W), np.float32)
    a[H - 700:] = g[:, None]
    a[:360] = np.maximum(a[:360], (np.linspace(1, 0, 360) ** 1.8 * 140)[:, None])
    return Img(a.astype(np.uint8))


class Timeline:
    """Thin line with date ticks; a tick lights when the narration reaches it, the segment between lit ticks fills."""
    X0, X1, Y = SAFE_X + 80, W - SAFE_X - 80, SAFE_TOP + 22   # label half-width ~65; the lit dot (radius 18) stays below SAFE_TOP

    def __init__(self, ticks):  # [{label, pos 0..1, at seconds}]
        self.ticks, self.cache = ticks, {}

    def frame(self, t):
        key = tuple(round(min(max((t - k["at"]) / 0.35, 0), 1), 1) for k in self.ticks)
        if key not in self.cache:
            im = Image.new("RGBA", (W, 190), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            xs = [self.X0 + (self.X1 - self.X0) * k["pos"] for k in self.ticks]
            d.line((self.X0, self.Y, self.X1, self.Y), fill=(255, 255, 255, 90), width=5)
            lit = [x for x, v in zip(xs, key) if v > 0]
            if len(lit) > 1:
                d.line((min(lit), self.Y, max(lit), self.Y), fill=YELLOW + (255,), width=7)
            latest = max((i for i, v in enumerate(key) if v > 0), key=lambda i: self.ticks[i]["at"], default=None)
            for i, (k, x, v) in enumerate(zip(self.ticks, xs, key)):
                r = 12 + (6 if i == latest else 0)
                d.ellipse((x - r, self.Y - r, x + r, self.Y + r), fill=YELLOW + (255,) if v > 0 else (60, 60, 60, 255), outline=(255, 255, 255, 255), width=3)
                d.text((x, self.Y + 36), k["label"], font=C.font(24), fill=(255, 255, 255, 255 if v > 0 else 130), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0, 200))
            self.cache[key] = im
        return self.cache[key]


class Captions:
    """3-5 word lines, white with a dark outline, one yellow key word (the longest) per sentence; the voice's tags never get here."""

    def __init__(self, sentences, max_words=5, max_chars=24):
        self.cache, flat = {}, []
        for ws in filter(None, sentences):
            key = max(range(len(ws)), key=lambda i: len(ws[i]["w"]))
            flat += [dict(w, key=i == key, **({"b": 1} if i == len(ws) - 1 else {})) for i, w in enumerate(ws)]
        cs = C.chunks(flat, max_words, max_chars, hold=0.12)
        self.lines = [c["words"] for c in cs]
        self.show = [(c["start"] - 0.05, c["end"]) for c in cs]

    def frame(self, t):
        for i, (a, b) in enumerate(self.show):
            if a <= t < b:
                if i not in self.cache:
                    self.cache[i] = self._render(self.lines[i])
                return self.cache[i], int(14 * (1 - ease((t - a) / 0.12)))
        return None, 0

    def _render(self, ln):
        ln = [w for w in ln if w.get("cap", w["w"])]  # a multi-word spoken form leaves empty caps behind
        words = [C.censor(w.get("cap", w["w"])).strip(".,?!;:") for w in ln]
        d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        size = 78
        while True:
            f = C.font(size)
            sp, ws = d.textlength(" ", font=f), [d.textlength(w, font=f) for w in words]
            tot = sum(ws) + sp * (len(ws) - 1)
            if tot <= W - 2 * SAFE_X or size < 50:
                break
            size -= 3
        im = Image.new("RGBA", (W, 170), (0, 0, 0, 0))
        d, x = ImageDraw.Draw(im), (W - tot) / 2
        for w, wd, src in zip(words, ws, ln):
            d.text((x, 85), w, font=f, anchor="lm", fill=YELLOW if src["key"] else (255, 255, 255), stroke_width=9, stroke_fill=(12, 12, 16))
            x += wd + sp
        return im


# ------------------------------------------------------------------ plan -> pieces (pure)
def first_len(L, cap):
    """Seconds a screenshot stays up in a sentence of L seconds: at most cap, and the photo/quote that follows gets at least MIN_REST."""
    if L < SHOT_MIN:   # too short to read: runs on into the next sentence, by at most RUN_ON
        return min(SHOT_MIN, L + RUN_ON)
    f = min(cap, L)
    if 0 < L - f < MIN_REST:
        f = L - MIN_REST if L - MIN_REST >= SHOT_MIN else L
    return f


def shot_cap(lens, total):
    """Largest cap <= SHOT_MAX that keeps the screenshots within SHOT_SHARE of the runtime (floor SHOT_MIN)."""
    cap = SHOT_MAX
    while cap > SHOT_MIN + 1e-9 and sum(first_len(L, cap) for L in lens) > SHOT_SHARE * total:
        cap = round(cap - 0.1, 1)
    return cap


def pick_photo(photos, uses, query, last):
    """Least-used photo, the query's own preferred, never `last` again when another exists; counts the use in `uses`."""
    if not photos:
        return None
    pool = [p for p in photos if p["file"] != last] or photos
    p = min(pool, key=lambda p: (uses.get(p["file"], 0), not (query and p.get("query") == query), photos.index(p)))
    uses[p["file"]] = uses.get(p["file"], 0) + 1
    return p


def render(job, cfg, run):
    plan, assets, run = job["plan"], job.get("assets") or {}, Path(run)
    cut = run / "cut"
    cut.mkdir(parents=True, exist_ok=True)
    script = plan["script"]
    v = tts.narrate([s.get("text") or s["spoken"] for s in script], [s["spoken"] for s in script], cfg, run)
    D = round(v["duration"] + HOLD, 3)
    spans = [(a, b) for a, b in v["spans"]]
    spans[-1] = (spans[-1][0], D)
    shots, photos = assets.get("screenshots") or {}, assets.get("photos") or []
    lens = [b - a for (a, b), s in zip(spans, script) if s["visual"]["kind"] == "screenshot" and shots.get(s["visual"].get("url"))]
    cap = shot_cap(lens, D)
    used, credits, uses, last = [], [], {}, [None]

    def photo(query=None):
        p = pick_photo(photos, uses, query, last[0])
        last[0] = p and p["file"]
        return p

    pieces = []   # (start, end, kind, person, factory)

    def add(a, b, kind, person, make):
        pieces.append((a, b, kind, person, make))

    def photo_piece(a, b, p, sign, text=None):
        if p is None:
            return add(a, b, "quote", False, lambda: TextSeg("", text or "", "", a, b))
        credits.append(f"Photo: {p['credit']} / {p['licence']} (Wikimedia Commons) {p.get('page') or ''}".strip())
        add(a, b, "photo", False, lambda: PhotoSeg(run / p["file"], a, b, zin=sign > 0))

    ticks = [dict(label=t["label"], pos=i / max(len(plan["timeline"]) - 1, 1), at=1e9) for i, t in enumerate(plan.get("timeline") or [])]
    tl_i, by_key = 0, {c["key"]: (c, f) for c, f in zip(plan["clips"], job.get("clips") or [])}
    for i, ((a, b), s) in enumerate(zip(spans, script)):
        vis, L = s["visual"], b - a
        kind, rest_from = vis["kind"], None
        if kind == "screenshot" and shots.get(vis["url"]):
            f = min(first_len(L, cap), D - a)
            add(a, a + f, "screenshot", False, lambda a=a, f=f, vis=vis: CardSeg(run / shots[vis["url"]], vis["outlet"], a, a + f))
            credits.append(f"Source: {vis['outlet']} {vis['url']}")
            rest_from = a + f
            if rest_from < b - 1e-6:   # then a photo or the highlighted quote
                p = photo() if i % 2 == 0 else None
                if p:
                    photo_piece(rest_from, b, p, 1)
                else:
                    add(rest_from, b, "quote", False, lambda r=rest_from, vis=vis, b=b: TextSeg("", vis["highlight"], vis["outlet"], r, b))
            continue
        if kind == "clip" and vis["clip"] in by_key:
            c, f = by_key[vis["clip"]]
            src, st, en = str(run / f["file"]), c["start"] - f.get("offset", 0), c["end"] - f.get("offset", 0)
            dst = cut / f"clip_{vis['clip']}.mp4"
            facecrop.render(src, dst, zoom=facecrop.push_in(1.0, 1.08, en - st), face_y=0.40, start=st, end=en, cam=facecrop.track(src, start=st, end=en))
            credits.append(f"Footage: {c['source']['url']}")
            add(a, b, "clip", True, lambda a=a, b=b, dst=dst: ClipSeg(dst, a, b))
            continue
        if kind == "timeline":
            lab = next((k for k, t in enumerate(ticks) if t["label"] == vis.get("label")), tl_i)
            if lab < len(ticks):
                ticks[lab]["at"] = a
                tl_i = lab + 1
            body = (plan["timeline"][lab]["text"] if lab < len(ticks) else s["spoken"])
            end = a + L / 2 if L > SPLIT_AT else b
            add(a, end, "timeline", False, lambda a=a, end=end, vis=vis, body=body: TextSeg(vis.get("label", ""), body, "", a, end, big=True))
        elif kind == "quote":
            end = a + L / 2 if L > SPLIT_AT else b
            add(a, end, "quote", False, lambda a=a, end=end, vis=vis: TextSeg("", vis["text"], vis.get("outlet"), a, end))
        else:  # photo, or a visual whose asset is missing
            p = photo(vis.get("query") if kind == "photo" else None)
            end = a + L / 2 if L > SPLIT_AT else b
            photo_piece(a, end, p, 1, s["spoken"])
        if pieces[-1][1] < b - 1e-6:   # a long sentence changes picture halfway
            photo_piece(pieces[-1][1], b, photo(), -1, s["spoken"])
    for k in range(1, len(pieces)):   # a screenshot that runs on into the next sentence pushes that picture's start back
        if pieces[k][0] < pieces[k - 1][1] < pieces[k][1]:
            pieces[k] = (pieces[k - 1][1], *pieces[k][1:])
    # ----- frames
    foot = Image.new("RGB", (W, H), DARK)
    grad, bar = _gradient(), Timeline(ticks) if ticks else None
    caps = Captions(v["words"])
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an",
                            "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(cut / "video.mp4")], stdin=subprocess.PIPE)
    cur, seg = -1, None
    for n in range(int(D * FPS)):
        t = n / FPS
        k = next((j for j, p in enumerate(pieces) if p[0] <= t < p[1]), len(pieces) - 1)
        if k != cur:
            if hasattr(seg, "close"):
                seg.close()
            seg, cur = pieces[k][4](), k
        img = seg.frame(t).convert("RGB")
        if not seg.card:
            img.paste(foot, (0, 0), grad)
        if bar:
            tl = bar.frame(t)
            img.paste(tl, (0, 20), tl)
        c, dy = caps.frame(t)
        if c:
            img.paste(c, (0, CAP_Y - 85 + dy), c)
        if t > D - FADE:
            img = Image.blend(img, foot, (t - (D - FADE)) / FADE)
        enc.stdin.write(np.asarray(img).tobytes())
    if hasattr(seg, "close"):
        seg.close()
    enc.stdin.close()
    enc.wait()
    if enc.returncode:
        raise RuntimeError("encode failed")

    # ----- audio: voice at -15 LUFS, music bed ducked under it, whole mix at -14 LUFS
    _ff("-i", v["file"], "-af", f"loudnorm=I={VOICE_LUFS}:TP=-1.5:LRA=7", "-ar", 44100, cut / "voice_norm.wav")
    track = job.get("track")
    if track and track.get("file"):
        music.mix(str(cut / "voice_norm.wav"), str(run / track["file"]), plan.get("musicOffset") or 0, str(cut / "mix.m4a"),
                  music_gain_db=MUSIC_DB, duck_db=DUCK_DB, video_duration=D)
        a_in = cut / "mix.m4a"
    else:
        a_in = cut / "voice_norm.wav"
    _ff("-i", cut / "video.mp4", "-i", a_in, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11,aresample=44100",
        "-c:a", "aac", "-b:a", "192k", "-t", f"{D:.3f}", "-movflags", "+faststart", run / "short.mp4")
    tl = [{"start": a, "end": b, "kind": kind, "person": person} for a, b, kind, person, _ in pieces]
    return {"short": {"file": "short.mp4", "duration": D}, "timeline": tl, "credits": list(dict.fromkeys(credits))}
