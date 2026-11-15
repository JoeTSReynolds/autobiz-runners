# proc.sh: run a command, return (code, stdout+stderr). Run: python3 shared/test_proc.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import proc  # noqa: E402

seen = []
class R:
    returncode, stdout, stderr = 3, ' out\n', 'err \n'
proc.subprocess.run = lambda cmd, **kw: seen.append((cmd, kw)) or R()
assert proc.sh('ls', Path('/x'), 5, cwd='/tmp', timeout=9) == (3, 'out\nerr'), 'joins and strips stdout+stderr'
assert seen[-1] == (['ls', '/x', '5'], dict(capture_output=True, text=True, cwd='/tmp', timeout=9)), seen
proc.sh('ls')
assert seen[-1][1]['cwd'] is None and seen[-1][1]['timeout'] == 1500, seen
print('ok')
