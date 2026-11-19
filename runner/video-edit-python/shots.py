import sys, os, json, hashlib, subprocess, statistics, urllib.request
try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("shots.py needs numpy and opencv-python-headless (point AUTOBIZ_PYTHON at a venv with them)")

URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SHA = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
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

probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", video], capture_output=True, text=True)
W, H = (int(v) for v in probe.stdout.strip().split("x"))
h = int(640 * H / W / 2 + 0.5) * 2
FPS, K = 10, W / 640
proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-vf", "fps=%d,scale=640:%d" % (FPS, h), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
detector = cv2.FaceDetectorYN.create(model, "", (640, h), 0.6, 0.3, 50)

cuts, ftimes, dets, prev, i = [0.0], [], [], None, 0
while True:
    buf = proc.stdout.read(640 * h * 3)
    while buf and len(buf) < 640 * h * 3:
        more = proc.stdout.read(640 * h * 3 - len(buf))
        if not more:
            break
        buf += more
    if len(buf) < 640 * h * 3:
        break
    img = np.frombuffer(buf, np.uint8).reshape(h, 640, 3)
    t = i / FPS
    hist = cv2.calcHist([cv2.cvtColor(img, cv2.COLOR_BGR2HSV)], [0, 1], None, [32, 32], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    # angles of one room share colours, so a cut also counts when a 64x36 grey thumbnail changes a lot (cuts ~0.2, motion <= 0.015)
    grey = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (64, 36), interpolation=cv2.INTER_AREA).astype(np.float32)
    if prev is not None and (cv2.compareHist(prev[0], hist, cv2.HISTCMP_CORREL) < 0.6 or float(np.mean(np.abs(grey - prev[1]))) / 255 > 0.08):
        cuts.append(t)
    prev = (hist, grey)
    if i % 2 == 0:
        ftimes.append(t)
        _, found = detector.detect(img)
        for x, y, fw, fh in ([r[:4] for r in found] if found is not None else []):
            dets.append((t, float(x + fw / 2) * K, float(y + fh / 2) * K, float(fw) * K))
    i += 1
proc.wait()
if i == 0:
    sys.exit("shots.py could not decode any frame of " + video)

bounds = cuts + [i / FPS]
shots = []
for s, e in zip(bounds, bounds[1:]):
    samples = [t for t in ftimes if s <= t < e]
    clusters = []
    for d in (d for d in dets if s <= d[0] < e):
        for c in clusters:
            if abs(statistics.median(x[1] for x in c) - d[1]) <= 0.12 * W:
                c.append(d)
                break
        else:
            clusters.append([d])
    faces = [c for c in clusters if len({x[0] for x in c}) >= 0.4 * len(samples)]
    faces = sorted(({"cx": round(statistics.median(x[1] for x in c), 1), "cy": round(statistics.median(x[2] for x in c), 1), "size": round(statistics.median(x[3] for x in c), 1)} for c in faces), key=lambda f: f["cx"])
    shots.append({"start": round(s, 3), "end": round(e, 3), "faces": faces})
print(json.dumps({"width": W, "height": H, "shots": shots}, separators=(",", ":")))
