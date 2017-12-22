import os
import shutil
import subprocess
import urllib

from picomc.logging import logger


def check_aria2():
    try:
        subprocess.run(
            "aria2c --version".split(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False


def downloader_aria2(q, d):
    p = subprocess.Popen(
        '/usr/bin/aria2c -i - -j8 --dir'.split() + [d],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    L = []
    for url, outs in q:
        L.append("{}\n out={}".format(url, outs[0]))
    out, err = p.communicate("\n".join(L).encode())
    if p.returncode:
        print(out.decode(), err.decode())
        raise RuntimeError("Failed to download files.")
    else:
        for url, outs in q:
            src = os.path.join(d, outs[0])
            for o in outs[1:]:
                dst = os.path.join(d, o)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy(src, dst)


def downloader_urllib(q, d):
    # Dumb and slow.
    for url, outs in q:
        aouts = list(os.path.join(d, o) for o in outs)
        for o in aouts:
            os.makedirs(os.path.dirname(o), exist_ok=True)
        pout, *eouts = aouts
        urllib.request.urlretrieve(url, pout)
        for o in eouts:
            shutil.copy(pout, o)


class DownloadQueue:
    def __init__(self):
        self.q = []

    def add(self, url, *filename):
        self.q.append((url, filename))

    def download(self, d):
        if not self.q:
            return
        if check_aria2():
            logger.info("Using aria2 downloader.")
            downloader = downloader_aria2
        else:
            logger.info("Using urllib downloader.")
            downloader = downloader_urllib
        downloader(self.q, d)
