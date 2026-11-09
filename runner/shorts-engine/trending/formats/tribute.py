"""Tribute renderer: grey, slow face-crop edit with two spine lines in the person's own voice, music bed ducked under them,
colour returning on the swell with the closing card. Look generalised from prototypes/trending/tribute/build.py.

    from trending.formats import tribute; tribute.render(job, cfg, run_dir) -> {short, timeline, credits}

Reads job["plan"], job["clips"] (media-fetch files, `plan.clips[i]` <-> `job.clips[i]`; file time t = source time offset + t),
job["track"] ({file, title, analysis}); plan.musicOffset puts the swell SWELL_IN s after the closing shot starts. File paths are
relative to `run`. Intermediates go to run/cut/, the video to run/short.mp4.
Sequence: m0 (name card) m1 spine0 m2 m3 spine1 m4.. last moment (closing card).
"""
import re, subprocess, textwrap
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from .. import captions, facecrop, music
from ..sensitive import caption_text
from .safe import SAFE_X

FONTS = Path(__file__).resolve().parents[1] / "fonts"
GRADE = ("hue=s=0,eq=contrast=1.28:brightness=-0.02:gamma=1.05,curves=all='0/0.07 0.5/0.5 1/0.95',noise=alls=11:allf=t")
SLOW, END_SPEED, CLOSE, SWELL_IN, DIP = 0.8, 0.4, 8.5, 1.7, 0.25   # closing shot lasts CLOSE s (footage, then a held frame)
BED_LUFS, DUCK_DB, TARGET_LUFS = -16, 9, -14
SUB_Y = int(1920 * 0.74)


def _ff(*cmd):
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, cmd)], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-600:])


def _lufs(path, ss=0, t=None):
    cut = ["-ss", str(ss)] + (["-t", str(t)] if t else [])
    err = subprocess.run(["ffmpeg", "-nostats", *cut, "-i", str(path), "-vn", "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])


def _font(name, size, wght=500):
    f = ImageFont.truetype(str(FONTS / name), size)
    try:
        f.set_variation_by_axes([wght])
    except Exception:  # static font file
        pass
    return f


def _text_png(lines, out, wght=500):
    """lines [(text, size, italic, y)] -> centred white serif text with soft shadow on a transparent 1080x1920 canvas."""
    im, sh = (Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)) for _ in range(2))
    d, ds = ImageDraw.Draw(im), ImageDraw.Draw(sh)
    for txt, size, it, y in lines:
        txt = caption_text(txt)
        name = "CormorantGaramond-Italic.ttf" if it else "CormorantGaramond.ttf"
        f = _font(name, size, wght)
        while d.textlength(txt, font=f) > 1080 - 2 * SAFE_X and size > 30:  # long names shrink to fit
            size -= 4
            f = _font(name, size, wght)
        x = (1080 - d.textlength(txt, font=f)) / 2
        ds.text((x + 2, y + 3), txt, font=f, fill=(0, 0, 0, 230))
        d.text((x, y), txt, font=f, fill=(255, 255, 255, 255))
    Image.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)), im).save(out)
    return str(out)


def _chunks(words):
    """Spine words -> captions.chunks lines: 40 chars, commas split from 20 chars, pauses split."""
    return captions.chunks(words, 99, 40, hold=0.15, soft_chars=20)


def _sub_png(txt, out):
    for size, width in ((80, 27), (64, 34)):
        ls = textwrap.wrap(txt, width)
        if len(ls) <= 2:
            break
    return _text_png([(l, size, False, SUB_Y - 40 + k * round(size * 1.15)) for k, l in enumerate(ls)], out, wght=600)


def _shots(plan, job, run):
    by_key = {c["key"]: (c, f) for c, f in zip(plan["clips"], job["clips"])}
    spines = {s["clip"]: s for s in plan["spine"]}
    mom = [m["clip"] for m in plan["moments"]]
    keys = mom[:2] + [plan["spine"][0]["clip"]] + mom[2:4] + [plan["spine"][1]["clip"]] + mom[4:-1] + mom[-1:]
    # with fewer than 4 moments the first slice runs short; the last moment always closes
    keys = [k for i, k in enumerate(keys) if k not in mom[-1:] or i == len(keys) - 1]
    shots, t = [], 0.0
    for i, k in enumerate(keys):
        c, f = by_key[k]
        s = dict(n=f"s{i}", key=k, file=str(Path(run) / f["file"]), a=c["start"] - f.get("offset", 0), b=c["end"] - f.get("offset", 0),
                 kind="moment", speed=SLOW, t0=t)
        if k in spines:
            ws = [w for w in spines[k]["words"] if c["start"] <= w["s"] < c["end"]]
            s.update(kind="spine", speed=1.0, words=ws, pre=ws[0]["s"] - c["start"], src_start=c["start"])
        if i == len(keys) - 1:
            nat = min((s["b"] - s["a"]) / END_SPEED, CLOSE - 2.0)
            s.update(kind="closing", speed=END_SPEED, nat=nat, b=s["a"] + nat * END_SPEED, dur=CLOSE)
        else:
            s["dur"] = (s["b"] - s["a"]) / s["speed"]
        t += s["dur"]
        shots.append(s)
    return shots, t


def _render_shot(s, out, ref=None, models=None):
    cam = facecrop.track(s["file"], start=s["a"], end=s["b"], ref=ref, models=models)
    sz = np.nanmedian(cam["size"][cam["found"]]) if cam["found"].any() else 0
    lo, hi = (1.25, 1.4) if s["kind"] == "closing" else (1.3, 1.42)
    z0 = min(max((min(cam["H"], cam["W"] * 16 / 9) * 9 / 16) / (sz / 0.50), lo), 2.3) if sz else lo  # face about half the crop width
    facecrop.render(s["file"], out, zoom=facecrop.push_in(z0, z0 * hi / lo, s["b"] - s["a"]), face_y=0.40, start=s["a"], end=s["b"],
                    grade="eq=contrast=1.08" if s["kind"] == "closing" else GRADE, cam=cam)


def _post(s, src, out, fin, fout):
    vf = []
    if s["speed"] != 1.0:
        vf.append(f"setpts=PTS/{s['speed']},framerate=fps=30")
    if s["kind"] == "closing":
        vf.append(f"tpad=stop_mode=clone:stop_duration={s['dur'] - s['nat'] + 0.2:.2f}")
        r0, r1 = SWELL_IN - 1.3, SWELL_IN + 1.0     # grey -> colour: saturation ramps 0 -> 1 around the swell
        vf.append(f"hue=s='clip((t-{r0:.2f})/{r1 - r0:.2f},0,1)',eq=contrast='1.22-0.14*clip((t-{r0:.2f})/{r1 - r0:.2f},0,1)'")
    vf += ["vignette=angle=PI/3.2:eval=init", f"trim=0:{s['dur']:.3f},setpts=PTS-STARTPTS"]
    if fin:
        vf.append(f"fade=t=in:st=0:d={DIP}:c={fin}")
    if fout:
        d = 1.0 if s["kind"] == "closing" else DIP
        vf.append(f"fade=t=out:st={s['dur'] - d:.3f}:d={d}:c={fout}")
    _ff("-i", src, "-vf", ",".join(vf), "-an", "-r", 30, "-c:v", "libx264", "-crf", 17, "-preset", "veryfast", "-pix_fmt", "yuv420p", out)


def _overlays(plan, shots, D, cut):
    ov, T = [], shots[-1]["t0"]
    for n, s in enumerate(x for x in shots if x["kind"] == "spine"):
        w, c0 = s["words"], s["t0"] - s["src_start"]
        for k, ch in enumerate(_chunks(w)):
            a, b = c0 + ch["start"], min(c0 + ch["end"], s["t0"] + s["dur"])
            ov.append((_sub_png(ch["text"], cut / f"sub{n}_{k}.png"), a, b, min(.35, (b - a) / 3)))
    name = plan.get("name") or plan["person"]["name"]
    years = plan.get("years") or plan["person"].get("years", "")
    ov.append((_text_png([(name, 84, False, SUB_Y - 60), (years, 52, True, SUB_Y + 50)], cut / "open.png", 600), 0.4, min(2.9, shots[0]["dur"] - 0.35), .5))
    grad = np.zeros((1920, 1080, 4), np.uint8)   # soft dark gradient behind the closing card
    grad[..., 3] = (np.clip((np.arange(1920) - 1000) / 600, 0, 1) ** 1.5 * 190)[:, None].astype(np.uint8)
    Image.fromarray(grad, "RGBA").save(cut / "grad.png")
    end = D - 0.8
    ov.append((str(cut / "grad.png"), T + 1.3, end, 1.2))
    ov.append((_text_png([(name, 92, False, 1280)], cut / "name.png", 600), T + 1.9, end, .9))
    ov.append((_text_png([(years, 52, True, 1405)], cut / "years.png"), T + 2.9, end, .9))
    ls = textwrap.wrap(plan["closingLine"], 38)
    ov.append((_text_png([(l, 46, True, 1500 + 58 * k) for k, l in enumerate(ls)], cut / "line.png"), T + 4.3, end, .9))
    return ov


def _voice(shots, D, cut):
    ins, fc, labs = [], [], []
    for i, s in enumerate(x for x in shots if x["kind"] == "spine"):
        ins += ["-i", cut / f"{s['n']}.mp4"]
        tail = max(s["dur"] - s["pre"] - 0.55, 0)
        fc.append(f"[{i}:a]atrim=start={s['pre']:.2f},asetpts=PTS-STARTPTS,loudnorm=I=-11:TP=-1.5:LRA=7,afade=t=in:d=0.15,"
                  f"afade=t=out:st={tail:.2f}:d=0.4,aresample=44100,adelay={int((s['t0'] + s['pre']) * 1000)}:all=1[a{i}]")
        labs.append(f"[a{i}]")
    fc.append("".join(labs) + f"amix=inputs={len(labs)}:duration=longest:normalize=0,apad=whole_dur={D}[o]")
    _ff(*ins, "-filter_complex", ";".join(fc), "-map", "[o]", "-ac", 2, cut / "voice.wav")
    return cut / "voice.wav"


def render(job, cfg, run):
    plan, run = job["plan"], Path(run)
    cut = run / "cut"
    cut.mkdir(parents=True, exist_ok=True)
    shots, D = _shots(plan, job, run)
    for i, s in enumerate(shots):
        _render_shot(s, cut / f"{s['n']}.mp4", facecrop.load_ref(run), cfg.get("models"))
        edge = lambda a, b: "white" if "spine" in (a["kind"], b["kind"]) else "black"
        fin = edge(shots[i - 1], s) if i else None
        fout = edge(s, shots[i + 1]) if i + 1 < len(shots) else "black"
        _post(s, cut / f"{s['n']}.mp4", cut / f"post{i}.mp4", fin, fout)
    (cut / "concat.txt").write_text("".join(f"file 'post{i}.mp4'\n" for i in range(len(shots))))
    _ff("-f", "concat", "-safe", 0, "-i", cut / "concat.txt", "-c", "copy", cut / "base.mp4")

    track = job["track"]
    mp = str(run / track["file"])
    off = plan.get("musicOffset")
    if off is None:
        off = music.place(track["analysis"], shots[-1]["t0"] + SWELL_IN, D)["music_offset"]
    gain = BED_LUFS - _lufs(mp, max(off, 0), D - max(-off, 0))   # bed at about -16 LUFS before ducking
    music.mix(_voice(shots, D, cut), mp, off, str(cut / "mix.m4a"), music_gain_db=gain, duck_db=DUCK_DB, video_duration=D,
              attack_ms=150, release_ms=800)
    fix = TARGET_LUFS - _lufs(cut / "mix.m4a")

    ins, fc, last = ["-i", cut / "base.mp4"], [], "0:v"
    ov = _overlays(plan, shots, D, cut)
    for i, (p, a, b, f) in enumerate(ov, start=1):
        L = b - a
        ins += ["-loop", 1, "-framerate", 30, "-t", f"{L:.2f}", "-i", p]
        fc += [f"[{i}:v]format=rgba,fade=t=in:st=0:d={f}:alpha=1,fade=t=out:st={L - f:.2f}:d={f}:alpha=1,setpts=PTS+{a}/TB[o{i}]",
               f"[{last}][o{i}]overlay=eof_action=pass[v{i}]"]
        last = f"v{i}"
    _ff(*ins, "-i", cut / "mix.m4a", "-filter_complex", ";".join(fc), "-map", f"[{last}]", "-map", f"{len(ov) + 1}:a",
        "-af", f"volume={fix:.2f}dB,alimiter=limit=0.89", "-t", f"{D}", "-c:v", "libx264", "-crf", 20, "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-r", 30, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", run / "short.mp4")

    urls = list(dict.fromkeys(c["source"]["url"] for c in plan["clips"]))
    return {"short": {"file": "short.mp4", "duration": D},
            "timeline": [{"start": s["t0"], "end": s["t0"] + s["dur"], "kind": s["kind"], "person": True} for s in shots],
            "credits": [f"Footage: {u}" for u in urls] + ([f"Music: {track['title']}"] if track.get("title") else [])}
