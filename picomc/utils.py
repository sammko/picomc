import hashlib
import json
import logging
import os
import sys
from functools import partial

from picomc.globals import APP_ROOT

logger = logging.getLogger("picomc.cli")


def get_filepath(*f):
    return os.path.join(APP_ROOT, *f)


def check_directories():
    """Create directory structure for the application."""
    dirs = ['', 'instances', 'versions', 'assets', 'assets/indexes',
            'assets/objects', 'assets/virtual', 'libraries']
    for d in dirs:
        path = os.path.join(APP_ROOT, *d.split('/'))
        logger.debug("Creating dir: {}".format(path))
        os.makedirs(path, exist_ok=True)


PLATFORM_MAP = {
    'darwin': 'osx',
    'win32': 'windows',
    'cygwin': 'windows',
    'linux': 'linux'
}


def get_platform():
    return PLATFORM_MAP[sys.platform]


def file_sha1(filename):
    h = hashlib.sha1()
    with open(filename, 'rb', buffering=0) as f:
        for b in iter(partial(f.read, 128*1024), b''):
            h.update(b)
    return h.hexdigest()


class PersistentObject(object):
    def __enter__(self):
        self.filename = os.path.join(APP_ROOT, self.CONFIG_FILE)
        self._load()
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        self._save()

    def _load(self):
        logger.debug("Loading {}.".format(self))
        try:
            with open(self.filename, 'r') as json_file:
                self.data.update(json.load(json_file))
        except FileNotFoundError:
            pass

    def _save(self):
        logger.debug("Saving {}.".format(self))
        os.makedirs(os.path.dirname(self.filename),
                    exist_ok=True)
        with open(self.filename, 'w') as json_file:
            json.dump(self.data, json_file)
