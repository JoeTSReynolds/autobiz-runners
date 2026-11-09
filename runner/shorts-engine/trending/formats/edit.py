"""Person-edit renderer: the person's own story over an edit track that builds, drops on `plan.dropLine`, then takes over completely.
Cut rate speeds up after the drop (3 beats per shot before, 1-2 after), stat slams follow the drop line, captions at 0.8 scale,
and after the last line speech stops: the last ~35 % is a pure edit (`assets.tail`) cut on the beat grid, building to a hard cut on a hit.
Look generalised from prototypes/trending/person-edit/build.py + engine.py.

    from trending.formats import edit; edit.render(job, cfg, run_dir) -> {short, timeline, credits}

Reads job["plan"] (lines[{clip, words}], dropLine, slams, popups, musicOffset), job["clips"] (`plan.clips[i]` <-> `job.clips[i]`; file time = source
time - offset), job["assets"] ({broll[{line, file, kind}], tail[{file, kind}]}), job["track"] ({file, analysis}). Paths are relative to `run`;
intermediates go to run/cut/, the video to run/short.mp4.
"""
import math, subprocess
from pathlib import Path
import cv2
import numpy as np
from .. import captions as C, compose as CP, facecrop, music
from ..facecrop import probe, FPS
from .tribute import _ff, _lufs

W, H = 1080, 1920
GAIN_DB, DUCK_DB, TARGET_LUFS = -6, 12, -14
TAIL_SHARE, PRE_BEATS, LAST_S, HOLD_MIN = 0.35, 3, 5.0, 0.15
TAIL_FX = ["whip", "punch", "flash", "shake"]   # one per downbeat, in turn
XFADE = 0.03                                    # audio fade at each filler cut
# Tail effects. k rises K0 -> 1 over the pure-edit tail (and 0 -> K0 over the last speech line), eased by K_POW; every shot change
# adds a short pulse (PULSE_DUR s, weight by transition) on top. Tune these; nothing else needs to change.
TAIL_K0, K_POW, PULSE_DUR = 0.15, 1.6, 0.25
PULSE_W = {"whip": 1.0, "punch": 1.0, "flash": 1.0, "shake": 1.0, "hit": 1.0, "blur": 0.45}   # downbeats strongest
WHIP_GAIN = 1.0       # whip/zoom transition blur: x (1 + gain * k)
MOVE_BLUR = 14.0      # radial blur span = zoom change per frame * this * k (camera moves)
PULSE_BLUR = 0.07     # extra radial span at a full pulse
CHROMA_PX, CHROMA_PULSE = 4.0, 16.0   # RGB split in px: CHROMA_PX * k + CHROMA_PULSE * pulse
GLOW, GLOW_PULSE, GLOW_TINT = 0.30, 0.22, (0.85, 1.0, 1.25)   # bloom strength (k, pulse) and its cool tint (r, g, b)
SAT, CON = 0.30, 0.14                 # grade rising to x(1 + SAT) saturation and x(1 + CON) contrast at k = 1
MIN_SHOT = 0.3                         # no speech shot shorter than this (a sliver is absorbed by the shot before it)
# Speed ramp on b-roll and tail shots: source speed starts at RAMP_FAST, eases down to RAMP_SLOW by RAMP_IN s, stays there, then eases
# back up to RAMP_FAST over the last RAMP_OUT s (shots shorter than both scale the ramps). Camera moves on images follow the same curve.
RAMP_FAST, RAMP_SLOW, RAMP_IN, RAMP_OUT = 2.5, 0.4, 0.5, 0.4
SPEED_BLUR = 0.06     # radial blur span at full RAMP_FAST speed (on top of MOVE_BLUR * k)
FACE_MAX = 0.48       # the speaker's face is at most this share of the frame width
RMS_HOP, IN_WIN, OUT_WIN, FADE = 0.02, (-0.35, 0.1), (-0.25, 0.35), 0.015   # audio cut search (s): quietest frame near the planned point; join fade
GRADE = "eq=contrast=1.12:saturation=1.12:brightness=-0.02,unsharp=5:5:0.7"


# ------------------------------------------------------------------ schedule (pure)
def grid(an, off, hi):
    """Beat times on the video timeline: the analysis beats shifted by the music offset, extended with the tempo to cover [0, hi]."""
    per = 60 / an["bpm"]
    bs = [b - off for b in (an.get("beats") or [an["drop"]]) if b - off > -1e-6]
    pre = [bs[0] - per * k for k in range(int((bs[0] + 1e-6) // per), 0, -1)]
    post = [bs[-1] + per * k for k in range(1, int(max(hi - bs[-1], 0) // per) + 2)]
    return pre + bs + post


def _first(g, t, lo=0):
    return next(i for i in range(lo, len(g)) if g[i] >= t - 1e-6)


def schedule(ld, dl, ns, g, td, share=TAIL_SHARE, music_len=None):
    """Shots on the beat grid g. ld: line durations; dl: drop line; ns: slams; td: video time the drop line starts (= sum(ld[:dl])).
    Returns {shots[{t0,t1,kind S|B|T,trans,slam?}], lines[(start,end)], slams[(start,end)], tdend, gap, tT (tail start), D}."""
    d0 = min(range(len(g)), key=lambda i: abs(g[i] - td))
    tdend = td + ld[dl]
    k1 = max(_first(g, tdend), d0 + 1)
    kg = k1 + 2 * ns                       # speech resumes here
    gap = g[kg] - tdend
    lines, t = [], 0.0
    for i, d in enumerate(ld):
        t0 = t + (gap if i > dl else 0)
        lines.append((t0, t0 + d))
        t += d
    kT = _first(g, lines[-1][1] + HOLD_MIN)
    kT += (kT - d0) % 2                   # 2-beat tail shots then land on downbeats
    kE = min(range(kT + 2, len(g)), key=lambda i: abs(g[i] - g[kT] / (1 - share)))
    while 1 - g[kT] / g[kE] < share - 0.04 and kE + 1 < len(g):
        kE += 1
    while 1 - g[kT] / g[kE] > share + 0.04 and kE - 1 > kT + 1:
        kE -= 1
    while music_len and g[kE] > music_len and kE - 1 > kT + 1:
        kE -= 1
    sh = []
    add = lambda a, b, kind, trans="blur", **kw: sh.append(dict(t0=g[a], t1=g[b], kind=kind, trans=trans, **kw))
    cuts = [d0 - PRE_BEATS * m for m in range(d0 // PRE_BEATS, 0, -1) if g[d0 - PRE_BEATS * m] > 1.0] + [d0]
    for n, (a, b) in enumerate(zip([0] + cuts, cuts)):
        sh.append(dict(t0=0.0 if n == 0 else g[a], t1=g[b], kind="SB"[n % 2 == 1], trans="blur" if n else None))
    i, n = d0, 0
    while i < k1:                          # after the drop: b-roll 1 beat, speaker 2 beats
        j = min(i + (1 if n % 2 == 0 else 2), k1)
        add(i, j, "BS"[n % 2], "drop" if i == d0 else "blur")
        i, n = j, n + 1
    for j in range(ns):
        add(k1 + 2 * j, k1 + 2 * j + 2, "B", "slam", slam=j)
    i, n = kg, 0
    while i < kT:
        j = min(i + (2 if n % 2 == 0 else 1), kT)
        add(i, j, "SB"[n % 2], "blur")
        i, n = j, n + 1
    sh[-1]["kind"] = "S"                   # the payoff line is always on the speaker
    i, nd = kT, 0
    while i < kE:
        j = min(i + (1 if g[i] >= g[kE] - LAST_S - 1e-6 else 2), kE)
        down = i == kT or (i - d0) % 4 == 0
        tr = "blur"
        if j == kE:
            tr = "hit"
        elif down:
            tr, nd = TAIL_FX[nd % 4], nd + 1
        add(i, j, "T", tr)
        i = j
    sh = _tidy(sh, lines)
    return dict(shots=sh, lines=lines, slams=[(g[k1 + 2 * j], g[k1 + 2 * j + 2]) for j in range(ns)], tdend=tdend, gap=gap, tT=g[kT], D=g[kE])


def _tidy(sh, lines):
    """Speech shots (S/B, no slam): a shot under MIN_SHOT is absorbed by the shot before it; a speaker-to-speaker cut on a line start gets a flash."""
    ok = lambda x: x["kind"] in "SB" and "slam" not in x
    out = []
    for x in sh:
        if out and ok(x) and ok(out[-1]) and x["t1"] - x["t0"] < MIN_SHOT and x["trans"] != "drop":
            out[-1]["t1"] = x["t1"]
            continue
        if out and ok(x) and ok(out[-1]) and x["kind"] == out[-1]["kind"] == "S" and x["trans"] == "blur" and any(abs(x["t0"] - a) < 0.02 for a, _ in lines[1:]):
            x["trans"] = "flash"
        out.append(x)
    return out


def speed_curve(d, avail=None):
    """Speed ramp for a shot of d s -> (pos, v, need): source seconds and speed (x) at each output frame, and the source needed (the integral
    of v over the shot). With avail (source s left in the clip) the curve is scaled down when it needs more than that."""
    n = max(round(d * FPS), 1)
    d = n / FPS
    zi, zo = RAMP_IN, RAMP_OUT
    if d < zi + zo:
        zi, zo = zi * d / (zi + zo), zo * d / (zi + zo)
    sm = lambda u: np.clip(u, 0, 1) ** 2 * (3 - 2 * np.clip(u, 0, 1))
    t = np.arange(4 * n + 1) / (4 * FPS)
    v = RAMP_SLOW + (RAMP_FAST - RAMP_SLOW) * np.where(t < zi, 1 - sm(t / zi), sm((t - (d - zo)) / zo))
    cum = np.concatenate([[0], np.cumsum((v[1:] + v[:-1]) / 2 / (4 * FPS))])
    pos, v, need = cum[:4 * n:4], v[:4 * n:4], cum[-1]
    if avail is not None and need > avail:
        k = avail / need
        pos, v, need = pos * k, v * k, avail
    return pos, v, need


def tail_slots(n, photos):
    """Tail shot indices (of n) that show the person: with photos about one in three, never adjacent; without, one or two spread
    moments from the speaker's own clips."""
    if photos:
        return set(range(1, n, 3))
    return set() if n < 3 else {n // 2} if n < 6 else {n // 3, 2 * n // 3}


def zoom_cap(size, W, H, face_max=FACE_MAX):
    """Largest total zoom of a W x H source at which a face `size` px wide stays under face_max of the 9:16 frame width."""
    return face_max * min(H, W * 16 / 9) * 9 / 16 / size if size > 0 else 99.0


def zoom_pair(z0, cap, step=0.1):
    """(start, end) of a push-in kept inside [1, max(cap, 1)]."""
    hi = max(cap, 1.0)
    a = max(min(z0, hi), 1.0)
    return a, min(a + step, hi)


def quiet_point(rms, t, lo, hi, hop=RMS_HOP):
    """Time of the quietest RMS frame (one per hop s from 0) within [t+lo, t+hi], inside the file. Levels within 3 dB count as equal: the
    one nearest t wins, so a flat noise floor keeps the planned point."""
    if not len(rms):
        return t
    dur = len(rms) * hop
    i0, i1 = math.ceil(max(t + lo, 0) / hop - 1e-9), min(math.floor(min(t + hi, dur) / hop + 1e-9) - 1, len(rms) - 1)
    if i1 < i0:
        return min(max(t, 0), dur)
    key = lambda i: (math.floor(20 * math.log10(rms[i] + 1e-6) / 3), abs((i + 0.5) * hop - t))
    return (min(range(i0, i1 + 1), key=key) + 0.5) * hop


def _rms(path):
    """RMS level per RMS_HOP of the file's audio (8 kHz mono); empty if there is none."""
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(path), "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw[:len(raw) // 4 * 4], np.float32)
    m = int(8000 * RMS_HOP)
    return np.sqrt((x[:len(x) // m * m].reshape(-1, m) ** 2).mean(1)) if len(x) >= m else np.zeros(0)


def tail_k(t, lead, tT, D, pulses=()):
    """Effect intensity at video time t -> (k, pulse), both 0..1. k: 0 before `lead` (last speech line), K0 at the tail start tT, 1 at D, eased.
    pulse: pulses [(time, weight)] decay over PULSE_DUR, scaled up as k rises."""
    if t < lead:
        return 0.0, 0.0
    e = lambda u: min(max(u, 0.0), 1.0) ** K_POW
    k = TAIL_K0 * e((t - lead) / max(tT - lead, 1e-6)) if t < tT else TAIL_K0 + (1 - TAIL_K0) * e((t - tT) / max(D - tT, 1e-6))
    p = sum(w * (1 - (t - a) / PULSE_DUR) ** 2 for a, w in pulses if 0 <= t - a < PULSE_DUR)
    return k, min(p * (0.5 + 0.5 * k), 1.0)


def _tail_fx(fr, k, p, dz, sp=0.0):
    """Build-up look on one RGB frame: radial blur (camera zoom change per frame dz, pulses, source speed sp 0..1), RGB split, cool bloom,
    saturation and contrast."""
    if k <= 0 and p <= 0 and sp <= 0:
        return fr
    span = abs(dz) * MOVE_BLUR * k + PULSE_BLUR * p + SPEED_BLUR * sp
    if span > 0.004:
        acc = np.zeros(fr.shape, np.float32)
        for i in range(7):
            s = 1 + span * i / 6
            acc += cv2.warpAffine(fr, np.float32([[s, 0, W / 2 * (1 - s)], [0, s, H / 2 * (1 - s)]]), (W, H), borderMode=cv2.BORDER_REPLICATE)
        fr = (acc / 7).astype(np.uint8)
    if k <= 0 and p <= 0:
        return fr
    o = int(round(CHROMA_PX * k + CHROMA_PULSE * p))
    if o:
        fr = fr.copy()
        fr[:, o:, 0] = fr[:, :-o, 0].copy()   # red right, blue left
        fr[:, :-o, 2] = fr[:, o:, 2].copy()
    sm = cv2.resize(fr, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
    sm = cv2.GaussianBlur(cv2.subtract(sm, 140), (0, 0), 5).astype(np.float32) * (GLOW * k + GLOW_PULSE * p) * 2.2 * np.float32(GLOW_TINT)
    fr = cv2.add(fr, cv2.resize(np.clip(sm, 0, 255).astype(np.uint8), (W, H), interpolation=cv2.INTER_LINEAR))
    gray = cv2.cvtColor(cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
    s = 1 + SAT * k
    fr = cv2.addWeighted(fr, s, gray, 1 - s, 0)
    c = 1 + CON * k
    return cv2.convertScaleAbs(fr, alpha=c, beta=128 * (1 - c))


# ------------------------------------------------------------------ frames
def _ease(u):
    return facecrop._ease(u)


def _zoom_about(fr, z, cy=0.40):
    M = np.float32([[z, 0, W / 2 * (1 - z)], [0, z, cy * H * (1 - z)]])
    return cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def _crop(fr, z, ox=0.5, oy=0.5):
    h, w = fr.shape[:2]
    ch = min(h, w * 16 / 9) / z
    cw = ch * 9 / 16
    x0, y0 = min(max(ox * w - cw / 2, 0), w - cw), min(max(oy * h - ch / 2, 0), h - ch)
    s = W / cw
    return cv2.warpAffine(fr, np.float32([[s, 0, -x0 * s], [0, s, -y0 * s]]), (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def _fx(fr, kind, k, sign=1, gain=1.0):
    """Transition look at strength k in (0, 1]: blur = radial zoom blur, whip = sideways slide + motion blur, punch = zoom spike."""
    if kind == "whip":
        fr = cv2.warpAffine(fr, np.float32([[1, 0, sign * 0.3 * W * k], [0, 1, 0]]), (W, H), borderMode=cv2.BORDER_REPLICATE)
        return cv2.blur(fr, (max(int(170 * k * gain), 1), 1))
    if kind == "punch":
        return np.clip(_zoom_about(fr, 1 + 0.25 * k, 0.5).astype(np.float32) * (1 + 0.15 * k), 0, 255).astype(np.uint8)
    acc = np.zeros(fr.shape, np.float32)
    for i in range(5):
        s = 1 + 0.30 * k * gain * i / 4
        acc += cv2.warpAffine(fr, np.float32([[s, 0, W / 2 * (1 - s)], [0, s, H / 2 * (1 - s)]]), (W, H), borderMode=cv2.BORDER_REPLICATE)
    return np.clip(acc / 5 * (1 + 0.35 * k) + 28 * k, 0, 255).astype(np.uint8)


FX = {"whip": "whip", "punch": "punch", "drop": "punch", "hit": "punch"}   # everything else (flash, shake, slam, blur) starts with a zoom blur


class _Reader:
    """Sequential RGB frames of a video section or a looped image; holds the last frame if the source runs out."""
    def __init__(self, path, ss, dur, image):
        w, h = map(int, subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path], text=True).strip().split(",")[:2])
        s = min(1.0, 1920 / max(w, h))
        self.w, self.h = int(w * s) // 2 * 2, int(h * s) // 2 * 2
        src = ["-loop", "1", "-framerate", str(FPS), "-i", path] if image else ["-ss", f"{ss:.3f}", "-i", path]
        self.p = subprocess.Popen(["ffmpeg", "-v", "quiet", *src, "-t", f"{dur + 0.3:.3f}", "-vf", f"fps={FPS},scale={self.w}:{self.h}", "-an",
                                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.last, self.sz = np.zeros((self.h, self.w, 3), np.uint8), self.w * self.h * 3
        self.prev, self.idx = self.last, -1

    def next(self):
        b = self.p.stdout.read(self.sz)
        if len(b) == self.sz:
            self.last = np.frombuffer(b, np.uint8).reshape(self.h, self.w, 3)
        return self.last

    def at(self, x):
        """Frame at (fractional, non-decreasing) source frame x: the two neighbours blended, so slow motion does not stutter."""
        i = int(x)
        while self.idx < i + 1:
            self.prev = self.last
            self.next()
            self.idx += 1
        f = x - i
        return self.prev if f < 0.02 else cv2.addWeighted(self.prev, 1 - f, self.last, f, 0)

    def close(self):
        self.p.stdout.close(); self.p.kill(); self.p.wait()


def _split_person(tl, shots):
    """Speech and hold entries cut at the shots inside them: only speaker shots ("S") are person shots, a b-roll cutaway is not."""
    out = []
    for e in tl:
        if not e["person"]:
            out.append(e)
            continue
        pieces = []
        for s in shots:
            a, b = max(e["start"], s["t0"]), min(e["end"], s["t1"])
            if b - a > 1e-6:
                p = s["kind"] == "S"
                if pieces and pieces[-1]["person"] == p and abs(pieces[-1]["end"] - a) < 1e-6:
                    pieces[-1]["end"] = b
                else:
                    pieces.append(dict(e, start=a, end=b, person=p))
        out += pieces if pieces and abs(pieces[0]["start"] - e["start"]) < 1e-6 and abs(pieces[-1]["end"] - e["end"]) < 1e-6 else [e]
    return out


def _assemble(shots, spk, dst, total, fx=lambda t: (0.0, 0.0)):
    """fx(t) -> (k, pulse): the tail build-up (tail_k); (0, 0) leaves a frame untouched."""
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", dst], stdin=subprocess.PIPE)
    f0 = 0
    for k, s in enumerate(shots):
        f1 = total if k + 1 == len(shots) else round(shots[k + 1]["t0"] * FPS)
        n = f1 - f0
        sk, vid = s["kind"] == "S", s["kind"] != "S" and not s["image"]
        pos, vel, need = (np.zeros(n), np.zeros(n), n / FPS) if sk else speed_curve(n / FPS, s.get("avail"))
        prog = np.array([_ease(i / max(n - 1, 1)) for i in range(n)]) if sk else pos / max(pos[-1], 1e-9)   # camera follows the speed curve
        rd = _Reader(spk if sk else s["file"], s["ss"], need if vid else n / FPS, not sk and s["image"])
        nxt = FX.get(shots[k + 1]["trans"], "blur") if k + 1 < len(shots) and shots[k + 1]["trans"] == "whip" else None
        for i in range(n):
            fr = rd.at(pos[i] * FPS) if vid else rd.next()
            z = s["z0"] + (s["z1"] - s["z0"]) * prog[i]
            fr = _zoom_about(fr, z) if s["kind"] == "S" else _crop(fr, z, s["ox"], s["oy"])
            kk, pp = fx((f0 + i) / FPS)
            if k and i < 3:
                fr = _fx(fr, FX.get(s["trans"], "blur"), 1 - i / 3, 1, 1 + WHIP_GAIN * kk)
            if nxt and i >= n - 2:
                fr = _fx(fr, "whip", 0.5 if i == n - 2 else 1.0, -1, 1 + WHIP_GAIN * kk)
            dz = (s["z1"] - s["z0"]) * (prog[i] - prog[max(i - 1, 0)])
            fr = _tail_fx(fr, kk, pp, dz, float(np.clip((vel[i] - 1) / (RAMP_FAST - 1), 0, 1)))
            enc.stdin.write(np.ascontiguousarray(fr).tobytes())
        rd.close()
        f0 = f1
    enc.stdin.close(); enc.wait()
    if enc.returncode:
        raise RuntimeError("base encode failed")


# ------------------------------------------------------------------ render
def _line_words(line, c):
    return [w for w in line.get("words", []) if c["start"] - 0.03 <= w["s"] < c["end"] and w["w"].replace(">>", "").strip() and not w["w"].startswith("[")]


def _cuts(line, c):
    """Spans (source seconds, snapped to frames) of fillers and stutter repeats inside a line: speech and video are cut there."""
    ws, out = _line_words(line, c), []
    for i in C.filler_idx([C.censor(w["w"].replace(">>", "").strip()) for w in ws]):
        w, nxt = ws[i], ws[i + 1]["s"] if i + 1 < len(ws) else c["end"]
        a = max(w["s"], c["start"])
        # a filler lasts what ASR says (capped like caption words); a stutter runs up to the repeated word
        b = nxt if C.filler_idx([ws[i]["w"]]) == set() else min(w["e"], nxt, w["s"] + 0.3 + 0.1 * len(w["w"]))
        a, b = round((a - c["start"]) * FPS) / FPS, round((b - c["start"]) * FPS) / FPS
        if b - a >= 0.05:
            out.append((a + c["start"], b + c["start"]))
    return sorted(out)


def _cut_file(src, dst, cuts, c0, dur):
    """Re-encode src without the spans `cuts` (source time, c0 = the clip's start), with an XFADE fade at each join."""
    keep, t = [], 0.0
    for a, b in cuts + [(c0 + dur, c0 + dur)]:
        if a - c0 > t + 1e-6:
            keep.append((t, a - c0))
        t = b - c0
    fc = []
    for j, (a, b) in enumerate(keep):
        fa = ("afade=t=in:d=%s," % XFADE if j else "") + ("afade=t=out:st=%.3f:d=%s," % (b - a - XFADE, XFADE) if j + 1 < len(keep) else "")
        fc += [f"[0:v]trim={a:.4f}:{b:.4f},setpts=PTS-STARTPTS[v{j}]", f"[0:a]atrim={a:.4f}:{b:.4f},asetpts=PTS-STARTPTS,{fa}aresample=44100[a{j}]"]
    fc.append("".join(f"[v{j}][a{j}]" for j in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=1[v][a]")
    _ff("-i", src, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-r", FPS, "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", dst)


def _words(line, c, v0, cuts=(), t0=None):
    """Line words -> [{w, s, e}] on the output timeline (v0 = the line's start); `cuts` (from _cuts) are taken out of the times.
    t0: source time the line's audio really starts (its in point was moved to a quiet frame); default c["start"]."""
    t0 = c["start"] if t0 is None else t0
    ws = _line_words(line, c)
    gone = lambda x: sum(min(b, x) - a for a, b in cuts if x > a)
    out = []
    for i, w in enumerate(ws):
        s = v0 + w["s"] - gone(w["s"]) - t0
        e = v0 + (ws[i + 1]["s"] if i + 1 < len(ws) else min(w["e"], c["end"])) - gone(ws[i + 1]["s"] if i + 1 < len(ws) else min(w["e"], c["end"])) - t0
        out.append(dict(w=w["w"].replace(">>", "").strip(), s=s, e=max(e, s + 0.1)))
    return out


def _pick(pool, uses, line, rng_ss=2.5, prev=None):
    """Next b-roll for a line: literal matches first, unused before reused; reused files start at a later in-point. Never `prev` (the file of
    the shot before) unless the pool has no other file."""
    ok = [i for i in range(len(pool)) if pool[i]["file"] != prev] or list(range(len(pool)))
    j = min(ok, key=lambda i: abs(pool[i].get("line", line) - line) + 2 * uses.get(pool[i]["file"], 0))
    it, n = pool[j], uses.get(pool[j]["file"], 0)
    uses[it["file"]] = n + 1
    return it, n * rng_ss


def render(job, cfg, run):
    plan, assets, run = job["plan"], job.get("assets") or {}, Path(run)
    cut = run / "cut"
    cut.mkdir(parents=True, exist_ok=True)
    by_key = {c["key"]: (c, f) for c, f in zip(plan["clips"], job["clips"])}
    lines = [(l, *by_key[l["clip"]]) for l in plan["lines"]]
    dl, slams = plan["dropLine"], plan["slams"]

    # speaker: one face-crop render per line (with its audio), concatenated
    ld, ref, cuts, lost, t0s, ezs, rms = [], facecrop.load_ref(run), [], [], [], [], {}
    for i, (l, c, f) in enumerate(lines):
        src, a, b = str(run / f["file"]), c["start"] - f.get("offset", 0), c["end"] - f.get("offset", 0)
        # safety net: a line's in and out points go to the quietest frame near the plan, so no line starts or ends mid-word
        W_, H_, fd = probe(src)
        r = rms.setdefault(src, _rms(src))
        a2, b2 = quiet_point(r, a, *IN_WIN), quiet_point(r, b, *OUT_WIN)
        a2, b2 = max(a2, 0.0), min(b2, fd)
        if b2 - a2 > 0.5 * (b - a):
            a, b = a2, b2
        t0s.append(a + f.get("offset", 0))
        cam = facecrop.track(src, start=a, end=b, ref=ref, models=cfg.get("models"))
        sz = cam["size"][cam["found"]]
        zc = zoom_cap(float(np.percentile(sz, 90)) if len(sz) else 0, W_, H_)   # total zoom keeping the face under FACE_MAX of the width
        z2 = max(1.0, min(1.75, zc))
        ezs.append(max(1.0, zc / z2))
        facecrop.render(src, cut / f"spk{i}.mp4", zoom=facecrop.push_in(max(1.0, min(1.6, zc)), z2, b - a), face_y=0.40, start=a, end=b, grade=GRADE, cam=cam)
        cuts.append(_cuts(l, c))
        if cuts[i]:
            (cut / f"spk{i}.mp4").replace(cut / f"full{i}.mp4")
            full = probe(str(cut / f"full{i}.mp4"))[2]
            _cut_file(str(cut / f"full{i}.mp4"), str(cut / f"spk{i}.mp4"), cuts[i], t0s[i], full)
        ld.append(probe(str(cut / f"spk{i}.mp4"))[2])
        lost.append(c["end"] - c["start"] - ld[i])   # what the cuts and snapped points took off the planned length
    (cut / "spk.txt").write_text("".join(f"file 'spk{i}.mp4'\n" for i in range(len(lines))))
    _ff("-f", "concat", "-safe", 0, "-i", cut / "spk.txt", "-c", "copy", cut / "spk.mp4")

    track = job["track"]
    mp, an = str(run / track["file"]), track["analysis"]
    td = sum(ld[:dl])
    off = plan.get("musicOffset")
    if off is None:
        off = music.place(an, td, 0)["music_offset"]
    else:  # the plan placed the drop for the uncut lines: what the filler cuts took out before the drop line moves the music with it
        off += sum(lost[:dl])
    S = schedule(ld, dl, len(slams), grid(an, off, 90.0), td, music_len=(an.get("duration") or 0) - off or None)
    D, shots, vs = S["D"], S["shots"], S["lines"]
    total = round(D * FPS)

    # visuals: speaker shots seek into spk.mp4 (the slam gap is not in it), b-roll and tail shots pick files
    line_at = lambda t: max(i for i, (a, _) in enumerate(vs) if a <= t + 1e-6)
    uses, tuses, puses, nb, nt, ti, mom, prev = {}, {}, {}, 0, 0, 0, 0, None
    broll, tails, persons = assets.get("broll") or [], list(assets.get("tail") or []), list(assets.get("person") or [])
    slots = tail_slots(sum(x["kind"] == "T" for x in shots), bool(persons))
    img = lambda it: it.get("kind") == "image" or str(it["file"]).lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    for s in shots:
        s.update(ss=0.0, z0=1.0, z1=1.1, ox=0.5, oy=0.5)
        if s["kind"] == "S":
            s["ss"] = s["t0"] - (S["gap"] if s["t0"] >= S["tdend"] else 0)
            cap = min(ezs[j] for j, (a, b) in enumerate(vs) if a < s["t1"] and b > s["t0"]) if any(a < s["t1"] and b > s["t0"] for a, b in vs) else 1.0
            s["z0"], s["z1"] = zoom_pair([1.0, 1.12, 1.24][nb % 3], cap)
            nb += 1
            prev = None
            continue
        isT, avail = s["kind"] == "T", None
        if isT and ti in slots and persons:
            it, ss = _pick(persons, puses, 0, prev=prev)
        elif isT and ti in slots:   # no photos: a short slow-motion moment from the speaker's own clips
            j, mom = mom % len(lines), mom + 1
            c, f = lines[j][1], lines[j][2]
            it, ss, avail = dict(file=f["file"]), max(c["start"] - f.get("offset", 0) + 0.3, 0.0), c["end"] - c["start"] - 0.3
        else:
            it, ss = _pick(tails + broll if isT else broll, tuses if isT else uses, dl if "slam" in s else line_at(s["t0"]), prev=prev)
        ti += isT
        nt += isT
        prev = it["file"]
        im = img(it) and avail is None
        if not im and avail is None:   # a reused clip may start past its end: restart it, and ramp within what is left
            fd = probe(str(run / it["file"]))[2]
            ss = ss if ss + 1.0 < fd else 0.0
            avail = fd - ss
        s.update(file=str(run / it["file"]), image=im, ss=0.0 if im else ss, avail=avail, z0=1.0 + 0.04 * (nt % 3), z1=1.16 + 0.05 * (nt % 4), ox=0.5, oy=0.5)
    lead, pulses = vs[-1][0], [(x["t0"], PULSE_W.get(x["trans"], 0.3)) for x in shots if x["t0"] >= vs[-1][0] and x["trans"]]
    _assemble(shots, str(cut / "spk.mp4"), str(cut / "base.mp4"), total, lambda t: tail_k(t, lead, S["tT"], D, pulses))

    # audio: lines at their start, music placed on the drop, no voice after the last line
    ins, fc, labs = [], [], []
    for i in range(len(lines)):
        ins += ["-i", cut / f"spk{i}.mp4"]
        fc.append(f"[{i}:a]loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=7,aresample=44100,afade=t=in:d={FADE},afade=t=out:st={ld[i] - FADE:.3f}:d={FADE},adelay={int(vs[i][0] * 1000)}:all=1[a{i}]")
        labs.append(f"[a{i}]")
    fc.append("".join(labs) + f"amix=inputs={len(labs)}:duration=longest:normalize=0,apad=whole_dur={D + 2}[o]")
    _ff(*ins, "-filter_complex", ";".join(fc), "-map", "[o]", "-ac", 2, cut / "voice.wav")
    # the mix is made 1.5 s longer so its end fade falls outside the video: the tail keeps full intensity and stops on the hit
    music.mix(str(cut / "voice.wav"), mp, off, str(cut / "mix.m4a"), music_gain_db=GAIN_DB, duck_db=DUCK_DB, video_duration=D + 1.5, boost_after=td)
    fix = TARGET_LUFS - _lufs(cut / "mix.m4a", 0, D)
    _ff("-i", cut / "mix.m4a", "-af", f"volume={fix:.2f}dB,alimiter=limit=0.89,afade=t=out:st={D - 0.04:.3f}:d=0.04", "-t", f"{D:.3f}",
        "-c:a", "aac", "-b:a", "192k", cut / "final.m4a")

    # overlays
    caps = []
    for i, (l, c, f) in enumerate(lines):
        caps += C.group_words(_words(l, c, vs[i][0], cuts[i], t0s[i]), max_words=2, max_chars=14)
    pops = [dict(text=p["text"], start=vs[p["line"]][0] + 0.4, end=min(vs[p["line"]][0] + 2.0, vs[p["line"]][1] - 0.1)) for p in plan.get("popups", [])]
    spec = dict(captions=caps, popups=pops, caption_scale=0.8,
                slams=[dict(text=t, start=a, end=b) for t, (a, b) in zip(slams, S["slams"])],
                flashes=[dict(at=s["t0"], dur=0.18 if s["trans"] == "drop" else 0.12) for s in shots if s["trans"] in ("flash", "drop", "slam", "hit")],
                shakes=[dict(at=s["t0"], dur=0.3, amp=26 if s["trans"] in ("drop", "hit") else 16) for s in shots if s["trans"] in ("shake", "drop", "slam", "hit")])
    CP.compose(str(cut / "base.mp4"), spec, str(run / "short.mp4"), audio=str(cut / "final.m4a"))

    tl = [{"start": a, "end": b, "kind": "speech", "person": True} for a, b in vs]
    tl.insert(dl + 1, {"start": S["tdend"], "end": S["tdend"] + S["gap"], "kind": "slam", "person": False})
    if S["tT"] - vs[-1][1] > 1e-6:
        tl.append({"start": vs[-1][1], "end": S["tT"], "kind": "hold", "person": True})
    tl.append({"start": S["tT"], "end": D, "kind": "tail", "person": False})
    tl = _split_person(tl, shots)
    urls = list(dict.fromkeys(c["source"]["url"] for c in plan["clips"]))
    cr = [x["credit"] for x in broll + tails + persons if x.get("credit")]
    return {"short": {"file": "short.mp4", "duration": D}, "timeline": tl, "musicOffset": off,
            "credits": [f"Footage: {u}" for u in urls] + list(dict.fromkeys(cr)) + ([f"Music: {track['title']}"] if track.get("title") else [])}
