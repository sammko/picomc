import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import certifi
import urllib3

from picomc.logging import logger


def check_aria2():
    try:
        subprocess.run(
            "aria2c --version".split(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except FileNotFoundError:
        return False


def downloader_aria2(q, d):
    p = subprocess.Popen(
        "/usr/bin/aria2c -i - -j8 --dir".split() + [d],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
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


def downloader_urllib3(q, d, workers=8):
    http_pool = urllib3.PoolManager(cert_reqs="CERT_REQUIRED", ca_certs=certifi.where())
    total = len(q)

    def dl(i, url, outs):
        aouts = list(os.path.join(d, o) for o in outs)
        for o in aouts:
            os.makedirs(os.path.dirname(o), exist_ok=True)
        pout, *eouts = aouts
        logger.debug("Downloading [{}/{}]: {}".format(i, total, url))
        resp = http_pool.request("GET", url, preload_content=False)
        with open(pout, "wb") as poutfd:
            shutil.copyfileobj(resp, poutfd)
        resp.release_conn()
        for o in eouts:
            shutil.copy(pout, o)

    # XXX: I'm not sure how much of a good idea this is on slower connections.
    with ThreadPoolExecutor(max_workers=workers) as tpe:
        for i, (url, outs) in enumerate(q, start=1):
            tpe.submit(dl, i, url, outs)


class DownloadQueue:
    def __init__(self):
        self.q = []

    def add(self, url, *filename):
        self.q.append((url, filename))

    def download(self, d):
        if not self.q:
            return
        if False and check_aria2():  # XXX: Disabled
            logger.info("Using aria2 downloader.")
            downloader = downloader_aria2
        else:
            logger.info("Using parallel urllib3 downloader.")
            downloader = downloader_urllib3
        downloader(self.q, d)
