import os
import sys
from functools import partial
from os.path import expanduser, join

from picomc.proxy import Proxy

APP_ROOT = {
    'linux': lambda: expanduser('~/.local/share/picomc'),
    'win32': lambda: join(os.getenv('APPDATA'), '.picomc'),
    'darwin': lambda: expanduser('~/Library/Application Support/picomc')
}[sys.platform]()

try:
    PLATFORM_MAP = {'darwin': 'osx', 'win32': 'windows', 'linux': 'linux'}
    platform = PLATFORM_MAP[sys.platform]
except KeyError:
    # This is probably not neccesary, as the game is not officialy supported
    # on other platforms and natives are not available. (Unless you compile
    # them and patch the corresponding version json)
    platform = sys.platform


def get_default_java():
    # FIXME. This is just a placeholder.
    return "java"


class Ptr:
    _a = None

    def get(self):
        return self._a

    def set(self, v):
        self._a = v


_ctx_ptr = Ptr()


def _get_object(name):
    ctx = _ctx_ptr.get()
    if ctx is None:
        raise RuntimeError("No context available.")
    r = getattr(ctx, name)
    return r


ctx = Proxy(_ctx_ptr.get)
am = Proxy(partial(_get_object, "am"))
vm = Proxy(partial(_get_object, "vm"))
gconf = Proxy(partial(_get_object, "gconf"))
