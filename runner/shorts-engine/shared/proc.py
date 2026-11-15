import subprocess


def sh(*cmd, cwd=None, timeout=1500):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, cwd=cwd, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()
