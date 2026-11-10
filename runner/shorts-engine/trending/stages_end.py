"""Trending stages cut, gate, record. Each is (job, cfg, run, state) -> (port, output, log); run and state are folders.

Spec: docs/plan/nowayclips-trending.plan.md (cut, gate, record), plan shape: docs/plan/briefs/plan-schema.md.
"""
import datetime as dt, importlib, json, re, subprocess
from pathlib import Path
from .sensitive import caption_text

FORMATS = ('tribute', 'topn', 'edit', 'casefile')
MIN_S, MAX_S, LUFS, LUFS_TOL, BLACK_S, TAIL_S = 20, 59, -14.0, 1.5, 1.0, 3.0
ID_FRAMES, ID_SHOTS, ID_SHARE = 2, 12, 0.9   # frames per person shot, shots sampled, share of shots that must match
ID_SHARE_TOPN = 0.5    # Top N: half the moments; the rest may stay on whoever the roast or dodge is aimed at
DESC_MAX = 4800


def _today():
    return dt.datetime.now(dt.timezone.utc).date()


def _jread(p, default):
    try: return json.loads(Path(p).read_text())
    except (OSError, ValueError): return default


def _invalid(why):
    return 'invalid', {'agentErrors': [why]}, why


def cut(job, cfg, run, state):
    fmt = (job.get('plan') or {}).get('format')
    if fmt not in FORMATS:
        raise SystemExit(f'cut: no renderer for plan.format {fmt!r} (formats: {", ".join(FORMATS)})')
    name = f'{__package__}.formats.{fmt}'
    try:
        mod = importlib.import_module(name)
    except ModuleNotFoundError as e:
        if e.name != name:
            raise   # a dependency of the renderer is missing, not the renderer
        raise SystemExit(f'cut: no renderer for format {fmt!r} yet ({name} is missing)')
    res = mod.render(job, {**cfg, 'models': str(Path(state) / 'models')}, Path(run))   # face models (topn picks its closer frame by identity)
    return 'next', {k: res[k] for k in ('short', 'timeline', 'credits')}, f'{fmt} rendered, {res["short"].get("duration")} s'


# ---- gate

def _ff(*args):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', *map(str, args)], capture_output=True, text=True)
    return r.stderr


def _duration(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)], capture_output=True, text=True).stdout
    return float(out.strip())


def _loudness(path):
    found = re.findall(r'I:\s+(-?[\d.]+) LUFS', _ff('-i', path, '-vn', '-af', 'ebur128', '-f', 'null', '-'))
    return float(found[-1]) if found else None


def _black_starts(path):
    return [float(m) for m in re.findall(r'black_start:([\d.]+)', _ff('-i', path, '-an', '-vf', f'blackdetect=d={BLACK_S}:pix_th=0.10', '-f', 'null', '-'))]


def _embed(img, models_dir):
    """Every noticeable face in the frame: the person can be the smaller face beside a host."""
    from . import faces
    return [e for e, _ in faces.embed_all(img, str(models_dir))]


def _frame(path, t, out):
    import cv2
    _ff('-y', '-v', 'error', '-ss', f'{t:.3f}', '-i', path, '-frames:v', 1, out)
    return cv2.imread(str(out))


def _identity(video, shots, ref, models, work, frames=ID_FRAMES, faceless_ok=False):
    """(hits, shots counted): sampled person shots with a face matching ref in at least one of `frames` frames. With
    faceless_ok a shot where no face is found at all (a wide shot) is left out of the count."""
    from . import faces
    step = max(1, -(-len(shots) // ID_SHOTS))   # even stride keeps the sample to ID_SHOTS shots
    sample = shots[::step]
    work.mkdir(parents=True, exist_ok=True)
    hit = faceless = 0
    for i, s in enumerate(sample):
        seen = False
        for k in range(frames):
            es = _embed(_frame(video, s['start'] + (s['end'] - s['start']) * (k + 1) / (frames + 1), work / f'{i}-{k}.png'), models)
            es = es if isinstance(es, list) else [] if es is None else [es]
            seen = seen or bool(es)
            if any(faces.match(e, ref) >= faces.MATCH for e in es):
                hit += 1
                break
        else:
            faceless += not seen
    return hit, len(sample) - (faceless if faceless_ok else 0)


def gate(job, cfg, run, state):
    import numpy as np
    run = Path(run)
    video = run / (job.get('short') or {}).get('file', 'short.mp4')
    if not video.is_file():
        return _invalid(f'gate: {video.name} was not rendered')
    d = _duration(video)
    if not MIN_S <= d <= MAX_S:
        return _invalid(f'gate: duration {d:.1f} s is outside {MIN_S}-{MAX_S} s')
    lu = _loudness(video)
    if lu is None or abs(lu - LUFS) > LUFS_TOL:
        return _invalid(f'gate: loudness {lu} LUFS is not {LUFS} +/- {LUFS_TOL}')
    black = [t for t in _black_starts(video) if t < d - TAIL_S]
    if black:
        return _invalid(f'gate: black frames from {black[0]:.1f} s (more than {BLACK_S} s, before the last {TAIL_S:.0f} s)')
    log, ref_file = f'{d:.1f} s, {lu:.1f} LUFS', (job.get('identity') or {}).get('file')
    shots = [s for s in job.get('timeline') or [] if s.get('person')]
    if ref_file and shots and (run / ref_file).is_file():
        topn = (job.get('plan') or {}).get('format') == 'topn'   # a Top N moment may show the person in only part of it
        edit = (job.get('plan') or {}).get('format') == 'edit'   # a wide stage shot has no detectable face: not someone else
        hit, n = _identity(video, shots, np.load(run / ref_file), Path(state) / 'models', run / 'gate', 4 if topn else ID_FRAMES, faceless_ok=edit)
        share = ID_SHARE_TOPN if (job.get('plan') or {}).get('format') == 'topn' else ID_SHARE
        if hit < share * n and not (edit and hit >= n - 1):   # an edit may miss one shot: the person turned away mid-climb
            return _invalid(f'gate: identity matched in {hit}/{n} sampled person shots (need {share:.0%})')
        log += f', identity {hit}/{n}'
    meta = dict(job.get('meta') or {})
    for k in ('title', 'description'):
        if isinstance(meta.get(k), str):
            meta[k] = caption_text(meta[k])
    for k in ('tags', 'hashtags'):
        if isinstance(meta.get(k), list):
            meta[k] = [caption_text(x) if isinstance(x, str) else x for x in meta[k]]
        elif isinstance(meta.get(k), str):
            meta[k] = caption_text(meta[k])
    credits = '\n'.join(job.get('credits') or [])
    if credits:
        meta['description'] = (meta.get('description', '') + '\n\n' + credits)[:DESC_MAX]
    return 'next', {'meta': meta}, log


# ---- record

def record(job, cfg, run, state):
    state, date = Path(state), _today().isoformat()
    state.mkdir(parents=True, exist_ok=True)
    p = job.get('person') or {}
    covered = _jread(state / 'trending-covered.json', []) + [{'qid': p.get('qid'), 'name': p.get('name'), 'format': (job.get('plan') or {}).get('format') or job.get('format'),
                                                               'date': date, 'title': (job.get('meta') or {}).get('title'), 'angle': (job.get('pick') or {}).get('angle')}]
    rest = [c for c in covered if c.get('format') != 'tribute'][-500:]   # tributes are kept: one per person, ever
    covered = [c for c in covered if c.get('format') == 'tribute' or c in rest]
    (state / 'trending-covered.json').write_text(json.dumps(covered, indent=1, ensure_ascii=False))
    sid = (job.get('track') or {}).get('id')
    if sid:
        used = _jread(state / 'trending-used-sounds.json', []) + [{'id': sid, 'date': date}]
        (state / 'trending-used-sounds.json').write_text(json.dumps(used[-200:], indent=1))
    return 'next', {}, f'recorded {p.get("name")}' + (f' and sound {sid}' if sid else '')
