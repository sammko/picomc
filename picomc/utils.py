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


PLATFORM_MAP = {
    'darwin': 'osx',
    'win32': 'windows',
    'linux': 'linux'
}


def get_platform():
    return PLATFORM_MAP[sys.platform]


def file_sha1(filename):
    h = hashlib.sha1()
    with open(filename, 'rb', buffering=0) as f:
        for b in iter(partial(f.read, 128 * 1024), b''):
            h.update(b)
    return h.hexdigest()


class PersistentConfig:
    def __init__(self, config_file, defaults):
        self._filename = os.path.join(APP_ROOT, config_file)
        self.__dict__.update(defaults)

    def __enter__(self):
        self.__load()
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        self.__save()

    def __load(self):
        logger.debug("Loading {}.".format(self))
        try:
            with open(self._filename, 'r') as json_file:
                self.__dict__.update(json.load(json_file))
        except FileNotFoundError:
            pass

    def __save(self):
        logger.debug("Saving {}.".format(self))
        os.makedirs(os.path.dirname(self._filename), exist_ok=True)
        with open(self._filename, 'w') as json_file:
            json.dump(
                {
                    k: v
                    for k, v in self.__dict__.items() if not k.startswith('_')
                },
                json_file,
                indent=4)
