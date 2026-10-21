# Story candidates for a lane: fetch its feeds, keep recent items, merge the same story across feeds,
# drop anything already covered. Writes <out>/candidates.json.
# Usage: python3 feeds.py <lane> <out-dir> [--hours 72] [--covered state/covered.json]
import email.utils, json, re, sys, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

here = Path(__file__).parent
lane, out = sys.argv[1], Path(sys.argv[2])
hours = int(sys.argv[sys.argv.index("--hours") + 1]) if "--hours" in sys.argv else 72
covered_path = Path(sys.argv[sys.argv.index("--covered") + 1]) if "--covered" in sys.argv else None
cfg = json.loads((here / "lanes" / lane / "lane.json").read_text())
UA = {"User-Agent": "Mozilla/5.0 (compatible; autobiz-newsroom/0.1)"}
STOP = set("a an the of to in on for and or with at by from as is are was be new its it this that how why what".split())


def text(el, *names):
    for n in names:
        x = el.find(n)
        if x is not None and (x.text or x.get("href")):
            return (x.text or x.get("href") or "").strip()
    return ""


def when(s):
    if not s:
        return None
    try:
        return email.utils.parsedate_to_datetime(s).astimezone(timezone.utc)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None


def fetch(feed):
    with urllib.request.urlopen(urllib.request.Request(feed["url"], headers=UA), timeout=30) as r:
        root = ET.fromstring(r.read())
    atom = "{http://www.w3.org/2005/Atom}"
    items = root.findall(".//item") or root.findall(f".//{atom}entry")
    for it in items:
        title = re.sub(r"\s+", " ", text(it, "title", f"{atom}title"))
        link = text(it, "link", f"{atom}link")
        summary = re.sub(r"<[^>]+>", " ", text(it, "description", f"{atom}summary", f"{atom}content"))
        yield {"title": title, "url": link, "summary": re.sub(r"\s+", " ", summary).strip()[:400],
               "published": when(text(it, "pubDate", f"{atom}published", f"{atom}updated")), "feed": feed["id"], "primary": feed.get("primary", False)}


def words(t):
    return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in STOP and len(w) > 2}


now, items, errors = datetime.now(timezone.utc), [], []
for f in cfg["feeds"]:
    try:
        items += [i for i in fetch(f) if i["title"] and i["url"] and i["published"] and now - i["published"] < timedelta(hours=hours)]
    except Exception as e:  # one dead feed must not stop the lane
        errors.append(f"{f['id']}: {e}")
covered = json.loads(covered_path.read_text()) if covered_path and covered_path.exists() else []
seen_urls, seen_titles = {c["url"] for c in covered}, [words(c["title"]) for c in covered]
clusters = []
for it in sorted(items, key=lambda i: i["published"], reverse=True):
    w = words(it["title"])
    if it["url"] in seen_urls or any(len(w & s) / max(1, len(w | s)) >= 0.5 for s in seen_titles):
        continue  # already covered
    for c in clusters:  # same story from another feed: merge
        if len(w & c["_w"]) / max(1, len(w | c["_w"])) >= 0.45:
            c["sources"].append({"feed": it["feed"], "url": it["url"], "title": it["title"]})
            c["primary"] = c["primary"] or it["primary"]
            break
    else:
        clusters.append({"id": f"c{len(clusters) + 1}", "title": it["title"], "summary": it["summary"], "published": it["published"].isoformat(),
                         "primary": it["primary"], "sources": [{"feed": it["feed"], "url": it["url"], "title": it["title"]}], "_w": w})
for c in clusters:
    del c["_w"]
out.mkdir(parents=True, exist_ok=True)
(out / "candidates.json").write_text(json.dumps({"lane": lane, "fetched": now.isoformat(), "feed_errors": errors, "candidates": clusters[:40]}, indent=1, ensure_ascii=False))
print(f"{lane}: {len(items)} recent items -> {len(clusters)} stories ({min(40, len(clusters))} kept); feed errors: {errors or 'none'}")
