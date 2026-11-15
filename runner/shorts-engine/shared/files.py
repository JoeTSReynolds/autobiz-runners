import json
from pathlib import Path


def jread(p, default=None):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else default
