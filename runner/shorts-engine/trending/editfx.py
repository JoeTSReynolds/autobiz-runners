"""Frame effects for the trending edit renderer: person matte, "AI enhance" look, After-Effects-style transitions, per-shot looks.
Frames are RGB uint8 (H, W, 3), any size; masks are float32 (H, W) alphas 0..1. numpy + cv2 only.

    segment(fr, models_dir)                       -> person alpha (MODNet ONNX via cv2.dnn, Apache-2.0, downloaded on first use, sha256 pinned)
    subject(fr, models_dir, prev)                 -> foreground alpha: the person, else the salient object (U2-Net-p, Apache-2.0); cutout_ok(m)
    inset_scale(m) / inset(fr, m, s)              -> a close-up shrunk over a blurred copy of itself, so the looks have background
    look(kind, fr, m, hist, bgs, t, pulse, n)     -> whole-shot montage look on the cut-out, kinds in LOOKS (echo, swap, scan, outline)
    fry(fr)                                       -> deep-fried enhance look (bilateral + detail + CLAHE + saturation + glow)
    transition(kind, out_fr, in_fr, u, m_out, m_in, sign) -> frame; u runs 0..1, kinds in KINDS, unknown kind returns in_fr
    grade(fr, i) / halftone(fr, strength)        per-shot colour and texture
"""
import os, urllib.request
from functools import lru_cache
from pathlib import Path
import cv2
import numpy as np
from .faces import _sha256

MODNET_NAME = 'modnet.onnx'
MODNET_URL = 'https://huggingface.co/Xenova/modnet/resolve/main/onnx/model.onnx'
MODNET_SHA256 = '07c308cf0fc7e6e8b2065a12ed7fc07e1de8febb7dc7839d7b7f15dd66584df9'
MODNET_SIDE = 512                 # long side of the network input (each side then floored to a multiple of 32)
KINDS = ('matte', 'flashblur', 'frame', 'spin', 'whip', 'punch', 'stutter')
WHITE = np.array([255, 255, 255], np.float32)
COOL = np.array([200, 225, 255], np.float32)   # glow tint of the matte silhouette
SPIN_DEG, SPIN_ZOOM, SPLIT_W, BLUR_W = 25.0, 0.3, 0.03, 0.03   # spin: angle, extra zoom, RGB split and blur as share of width
U2NET_NAME = 'u2netp.onnx'
U2NET_URL = 'https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx'
U2NET_SHA256 = '309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8'
U2NET_SIDE = 320
SUBJECT_MIN, SUBJECT_MAX, SUBJECT_EMA = 0.03, 0.5, 0.4   # cut-out area share: below MIN is no person (try the salient object), above MAX a close-up; prev weight
INSET_AREA, INSET_MIN = 0.4, 0.65   # a close-up shrinks (to at least INSET_MIN) until the subject is INSET_AREA of the frame
LOOKS = ('echo', 'swap', 'scan', 'outline')
ECHO = np.array([[40, 160, 255], [70, 110, 255], [140, 80, 255]], np.float32)   # silhouette copies: cyan, blue, violet (nearest first)
ECHO_DX, ECHO_GROW, ECHO_BG = 0.07, 0.04, 0.7    # still subject: copy j sits j * DX of the width aside, grown j * GROW; background dimmed to BG
DUO = (((20, 10, 80), (0, 230, 255)), ((60, 0, 40), (255, 80, 200)), ((0, 20, 60), (90, 200, 255)), ((40, 10, 0), (255, 170, 40)))   # (shadow, light)
NEON = ((0, 220, 255), (255, 60, 200), (120, 120, 255))
DOT_PERIOD = 6.0
GRADES = (  # (rgb gain, saturation, contrast): warm orange, teal-cyan, cold desaturated blue, neutral punchy
    ((1.15, 1.0, 0.80), 1.20, 0.35),
    ((0.82, 1.04, 1.18), 1.15, 0.35),
    ((0.88, 0.97, 1.15), 0.65, 0.30),
    ((1.0, 1.0, 1.0), 1.35, 0.45),
)


def _model(models_dir, name, url, sha):
    """Path of the verified model `name` in models_dir, downloading it first if missing. A file with the wrong hash is an error."""
    p = Path(models_dir) / name
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix('.part')
        with urllib.request.urlopen(url, timeout=300) as r, open(tmp, 'wb') as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        if _sha256(tmp) != sha:
            os.remove(tmp)
            raise RuntimeError(f'{url}: download sha256 does not match the pinned {sha}')
        os.replace(tmp, p)
    elif _sha256(p) != sha:
        raise RuntimeError(f'{p}: file sha256 does not match the pinned {sha}')
    return str(p)


def modnet_path(models_dir):
    return _model(models_dir, MODNET_NAME, MODNET_URL, MODNET_SHA256)


_NETS = {}


def segment(fr, models_dir):
    """Person alpha float32 (H, W) in 0..1 for an RGB frame."""
    path = modnet_path(models_dir)
    if path not in _NETS:
        _NETS[path] = cv2.dnn.readNetFromONNX(path)
    h, w = fr.shape[:2]
    s = MODNET_SIDE / max(h, w)
    tw, th = max(32, int(w * s) // 32 * 32), max(32, int(h * s) // 32 * 32)
    x = (cv2.resize(fr.astype(np.float32) / 255, (tw, th)) - 0.5) / 0.5
    net = _NETS[path]
    net.setInput(np.ascontiguousarray(x.transpose(2, 0, 1)[None]))
    a = net.forward()[0, 0]
    return np.clip(cv2.resize(a, (w, h)), 0, 1).astype(np.float32)


def _salient(fr, models_dir):
    """Salient-object alpha (U2-Net-p), min-max normalised."""
    path = _model(models_dir, U2NET_NAME, U2NET_URL, U2NET_SHA256)
    if path not in _NETS:
        _NETS[path] = cv2.dnn.readNetFromONNX(path)
    h, w = fr.shape[:2]
    x = (cv2.resize(fr.astype(np.float32) / 255, (U2NET_SIDE, U2NET_SIDE)) - (0.485, 0.456, 0.406)) / (0.229, 0.224, 0.225)
    _NETS[path].setInput(np.ascontiguousarray(x.transpose(2, 0, 1)[None].astype(np.float32)))
    a = _NETS[path].forward()[0, 0]
    a = (a - a.min()) / (a.max() - a.min() + 1e-6)
    return np.clip(cv2.resize(a, (w, h)), 0, 1).astype(np.float32)


def subject(fr, models_dir, prev=None):
    """Foreground alpha: the person (MODNet), else the most salient object; blended with the previous frame's alpha against flicker."""
    m = segment(fr, models_dir)
    if (m > 0.5).mean() < SUBJECT_MIN:
        m = _salient(fr, models_dir)
    return m if prev is None else (1 - SUBJECT_EMA) * m + SUBJECT_EMA * prev


def cutout_ok(m):
    """A cut-out the looks can use: neither missing nor a close-up filling the frame."""
    return SUBJECT_MIN <= float((m > 0.5).mean()) <= SUBJECT_MAX


def _half(f):
    return cv2.resize(f, (f.shape[1] // 2, f.shape[0] // 2), interpolation=cv2.INTER_AREA)


def fry(fr):
    """Deep-fried enhance look. Bilateral + detail run at half size; only their detail delta is added to the full frame."""
    h, w = fr.shape[:2]
    sm = _half(fr)
    e = cv2.detailEnhance(cv2.bilateralFilter(sm, 9, 40, 9), sigma_s=8, sigma_r=0.12)
    d = cv2.resize(e.astype(np.int16) - sm, (w, h), interpolation=cv2.INTER_LINEAR)
    s = np.clip(fr.astype(np.int16) + d, 0, 255).astype(np.uint8)
    lab = cv2.cvtColor(s, cv2.COLOR_RGB2LAB)
    lab[..., 0] = cv2.createCLAHE(2.0, (8, 8)).apply(lab[..., 0])
    hsv = cv2.cvtColor(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), cv2.COLOR_RGB2HSV)
    hsv[..., 1] = np.minimum(hsv[..., 1].astype(np.float32) * 1.25, 255).astype(np.uint8)
    s = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    g = cv2.resize(cv2.GaussianBlur(_half(_half(s)), (0, 0), 3), (w, h), interpolation=cv2.INTER_LINEAR)  # sigma 12 at quarter size
    return cv2.addWeighted(s, 0.85, g, 0.25, 0)


# ---- transitions -----------------------------------------------------------------------------------------------------------

def _mix(a, b, w):
    """a*(1-w) + b*w for frames/colours a, b; w scalar or (H, W)."""
    w = w[..., None] if np.ndim(w) == 2 else w
    return np.clip(np.asarray(a, np.float32) * (1 - w) + np.asarray(b, np.float32) * w, 0, 255).astype(np.uint8)


def _blur(f, sigma):
    """Gaussian blur; big sigmas run at quarter size."""
    if sigma < 0.5:
        return f
    if sigma <= 8:
        return cv2.GaussianBlur(f, (0, 0), sigma)
    h, w = f.shape[:2]
    return cv2.resize(cv2.GaussianBlur(cv2.resize(f, (w // 4, h // 4), interpolation=cv2.INTER_AREA), (0, 0), sigma / 4), (w, h), interpolation=cv2.INTER_LINEAR)


def _hblur(f, k):
    k = int(k) | 1
    return f if k < 3 else cv2.blur(f, (k, 1))


def _xform(f, ang=0.0, zoom=1.0, border=cv2.BORDER_REFLECT):
    if ang == 0 and zoom == 1:
        return f
    h, w = f.shape[:2]
    return cv2.warpAffine(f, cv2.getRotationMatrix2D((w / 2, h / 2), ang, zoom), (w, h), flags=cv2.INTER_LINEAR, borderMode=border)


def _split(f, px):
    """RGB split: red shifted right, blue left by px."""
    px = int(round(px))
    if px < 1:
        return f
    o = f.copy()
    o[..., 0] = np.roll(f[..., 0], px, 1)
    o[..., 2] = np.roll(f[..., 2], -px, 1)
    return o


def _smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def _scaled(m, s):
    """Mask scaled by s about its own centroid."""
    tot = float(m.sum())
    if tot < 1:
        return m
    ys, xs = np.indices(m.shape)
    cx, cy = float((m * xs).sum()) / tot, float((m * ys).sum()) / tot
    M = np.array([[s, 0, cx - s * cx], [0, s, cy - s * cy]], np.float32)
    return cv2.warpAffine(m, M, (m.shape[1], m.shape[0]), flags=cv2.INTER_LINEAR)


def _matte(out_fr, in_fr, u, m_in):
    if m_in is None:  # no silhouette: white radial burst from the centre
        h, w = out_fr.shape[:2]
        ys, xs = np.indices((h, w), dtype=np.float32)
        d = np.hypot(xs - w / 2, ys - h / 2) / np.hypot(w / 2, h / 2)
        cover = np.clip((2 * u * 1.25 - d) * 5, 0, 1)
        reveal = np.clip(((2 * u - 1) * 1.25 - d) * 5, 0, 1)
        return _mix(_mix(out_fr, WHITE, cover), in_fr, reveal) if u >= 0.5 else _mix(out_fr, WHITE, cover)
    if u < 0.45:  # white silhouette grows over the outgoing frame
        v = u / 0.45
        a = cv2.GaussianBlur(_scaled(m_in, 0.6 + 0.4 * v), (0, 0), 1.5)
        glow = _blur(a, 10) * 0.35 * min(1.0, u / 0.1)
        a = a * min(1.0, u / 0.1)  # fades in so u=0 is the outgoing frame
        base = _mix(out_fr, COOL, glow)
        return _mix(base, WHITE, a)
    a = cv2.GaussianBlur(m_in, (0, 0), 1.5)
    if u < 0.7:  # white fill turns into the person
        return _mix(out_fr, _mix(WHITE, in_fr, (u - 0.45) / 0.25), a)
    return _mix(_mix(out_fr, in_fr, (u - 0.7) / 0.3), in_fr, a)  # background fades in around them


def _flashblur(out_fr, in_fr, u):
    p = 1 - abs(2 * u - 1)
    base = out_fr if u < 0.5 else in_fr
    return _mix(_blur(base, SPLIT_W * 1.33 * base.shape[1] * p), WHITE, 0.85 * p)


def _paste(canvas, img, x, y):
    H, W = canvas.shape[:2]
    h, w = img.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 > x0 and y1 > y0:
        canvas[y0:y1, x0:x1] = img[y0 - y:y1 - y, x0 - x:x1 - x]


def _frame(out_fr, in_fr, u):
    h, w = out_fr.shape[:2]
    canvas = np.zeros_like(out_fr)
    if u < 0.15:  # outgoing shrinks 1.0 -> 0.85, then the cut
        s = 1 - 0.15 * (u / 0.15)
        _paste(canvas, cv2.resize(out_fr, (int(w * s), int(h * s))), (w - int(w * s)) // 2, (h - int(h * s)) // 2)
        return canvas
    v = (u - 0.15) / 0.85
    e = 1 - (1 - v) ** 3
    s = 0.72 + 0.28 * e
    sw, sh = int(w * s), int(h * s)
    img = cv2.copyMakeBorder(cv2.resize(in_fr, (sw, sh)), 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    shake = int(6 * (1 - e) * np.sin(u * 60))
    _paste(canvas, img, (w - sw) // 2 - 6 + shake, (h - sh) // 2 - 6 + shake // 2)
    return canvas


def _spin(out_fr, in_fr, u, sign):
    w = out_fr.shape[1]
    if u < 0.5:
        v, src, sg = u / 0.5, out_fr, 1
    else:
        v, src, sg = (1 - u) / 0.5, in_fr, -1
    r = _xform(src, sg * sign * SPIN_DEG * v, 1 + SPIN_ZOOM * v)
    return _split(_hblur(r, BLUR_W * w * v), SPLIT_W * w * v)


def _whip(out_fr, in_fr, u, sign):
    w = out_fr.shape[1]
    strip, off = (np.concatenate([out_fr, in_fr], 1), u * w) if sign >= 0 else (np.concatenate([in_fr, out_fr], 1), (1 - u) * w)
    off = int(round(off))
    return _hblur(strip[:, off:off + w], 0.15 * w * 4 * u * (1 - u))


def _punch(in_fr, u):
    k = (1 - u) ** 2
    return np.clip(_xform(in_fr, 0, 1 + 0.25 * k).astype(np.float32) * (1 + 0.15 * k), 0, 255).astype(np.uint8)


def transition(kind, out_fr, in_fr, u, m_out=None, m_in=None, sign=1):
    """Frame u (0..1) of transition `kind` from out_fr (the frozen last frame of the outgoing shot) to in_fr (the live incoming frame).
    Masks are segment() alphas or None; m_out is accepted for symmetry, no kind needs it yet. At u=1 every kind equals in_fr."""
    u = min(max(float(u), 0.0), 1.0)
    if kind == 'matte':
        return _matte(out_fr, in_fr, u, m_in)
    if kind == 'flashblur':
        return _flashblur(out_fr, in_fr, u)
    if kind == 'frame':
        return _frame(out_fr, in_fr, u)
    if kind == 'spin':
        return _spin(out_fr, in_fr, u, sign)
    if kind == 'whip':
        return _whip(out_fr, in_fr, u, sign)
    if kind == 'punch':
        return _punch(in_fr, u)
    if kind == 'stutter':
        return np.clip(in_fr.astype(np.float32) * (1 + 0.25 * max(0.0, 1 - u / 0.3)), 0, 255).astype(np.uint8)
    return in_fr


# ---- per-shot looks --------------------------------------------------------------------------------------------------------

def grade(fr, i):
    """Colourist-style look cycling by shot index: warm orange, teal-cyan, cold desaturated blue, neutral punchy."""
    gain, sat, con = GRADES[i % len(GRADES)]
    gray = cv2.cvtColor(cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
    s = cv2.addWeighted(fr, sat, gray, 1 - sat, 0)
    x = np.arange(256, dtype=np.float32) / 255
    curve = x * (1 - con) + con * x * x * (3 - 2 * x)  # gentle S-curve
    lut = np.stack([np.clip(curve * g, 0, 1) * 255 for g in gain], -1).round().astype(np.uint8)
    return cv2.LUT(s, lut.reshape(256, 1, 3))


# ---- montage looks (whole shot, on the subject cut-out) --------------------------------------------------------------------

def _soft(x, sigma):
    """Wide blur at quarter size (glows)."""
    h, w = x.shape[:2]
    return cv2.resize(cv2.GaussianBlur(cv2.resize(x, (w // 4, h // 4), interpolation=cv2.INTER_AREA), (0, 0), sigma / 4), (w, h), interpolation=cv2.INTER_LINEAR)


def _centroid(m):
    tot = float(m.sum())
    if tot < 1:
        return None
    ys, xs = np.indices(m.shape)
    return float((m * xs).sum()) / tot, float((m * ys).sum()) / tot


def _edge(m, px):
    """Ring px wide just outside the mask."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    b = (m > 0.5).astype(np.uint8)
    return np.clip(cv2.dilate(b, k).astype(np.float32) - b, 0, 1)


def _duotone(fr, i):
    lo, hi = (np.float32(x) for x in DUO[i % len(DUO)])
    l = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY).astype(np.float32)[..., None] / 255
    return np.clip(lo * (1 - l) + hi * l, 0, 255).astype(np.uint8)


def _zoomblur(fr, span, n=6):
    h, w = fr.shape[:2]
    acc = np.zeros(fr.shape, np.float32)
    for i in range(n):
        s = 1 + span * i / (n - 1)
        acc += cv2.warpAffine(fr, np.float32([[s, 0, w / 2 * (1 - s)], [0, s, h / 2 * (1 - s)]]), (w, h), borderMode=cv2.BORDER_REPLICATE)
    return (acc / n).astype(np.uint8)


def _echo(fr, m, hist, pulse):
    """Glowing blue silhouette copies trailing the subject's motion (masks 3/6/9 frames back); a still subject gets copies stepped
    out to the side and grown, pushed further on the beat."""
    h, w = m.shape
    c = _centroid(m)
    if c is None:
        return fr
    old = _centroid(hist[0]) if hist else None
    moving = old is not None and np.hypot(c[0] - old[0], c[1] - old[1]) > 0.02 * w
    out, glow = fr.astype(np.float32) * ECHO_BG, np.zeros(fr.shape, np.float32)
    for j in (3, 2, 1):  # furthest first so nearer copies sit on top
        if moving and len(hist) >= 3 * j:
            e = hist[-3 * j]
        else:
            s, dx = 1 + ECHO_GROW * j * (0.5 + pulse), -ECHO_DX * w * j * (0.7 + 0.6 * pulse)
            M = np.float32([[s, 0, c[0] * (1 - s) + dx], [0, s, c[1] * (1 - s) - 0.01 * h * j]])
            e = cv2.warpAffine(m, M, (w, h), flags=cv2.INTER_LINEAR)
        e = e * (1 - m)
        a = (e * (0.95 - 0.2 * j))[..., None]
        out = out * (1 - a) + ECHO[j - 1] * a
        glow += _soft(e, 14)[..., None] * ECHO[j - 1]
    out += glow * (0.5 + 0.6 * pulse)
    out = out * (1 - m[..., None]) + fr.astype(np.float32) * m[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def _swap(fr, m, bgs, pulse, n):
    """The subject stays sharp in a white outline; behind them another clip, zoom-blurred and duotoned, changing every beat n."""
    bg = _duotone(_zoomblur(bgs[n % len(bgs)] if bgs else fr, 0.06 + 0.12 * pulse), n)
    out = _mix(_mix(bg, WHITE, 0.5 * pulse), fr, m)
    return _mix(out, WHITE, _edge(m, max(2, fr.shape[1] // 160)))


def _scan(fr, m, t, pulse, n):
    """Background only: rippling scanlines over a duotone, white flash on the beat; the subject untouched inside a thin cyan rim."""
    h, w = fr.shape[:2]
    ph = 2 * np.pi * (np.arange(h, dtype=np.float32) / max(4, h // 160) - 1.5 * t)
    sq = np.sign(np.sin(ph))
    mx = np.arange(w, dtype=np.float32)[None, :] + (w * (0.015 + 0.04 * pulse) * np.sin(ph * 0.25 + 3 * t) * sq)[:, None]
    bg = cv2.remap(fr, mx, np.repeat(np.arange(h, dtype=np.float32)[:, None], w, 1), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    bg = _mix(bg, _duotone(bg, n + 1), 0.8).astype(np.float32) * (0.55 + 0.45 * (sq > 0))[:, None, None]
    out = _mix(_mix(bg, WHITE, 0.6 * pulse), fr, m)
    return _mix(out, (60, 220, 255), _edge(m, max(1, w // 300)) * 0.9)


def _outline(fr, m, pulse, n):
    """Neon glow around the subject flaring on each beat, white rim; the background desaturated and dimmed."""
    w = fr.shape[1]
    g = cv2.cvtColor(cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
    out = cv2.addWeighted(fr, 0.35, g, 0.65, 0).astype(np.float32) * 0.6 * (1 - m[..., None]) + fr.astype(np.float32) * m[..., None]
    gl = np.clip(_soft(_edge(m, max(4, w // 90)), 10 + 20 * pulse) * (4 + 6 * pulse), 0, 1.5 + 1.5 * pulse)
    out += gl[..., None] * np.float32(NEON[n % len(NEON)]) * (1 - m[..., None])
    return _mix(out, WHITE, _edge(m, max(2, w // 200)))


def inset_scale(m):
    """Scale that brings a close-up's subject down to INSET_AREA of the frame (at least INSET_MIN); 1.0 when it already fits."""
    a = float((m > 0.5).mean())
    return 1.0 if a <= SUBJECT_MAX else max(INSET_MIN, (INSET_AREA / a) ** 0.5)


def inset(fr, m, s):
    """(frame, alpha): the subject cut out, scaled by s and bottom-centred over a blurred copy of the frame; s = 1 returns them unchanged."""
    if s >= 1:
        return fr, m
    h, w = m.shape
    M = np.float32([[s, 0, w * (1 - s) / 2], [0, s, h * (1 - s)]])
    warp = lambda x: cv2.warpAffine(x, M, (w, h), flags=cv2.INTER_LINEAR)
    ms = warp(m)
    return _mix(_blur(fr, 0.03 * w), warp(fr), ms), ms


def look(kind, fr, m, hist=(), bgs=(), t=0.0, pulse=0.0, n=0):
    """Montage look `kind` (LOOKS) on frame fr with subject alpha m. hist: earlier alphas of this shot (newest last), bgs: frames of other
    shots, t: seconds, pulse: beat pulse 0..1, n: beat count (picks backgrounds and colours). Unknown kind returns fr."""
    if kind == 'echo':
        return _echo(fr, m, hist, pulse)
    if kind == 'swap':
        return _swap(fr, m, bgs, pulse, n)
    if kind == 'scan':
        return _scan(fr, m, t, pulse, n)
    if kind == 'outline':
        return _outline(fr, m, pulse, n)
    return fr


@lru_cache(maxsize=4)
def _screen(h, w):
    ys, xs = np.indices((h, w), dtype=np.float32)
    k = 2 * np.pi / DOT_PERIOD
    u, v = (xs + ys) * 0.7071 * k, (xs - ys) * 0.7071 * k  # 45 degree dot grid
    return 0.5 + 0.25 * (np.cos(u) + np.cos(v))             # 0..1 threshold map


def halftone(fr, strength=0.15):
    """Subtle dot-screen texture: darkens the pixels whose brightness is below the dot threshold."""
    lum = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    on = np.clip((lum - _screen(*fr.shape[:2])) * 8 + 0.5, 0, 1)
    return np.clip(fr.astype(np.float32) * (1 - strength * (1 - on))[..., None], 0, 255).astype(np.uint8)
