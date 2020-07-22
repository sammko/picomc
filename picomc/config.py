import json
import os
from contextlib import AbstractContextManager

from picomc.logging import logger
from picomc.utils import cached_property


def get_default_config():
    return {
        "java.path": "java",
        "java.memory.min": "512M",
        "java.memory.max": "2G",
        "java.jvmargs": "-XX:+UnlockExperimentalVMOptions -XX:+UseG1GC -XX:G1NewSizePercent=20 -XX:G1ReservePercent=20 -XX:MaxGCPauseMillis=50 -XX:G1HeapRegionSize=32M",
    }


class ConfigManager(AbstractContextManager):
    def __init__(self, root):
        self.configs = dict()
        self.root = root

    @cached_property
    def global_config(self):
        return self.get("config.json", bottom=get_default_config())

    def __exit__(self, type, value, traceback):
        self.commit_all_dirty()

    def get(self, path, bottom={}, init={}):
        abspath = os.path.join(self.root, path)
        if abspath in self.configs:
            return self.configs[abspath]
        conf = Config(abspath, bottom=bottom, init=init)
        self.configs[abspath] = conf
        return conf

    def get_instance_config(self, path):
        return self.get(path, bottom=self.global_config)

    def commit_all_dirty(self):
        logger.debug("Commiting all dirty configs")
        for conf in self.configs.values():
            conf.save_if_dirty()


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
        self.filepath = config_file
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
