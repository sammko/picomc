import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import certifi
import urllib3
from picomc.env import Env
from picomc.logging import logger
from tqdm import tqdm


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

    disable_progressbar = Env.debug

    # XXX: I'm not sure how much of a good idea multithreaded downloading is on slower connections.
    with tqdm(total=total, disable=disable_progressbar) as tq, ThreadPoolExecutor(
        max_workers=workers
    ) as tpe:

        def done(fut):
            tq.update()

        for i, (url, outs) in enumerate(q, start=1):
            fut = tpe.submit(dl, i, url, outs)
            fut.add_done_callback(done)


class DownloadQueue:
    def __init__(self):
        self.q = []

    def add(self, url, *filename):
        self.q.append((url, filename))

    def __len__(self):
        return len(self.q)

    def download(self, d):
        if not self.q:
            return
        else:
            logger.info("Using parallel urllib3 downloader.")
            downloader = downloader_urllib3
        downloader(self.q, d)
