import concurrent.futures
import os
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import certifi
import urllib3
from tqdm import tqdm

import picomc.logging
from picomc.logging import logger


@contextmanager
def DlTempFile(*args, default_mode=0o666, try_delete=True, **kwargs):
    """A NamedTemporaryFile which is created with permissions as per
    the current umask. It is removed after exiting the context manager,
    but only if it stil exists."""
    if kwargs.get("delete", False):
        raise ValueError("delete must be False")
    kwargs["delete"] = False
    f = tempfile.NamedTemporaryFile(*args, **kwargs)
    umask = os.umask(0)
    os.umask(umask)
    os.chmod(f.name, default_mode & ~umask)
    try:
        with f as uf:
            yield uf
    finally:
        if os.path.exists(f.name):
            os.unlink(f.name)


class Downloader:
    def __init__(self, queue, total_size=None, workers=16):
        self.queue = queue
        self.total = len(queue)
        self.known_size = total_size is not None
        if self.known_size:
            self.total_size = total_size
        self.errors = list()
        self.workers = workers
        self.fut_to_url = dict()
        self.http_pool = urllib3.PoolManager(
            cert_reqs="CERT_REQUIRED", ca_certs=certifi.where()
        )
        self.stop_event = threading.Event()

    def copyfileobj_prog(self, fsrc, fdst, callback, length=0):
        if not length:
            # COPY_BUFSIZE is undocumented and requires python 3.8
            length = getattr(shutil, "COPY_BUFSIZE", 64 * 1024)

        fsrc_read = fsrc.read
        fdst_write = fdst.write

        while True:
            if self.stop_event.is_set():
                raise InterruptedError
            buf = fsrc_read(length)
            if not buf:
                break
            fdst_write(buf)
            callback(len(buf))

    def download_file(self, i, url, dest, sz_callback):
        # In case the task could not be cancelled
        if self.stop_event.is_set():
            raise InterruptedError
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        logger.debug("Downloading [{}/{}]: {}".format(i, self.total, url))
        resp = self.http_pool.request("GET", url, preload_content=False)
        if resp.status != 200:
            self.errors.append(
                "Failed to download ({}) [{}/{}]: {}".format(
                    resp.status, i, self.total, url
                )
            )
            resp.release_conn()
            return
        with DlTempFile(dir=os.path.dirname(dest), delete=False) as tempf:
            self.copyfileobj_prog(resp, tempf, sz_callback)
            tempf.close()
            os.replace(tempf.name, dest)
        resp.release_conn()

    def reap_future(self, future, tq):
        try:
            future.result()
        except Exception as ex:
            msg = f"Exception while downloading {self.fut_to_url[future]}: {ex}"
            self.errors.append(msg)
        else:
            if not self.known_size:
                tq.update(1)
            # if we have size, the progress bar was already updated
            # from within the thread

    def cancel(self, tq, tpe):
        tq.close()
        logger.warning("Stopping downloader threads.")
        self.stop_event.set()
        tpe.shutdown()
        for fut in self.fut_to_url:
            fut.cancel()

    def download(self):
        logger.debug("Downloading {} files.".format(self.total))
        disable_progressbar = picomc.logging.debug

        if self.known_size:
            cm_progressbar = tqdm(
                total=self.total_size,
                disable=disable_progressbar,
                unit_divisor=1024,
                unit="iB",
                unit_scale=True,
            )
        else:
            cm_progressbar = tqdm(total=self.total, disable=disable_progressbar)

        with cm_progressbar as tq, ThreadPoolExecutor(max_workers=self.workers) as tpe:
            for i, (url, dest) in enumerate(self.queue, start=1):
                cb = tq.update if self.known_size else (lambda x: None)
                fut = tpe.submit(self.download_file, i, url, dest, cb)
                self.fut_to_url[fut] = url

            try:
                for fut in concurrent.futures.as_completed(self.fut_to_url.keys()):
                    self.reap_future(fut, tq)
            except KeyboardInterrupt as ex:
                self.cancel(tq, tpe)
                raise ex from None

        # Do this at the end in order to not break the progress bar.
        for error in self.errors:
            logger.error(error)

        return not self.errors


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
        return Downloader(self.q, total_size=self.size).download()
