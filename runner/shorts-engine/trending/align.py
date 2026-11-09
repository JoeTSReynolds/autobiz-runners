"""Re-time caption words with Whisper. Captions keep their text; only the times come from the audio."""
import difflib, glob, json, os, re, subprocess, sys, tempfile


def _whisper(audio_path):
    """Whisper's words for one audio/video file as [{w, s, e}] in file seconds (whisper-ctranslate2 base.en, CPU, int8, as media-fetch)."""
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['whisper-ctranslate2', audio_path, '--model', 'base.en', '--device', 'cpu', '--compute_type', 'int8',
                        '--word_timestamps', 'True', '--output_format', 'json', '--output_dir', d],
                       check=True, capture_output=True, text=True, timeout=180)
        doc = json.load(open(glob.glob(os.path.join(d, '*.json'))[0]))
    return [{'w': w['word'], 's': w['start'], 'e': w['end']} for seg in doc['segments'] for w in seg.get('words', [])]


WORD_S = 0.45   # longest a word is assumed to take when it is followed by words nobody heard


def _fold(w):
    return re.sub(r'[^a-z0-9]', '', w.lower())


def _assign(words, heard, offset, mark=None):
    """Copy of words with the times of the heard words they match (shifted by offset); the rest are spread between matched neighbours.
    Unchanged copy when nothing matches."""
    out = [dict(w) for w in words]
    a, b = [_fold(w['w']) for w in out], [_fold(h['w']) for h in heard]
    hit = {}
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            if a[blk.a + k]:
                hit[blk.a + k] = heard[blk.b + k]
    if not hit:
        return out
    for i, h in hit.items():
        out[i]['s'], out[i]['e'] = round(offset + h['s'], 3), round(offset + h['e'], 3)
    i = 0
    while i < len(out):
        if i in hit:
            i += 1
            continue
        j = i
        while j < len(out) and j not in hit:
            j += 1
        if i:   # a heard word's end runs to the next heard word's start, so it also covers the missed words: it ends within a normal word length
            out[i - 1]['e'] = min(out[i - 1]['e'], round(out[i - 1]['s'] + WORD_S, 3))
        lo = out[i - 1]['e'] if i else words[i]['s']                    # no matched word before: keep the caption's own start
        hi = max(out[j]['s'] if j < len(out) else words[j - 1]['e'], lo)
        for k in range(i, j):
            out[k]['s'], out[k]['e'] = round(lo + (hi - lo) * (k - i) / (j - i), 3), round(lo + (hi - lo) * (k - i + 1) / (j - i), 3)
        i = j
    for a_, b_ in zip(out, out[1:]):   # automatic captions end an event's last word at the event's end, past the next word's start
        a_['e'] = max(a_['s'], min(a_['e'], b_['s']))
    if mark:
        for w in out: w[mark] = True
    return out


def merge(words, heard):
    """words (manual captions, line-level times) with the per-word times of an automatic track; every word is marked timed.
    Unchanged copy, not marked, when nothing matches."""
    out = _assign(words, heard, 0, 'timed')
    return out if any(w.get('timed') for w in out) else [dict(w) for w in words]


def retime(words, audio_path, offset):
    """words (source seconds) with Whisper's times for the clip file audio_path (file time t is source time offset + t).
    Words Whisper did not hear are spread between their matched neighbours. Never raises: on any failure the words come back unchanged."""
    try:
        if not words:
            return [dict(w) for w in words]
        out = _assign(words, _whisper(audio_path), offset)
        if out == words:
            print('align: no words matched, keeping caption times', file=sys.stderr)
        return out
    except Exception as e:  # missing binary, model download, timeout, bad json: captions keep their old times
        print(f'align: whisper unavailable ({type(e).__name__}: {e}), keeping caption times', file=sys.stderr)
        return [dict(w) for w in words]
