# editfx: matte, fry speed/similarity, transitions, per-shot looks. Run: python3 test_editfx.py (copies the MODNet / U2-Net-p models from MODNET_COPY / U2NET_COPY if set, else downloads)
import os, shutil, sys, tempfile, time
import cv2
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending import editfx

HERE = Path(__file__).resolve().parent
MODNET_COPY = os.environ.get('MODNET_COPY', '')
U2NET_COPY = os.environ.get('U2NET_COPY', '')
mad = lambda a, b: float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean())

photo = cv2.cvtColor(cv2.imread(str(HERE / 'fixtures' / 'person.jpg')), cv2.COLOR_BGR2RGB)  # 270x480 RGB
H, W = photo.shape[:2]

with tempfile.TemporaryDirectory() as d:  # wrong-hash model is refused
    (Path(d) / editfx.MODNET_NAME).write_bytes(b'junk')
    try:
        editfx.segment(photo, d)
        raise AssertionError('expected sha256 mismatch')
    except RuntimeError as e:
        assert 'sha256' in str(e), e

models = tempfile.mkdtemp()
if MODNET_COPY:
    shutil.copy(MODNET_COPY, Path(models) / editfx.MODNET_NAME)
m = editfx.segment(photo, models)
assert m.shape == (H, W) and m.dtype == np.float32 and 0 <= m.min() and m.max() <= 1
assert 0.2 < float(m.mean()) < 0.95, m.mean()
t0 = time.time(); editfx.segment(photo, models); print('segment s/frame at 270x480: %.3f' % (time.time() - t0))

# fry: <= 0.15 s at 1080x1920 and close to the slow reference look (reference runs on BGR as approved)
def fry_ref(f):
    s = cv2.bilateralFilter(f, 9, 40, 9)
    s = cv2.detailEnhance(s, sigma_s=8, sigma_r=0.12)
    lab = cv2.cvtColor(s, cv2.COLOR_BGR2LAB); lab[..., 0] = cv2.createCLAHE(2.0, (8, 8)).apply(lab[..., 0]); s = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    hsv = cv2.cvtColor(s, cv2.COLOR_BGR2HSV).astype(np.float32); hsv[..., 1] *= 1.25; s = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
    g = cv2.GaussianBlur(s, (0, 0), 12); return cv2.addWeighted(s, 0.85, g, 0.25, 0)
big = cv2.resize(cv2.cvtColor(cv2.imread(str(HERE / 'fixtures' / 'person.jpg')), cv2.COLOR_BGR2RGB), (1080, 1920), interpolation=cv2.INTER_CUBIC)
editfx.fry(big)
dt = 9.0
for _ in range(3):  # best of 3: one timing is noisy on a busy machine
    t0 = time.time(); fo = editfx.fry(big); dt = min(dt, time.time() - t0)
ref = cv2.cvtColor(fry_ref(cv2.cvtColor(big, cv2.COLOR_RGB2BGR)), cv2.COLOR_BGR2RGB)
print('fry s/frame: %.3f  MAD vs reference: %.2f' % (dt, mad(fo, ref)))
assert fo.shape == big.shape and fo.dtype == np.uint8
assert dt <= 0.15, dt
assert mad(fo, ref) <= 6, mad(fo, ref)

# transitions
out_fr = photo
rng = np.random.default_rng(0)
in_fr = np.clip(255 - photo[::-1].astype(np.int16) * 0.8 + rng.integers(0, 20, photo.shape), 0, 255).astype(np.uint8)  # clearly different shot
m_in = np.zeros((H, W), np.float32); m_in[H // 4:3 * H // 4, W // 4:3 * W // 4] = 1
m_out = m.copy()
for kind in ('matte', 'flashblur', 'frame', 'spin', 'whip', 'punch', 'stutter'):
    for masks in ((None, None), (m_out, m_in)):
        for u in (0, .2, .5, .8, 1):
            r = editfx.transition(kind, out_fr, in_fr, u, *masks, sign=-1)
            assert r.shape == photo.shape and r.dtype == np.uint8, (kind, u)
        assert mad(editfx.transition(kind, out_fr, in_fr, 1.0, *masks), in_fr) < 3, (kind, 'u=1', mad(editfx.transition(kind, out_fr, in_fr, 1.0, *masks), in_fr))
        if kind in ('matte', 'flashblur', 'spin', 'whip', 'frame'):
            assert mad(editfx.transition(kind, out_fr, in_fr, 0.0, *masks), out_fr) < 12, (kind, 'u=0', mad(editfx.transition(kind, out_fr, in_fr, 0.0, *masks), out_fr))
    assert mad(editfx.transition(kind, out_fr, in_fr, .4), out_fr) > 1 or kind in ('punch', 'stutter')
assert editfx.transition('nope', out_fr, in_fr, .5) is in_fr or mad(editfx.transition('nope', out_fr, in_fr, .5), in_fr) == 0
mid = editfx.transition('matte', out_fr, in_fr, .2, None, m_in)  # white silhouette over the outgoing frame
assert (mid[H // 2, W // 2] > 240).all()

# per-shot looks
means = [editfx.grade(photo, i).reshape(-1, 3).mean(0) for i in range(4)]
assert editfx.grade(photo, 4).tolist() == editfx.grade(photo, 0).tolist()
for i in range(4):
    g = editfx.grade(photo, i); assert g.shape == photo.shape and g.dtype == np.uint8
    assert 0 < mad(g, photo) < 40 and g.std() > 0.6 * photo.std()
assert means[0][0] - means[0][2] > photo.reshape(-1, 3).mean(0)[0] - photo.reshape(-1, 3).mean(0)[2]  # warm: more red over blue
assert means[1][2] - means[1][0] > photo.reshape(-1, 3).mean(0)[2] - photo.reshape(-1, 3).mean(0)[0]  # teal: more blue over red

# subject cut-out: MODNet for people, U2-Net-p (salient object) when MODNet finds no person
if U2NET_COPY:
    shutil.copy(U2NET_COPY, Path(models) / editfx.U2NET_NAME)
disc = np.full((H, W, 3), 90, np.uint8); cv2.circle(disc, (W // 2, H // 2), W // 4, (230, 40, 40), -1)
sd = editfx.subject(disc, models)
assert sd.shape == (H, W) and sd.dtype == np.float32
assert sd[H // 2, W // 2] > 0.5 and sd[5, 5] < 0.5, (sd[H // 2, W // 2], sd[5, 5])   # the disc, not the background
sp = editfx.subject(photo, models)
assert mad((sp * 255).astype(np.uint8), (m * 255).astype(np.uint8)) < 1   # a person keeps the MODNet matte
assert 0.4 * float(m.mean()) < float(editfx.subject(photo, models, prev=np.zeros_like(m)).mean()) < float(m.mean())   # smoothed with prev
assert editfx.cutout_ok(m_in) and not editfx.cutout_ok(np.ones((H, W), np.float32)) and not editfx.cutout_ok(np.zeros((H, W), np.float32))

# a close-up shrinks into an inset over a blurred copy of itself, so the looks get background around the subject
big_m = np.zeros((H, W), np.float32); big_m[H // 10:, W // 20:W - W // 20] = 1   # ~0.8 of the frame
sc = editfx.inset_scale(big_m)
assert editfx.inset_scale(m_in) == 1.0 and editfx.INSET_MIN <= sc < 1
fi, mi = editfx.inset(photo, big_m, sc)
assert fi.shape == photo.shape and fi.dtype == np.uint8 and mi.shape == big_m.shape
assert editfx.cutout_ok(mi) and float((mi > .5).mean()) <= editfx.INSET_AREA + 0.05, (mi > .5).mean()
assert editfx.inset(photo, m_in, 1.0)[0] is photo

# montage looks: the subject (inside the mask, away from its edge) stays as it is, the background changes, pulse makes it stronger
inner = cv2.erode((m_in > .5).astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
outer = cv2.dilate((m_in > .5).astype(np.uint8), np.ones((61, 61), np.uint8)) == 0
bgs = [in_fr, photo[::-1].copy()]
for kind in editfx.LOOKS:
    r0 = editfx.look(kind, photo, m_in, hist=[], bgs=bgs, t=0.3, pulse=0.0, n=1)
    r1 = editfx.look(kind, photo, m_in, hist=[], bgs=bgs, t=0.3, pulse=1.0, n=1)
    assert r0.shape == photo.shape and r0.dtype == np.uint8, kind
    assert mad(r0[inner], photo[inner]) < 2, (kind, mad(r0[inner], photo[inner]))
    assert mad(r0[outer], photo[outer]) > 10, (kind, mad(r0[outer], photo[outer]))
    assert r1.mean() > r0.mean() + 1, (kind, r1.mean(), r0.mean())   # the beat flare brightens the frame
    assert (editfx.look(kind, photo, m_in, hist=[], bgs=bgs, t=0.3, pulse=0.0, n=1) == r0).all(), kind
assert editfx.look('nope', photo, m_in, hist=[], bgs=bgs, t=0.3, pulse=0.0, n=1) is photo
gray = np.full((H, W, 3), 128, np.uint8)
e = editfx.look('echo', gray, m_in, hist=[], bgs=[], t=0.0, pulse=0.0, n=0)   # still subject: blue copies beside the body
left = e[H // 4:3 * H // 4, :W // 4].reshape(-1, 3).mean(0)
assert left[2] > left[0] + 30, left
moved = np.roll(m_in, -W // 5, 1)   # the subject was further left 9 frames ago: the copy sits there
e2 = editfx.look('echo', gray, m_in, hist=[moved] * 10, bgs=[], t=0.0, pulse=0.0, n=0)
assert e2[H // 2, W // 4 - W // 5 + 5, 2] > e2[H // 2, W // 4 - W // 5 + 5, 0] + 30
sw = [editfx.look('swap', photo, m_in, hist=[], bgs=bgs, t=0.0, pulse=0.0, n=k) for k in (0, 1)]
assert mad(sw[0][outer], sw[1][outer]) > 10   # a new background every beat

h = editfx.halftone(photo)
assert h.shape == photo.shape and 0 < mad(h, photo) < 15

print('ok')
