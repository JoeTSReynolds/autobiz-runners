"""Streamer voice check for media-fetch (needs numpy and sherpa-onnx; point AUTOBIZ_PYTHON at a venv with them). Every subcommand prints one JSON object.

  enroll <model> <wav...>   the largest group of clips whose members are each >= 0.6 cosine from the group's centroid:
                            {"embedding": [...], "used": n, "videos": k}, or {"embedding": null} unless it has 5+ clips from 2+ videos
                            (a clip's video is its file name before the last "-")
  scan <model> <embedding.json> <audio> <sentences.json>
                            <sentences.json> is [{"start", "end"}, ...] in stream seconds, <audio> the whole stream's audio. Prints
                            {"windows": [{"start", "end", "scores": [...]}]}: 120 s bins with at least 2 hits (cosine >= 0.45) among
                            their 4 longest sentences, the 12 with most hits, touching ones merged; scores are for every sentence
                            starting in the window, in order. Audio is decoded one bin at a time.
  remove <file...>          deletes the files (the temporary wavs and json of one check)

The model (3D-Speaker CAM++) is downloaded to <model> when it is missing.
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np

URL = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx'
RATE = 16000
MIN_SPAN = 3.0  # seconds: shorter ranges are padded around their centre, a speaker embedding needs about this much
SILENT = 0.01  # peak amplitude below which audio counts as silence
GROUP_COSINE, MIN_CLIPS, MIN_VIDEOS = 0.6, 5, 2
CUTOFF = 0.45  # cosine to the reference at or above which a sentence is the streamer's
BIN, BIN_LONGEST, BINS_KEPT = 120, 4, 12  # scan: seconds per bin, sentences scored in the coarse pass, bins taken to the full pass


def extractor(model):
    import sherpa_onnx
    if not os.path.exists(model):
        import urllib.request
        os.makedirs(os.path.dirname(model) or '.', exist_ok=True)
        urllib.request.urlretrieve(URL, model + '.part')
        os.rename(model + '.part', model)
    return sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=model, num_threads=2))


def load(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def embed(ex, x):
    """The unit embedding of the samples, or None for silence."""
    if len(x) < RATE // 2 or np.abs(x).max() < SILENT:
        return None
    s = ex.create_stream()
    s.accept_waveform(RATE, x)
    s.input_finished()
    v = np.array(ex.compute(s))
    return v / np.linalg.norm(v)


def unit(v):
    return v / np.linalg.norm(v)


def largest_group(E):
    """Indices of the largest stable group: seeded by each clip, then re-centred until every member is >= GROUP_COSINE from the centroid."""
    best = []
    for seed in range(len(E)):
        members = E @ E[seed] >= GROUP_COSINE
        for _ in range(10):
            again = E @ unit(E[members].mean(0)) >= GROUP_COSINE
            if (again == members).all():
                break
            members = again
        else:
            continue
        if members.sum() > len(best):
            best = list(np.flatnonzero(members))
    return best


def enroll(model, wavs):
    ex = extractor(model)
    pairs = [(w, embed(ex, load(w))) for w in wavs]
    pairs = [(w, e) for w, e in pairs if e is not None]
    if not pairs:
        return {'embedding': None}
    group = largest_group(np.array([e for _, e in pairs]))
    videos = {os.path.basename(pairs[i][0]).rsplit('.', 1)[0].rsplit('-', 1)[0] for i in group}
    if len(group) < MIN_CLIPS or len(videos) < MIN_VIDEOS:
        return {'embedding': None}
    centroid = unit(np.array([pairs[i][1] for i in group]).mean(0))
    return {'embedding': [round(float(v), 6) for v in centroid], 'used': len(group), 'videos': len(videos)}


def decode(audio, start, length):
    out = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(start), '-t', str(length), '-i', audio, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'],
                         capture_output=True, timeout=120, check=True).stdout
    return np.frombuffer(out, np.int16).astype(np.float32) / 32768


def similarity(ex, ref, x, offset, start, end):
    """Cosine of the range [start, end] (stream seconds; x starts at offset) to ref; ranges under MIN_SPAN are padded around their centre inside x. Silence is 0."""
    a, b, length = start - offset, end - offset, len(x) / RATE
    if b - a < MIN_SPAN:
        a, b = (a + b) / 2 - MIN_SPAN / 2, (a + b) / 2 + MIN_SPAN / 2
        a, b = max(0.0, a - max(0.0, b - length)), min(length, b - min(0.0, a))
    e = embed(ex, x[int(max(0.0, a) * RATE):int(max(0.0, b) * RATE)])
    return 0.0 if e is None else float(e @ ref)


def scan(model, embedding, audio, sentences):
    """Windows of the stream where the reference voice talks. A coarse pass scores the BIN_LONGEST longest sentences of each BIN-second bin
    (one ffmpeg decode of that bin at a time, never the whole file); the BINS_KEPT bins with at least 2 hits come first, then every sentence
    of those bins is scored and touching bins merge into one window with the scores of its sentences (start in [start, end)) in order."""
    ex = extractor(model)
    ref = unit(np.array(json.load(open(embedding)), dtype=np.float32))
    spoken = json.load(open(sentences))
    bins = {}
    for s in spoken:
        bins.setdefault(int(s['start'] // BIN), []).append(s)
    hits, audio_of = {}, {}
    for n, inside in sorted(bins.items()):
        x = decode(audio, n * BIN, BIN)
        top = sorted(inside, key=lambda s: s['start'] - s['end'])[:BIN_LONGEST]
        hits[n] = sum(similarity(ex, ref, x, n * BIN, s['start'], s['end']) >= CUTOFF for s in top)
        if hits[n] >= 2:
            audio_of[n] = x
    best = sorted((n for n in hits if hits[n] >= 2), key=lambda n: (-hits[n], n))[:BINS_KEPT]
    windows = []
    for n in sorted(best):
        if windows and windows[-1]['bins'][-1] == n - 1:
            windows[-1]['bins'].append(n)
        else:
            windows.append({'bins': [n]})
    for w in windows:
        w['start'], w['end'] = w['bins'][0] * BIN, (w['bins'][-1] + 1) * BIN
        w['scores'] = [round(similarity(ex, ref, audio_of[int(s['start'] // BIN)], int(s['start'] // BIN) * BIN, s['start'], s['end']), 4)
                       for n in w['bins'] for s in bins[n]]
        del w['bins']
    return {'windows': windows}


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    sub, args = argv[1], argv[2:]
    if sub == 'enroll' and len(args) >= 1:
        result = enroll(args[0], args[1:])
    elif sub == 'scan' and len(args) == 4:
        result = scan(*args)
    elif sub == 'remove':
        for path in args:
            if os.path.exists(path):
                os.remove(path)
        result = {'removed': len(args)}
    else:
        sys.exit(__doc__)
    print(json.dumps(result, separators=(',', ':')))


if __name__ == '__main__':
    main(sys.argv)
