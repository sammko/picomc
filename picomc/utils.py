import hashlib
import json
import logging
import os
import sys
from functools import partial

from picomc.globals import APP_ROOT

logger = logging.getLogger("picomc.cli")


class cached_property(object):
    def __init__(self, fn):
        self.fn = fn

    def __get__(self, inst, cls):
        if inst is None:
            return self
        r = self.fn(inst)
        setattr(inst, self.fn.__name__, r)
        return r


def get_filepath(*f):
    return os.path.join(APP_ROOT, *f)


def join_classpath(*cp):
    sep = ';' if (sys.platform == 'win32') else ':'
    return sep.join(cp)


def check_directories():
    """Create directory structure for the application."""
    dirs = [
        '', 'instances', 'versions', 'assets', 'assets/indexes',
        'assets/objects', 'assets/virtual', 'libraries'
    ]
    for d in dirs:
        path = os.path.join(APP_ROOT, *d.split('/'))
        try:
            os.makedirs(path)
            logger.debug("Created dir: {}".format(path))
        except FileExistsError:
            pass


def file_sha1(filename):
    h = hashlib.sha1()
    with open(filename, 'rb', buffering=0) as f:
        for b in iter(partial(f.read, 128 * 1024), b''):
            h.update(b)
    return h.hexdigest()


class PersistentConfig:
    def __init__(self, config_file, defaults={}):
        self._filename = os.path.join(APP_ROOT, config_file)
        self.__dict__.update(defaults)

    def __enter__(self):
        self.__load()
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        self.__save()

    # Maybe we should somehow subclass a dict instead of re-implementing these?
    def __iter__(self):
        return (n for n in self.__dict__ if not n.startswith('_'))

    def keys(self):
        return self.__iter__()

    def items(self):
        for k, v in self.__dict__.items():
            if not k.startswith('_'):
                yield (k, v)

    def values(self):
        return (v for k, v in self.items())

    def get(self, *args, **kwargs):
        return self.__dict__.get(*args, **kwargs)

    def __load(self):
        logger.debug("Loading Config from {}.".format(self._filename))
        try:
            with open(self._filename, 'r') as json_file:
                self.__dict__.update(json.load(json_file))
        except FileNotFoundError:
            pass

    def __save(self):
        logger.debug("Saving Config to {}.".format(self._filename))
        os.makedirs(os.path.dirname(self._filename), exist_ok=True)
        with open(self._filename, 'w') as json_file:
            json.dump(
                {
                    k: v
                    for k, v in self.__dict__.items() if not k.startswith('_')
                },
                json_file,
                indent=4)
