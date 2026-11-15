"""Every yt-dlp call in the engine goes through run(). It adds the spare account's cookies when YTDLP_COOKIES_FILE is set, and
when YouTube blocks this address (HTTP 429, bot check) it runs AUTOBIZ_NETWORK_RESET_COMMAND for a fresh address and tries again."""
import os, re, subprocess

BLOCKED = re.compile(r"HTTP Error 429|confirm you.re not a bot")
RESETS = 2  # per call: a new address can land on another blocked one, so allow one more


def _reset(cmd):
    try: subprocess.run(['bash', '-c', cmd], capture_output=True, timeout=120)  # captured: stage stdout is the result JSON
    except (OSError, subprocess.TimeoutExpired): pass  # a failed reset must not stop the retry that follows


def run(args, **kw):
    """subprocess.run(['yt-dlp', *args], **kw), retried from a fresh address when blocked."""
    cookies = os.environ.get('YTDLP_COOKIES_FILE')
    cmd = ['yt-dlp', *(['--cookies', cookies] if cookies and '--cookies' not in args else []), *args]  # signed-in spare account
    reset = os.environ.get('AUTOBIZ_NETWORK_RESET_COMMAND')
    for attempt in range(RESETS + 1):
        r = subprocess.run(cmd, **kw)
        if not reset or attempt == RESETS or not (r.returncode and isinstance(r.stderr, str) and BLOCKED.search(r.stderr)): return r
        _reset(reset)
