import os
import shutil
from concurrent.futures import ThreadPoolExecutor

import certifi
import urllib3
from picomc.env import Env
from picomc.logging import logger
from tqdm import tqdm


def downloader_urllib3(q, basedir, workers=8):
    http_pool = urllib3.PoolManager(cert_reqs="CERT_REQUIRED", ca_certs=certifi.where())
    total = len(q)

    errors = []

    def dl(i, url, reldest):
        dest = os.path.join(basedir, reldest)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        logger.debug("Downloading [{}/{}]: {}".format(i, total, url))
        resp = http_pool.request("GET", url, preload_content=False)
        if resp.status != 200:
            errors.append(
                "Failed to download ({}) [{}/{}]: {}".format(resp.status, i, total, url)
            )
            resp.release_conn()
            return
        with open(dest, "wb") as destfd:
            shutil.copyfileobj(resp, destfd)
        resp.release_conn()

    disable_progressbar = Env.debug

    # XXX: I'm not sure how much of a good idea multithreaded downloading is on slower connections.
    with tqdm(total=total, disable=disable_progressbar) as tq, ThreadPoolExecutor(
        max_workers=workers
    ) as tpe:

        def done(fut):
            tq.update()

        for i, (url, dest) in enumerate(q, start=1):
            fut = tpe.submit(dl, i, url, dest)
            fut.add_done_callback(done)

    for error in errors:
        logger.warn(error)

    return not errors


class DownloadQueue:
    def __init__(self):
        self.q = []

    def add(self, url, filename):
        self.q.append((url, filename))

    def __len__(self):
        return len(self.q)

    def download(self, d):
        if not self.q:
            return True
        else:
            logger.debug("Using parallel urllib3 downloader.")
            downloader = downloader_urllib3
        return downloader(self.q, d)
