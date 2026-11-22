import sys, os, json, hashlib, subprocess, urllib.request
try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("facecam.py needs numpy and opencv-python-headless (point AUTOBIZ_PYTHON at a venv with them)")

# Finds the small facecam rectangle that a Twitch stream overlays on its gameplay. Prints {"frame": {w, h}, "cam": {x, y, w, h} | null}.
# Same model path, download and sha256 check as shots.py. Usage: facecam.py <video> <model.onnx>
URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SHA = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
SAMPLES, WIDTH = 24, 640
video, model = sys.argv[1], sys.argv[2]

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

if os.path.exists(model):
    if sha(model) != SHA:
        sys.exit("face model " + model + " has the wrong sha256; delete it to download it again")
else:
    os.makedirs(os.path.dirname(model) or ".", exist_ok=True)
    urllib.request.urlretrieve(URL, model + ".part")
    if sha(model + ".part") != SHA:
        os.remove(model + ".part")
        sys.exit("downloaded face model has the wrong sha256; deleted it")
    os.rename(model + ".part", model)

W, H = (int(v) for v in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", video], capture_output=True, text=True).stdout.strip().split("x"))
try:
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video], capture_output=True, text=True).stdout)
except ValueError:
    dur = 0.0
h = int(WIDTH * H / W / 2 + 0.5) * 2
K = W / WIDTH
rate = SAMPLES / dur if dur > 0 else 1
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", "fps=%f,scale=%d:%d" % (rate, WIDTH, h), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
frames = np.frombuffer(raw[: len(raw) // (WIDTH * h * 3) * WIDTH * h * 3], np.uint8).reshape(-1, h, WIDTH, 3)
if len(frames) == 0:
    sys.exit("facecam.py could not decode any frame of " + video)

def result(cam):
    print(json.dumps({"frame": {"w": W, "h": H}, "cam": cam}, separators=(",", ":")))
    sys.exit(0)

# 1. the face of each sample: the most confident detection
detector = cv2.FaceDetectorYN.create(model, "", (WIDTH, h), 0.6, 0.3, 50)
faces = []
for img in frames:
    _, found = detector.detect(img)
    faces.append(max(found, key=lambda r: r[-1])[:4] if found is not None and len(found) else None)
seen = [f for f in faces if f is not None]
if len(seen) < 0.5 * len(frames):
    result(None)
mx, my = np.median([f[0] + f[2] / 2 for f in seen]), np.median([f[1] + f[3] / 2 for f in seen])
steady = [f for f in seen if abs(f[0] + f[2] / 2 - mx) <= 0.04 * WIDTH and abs(f[1] + f[3] / 2 - my) <= 0.04 * WIDTH]
if len(steady) < 0.5 * len(frames):
    result(None)
fw, fh = float(np.median([f[2] for f in steady])), float(np.median([f[3] for f in steady]))
if fh >= 0.25 * h:  # a big face: a full-camera stream, there is no overlay
    result(None)
fx0, fy0, fx1, fy1 = int(max(0, mx - fw / 2)), int(max(0, my - fh / 2)), int(min(WIDTH, mx + fw / 2)), int(min(h, my + fh / 2))

# 2. borders: overlay edges stay put while the gameplay moves, so they survive the temporal median of the edge magnitude
grey = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frames]
gx = np.median([np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0)) for g in grey], axis=0)
gy = np.median([np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1)) for g in grey], axis=0)
reach = int(4 * max(fw, fh))

def best(profile, lo, hi, inward_first):
    # the nearest line to the face among the strong ones in [lo, hi) (inward_first: the face is at the high end), or None when nothing stands out.
    # Strength is capped, so a thick bright bar far away (a progress bar, a HUD) does not outrank the thin overlay border next to the face.
    lo, hi = max(lo, 0), min(hi, len(profile))
    if hi - lo < 3:
        return None, 0.0
    part = np.minimum(profile[lo:hi], 100.0)
    strong = np.flatnonzero(part >= max(20.0, 0.6 * part.max()))
    if len(strong) == 0 or part.max() < 3 * float(np.median(part)):
        return None, 0.0
    i = int(strong[-1] if inward_first else strong[0])
    i = max(0, i - 2) + int(np.argmax(part[max(0, i - 2) : i + 3]))
    return lo + i, float(part[i])

# fallback box: the face expanded 3.2 x 2.6, centred slightly below the face
ex0, ex1 = max(0.0, mx - 1.6 * fw), min(float(WIDTH), mx + 1.6 * fw)
ey0, ey1 = max(0.0, my + 0.15 * fh - 1.3 * fh), min(float(h), my + 0.15 * fh + 1.3 * fh)
# a border is straight and unbroken, so a line's strength is the 25th percentile of its gradient along the strip (static game text is strong but broken)
strip = lambda g, a, b: np.percentile(g[:, a:b], 25, axis=1)
rowp = strip(gy, int(max(0, mx - fw)), int(min(WIDTH, mx + fw)))
top, st = best(rowp, fy0 - reach, fy0, True)
bottom, sb = best(rowp, fy1, fy1 + reach, False)
top = (0 if fy0 - reach <= 0 else ey0) if top is None else top  # no line: the frame edge when in reach, else the expanded face
bottom = (h if fy1 + reach >= h else ey1) if bottom is None else bottom
span = np.percentile(gx[int(top) + 3 : max(int(top) + 4, int(bottom) - 2)], 25, axis=0)
left, sl = best(span, fx0 - reach, fx0, True)
right, sr = best(span, fx1, fx1 + reach, False)
# a frame edge counts as a border: when the scan reaches it and the best interior line is weaker than 0.9 x the median of the other borders, the edge wins
med = lambda *v: float(np.median([s for s in v if s > 0] or [0.0]))
if fx0 - reach <= 0 and (left is None or sl < 0.9 * med(st, sb, sr)):
    left = 0
if fx1 + reach >= WIDTH and (right is None or sr < 0.9 * med(st, sb, sl)):
    right = WIDTH
left, right = (ex0 if left is None else left), (ex1 if right is None else right)
box = (left, top, right, bottom)
bw, bh = right - left, bottom - top
if bw < 1.2 * fw or bh < 1.2 * fh or bw > 0.6 * WIDTH or bh > 0.6 * h:  # not a plausible overlay: use the expanded face
    box = (ex0, ey0, ex1, ey1)
x0, y0, x1, y1 = (int(round(v * K)) for v in box)
result({"x": max(0, x0), "y": max(0, y0), "w": min(W, x1) - max(0, x0), "h": min(H, y1) - max(0, y0)})
