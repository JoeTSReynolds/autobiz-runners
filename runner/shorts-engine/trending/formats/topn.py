"""Top-N renderer: black header, numbered list down the left (a label appears as each slot starts), clips play rank N -> 1 with their
own audio, small cut subtitles, whoosh + flash + shake between slots, a darkened freeze-frame news closer. Look generalised from
prototypes/trending/top5/build.py.

    from trending.formats import topn; topn.render(job, cfg, run_dir) -> {short, timeline, credits}

Reads job["plan"] (title, n, person.name, moments[{clip, rank, label, words}] in on-screen order, closer{line1, line2}), job["clips"]
(media-fetch files; file time t = source time - offset). Paths are relative to `run`; intermediates go to run/cut/, video to run/short.mp4.
"""
import re, subprocess, unicodedata, urllib.parse, urllib.request
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw
from .. import captions as C, compose as CP, facecrop, faces
from ..sensitive import caption_text as _ct
from .safe import SAFE_X, SAFE_TOP, SAFE_BOTTOM, fit_lines
from .tribute import _ff

SOUNDS = Path(__file__).resolve().parents[2] / "sounds"
WHOOSH, CLICK = SOUNDS / "whoosh" / "whoosh.m4a", SOUNDS / "click" / "ui2.m4a"
FACE_Y, CLOSER, TARGET_LUFS, CLICK_DB = 0.47, 4.4, -14, -8
W, ROW = 1080, 118
INNER = W - 2 * SAFE_X                       # text width between the safe margins
LIST_X = SAFE_X                              # the list starts 22 px under the header bar
STACK_Y, BTN_W, BTN_H, BTN_Y = 960, 600, 124, 1330   # closer text block, then the subscribe button (hand and thumb end above 1660)


FLUENT = "https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/"  # Microsoft Fluent Emoji 3D (MIT), as video-edit uses
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]\uFE0F?")


def split_emoji(text):
    """('STILL DODGING?', '👀') from 'STILL DODGING? 👀': Montserrat cannot draw emoji, so the first one becomes an image."""
    m = EMOJI.search(text)
    return (re.sub(r"\s+", " ", EMOJI.sub("", text)).strip(), m.group().replace("\uFE0F", "")) if m else (text.strip(), None)


NAMES = {"👆": "backhand index pointing up", "👍": "thumbs up"}   # Fluent folder names differ from the Unicode names


def emoji_urls(ch):
    name = NAMES.get(ch) or unicodedata.name(ch).lower()
    snake, folder = name.replace(" ", "_"), urllib.parse.quote(name[0].upper() + name[1:])
    return [f"{FLUENT}{folder}/3D/{snake}_3d.png", f"{FLUENT}{folder}/Default/3D/{snake}_3d_default.png"]


def _emoji_png(ch, dest):
    """The emoji as a 150 px PNG, or None when it cannot be fetched (the closer then shows text only)."""
    for url in emoji_urls(ch):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "autobiz-shorts"}), timeout=20) as r:
                dest.write_bytes(r.read())
            Image.open(dest).convert("RGBA").resize((150, 150), Image.LANCZOS).save(dest)
            return dest
        except Exception:
            continue
    return None
RED, WHITE, GOLD = (230, 32, 32), (255, 255, 255), (255, 200, 40)
NUM_COL = [GOLD, (70, 150, 255), WHITE, (255, 105, 180), WHITE]   # rank 1 gold, 2 blue, 3 white, 4 pink, 5 white


class _Cards(CP.Cards):
    """compose.Cards plus anim 'cut' (instantly on and off, no resize, under the animated cards), 'over' (the same, drawn over them) and
    'glide' (moves from x0,y0 to x,y in `glide` s, fading in, then a small press: scale down and back)."""
    SPECIAL = ("cut", "over", "glide")

    def __init__(self, items):
        super().__init__([c for c in items if c.get("anim") not in self.SPECIAL])
        self.cut, self.over = ([(Image.open(c["image"]).convert("RGBA"), c) for c in items if c.get("anim") == a] for a in ("cut", "over"))
        self.glide = [(Image.open(c["image"]).convert("RGBA"), c) for c in items if c.get("anim") == "glide"]

    def _still(self, ims, t):
        return [(im, (round((W - im.width) / 2 if c.get("x") in (None, "center") else c["x"]), round(c["y"]))) for im, c in ims if c["start"] <= t < c["end"]]

    def _glide(self, t):
        out = []
        for im, c in self.glide:
            if not c["start"] <= t < c["end"]:
                continue
            tt = t - c["start"]
            k = C._out(tt / c["glide"])
            p = tt - c["glide"]   # seconds since the press
            sc = 1 - 0.15 * (min(p / 0.08, 1) if p < 0.08 else max(1 - (p - 0.08) / 0.12, 0)) if p > 0 else 1
            out.append(C._at(C._scaled(im, sc, min(tt / 0.12, 1)), c["x0"] + (c["x"] - c["x0"]) * k + im.width / 2, c["y0"] + (c["y"] - c["y0"]) * k + im.height / 2))
        return out

    def frame(self, t):
        return self._still(self.cut, t) + super().frame(t) + self._still(self.over, t) + self._glide(t)


def _stroke(d, xy, text, f, fill, stroke=7, anchor="la"):
    d.text(xy, text, font=f, fill=fill, stroke_width=stroke, stroke_fill=(10, 10, 10), anchor=anchor)


def _header(lines, out):
    """lines [(text, size, colour)] centred on a black bar, first line SAFE_TOP from the top, inside the side margins. A line too wide
    shrinks to 44 px, then wraps; nothing is cut. Returns the bar height."""
    gap, items = 26, []
    for t, s, c in lines:
        ls, s = fit_lines(_ct(t), s, INNER, 1, min(s, 44))
        f = C.font(s)
        items += [(x, f, c, f.getbbox("H")[3] - f.getbbox("H")[1]) for x in ls]
    h = SAFE_TOP + sum(i[3] for i in items) + gap * (len(items) - 1) + 40
    im = Image.new("RGBA", (W, h), (0, 0, 0, 255))
    d, y = ImageDraw.Draw(im), SAFE_TOP
    for t, f, col, hh in items:
        d.text((W / 2, y - f.getbbox("H")[1]), t, font=f, fill=col, anchor="ma")
        y += hh + gap
    im.save(out)
    return h


def _rank_list(labels, n, out):
    """labels {rank: text} for the slots already shown; numbers 1..n are always drawn."""
    im = Image.new("RGBA", (INNER, ROW * n + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fn = C.font(92)
    for k in range(n):
        y = 4 + k * ROW
        _stroke(d, (0, y), f"{k + 1}.", fn, NUM_COL[k % 5], 8)
        if k + 1 in labels:   # a long label shrinks, then takes two lines; never cut
            ls, sz = fit_lines(_ct(labels[k + 1]), 48, INNER - 118 - 16, 1, 32)
            for j, x in enumerate(ls):
                _stroke(d, (118, y + (24 if len(ls) == 1 else 4) + j * (sz + 8)), x, C.font(sz), WHITE)
    im.save(out)


def _caption(text, out):
    text = _ct(text)
    f = C.font(58)
    b = f.getbbox(text, stroke_width=8)
    im = Image.new("RGBA", (b[2] - b[0] + 20, b[3] - b[1] + 20), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10 - b[0], 10 - b[1]), text, font=f, fill=WHITE, stroke_width=8, stroke_fill=(0, 0, 0))
    im.save(out)
    return im.width


def _stack(lines, out, size):
    """Big centred stack, white bold with a dark outline; lines [(text, colour)]."""
    lines = [(_ct(t), c) for t, c in lines]
    f = C.font(size)
    hh = f.getbbox("H")[3] - f.getbbox("H")[1]
    im = Image.new("RGBA", (W, (hh + 36) * len(lines) + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, (t, col) in enumerate(lines):
        _stroke(d, (W / 2, 15 + i * (hh + 36) - f.getbbox("H")[1]), t, f, col, 9, "ma")
    im.save(out)
    return im.height


def _button(text, fill, out, check=False):
    """Red (or grey) pill, white bold text. Not the YouTube logo."""
    im = Image.new("RGBA", (BTN_W, BTN_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, BTN_W - 1, BTN_H - 1), BTN_H // 2, fill=fill + (255,))
    f = C.font(50)
    tw, off = d.textlength(text, font=f), (34 if check else 0)
    x = (BTN_W - tw) / 2 + off
    d.text((x, BTN_H / 2), text, font=f, fill=WHITE, anchor="lm")
    if check:
        cx, cy = x - 44, BTN_H / 2
        d.line([(cx - 14, cy), (cx - 3, cy + 12), (cx + 16, cy - 12)], fill=WHITE, width=9, joint="curve")
    im.save(out)


def closer_times():
    """Seconds after the closer starts: both lines, then the subscribe button, the hand gliding onto it, the press (click, turns grey), the like (click)."""
    return dict(line1=0.1, line2=1.5, button=2.0, hand=2.15, press=2.85, thumb=3.3, end=CLOSER - 0.05)


def audio_events(cuts, closer_t):
    """[(file, start s, dB)]: a whoosh just before every cut, a click on the subscribe press and on the like."""
    T = closer_times()
    return [(WHOOSH, max(c - 0.25, 0), -9) for c in cuts] + [(CLICK, closer_t + T["press"], CLICK_DB), (CLICK, closer_t + T["thumb"], CLICK_DB)]


def mix_filter(events):
    """Filter graph: input 0 is the clips' speech, input i+1 is events[i]'s file; delayed, levelled, mixed, loudnorm -14."""
    fc = "[0:a]aresample=44100,aformat=channel_layouts=stereo[sp];"
    for i, (_, t, db) in enumerate(events):
        ms = int(t * 1000)
        fc += f"[{i + 1}:a]aresample=44100,aformat=channel_layouts=stereo,volume={db}dB,adelay={ms}|{ms}[w{i}];"
    return fc + "[sp]" + "".join(f"[w{i}]" for i in range(len(events))) + f"amix=inputs={len(events) + 1}:normalize=0,loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11,apad[a]"


def pick_closer_frame(samples, ident):
    """samples [(src, t, [(embedding, face width share)])] -> (src, t) of the frame whose face best matches ident (bigger faces win ties), or None."""
    best, top = None, -1.0
    for src, t, fs in samples:
        for e, share in fs:
            sim = faces.match(ident, e)
            if sim >= faces.MATCH and sim + share > top:
                best, top = (src, t), sim + share
    return best


def closer_source(moments, run, faces_at):
    """(file, time) of the closer's background: the best identity match among 3 frames per moment clip; today's frame (0.5 s before the last
    clip's end) without run/identity.npy or without a match. moments [(src, a, b)]; faces_at(src, t) -> [(embedding, share)]."""
    last = (moments[-1][0], max(moments[-1][2] - 0.5, 0))
    ref = Path(run) / "identity.npy"
    if not ref.exists():
        return last
    ts = [(src, a + (b - a) * k / 4) for src, a, b in moments for k in (1, 2, 3)]
    return pick_closer_frame([(s, t, faces_at(s, t)) for s, t in ts], np.load(ref)) or last


def closer_cards(cl, cut, closer_t, total, emoji=None):
    """Closer cards: line 1, line 2 (+ its emoji), then SUBSCRIBE, the hand gliding on, SUBSCRIBED (grey) at the press, the like. All in the safe box."""
    emoji = emoji or _emoji_png
    T, at = closer_times(), lambda k: closer_t + T[k]
    text2, emo = split_emoji(cl["line2"])
    emo_png = emoji(emo, cut / "emoji.png") if emo else None
    l1, s1 = fit_lines(cl["line1"].upper(), 64, INNER - 20, 3)
    l2, s2 = fit_lines(re.sub(r"[^\w\s?!.,'’\"“”-]", "", text2).strip().upper(), 110, (640 if emo_png else INNER - 20), 2)
    _stack([(x, GOLD if k == 0 else WHITE) for k, x in enumerate(l1)], cut / "closer1.png", s1)
    _stack([(x, WHITE if k == 0 else GOLD) for k, x in enumerate(l2)], cut / "closer2.png", s2)
    cards = [dict(image=str(cut / "closer1.png"), start=at("line1"), end=at("line2"), x=0, y=STACK_Y, w=W, anim="pop"),
             dict(image=str(cut / "closer2.png"), start=at("line2"), end=total - 0.05, x=0, y=STACK_Y, w=W, anim="pop")]
    if emo_png:  # beside the second line, popping in just after it, as in the approved prototype
        cards.append(dict(image=str(emo_png), start=at("line2") + 0.25, end=total - 0.05, x=W - SAFE_X - 150, y=STACK_Y + 97, w=150, anim="pop"))
    bx = (W - BTN_W) // 2
    _button("SUBSCRIBE", RED, cut / "sub.png")
    _button("SUBSCRIBED", (110, 110, 110), cut / "subbed.png", check=True)
    cards += [dict(name="subscribe", image=str(cut / "sub.png"), start=at("button"), end=total - 0.05, x=bx, y=BTN_Y, w=BTN_W, anim="pop"),
              dict(name="subscribed", image=str(cut / "subbed.png"), start=at("press"), end=total - 0.05, x=bx, y=BTN_Y, w=BTN_W, anim="over")]
    hand, thumb = emoji("👆", cut / "hand.png"), emoji("👍", cut / "thumb.png")
    if hand:   # fingertip lands on the button's lower half; starts down and right of it
        hx, hy = bx + 370, BTN_Y + BTN_H - 30
        cards.append(dict(name="hand", image=str(hand), start=at("hand"), end=total - 0.05, x=hx, y=hy, x0=hx + 180, y0=hy + 60, glide=T["press"] - T["hand"], w=150, anim="glide"))
    if thumb:
        cards.append(dict(name="thumb", image=str(thumb), start=at("thumb"), end=total - 0.05, x=bx + BTN_W + 10, y=BTN_Y - 3, w=130, anim="pop"))
    return cards


def _chunks(words, a, b, t0):
    """Words inside source [a, b) -> [(text, start, end)] on the output timeline: captions.chunks, 3 words / 16 chars, split at pauses."""
    ws = [w for w in words if a - 0.05 <= w["s"] < b]
    return [(c["text"], c["start"] - a + t0, min(c["end"], b) - a + t0) for c in C.chunks(ws, 3, 16)]


def _faces_at(src, t, models, png):
    """[(embedding, face width share)] of the noticeable faces in the frame of src at t seconds."""
    _ff("-ss", f"{t:.2f}", "-i", src, "-frames:v", 1, png)
    return faces.embed_all(cv2.imread(str(png)), models)


def render(job, cfg, run):
    plan, run = job["plan"], Path(run)
    cut = run / "cut"
    cut.mkdir(parents=True, exist_ok=True)
    by_key = {c["key"]: (c, f) for c, f in zip(plan["clips"], job["clips"])}
    name = plan["person"]["name"]
    ref = facecrop.load_ref(run)

    segs, subs, starts, ranks, t = [], [], [], [], 0.0
    for i, m in enumerate(plan["moments"]):
        c, f = by_key[m["clip"]]
        src, a, b = str(run / f["file"]), c["start"] - f.get("offset", 0), c["end"] - f.get("offset", 0)
        chunks = _chunks(m.get("words", []), c["start"], c["end"], t)
        punch = [chunks[-1][1] - t] if chunks else []   # punch-in on the answer: the last subtitle chunk
        dst = cut / f"seg{i}.mp4"
        cam = facecrop.track(src, start=a, end=b, ref=ref, models=cfg.get("models"))
        facecrop.render(src, dst, zoom=facecrop.mul(facecrop.push_in(1.0, 1.12, b - a), facecrop.punch(punch, 1.12)), face_y=FACE_Y, start=a, end=b, cam=cam)
        subs += chunks
        segs.append(dst); starts.append(t); ranks.append(m)
        t += b - a
    # closer: a frozen frame of the person (best identity match across the clips; else near the end of the last clip), slow push-in, darkened,
    # silent (audio rate matches the clips so concat is clean)
    closer_t, total = t, t + CLOSER
    mom = [(str(run / by_key[m["clip"]][1]["file"]), by_key[m["clip"]][0]["start"] - by_key[m["clip"]][1].get("offset", 0),
            by_key[m["clip"]][0]["end"] - by_key[m["clip"]][1].get("offset", 0)) for m in plan["moments"]]
    models = cfg.get("models")
    src, ft = closer_source(mom, run, (lambda s_, t_: _faces_at(s_, t_, models, cut / "pick.png")) if models else (lambda s_, t_: []))
    rate = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate", "-of", "csv=p=0", str(segs[0])], text=True).strip() or "44100"
    _ff("-ss", f"{ft:.2f}", "-i", src, "-frames:v", 1, cut / "freeze.png")
    _ff("-loop", 1, "-framerate", 30, "-i", cut / "freeze.png", "-f", "lavfi", "-i", f"anullsrc=r={rate}:cl=stereo", "-t", CLOSER,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", cut / "freeze.mp4")
    facecrop.render(str(cut / "freeze.mp4"), cut / "closer.mp4", zoom=facecrop.push_in(1.0, 1.1, CLOSER), face_y=FACE_Y,
                    grade="eq=brightness=-0.22:saturation=0.85", cam=facecrop.track(str(cut / "freeze.mp4")))
    segs.append(cut / "closer.mp4")
    (cut / "list.txt").write_text("".join(f"file '{p.resolve()}'\n" for p in segs))
    _ff("-f", "concat", "-safe", 0, "-i", cut / "list.txt", "-c:v", "libx264", "-crf", 18, "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-r", 30, "-c:a", "aac", "-ar", 44100, "-ac", 2, "-t", f"{total:.3f}", cut / "base.mp4")

    # audio: the clips' own speech + a whoosh just before every cut + clicks on the subscribe press and the like, loudnorm -14
    cuts = starts[1:] + [closer_t]
    ev = audio_events(cuts, closer_t)
    _ff("-i", cut / "base.mp4", *sum([["-i", f] for f, _, _ in ev], []), "-filter_complex", mix_filter(ev), "-map", "[a]", "-t", f"{total + 0.3:.2f}",
        "-c:a", "aac", "-b:a", "192k", cut / "mix.m4a")

    # overlays
    title = plan["title"]
    pre, _, post = title.partition(name)
    top = [(pre.strip() or f"Top {plan['n']}", 60, WHITE), (name.upper(), 92, RED)] + ([(post.strip(), 52, WHITE)] if post.strip() else [])
    head_h = _header(top, cut / "header_main.png")
    _header([("Why they're trending", 56, WHITE), (name.upper(), 92, RED)], cut / "header_news.png")
    cards = [dict(image=str(cut / "header_main.png"), start=0, end=closer_t, x=0, y=0, w=W, anim="cut"),
             dict(image=str(cut / "header_news.png"), start=closer_t, end=total, x=0, y=0, w=W, anim="cut")]
    shown = {}
    for i, m in enumerate(ranks):
        shown[m["rank"]] = m["label"]
        _rank_list(shown, plan["n"], cut / f"list_{i + 1}.png")
        cards.append(dict(image=str(cut / f"list_{i + 1}.png"), start=starts[i], end=cuts[i], x=LIST_X, y=head_h + 22, w=Image.open(cut / f"list_{i + 1}.png").width, anim="cut"))
    for i, (txt, a, b) in enumerate(subs):
        cards.append(dict(image=str(cut / f"cap_{i}.png"), start=a, end=b, x="center", y=1500, w=_caption(txt, cut / f"cap_{i}.png"), anim="cut"))
    cards += closer_cards(plan["closer"], cut, closer_t, total)
    spec = dict(cards=cards, flashes=[dict(at=c, dur=0.1) for c in cuts], shakes=[dict(at=c, dur=0.2, amp=14) for c in cuts])
    plain, CP.Cards = CP.Cards, _Cards   # compose looks Cards up in its own namespace
    try:
        CP.compose(str(cut / "base.mp4"), spec, str(run / "short.mp4"), audio=str(cut / "mix.m4a"))
    finally:
        CP.Cards = plain

    urls = list(dict.fromkeys(c["source"]["url"] for c in plan["clips"]))
    tl = [{"start": s, "end": e, "kind": "moment", "person": True} for s, e in zip(starts, starts[1:] + [closer_t])]
    return {"short": {"file": "short.mp4", "duration": total}, "timeline": tl + [{"start": closer_t, "end": total, "kind": "closer", "person": False}],
            "credits": [f"Footage: {u}" for u in urls]}
