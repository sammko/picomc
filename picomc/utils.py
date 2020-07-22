import hashlib
import os
import sys
from enum import Enum, auto
from functools import partial
from pathlib import Path

from picomc.logging import logger


def join_classpath(*cp):
    return os.pathsep.join(map(str, cp))


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


def recur_files(path: Path):
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            yield Path(dirpath) / f


class Directory(Enum):
    ASSETS = auto()
    ASSET_INDEXES = auto()
    ASSET_OBJECTS = auto()
    ASSET_VIRTUAL = auto()
    INSTANCES = auto()
    LIBRARIES = auto()
    VERSIONS = auto()


class CachedProperty:
    def __init__(self, fn):
        self.fn = fn

    def __get__(self, obj, cls):
        if obj is None:
            return self
        value = obj.__dict__[self.fn.__name__] = self.fn(obj)
        return value


cached_property = CachedProperty
