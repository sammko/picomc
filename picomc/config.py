import json
import os

from picomc.env import get_filepath
from picomc.logging import logger


class CommitManager:
    def __init__(self):
        self.configs = dict()

    def add(self, config):
        self.configs[id(config)] = config

    def remove(self, config):
        del self.configs[id(config)]

    def commit_all_dirty(self):
        logger.debug("Commiting all dirty configs")
        for _, conf in self.configs.items():
            conf.save_if_dirty()

    def commit_all(self):
        logger.debug("Commiting all configs")
        for _, conf in self.configs.items():
            conf.save()


class OverlayDict(dict):
    def __init__(self, bottom={}, init={}):
        super().__init__(**init)
        self.bottom = bottom

    # By default get does not call __missing__ but immediately returns default.
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __missing__(self, key):
        return self.bottom[key]

    def __repr__(self):
        return "{}[{}]".format(super().__repr__(), repr(self.bottom))


class Config(OverlayDict):
    def __init__(self, config_file, bottom={}, init={}):
        super().__init__(init=init, bottom=bottom)
        self.filepath = get_filepath(config_file)
        self.dirty = not self.load()

    # TODO This way of detecting dirtyness is not good enough, as for example
    # a dict within the config can be modified (account config is not flat)
    # Not sure what to do about this

    def __setitem__(self, key, value):
        self.dirty = True
        super().__setitem__(key, value)

    def __delitem__(self, key):
        self.dirty = True
        return super().__delitem__(key)

    # The update, setdefault and clear implementations are necessary, because
    # the builtins do not call __setitem__ (__delitem__) thereforce would not trip the
    # dirty flag.

    def clear(self):
        self.dirty = True
        return super().clear()

    def update(self, *args, **kwargs):
        # This has false positives, but who cares
        self.dirty = True
        super().update(*args, **kwargs)

    def setdefault(self, key, value=None):
        if key not in self:
            self.dirty = True
            self[key] = value
        return self[key]

    def load(self):
        logger.debug("Loading Config from {}".format(self.filepath))
        try:
            with open(self.filepath, "r") as fd:
                data = json.load(fd)
                self.clear()
                self.update(data)
                return True
        except FileNotFoundError:
            return False

    def save(self):
        logger.debug("Writing Config to {}".format(self.filepath))
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, "w") as fd:
            json.dump(self, fd, indent=4)

    def save_if_dirty(self):
        if self.dirty:
            self.save()
            self.dirty = False
