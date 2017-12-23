import hashlib
import json
import os
from functools import partial

from picomc.globals import APP_ROOT
from picomc.logging import logger


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
    return os.pathsep.join(cp)


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


def write_profiles_dummy():
    # This file makes the forge installer happy.
    fname = get_filepath('launcher_profiles.json')
    with open(fname, 'w') as fd:
        fd.write(r'{"profiles":{}}')


def file_sha1(filename):
    h = hashlib.sha1()
    with open(filename, 'rb', buffering=0) as f:
        for b in iter(partial(f.read, 128 * 1024), b''):
            h.update(b)
    return h.hexdigest()


class ConfigLoader:
    def __init__(self, config_file, defaults={}, dict_impl=dict):
        self.filename = os.path.join(APP_ROOT, config_file)
        self.dict_impl = dict_impl
        self.data = dict_impl(defaults)

    def __enter__(self):
        self._load()
        return self.data

    def __exit__(self, ext_type, exc_value, traceback):
        self._save()

    def _load(self):
        logger.debug("Loading Config from {}.".format(self.filename))
        try:
            with open(self.filename, 'r') as json_file:
                self.data.update(
                    json.load(
                        json_file, object_hook=lambda d: self.dict_impl(d)))
        except FileNotFoundError:
            pass

    def _save(self):
        logger.debug("Saving Config to {}.".format(self.filename))
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, 'w') as json_file:
            json.dump(self.data, json_file, indent=4)
