"""Face-following 9:16 crop with zoom (prototype).

    from trending import facecrop
    facecrop.render("in.mp4", "out.mp4", zoom=facecrop.mul(facecrop.push_in(1.0, 1.12, 12), facecrop.punch([3.0, 7.5])),
                    face_y=0.40, start=60, end=72, grade="hue=s=0,eq=contrast=1.15")
    cam = facecrop.track("in.mp4")   # dict: fps, n, W, H, cx, cy (smoothed camera), raw_cx, raw_cy, size, found, cuts

Zoom curves take OUTPUT time t (seconds from clip start). Everything is 30 fps.
CLI: python -m trending.facecrop in.mp4 out.mp4 [--push 1.0:1.12] [--punch 3,7.5] [--start S --end E]
"""
import argparse, math, os, subprocess, sys
import cv2
import numpy as np
from .faces import YUNET as MODEL, MATCH, match, sface_path

FPS = 30
OW, OH = 1080, 1920


def probe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height:format=duration", "-of", "csv=p=0:s=,", path], text=True).split()
    w, h = out[0].split(",")[:2]
    return int(w), int(h), float(out[1]) if len(out) > 1 else None


def _seek(start, end):
    a = []
    if start:
        a += ["-ss", str(start)]
    if end is not None:
        a += ["-t", str(end - (start or 0))]
    return a


# ---------------------------------------------------------------- zoom helpers
def _ease(u):
    u = min(max(u, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * u)


def push_in(a=1.0, b=1.12, dur=10.0):
    """Zoom a -> b over dur seconds (sine ease), then hold b."""
    return lambda t: a + (b - a) * _ease(t / dur)


def punch(times, amount=1.15, attack=0.06, release=0.35):
    """Quick zoom spikes: 1 -> amount in `attack` s, back to 1 in `release` s, at each time. Multiplied together."""
    def f(t):
        z = 1.0
        for t0 in times:
            d = t - t0
            if 0 <= d < attack:
                z *= 1 + (amount - 1) * _ease(d / attack)
            elif attack <= d < attack + release:
                z *= 1 + (amount - 1) * (1 - _ease((d - attack) / release))
        return z
    return f


def mul(*fns):
    return lambda t: math.prod(f(t) for f in fns)


# -------------------------------------------------------------------- tracking
def smooth(cx, cy, cuts, W, fps=FPS, dead=0.04, alpha=0.10, vmax=0.35):
    """Virtual camera. Per axis: ignore errors < dead*W, then exponential approach capped at vmax*W px/s.
    Jumps (no smoothing) to the raw target at index 0 and at each cut index."""
    n = len(cx)
    out = np.zeros((n, 2))
    cuts = set(cuts) | {0}
    dz, step = dead * W, vmax * W / fps
    cam, moving = [0.0, 0.0], [False, False]
    for i in range(n):
        tgt = (cx[i], cy[i])
        if i in cuts:
            cam, moving = [tgt[0], tgt[1]], [False, False]
        else:
            for k in (0, 1):
                err = tgt[k] - cam[k]
                if not moving[k] and abs(err) > dz:
                    moving[k] = True
                if moving[k]:
                    cam[k] += max(-step, min(step, alpha * err))
                    if abs(tgt[k] - cam[k]) < 0.01 * W:
                        moving[k] = False
        out[i] = cam
    return out[:, 0], out[:, 1]


def _follow(samples, fps_s, W, hold=1.0):
    """samples: list of (frame_idx, [faces (cx,cy,size[,matches_ref])]) for ONE shot -> list of target (cx,cy,size)|None.
    A face flagged as matching the reference is followed (held `hold` s when it vanishes), else the largest, as without a reference."""
    cur, last_switch, last_match, res = None, -1e9, -1e9, []
    for fi, faces in samples:
        t = fi / FPS
        hit = [f for f in faces if len(f) > 3 and f[3]]
        if hit:
            cur, last_switch, last_match = max(hit, key=lambda f: f[2]), t, t
            res.append(cur)
            continue
        if t - last_match <= hold:
            res.append(cur)  # the person is not visible for a moment: stay where they were
            continue
        if last_match > -1e9 and faces:  # hold over: back to the largest face
            cur, last_switch, last_match = max(faces, key=lambda f: f[2]), t, -1e9
            res.append(cur)
            continue
        if not faces:
            res.append(cur)  # hold last position through short dropouts
            continue
        big = max(faces, key=lambda f: f[2])
        if cur is None:
            cur, last_switch = big, t
        else:
            near = min(faces, key=lambda f: math.hypot(f[0] - cur[0], f[1] - cur[1]))
            if math.hypot(near[0] - cur[0], near[1] - cur[1]) > 0.35 * W:  # lost the face, take the biggest
                cur, last_switch = big, t
            elif big is not near and big[2] > 1.25 * near[2] and t - last_switch >= 1.5:
                cur, last_switch = big, t
            else:
                cur = near
        res.append(cur)
    return res


def track(video_path, fps=5, start=None, end=None, model=MODEL, ref=None, models=None):
    """With ref (an identity embedding) and models (dir with SFace), follow the face matching ref instead of the largest."""
    rec = cv2.FaceRecognizerSF.create(sface_path(models), "") if ref is not None and models else None
    W, H, _ = probe(video_path)
    sw = 640
    sh = int(round(sw * H / W / 2)) * 2
    sc = W / sw
    det = cv2.FaceDetectorYN.create(model, "", (sw, sh), 0.6, 0.3, 50)
    k = max(1, round(FPS / fps))
    cmd = ["ffmpeg", "-v", "error"] + _seek(start, end) + ["-i", video_path, "-vf", f"fps={FPS},scale={sw}:{sh}",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    fsz = sw * sh * 3
    shots, cuts, prev, i = [[]], [], None, 0
    while True:
        buf = p.stdout.read(fsz)
        if len(buf) < fsz:
            break
        fr = np.frombuffer(buf, np.uint8).reshape(sh, sw, 3)
        th = cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (64, 36), interpolation=cv2.INTER_AREA).astype(np.float32)
        cut = prev is not None and float(np.abs(th - prev).mean()) > 30  # ~0.12 of full scale: hard cut
        prev = th
        if cut:
            cuts.append(i)
            shots.append([])
        if cut or i % k == 0:
            _, f = det.detect(fr)
            faces = [] if f is None else [((r[0] + r[2] / 2) * sc, (r[1] + r[3] / 2) * sc, r[2] * sc) for r in f]
            if rec and faces:
                faces = [fc + (match(rec.feature(rec.alignCrop(fr, r.reshape(1, -1))).flatten(), ref) >= MATCH,) for fc, r in zip(faces, f)]
            shots[-1].append((i, faces))
        i += 1
    p.wait()
    n = i
    cxr, cyr, size, found = (np.full(n, np.nan) for _ in range(4))
    bounds = [0] + cuts + [n]
    for si, samples in enumerate(shots):
        a, b = bounds[si], bounds[si + 1]
        tg = _follow(samples, fps, W)
        pts = [(fi, t) for (fi, _), t in zip(samples, tg) if t]
        if pts:
            x = np.arange(a, b)
            fi = [p_[0] for p_ in pts]
            cxr[a:b] = np.interp(x, fi, [p_[1][0] for p_ in pts])
            cyr[a:b] = np.interp(x, fi, [p_[1][1] for p_ in pts])
            size[a:b] = np.interp(x, fi, [p_[1][2] for p_ in pts])
            found[a:b] = 1
        else:
            cxr[a:b], cyr[a:b], size[a:b], found[a:b] = W / 2, H / 2, 0, 0
    cx, cy = smooth(cxr, cyr, cuts, W)
    return dict(fps=FPS, n=n, W=W, H=H, cx=cx, cy=cy, raw_cx=cxr, raw_cy=cyr, size=size, found=found.astype(bool), cuts=cuts)


# ---------------------------------------------------------------------- render
def crop_window(W, H, cx, cy, z, face_y=0.40, found=True):
    """9:16 window (x0, y0, w, h) in source px, inside the frame. Base height = H (or W*16/9 for narrow sources)."""
    ch = min(H, W * 16 / 9) / max(z, 1.0)
    cw = ch * 9 / 16
    x0 = min(max(cx - cw / 2, 0), W - cw)
    y0 = cy - face_y * ch if found else (H - ch) / 2
    return x0, min(max(y0, 0), H - ch), cw, ch


def _warp(fr, x0, y0, cw, ch):
    s = OW / cw
    if s >= 1:  # upscale: sub-pixel accurate
        M = np.float32([[s, 0, -x0 * s], [0, s, -y0 * s]])
        return cv2.warpAffine(fr, M, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    xi, yi = int(round(x0)), int(round(y0))
    return cv2.resize(fr[yi:yi + int(round(ch)), xi:xi + int(round(cw))], (OW, OH), interpolation=cv2.INTER_AREA)


def load_ref(run):
    """The run's identity embedding (run/identity.npy), or None."""
    p = os.path.join(run, "identity.npy")
    return np.load(p) if os.path.isfile(p) else None


def render(src, dst, zoom=lambda t: 1.0, face_y=0.40, start=None, end=None, grade=None, cam=None, ref=None, models=None):
    W, H, dur = probe(src)
    cam = cam or track(src, start=start, end=end, ref=ref, models=models)
    vf = f"fps={FPS}" + (f",{grade}" if grade else "")
    dec = subprocess.Popen(["ffmpeg", "-v", "error"] + _seek(start, end) + ["-i", src, "-vf", vf, "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}",
                            "-r", str(FPS), "-i", "-"] + _seek(start, end) + ["-i", src, "-map", "0:v", "-map", "1:a:0?",
                            "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS),
                            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", dst], stdin=subprocess.PIPE)
    fsz = W * H * 3
    i = 0
    while i < cam["n"]:
        buf = dec.stdout.read(fsz)
        if len(buf) < fsz:
            break
        fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        x0, y0, cw, ch = crop_window(W, H, cam["cx"][i], cam["cy"][i], zoom(i / FPS), face_y, cam["found"][i])
        enc.stdin.write(np.ascontiguousarray(_warp(fr, x0, y0, cw, ch)).tobytes())
        i += 1
    dec.stdout.close(); dec.wait()
    enc.stdin.close(); enc.wait()
    if enc.returncode:
        raise RuntimeError("encode failed")
    return dst


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--start", type=float); ap.add_argument("--end", type=float)
    ap.add_argument("--push", help="a:b e.g. 1.0:1.12"); ap.add_argument("--punch", help="comma list of times (s)")
    ap.add_argument("--face-y", type=float, default=0.40); ap.add_argument("--grade")
    a = ap.parse_args()
    d = (a.end if a.end else probe(a.src)[2]) - (a.start or 0)
    fns = []
    if a.push:
        lo, hi = map(float, a.push.split(":")); fns.append(push_in(lo, hi, d))
    if a.punch:
        fns.append(punch([float(x) for x in a.punch.split(",")]))
    render(a.src, a.dst, mul(*fns) if fns else (lambda t: 1.0), a.face_y, a.start, a.end, a.grade)
