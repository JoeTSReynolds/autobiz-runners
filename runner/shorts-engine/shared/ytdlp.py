"""Every yt-dlp call in the engine goes through run(). It adds the spare account's cookies when YTDLP_COOKIES_FILE is set, and
when YouTube blocks this address (HTTP 429, bot check) it runs AUTOBIZ_NETWORK_RESET_COMMAND for a fresh address and tries again."""
import os, re, subprocess

BLOCKED = re.compile(r"HTTP Error 429|confirm you.re not a bot")
RESETS = 2  # per call: a new address can land on another blocked one, so allow one more


def _reset(cmd):
    try: subprocess.run(['bash', '-c', cmd], capture_output=True, timeout=120)  # captured: stage stdout is the result JSON
    except (OSError, subprocess.TimeoutExpired): pass  # a failed reset must not stop the retry that follows


# shortcut: YouTube's 2026-11-23 player breaks the n challenge for signed-in requests (yt-dlp#18123); remove once a stable yt-dlp after
# 2026.10.26 is pinned. Same rule as signedInArgs in apps/server/src/tools.ts: a second youtube extractor-args would replace this one, so merge.
def _tv_variant(args):
    i = next((k for k, a in enumerate(args[:-1]) if a == '--extractor-args' and args[k + 1].startswith('youtube:')), None)
    if i is None: return ['--extractor-args', 'youtube:player_js_variant=tv', *args]
    args[i + 1] = 'youtube:player_js_variant=tv;' + args[i + 1][len('youtube:'):]
    return args


def run(args, **kw):
    """subprocess.run(['yt-dlp', *args], **kw), retried from a fresh address when blocked."""
    cookies = os.environ.get('YTDLP_COOKIES_FILE')
    if cookies or '--cookies' in args: args = _tv_variant(list(args))
    cmd = ['yt-dlp', *(['--cookies', cookies] if cookies and '--cookies' not in args else []), *args]  # signed-in spare account
    reset = os.environ.get('AUTOBIZ_NETWORK_RESET_COMMAND')
    for attempt in range(RESETS + 1):
        r = subprocess.run(cmd, **kw)
        if not reset or attempt == RESETS or not (r.returncode and isinstance(r.stderr, str) and BLOCKED.search(r.stderr)): return r
        _reset(reset)
