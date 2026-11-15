"""Music helpers: find trending sounds, fetch audio, analyse (bpm/beats/drop), place and mix.
CLI: python -m trending.music trending TAG... | fetch ID MUSIC_DIR | analyse FILE"""
import collections, hashlib, json, os, subprocess, sys, time, urllib.request
from pathlib import Path
import numpy as np
from shared import media, ytdlp  # engine folder is on sys.path
from .sound import sound

SR, N, HOP = 22050, 2048, 512          # hop = 23.2 ms
HOPS = HOP / SR

def trending(hashtags, per_tag=30, sleep=0.3):
    """Rank sounds (title, source) used by recent Shorts under the hashtags. Skips 'Original Sound'."""
    tally, ex = collections.Counter(), collections.defaultdict(list)
    for tag in hashtags:
        out = ytdlp.run(['--flat-playlist', '-I', f'1:{per_tag}', '--print', '%(id)s %(view_count)s',
                   f'https://www.youtube.com/hashtag/{tag}/shorts'], capture_output=True, text=True).stdout
        for line in out.split('\n'):
            if not line.strip(): continue
            vid = line.split()[0]
            try: s = sound(vid)
            except Exception: s = None
            time.sleep(sleep)
            if not s or s['title'].lower().startswith('original sound'): continue
            k = (s['title'], s['source'])
            tally[k] += 1; ex[k].append(vid)
    return [dict(title=t, source=src, count=c, example_shorts=ex[(t, src)][:5]) for (t, src), c in tally.most_common()]

def fetch(source_id, music_dir):
    """Download audio of a video to <music_dir>/<id>.m4a (+ .json sidecar). Cached."""
    os.makedirs(music_dir, exist_ok=True)
    path = os.path.join(music_dir, f'{source_id}.m4a')
    if os.path.exists(path) and os.path.exists(path + '.json'): return path
    r = ytdlp.run(['-f', 'ba', '-x', '--audio-format', 'm4a', '--no-simulate', '--no-playlist',
             '--print', '%(.{title,uploader,duration,webpage_url})j', '-o', os.path.join(music_dir, '%(id)s.%(ext)s'),
             f'https://www.youtube.com/watch?v={source_id}'], capture_output=True, text=True)
    if not os.path.exists(path): raise RuntimeError('fetch failed: ' + r.stderr[-400:])
    meta = json.loads(r.stdout.strip().split('\n')[0])
    json.dump(dict(meta, id=source_id, url=meta.pop('webpage_url')), open(path + '.json', 'w'), indent=1)
    return path

def _decode(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32)

def _spec(x):
    """Magnitude STFT, shape (frames, bins)."""
    x = np.pad(x, (N // 2, N // 2))
    n = 1 + (len(x) - N) // HOP
    idx = np.arange(N)[None, :] + HOP * np.arange(n)[:, None]
    return np.abs(np.fft.rfft(x[idx] * np.hanning(N), axis=1))

def _db(p): return 10 * np.log10(p + 1e-10)

def _tempo(onset):
    """Return (bpm, beat times) by autocorrelation of onset strength, then comb phase alignment."""
    o = onset - onset.mean()
    ac = np.correlate(o, o, 'full')[len(o) - 1:]
    bpms = np.arange(70, 180.01, 0.25)
    lags = 60 / bpms / HOPS
    score = np.interp(lags, np.arange(len(ac)), ac) + 0.5 * np.interp(2 * lags, np.arange(len(ac)), ac)
    score = score * np.exp(-0.5 * (np.log2(bpms / 120) / 1.0) ** 2)   # mild bias against octave errors
    bpm = float(bpms[np.argmax(score)])
    period = 60 / bpm / HOPS
    # phase: sum onset at phase + k*period (linear interp), choose best phase
    best = max(np.arange(0, period, 0.25), key=lambda ph: np.interp(np.arange(ph, len(onset) - 1, period), np.arange(len(onset)), onset).sum())
    return bpm, (np.arange(best, len(onset) - 1, period) * HOPS)

# YAMNet (Google AudioSet classifier, Apache 2.0) as ONNX, waveform in, 521 class scores per 0.48 s frame out
YAMNET_NAME = 'yamnet.onnx'
YAMNET_URL = 'https://huggingface.co/audiomagic/yamnet-onnx/resolve/main/yamnet.onnx'
YAMNET_SHA256 = 'd3835ffbbd4a1bb3e777f0ca217b5007907f5171dd5d17c4236b95b2af8f908e'
# AudioSet ids: Speech, Conversation, Narration, Singing, Choir, Chant, Mantra, Child singing, Synthetic singing, Rapping, Vocal music, A capella
VOCAL_CLASSES = [0, 2, 3, 24, 25, 27, 28, 29, 30, 31, 249, 250]
VOCAL_TOP = 5            # a frame is vocal when a vocal class is among its 5 best
VOCAL_SHARE_MAX = 0.15   # real tracks (2026-11-08): vocal songs 0.32-0.74, instrumentals 0.00-0.03
MAX_VOCAL_S = 240        # only the first 4 minutes are classified


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def yamnet_path(models_dir):
    """Path of the sha256-verified YAMNet model in models_dir, downloaded first if missing. A wrong hash is an error."""
    p = Path(models_dir) / YAMNET_NAME
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix('.part')
        with urllib.request.urlopen(YAMNET_URL, timeout=120) as r, open(tmp, 'wb') as f:
            while chunk := r.read(1 << 20): f.write(chunk)
        if _sha256(tmp) != YAMNET_SHA256: os.remove(tmp); raise RuntimeError(f'{YAMNET_URL}: download sha256 does not match the pinned {YAMNET_SHA256}')
        os.replace(tmp, p)
    elif _sha256(p) != YAMNET_SHA256: raise RuntimeError(f'{p}: file sha256 does not match the pinned {YAMNET_SHA256}')
    return str(p)


def _share(scores):
    """Share of frames (rows of class scores) with a vocal class among the VOCAL_TOP best."""
    return float(np.isin(np.argsort(-scores, 1)[:, :VOCAL_TOP], VOCAL_CLASSES).any(1).mean())


def vocal_share(path, models_dir):
    import onnxruntime
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-t', str(MAX_VOCAL_S), '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout
    sess = onnxruntime.InferenceSession(yamnet_path(models_dir), providers=['CPUExecutionProvider'])
    return _share(sess.run(None, {'waveform': np.frombuffer(raw, np.float32)})[0])


def analyse(path, models_dir=None):
    """Analyse a music file (cached in <path>.analysis.json). See keys in code. vocal_hint is crude (old data only); with models_dir
    the analysis has vocal_share, the YAMNet vocal measure, and an older cache without it is analysed again."""
    cache = path + '.analysis.json'
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(path):
        old = json.load(open(cache))
        if not models_dir or 'vocal_share' in old: return old
    x = _decode(path)
    S = _spec(x); P = S ** 2
    f = np.fft.rfftfreq(N, 1 / SR)
    low = _db(P[:, f < 150].sum(1) / N)
    mid = _db(P[:, (f >= 300) & (f < 3000)].sum(1) / N)
    full = _db(P.sum(1) / N)
    # onset strength: positive diff of log magnitude, summed over bins
    L = np.log1p(100 * S / S.max())
    onset = np.maximum(np.diff(L, axis=0, prepend=L[:1]), 0).sum(1)
    bpm, beats = _tempo(onset)
    dur = len(x) / SR
    fps = 1 / HOPS
    # drop: largest sustained step up of low band (next 4 s mean - previous 4 s mean), after 3 s
    # power means (not dB means: kick-heavy bass is bursty, dB averaging is dominated by the gaps)
    w = int(4 * fps); lp = P[:, f < 150].sum(1) + 1e-9; cs = np.concatenate([[0], np.cumsum(lp)])
    cand = []
    for i in range(int(3 * fps), len(lp) - int(2 * fps)):
        j = min(i + w, len(lp)); k = max(i - w, 0)
        cand.append((10 * np.log10(((cs[j] - cs[i]) / (j - i)) / ((cs[i] - cs[k]) / (i - k))), i * HOPS))
    cand.sort(reverse=True)
    drops = []
    for sc, t in cand:
        if all(abs(t - d['time']) > 4 for d in drops):
            drops.append(dict(time=float(beats[np.abs(beats - t).argmin()]) if len(beats) else t, score=float(sc)))
        if len(drops) == 3: break
    # intensity per second
    k = max(len(x) // SR, 1); rms = np.sqrt((x[:k * SR] ** 2).reshape(k, -1).mean(1)) if len(x) >= SR else np.array([np.sqrt((x ** 2).mean())])
    inten = rms / (rms.max() + 1e-9)
    build = float(np.corrcoef(inten, np.arange(len(inten)))[0, 1]) if len(inten) > 2 and inten.std() > 0 else 0.0
    # crude: mid-band loudness variance relative to bass variance; high -> melodic/vocal-heavy mids, low -> bass/beat driven
    vocal = float(mid.var() / (low.var() + 1e-9))
    res = dict(duration=dur, bpm=round(bpm, 1), beats=[round(float(b), 3) for b in beats],
               drop=drops[0]['time'] if drops else None, drops=drops,
               intensity=[round(float(v), 3) for v in inten], build_score=round(build, 3), vocal_hint=round(vocal, 3))
    if models_dir: res['vocal_share'] = round(vocal_share(path, models_dir), 3)
    json.dump(res, open(cache, 'w'))
    return res

def place(analysis, target_drop_time, video_duration):
    """Offset into the music file so its drop lands at target_drop_time in the video.
    music_offset < 0 means start the music that many seconds into the video (drop is later in the video than the file allows)."""
    drop = analysis['drop'] if analysis.get('drop') is not None else 0.0
    off = drop - target_drop_time
    if analysis.get('duration'):   # keep enough song for the whole video, even if the drop then lands earlier
        off = min(off, analysis['duration'] - video_duration)
    off = max(off, -target_drop_time)   # cannot start before 0 s of the video
    return dict(music_offset=round(off, 3), fade_in=0.4 if off >= 0 else 0.8, fade_out=min(1.5, video_duration / 4))

def mix(voice_audio, music_path, music_offset, out, music_gain_db=-8, duck_db=10, video_duration=None, boost_after=None, attack_ms=10, release_ms=250,
        swell=(), swell_s=2.0):
    """Mix speech/clip audio with music: ducked via sidechaincompress, optional +4 dB from boost_after (s), alimiter, AAC 192k.
    duck_db is approximate: ratio = 1 + duck_db/2 (10 -> 6); attack_ms/release_ms shape the duck. Negative music_offset delays the music instead of trimming.
    swell: speech pauses [(a, b)] where the music goes unducked, crossfading from the ducked music over swell_s before a and after b."""
    d = video_duration or media.duration(voice_audio)
    pre = ['-ss', f'{music_offset:.3f}'] if music_offset > 0 else []
    delay = f',adelay={int(-music_offset * 1000)}:all=1' if music_offset < 0 else ''
    g = music_gain_db
    vol = f"volume='pow(10,({g}+4*min(1,max(0,(t-{boost_after})/0.3)))/20)':eval=frame" if boost_after is not None else f'volume={g}dB'
    fo = min(1.5, d / 4)
    fc = (f'[0:a]aresample=44100,apad,atrim=0:{d},asplit=2[v1][v2];'
          f'[1:a]aresample=44100{delay},{vol},afade=t=in:d=0.4,apad,atrim=0:{d},afade=t=out:st={d - fo:.3f}:d={fo:.3f}[m];'   # apad: a song that ends early must not end the mix
          f'[m][v1]sidechaincompress=threshold=0.03:ratio={1 + duck_db / 2:g}:attack={attack_ms}:release={release_ms}[md];'
          f'[md][v2]amix=inputs=2:duration=first:dropout_transition=0,volume=2,alimiter=limit=0.95[o]')
    if swell:   # w(t) 0..1: the share of the unducked music, ramping over swell_s either side of each pause
        r = swell_s
        w = 'min(1,' + '+'.join(f'min(1,max(0,(t-{a - r:.3f})/{r}))*min(1,max(0,({b + r:.3f}-t)/{r}))' for a, b in swell) + ')'
        fc = fc.replace('[m][v1]sidechaincompress', '[m]asplit=2[m1][m2];[m1][v1]sidechaincompress').replace(
            '[md][v2]amix', f"[md]volume='1-{w}':eval=frame[mdw];[m2]volume='{w}':eval=frame[mw];[mdw][mw]amix=inputs=2:normalize=0[mm];[mm][v2]amix")
    r = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', voice_audio, *pre, '-i', music_path, '-filter_complex', fc,
             '-map', '[o]', '-t', f'{d}', '-c:a', 'aac', '-b:a', '192k', out], capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr[-600:])
    return out

if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'trending':
        for i, r in enumerate(trending(args), 1): print(f"{i:2} {r['count']:3}  {r['source']}  {r['title']}")
    elif cmd == 'fetch': print(fetch(*args[:2]))
    elif cmd == 'analyse':
        a = analyse(*args[:2]); print({k: v for k, v in a.items() if k not in ('beats', 'intensity')})
