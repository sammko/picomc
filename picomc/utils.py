import hashlib
import os
import sys
from functools import partial

from picomc.logging import logger


def join_classpath(*cp):
    return os.pathsep.join(cp)


def file_sha1(filename):
    h = hashlib.sha1()
    with open(filename, "rb", buffering=0) as f:
        for b in iter(partial(f.read, 128 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def die(mesg, code=1):
    logger.error(mesg)
    sys.exit(code)


def sanitize_name(name):
    return name.replace("..", "_").replace("/", "_")


def recur_files(path):
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            yield os.path.join(dirpath, f)
