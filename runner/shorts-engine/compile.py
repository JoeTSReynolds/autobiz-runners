# Compile <project>/storyboard.json into a HyperFrames project: script.json (for the voiceover),
# storyboard.js, index.html (from shell.html) and assets (lane look, kit, driver, used blueprints).
# Usage: python3 compile.py <project-dir>
import json, re, shutil, sys
from pathlib import Path

here, root = Path(__file__).parent, Path(sys.argv[1])
sb = json.loads((root / "storyboard.json").read_text())
errs = []
lane = here / "lanes" / sb.get("lane", "")
if not sb.get("lane") or not lane.is_dir():
    errs.append(f"lane: unknown lane {sb.get('lane')!r} (have: {', '.join(p.name for p in (here / 'lanes').iterdir() if p.is_dir())})")
ids = [s.get("id") for s in sb.get("scenes", [])]
if not ids or len(set(ids)) != len(ids) or not all(isinstance(i, str) and re.fullmatch(r"[a-z][a-z0-9-]*", i) for i in ids):
    errs.append("scenes: need unique lower-case ids")
for s in sb.get("scenes", []):
    if not isinstance(s.get("say"), str) or not s["say"].strip():
        errs.append(f"scenes.{s.get('id')}.say: the narration is required")
assets = root / "assets"
def images(v):  # every params value that names an image file
    if isinstance(v, dict): return [x for w in v.values() for x in images(w)]
    if isinstance(v, list): return [x for w in v for x in images(w)]
    return [v] if isinstance(v, str) and re.search(r"\.(jpe?g|png|webp)$", v, re.I) else []
for s in sb.get("scenes", []):
    for img in images([p.get("params") for p in s.get("parts", [])]):
        if not (assets / img).is_file():
            errs.append(f"scenes.{s['id']}: image {img} is not in {assets}")
names = sorted({p.get("blueprint") for s in sb.get("scenes", []) for p in s.get("parts", [])})
# variety: a Short that repeats one scene type looks like a slideshow
mains = [s["parts"][0].get("blueprint") for s in sb.get("scenes", []) if s.get("parts")]
for i in range(len(mains) - 2):
    if mains[i] == mains[i + 1] == mains[i + 2]:
        errs.append(f"scenes {', '.join(s['id'] for s in sb['scenes'][i:i + 3])}: three scenes in a row open with {mains[i]}; use a different blueprint for one of them")
        break
# a layout counts as its own look (bars compare / versus / forecast differ on screen)
looks = [f"{p['blueprint']} {p['params']['layout']}" if isinstance(p.get("params"), dict) and p["params"].get("layout") else p.get("blueprint")
         for s in sb.get("scenes", []) if s.get("parts") for p in s["parts"][:1]]
for look in sorted(set(looks)):
    if looks.count(look) > 2:
        errs.append(f"{looks.count(look)} scenes open with {look}, max 2; show the others with a different blueprint from the catalogue (a chart, timeline, diagram or measured photo)")
# the first frame decides the swipe: open on a picture, not text on a blank ground
# (statement and question photos are dimmed backdrops, so they still read as a blank frame)
TEXT_ONLY = {"statement", "question", "timeline-years"}
first = (sb.get("scenes") or [{}])[0].get("parts", [{}])[:1]
if first and (first[0].get("blueprint") in TEXT_ONLY or (first[0].get("blueprint") == "tease-three" and not (first[0].get("params") or {}).get("image"))):
    errs.append(f"the hook opens with {first[0]['blueprint']}, which reads as text on a blank frame; open with a photo or diagram blueprint (photo-hook, photo-target, photo-measure, big-number or split with an image, doc, phone, a chart) or tease-three with an `image`")
if re.search(r"\bimg\d", sb.get("credit", "")):
    errs.append(f"credit names image files ({', '.join(sorted(set(re.findall(r'img\d+', sb['credit']))))}); credit each image by its artist or agency and licence, never its file name")
if len(names) < 5:
    errs.append(f"only {len(names)} different blueprints ({', '.join(names)}); use at least 5 so the video keeps changing")
files = {}
for n in names:
    f = next((d / f"{n}.js" for d in (here / "blueprints" / sb.get("lane", ""), here / "blueprints") if (d / f"{n}.js").is_file()), None)
    if f: files[n] = f
    else: errs.append(f"blueprint {n!r} has no file in blueprints/ or blueprints/{sb.get('lane')}/")
if errs:
    sys.exit("compile failed:\n- " + "\n- ".join(errs))

assets.mkdir(exist_ok=True)
(root / "script.json").write_text(json.dumps([{"id": s["id"], "text": s["say"]} for s in sb["scenes"]], indent=1, ensure_ascii=False))
import subprocess
dims = {}
for s in sb["scenes"]:
    for img in images([p.get("params") for p in s.get("parts", [])]):
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(assets / img)], capture_output=True, text=True, check=True).stdout
        dims[img] = [int(n) for n in out.strip().split(",")[:2]]
(root / "storyboard.js").write_text("window.STORYBOARD = " + json.dumps(sb, ensure_ascii=False) + ";\nwindow.IMAGES = " + json.dumps(dims) + "; // [width, height] for focus-point mapping\n")
for f in list(lane.iterdir()) + [here / "lanes" / "gsap.min.js", here / "lanes" / "grain.png", here / "kit.js", here / "driver.js"]:
    shutil.copy(f, assets / f.name)
(assets / "bp").mkdir(exist_ok=True)
for n, f in files.items():
    shutil.copy(f, assets / "bp" / f.name)
for f in ("hyperframes.json", "meta.json", "package.json"):
    if not (root / f).exists():
        shutil.copy(here / "lanes" / f, root / f)
esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;")
html = (here / "shell.html").read_text()
html = html.replace("{{TITLE}}", esc(sb.get("title", root.name)))
timing = root / "timing.js"  # after the voiceover exists, the root carries its length (HyperFrames reads it)
duration = json.loads(timing.read_text()[len("window.TIMING = "):].rstrip().rstrip(";"))["duration"] if timing.exists() else 1
html = html.replace("{{DURATION}}", str(duration))
html = html.replace("{{BLUEPRINTS}}", "\n".join(f'<script src="assets/bp/{f.name}"></script>' for f in files.values()))
(root / "index.html").write_text(html)
print(f"compiled {root}: {len(sb['scenes'])} scenes, blueprints: {', '.join(names)}")
