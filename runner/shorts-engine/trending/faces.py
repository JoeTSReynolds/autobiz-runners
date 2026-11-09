"""Face models: YuNet detection (committed in models/) and SFace identity (downloaded on first use, sha256 pinned).

    faces.embed(frame_bgr, models_dir) -> 128-d vector of the largest face, or None
    faces.match(a, b) >= faces.MATCH  -> same person (SFace cosine threshold)
"""
import hashlib, os, urllib.request
from pathlib import Path
import cv2
import numpy as np

YUNET = str(Path(__file__).parent / 'models' / 'face_detection_yunet_2023mar.onnx')
SFACE_NAME = 'face_recognition_sface_2021dec.onnx'
SFACE_URL = 'https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/' + SFACE_NAME
SFACE_SHA256 = '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79'
MATCH = 0.363  # cosine threshold from the SFace paper / opencv_zoo demo


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def sface_path(models_dir):
    """Path of the verified SFace model in models_dir, downloading it first if missing. A file with the wrong hash is an error."""
    p = Path(models_dir) / SFACE_NAME
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix('.part')
        with urllib.request.urlopen(SFACE_URL, timeout=120) as r, open(tmp, 'wb') as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        if _sha256(tmp) != SFACE_SHA256:
            os.remove(tmp)
            _bad(SFACE_URL, 'download')
        os.replace(tmp, p)
    elif _sha256(p) != SFACE_SHA256:
        _bad(str(p), 'file')
    return str(p)


def _bad(what, kind):
    raise RuntimeError(f'{what}: {kind} sha256 does not match the pinned {SFACE_SHA256}')


DETECT_MAX = 640  # YuNet misses faces that fill a large frame, so it looks at a copy at most this long


def detect(image_bgr, score=0.6):
    """YuNet rows (x, y, w, h, 10 landmark values, score) for every face, in image pixels, [] if none."""
    h, w = image_bgr.shape[:2]
    k = max(h, w) / DETECT_MAX
    small = cv2.resize(image_bgr, (round(w / k), round(h / k)), interpolation=cv2.INTER_AREA) if k > 1 else image_bgr
    k = max(k, 1)
    det = cv2.FaceDetectorYN.create(YUNET, '', (small.shape[1], small.shape[0]), score, 0.3, 50)
    _, f = det.detect(small)
    if f is None:
        return []
    f = np.array(f, np.float32)
    f[:, :14] *= k  # box and landmarks back to image pixels; the score stays
    return list(f)


def embed(image_bgr, models_dir):
    """SFace feature (128,) of the largest face, aligned with FaceRecognizerSF.alignCrop; None if no face."""
    if image_bgr is None or min(image_bgr.shape[:2]) < 32:
        return None
    rows = detect(image_bgr)
    if not rows:
        return None
    big = max(rows, key=lambda r: r[2] * r[3])
    rec = cv2.FaceRecognizerSF.create(sface_path(models_dir), '')
    return rec.feature(rec.alignCrop(image_bgr, big.reshape(1, -1))).flatten()


def embed_all(image_bgr, models_dir, min_share=0.06):
    """(SFace feature, face width / image width) of every face at least min_share of the image width (the faces a viewer notices)."""
    rows = [r for r in detect(image_bgr) if r[2] >= min_share * image_bgr.shape[1]] if image_bgr is not None else []
    if not rows:
        return []
    rec = cv2.FaceRecognizerSF.create(sface_path(models_dir), '')
    return [(rec.feature(rec.alignCrop(image_bgr, r.reshape(1, -1))).flatten(), float(r[2]) / image_bgr.shape[1]) for r in rows]


def match(a, b):
    """Cosine similarity of two embeddings (0.0 if either is all zeros)."""
    n = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / n) if n else 0.0
