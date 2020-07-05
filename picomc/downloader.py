import concurrent.futures
import os
import shutil
from concurrent.futures import ThreadPoolExecutor

import certifi
import urllib3
from picomc.env import Env
from picomc.logging import logger
from tqdm import tqdm


def copyfileobj_prog(fsrc, fdst, callback, length=0):
    if not length:
        # COPY_BUFSIZE is undocumented and requires python 3.8
        length = getattr(shutil, "COPY_BUFSIZE", 64*1024)

    fsrc_read = fsrc.read
    fdst_write = fdst.write

    while True:
        buf = fsrc_read(length)
        if not buf:
            break
        fdst_write(buf)
        callback(len(buf))


def downloader_urllib3(q, size=None, workers=16):
    http_pool = urllib3.PoolManager(cert_reqs="CERT_REQUIRED", ca_certs=certifi.where())
    total = len(q)

    have_size = size is not None

    errors = []

    def dl(i, url, dest, sz_callback):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        logger.debug("Downloading [{}/{}]: {}".format(i, total, url))
        resp = http_pool.request("GET", url, preload_content=False)
        if resp.status != 200:
            errors.append(
                "Failed to download ({}) [{}/{}]: {}".format(resp.status, i, total, url)
            )
            resp.release_conn()
            return 0
        with open(dest, "wb") as destfd:
            copyfileobj_prog(resp, destfd, sz_callback)
        resp.release_conn()
        return len(resp.data)

    disable_progressbar = Env.debug

    if have_size:
        cm_progressbar = tqdm(
            total=size,
            disable=disable_progressbar,
            unit_divisor=1024,
            unit="iB",
            unit_scale=True,
        )
    else:
        cm_progressbar = tqdm(total=total, disable=disable_progressbar)

    # XXX: I'm not sure how much of a good idea multithreaded downloading is on slower connections.
    with cm_progressbar as tq, ThreadPoolExecutor(max_workers=workers) as tpe:
        fut_to_url = dict()

        def sz_callback(sz):
            tq.update(sz)

        for i, (url, dest) in enumerate(q, start=1):
            cb = sz_callback if have_size else (lambda x: None)
            fut = tpe.submit(dl, i, url, dest, cb)
            fut_to_url[fut] = url

        for fut in concurrent.futures.as_completed(fut_to_url.keys()):
            try:
                size = fut.result()
            except Exception as ex:
                logger.error(
                    "Exception while downloading {}: {}".format(fut_to_url[fut], ex)
                )
            else:
                if not have_size:
                    tq.update(1)

    for error in errors:
        logger.warn(error)

    return not errors


class DownloadQueue:
    def __init__(self):
        self.q = []
        self.size = 0

    def add(self, url, filename, size=None):
        self.q.append((url, filename))
        if self.size is not None and size is not None:
            self.size += size
        else:
            self.size = None

    def __len__(self):
        return len(self.q)

    def download(self):
        if not self.q:
            return True
        else:
            logger.debug("Using parallel urllib3 downloader.")
            downloader = downloader_urllib3
        return downloader(self.q, size=self.size)
