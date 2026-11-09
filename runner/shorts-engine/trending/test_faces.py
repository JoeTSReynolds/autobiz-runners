# faces.match on synthetic vectors, and the pinned SFace checksum (no network). Run: python3 test_faces.py
import sys, tempfile
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending import faces

a = np.array([1.0, 0.0, 2.0]); b = np.array([2.0, 0.0, 4.0]); c = np.array([0.0, 3.0, 0.0])
assert abs(faces.match(a, b) - 1.0) < 1e-6
assert abs(faces.match(a, c)) < 1e-6
assert abs(faces.match(a, -a) + 1.0) < 1e-6
assert faces.match(a, np.zeros(3)) == 0.0
assert faces.MATCH == 0.363
assert len(faces.SFACE_SHA256) == 64

with tempfile.TemporaryDirectory() as d:  # a wrong file already in the models dir is refused, not replaced
    (Path(d) / faces.SFACE_NAME).write_bytes(b'junk')
    try:
        faces.sface_path(d)
        raise AssertionError('expected sha256 mismatch')
    except RuntimeError as e:
        assert 'sha256' in str(e), e
assert faces.embed(np.zeros((8, 8, 3), np.uint8), None) is None  # too small for a face, never loads the model

# YuNet misses faces that fill a big frame (a 600 px face in a 1080x1920 crop, live 2026-11-07): detection runs on a copy
# at most DETECT_MAX px on its long side and the boxes are scaled back to the image
import cv2
seen = []
class FakeDet:
    def detect(self, img):
        seen.append(img.shape[:2]); return 1, np.array([[100, 200, 50, 60] + [10.0] * 10 + [0.9]], np.float32)
real = cv2.FaceDetectorYN.create
cv2.FaceDetectorYN.create = lambda model, cfg, size, *a: FakeDet()
rows = faces.detect(np.zeros((1920, 1080, 3), np.uint8))
assert max(seen[0]) == faces.DETECT_MAX, seen
k = 1920 / faces.DETECT_MAX
assert np.allclose(rows[0][:4], [100 * k, 200 * k, 50 * k, 60 * k]) and np.isclose(rows[0][14], 0.9) and np.isclose(rows[0][4], 10 * k), rows[0]
seen.clear(); faces.detect(np.zeros((360, 640, 3), np.uint8)); assert seen == [(360, 640)]   # small images unchanged
cv2.FaceDetectorYN.create = real
print('ok')
