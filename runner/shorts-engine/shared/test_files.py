# files.jread: parsed JSON of a file, or the default when it does not exist. Run: python3 shared/test_files.py
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import files  # noqa: E402

d = Path(tempfile.mkdtemp())
(d / 'a.json').write_text('{"k": [1]}')
assert files.jread(d / 'a.json') == {'k': [1]}
assert files.jread(str(d / 'a.json'), []) == {'k': [1]}, 'str paths work'
assert files.jread(d / 'none.json') is None
assert files.jread(d / 'none.json', {}) == {}
(d / 'bad.json').write_text('{')
try: files.jread(d / 'bad.json')
except ValueError: pass
else: raise AssertionError('corrupt JSON must raise')
print('ok')
