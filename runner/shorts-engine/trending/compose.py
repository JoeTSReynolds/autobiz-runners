"""Final compositor: base video + overlay spec -> H.264 mp4 (1080x1920, 30 fps).

    from trending import compose; compose.compose("base.mp4", spec_dict, "out.mp4", audio="mix.m4a")
    python -m trending.compose base.mp4 spec.json out.mp4 [--audio mix.m4a]

spec keys (all optional, times in seconds):
  captions [{text,start,end}]  gold pop word captions (hidden while a slam is on)
  popups   [{text,start,end}]  contrast cards     slams [{text,start,end}]  big stat text     caption_scale (default 1.0)
  cards    [{image,start,end,x,y,w,anim}]  PNG overlay scaled to width w, x/y = top-left ("center" or null = centred on that axis);
           anim pop | slide-up | fade
  flashes  [{at,dur=0.12,color="white"}]   shakes [{at,dur=0.25,amp=18}]   fades [{start,end,color,mode:"in"|"out"}]
Order: shake, cards, slams, captions, popups, flashes/fades.
"""
import argparse, json, subprocess, sys, time
import cv2
import numpy as np
from PIL import Image
from . import captions as C
from .facecrop import probe, FPS

W, H = C.W, C.H
COLORS = {"white": (255, 255, 255), "black": (0, 0, 0)}


def _col(c):
    return COLORS.get(c, c)


class Cards:
    def __init__(self, items):
        self.items = items
        self.imgs = {}
        for i, c in enumerate(items):
            im = Image.open(c["image"]).convert("RGBA")
            w = c["w"]
            self.imgs[i] = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)

    def frame(self, t):
        out = []
        for i, c in enumerate(self.items):
            if not c["start"] <= t < c["end"]:
                continue
            im, tt, rem = self.imgs[i], t - c["start"], c["end"] - t
            x = (W - im.width) / 2 if c.get("x") in (None, "center") else c["x"]
            y = (H - im.height) / 2 if c.get("y") in (None, "center") else c["y"]
            anim, a, sc, dy = c.get("anim", "fade"), 1.0, 1.0, 0.0
            if anim == "pop":
                u = min(tt / 0.18, 1)
                sc = 1.08 * C._out(u / 0.7) if u < 0.7 else 1.08 - 0.08 * (u - 0.7) / 0.3
                if rem < 0.15:
                    sc, a = sc * (0.85 + 0.15 * rem / 0.15), rem / 0.15
            elif anim == "slide-up":
                k = C._out(tt / 0.25)
                dy, a = 120 * (1 - k), min(k * 1.5, 1) * min(rem / 0.15, 1)
            else:
                a = min(tt / 0.15, 1) * min(rem / 0.15, 1)
            out.append(C._at(C._scaled(im, sc, a), x + im.width / 2, y + im.height / 2 + dy))
        return out


def shake_at(t, shakes):
    for k, s in enumerate(shakes):
        d = s.get("dur", 0.25)
        if s["at"] <= t < s["at"] + d:
            rng = np.random.RandomState(int(round(t * FPS)) * 31 + k)  # seeded: reproducible
            amp = s.get("amp", 18) * (1 - (t - s["at"]) / d) ** 2
            return rng.uniform(-1, 1, 2) * amp
    return None


def _overlay_alpha(t, spec):
    """(color, alpha) tuples for flashes and fades at time t."""
    out = []
    for f in spec.get("flashes", []):
        d = f.get("dur", 0.12)
        if f["at"] <= t < f["at"] + d:
            out.append((_col(f.get("color", "white")), 0.9 * (1 - (t - f["at"]) / d)))
    for f in spec.get("fades", []):
        u = (t - f["start"]) / max(f["end"] - f["start"], 1e-6)
        if f.get("mode", "out") == "in":
            if 0 <= u < 1:
                out.append((_col(f.get("color", "black")), 1 - u))
        elif u >= 0:
            out.append((_col(f.get("color", "black")), min(u, 1)))
    return out


def compose(base_video, spec, dst, audio=None):
    bw, bh, dur = probe(base_video)
    cards = Cards(spec.get("cards", []))
    caps, pops, slams = C.GoldCaptions(spec.get("captions", []), scale=spec.get("caption_scale", 1.0)), C.PopupCards(spec.get("popups", [])), C.StatSlams(spec.get("slams", []))
    shakes = spec.get("shakes", [])
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", base_video, "-vf", f"fps={FPS},scale={W}:{H}", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    a_src = audio or base_video
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-i", a_src, "-map", "0:v", "-map", "1:a:0?", "-c:v", "libx264", "-crf", "20",
                            "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
                            "-shortest", "-movflags", "+faststart", dst], stdin=subprocess.PIPE)
    fsz, i, t0 = W * H * 3, 0, time.time()
    total = int((dur or 0) * FPS)
    while True:
        buf = dec.stdout.read(fsz)
        if len(buf) < fsz:
            break
        t = i / FPS
        fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        sh = shake_at(t, shakes)
        if sh is not None:  # overscale 1.04 so shifted edges never show black
            M = np.float32([[1.04, 0, sh[0] - 0.02 * W], [0, 1.04, sh[1] - 0.02 * H]])
            fr = cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        layers = [cards] + ([slams] if slams.active(t) else [caps]) + [pops]
        items = [it for L in layers for it in L.frame(t)]
        ov = _overlay_alpha(t, spec)
        if items or ov:
            img = Image.fromarray(fr)
            for im, pos in items:
                img.paste(im, pos, im)
            for col, a in ov:
                img = Image.blend(img, Image.new("RGB", (W, H), col), min(max(a, 0), 1))
            fr = np.asarray(img)
        enc.stdin.write(np.ascontiguousarray(fr).tobytes())
        i += 1
        if i % 150 == 0:
            print(f"frame {i}/{total or '?'}  {i / (time.time() - t0):.1f} fps", flush=True)
    dec.stdout.close(); dec.wait()
    enc.stdin.close(); enc.wait()
    if enc.returncode:
        raise RuntimeError("encode failed")
    return dst


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("base"); ap.add_argument("spec"); ap.add_argument("dst"); ap.add_argument("--audio")
    a = ap.parse_args()
    compose(a.base, json.load(open(a.spec)), a.dst, a.audio)
