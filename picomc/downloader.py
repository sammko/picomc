import concurrent.futures
import os
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import certifi
import urllib3
from picomc.env import Env
from picomc.logging import logger
from tqdm import tqdm


def copyfileobj_prog(fsrc, fdst, callback, stop_event, length=0):
    if not length:
        # COPY_BUFSIZE is undocumented and requires python 3.8
        length = getattr(shutil, "COPY_BUFSIZE", 64 * 1024)

    fsrc_read = fsrc.read
    fdst_write = fdst.write

    while True:
        if stop_event.is_set():
            raise InterruptedError
        buf = fsrc_read(length)
        if not buf:
            break
        fdst_write(buf)
        callback(len(buf))


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


def downloader_urllib3(q, size=None, workers=16):
    http_pool = urllib3.PoolManager(cert_reqs="CERT_REQUIRED", ca_certs=certifi.where())
    total = len(q)
    logger.debug("Downloading {} files.".format(total))
    have_size = size is not None
    errors = []
    had_error = False

    def dl_file(i, url, dest, sz_callback, stop_event):
        # In case the task could not be cancelled
        if stop_event.is_set():
            raise InterruptedError
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        logger.debug("Downloading [{}/{}]: {}".format(i, total, url))
        resp = http_pool.request("GET", url, preload_content=False)
        if resp.status != 200:
            errors.append(
                "Failed to download ({}) [{}/{}]: {}".format(resp.status, i, total, url)
            )
            resp.release_conn()
            return 0
        with DlTempFile(dir=os.path.dirname(dest), delete=False) as tempf:
            copyfileobj_prog(resp, tempf, sz_callback, stop_event)
            tempf.close()
            os.replace(tempf.name, dest)
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

    with cm_progressbar as tq, ThreadPoolExecutor(max_workers=workers) as tpe:
        fut_to_url = dict()
        stop_event = threading.Event()

        def sz_callback(sz):
            tq.update(sz)

        for i, (url, dest) in enumerate(q, start=1):
            cb = sz_callback if have_size else (lambda x: None)
            fut = tpe.submit(dl_file, i, url, dest, cb, stop_event)
            fut_to_url[fut] = url

        try:
            for fut in concurrent.futures.as_completed(fut_to_url.keys()):
                try:
                    size = fut.result()
                except Exception as ex:
                    logger.error(
                        "Exception while downloading {}: {}".format(fut_to_url[fut], ex)
                    )
                    had_error = True
                else:
                    if not have_size:
                        tq.update(1)
                    # if we have size, the progress bar was already updated
                    # from within the thread
        except KeyboardInterrupt as ex:
            tq.close()
            logger.warn("Stopping downloader threads.")
            stop_event.set()
            tpe.shutdown()
            for fut in fut_to_url:
                fut.cancel()
            raise ex from None

    # Do this at the end in order to not break the progress bar.
    for error in errors:
        logger.warn(error)

    return not errors and not had_error


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
        return downloader_urllib3(self.q, size=self.size)
