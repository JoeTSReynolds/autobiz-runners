"""subprocess.run for the kit; yt-dlp calls get the spare account's cookies when YTDLP_COOKIES_FILE is set."""
import os, subprocess


def run(cmd, **kw):
    cookies = os.environ.get('YTDLP_COOKIES_FILE')
    if cmd and cmd[0] == 'yt-dlp' and cookies and '--cookies' not in cmd:
        cmd = [cmd[0], '--cookies', cookies, *cmd[1:]]  # signed-in spare account gets past 429s / bot checks
    return subprocess.run(cmd, **kw)
