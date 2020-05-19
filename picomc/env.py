import os
import sys
from contextlib import ExitStack
from os.path import expanduser, join


# This is not the best design, but passing these around is too much of a hassle.
# I considered singletons for the Managers, but I would still have to keep
# this for the other stuff. ¯\_(ツ)_/¯
# Better than the weirdo proxies I had before, not sure what I was thinking then.
class Env:
    am = None
    vm = None
    estack: ExitStack
    gconf: dict
    app_root: str
    platform: str
    debug: bool


def get_filepath(*f):
    return os.path.join(Env.app_root, *f)


def get_default_java():
    # This is probably the most friendly thing we can do short of detecting
    # java installations in various places depending on platform.
    # Having gained some experience, java is usually found in the PATH on
    # all three supported platforms, so this is no problem at all.
    return "java"


def get_default_root():
    MAP = {
        "linux": lambda: expanduser("~/.local/share/picomc"),
        "win32": lambda: join(os.getenv("APPDATA"), ".picomc"),
        "darwin": lambda: expanduser("~/Library/Application Support/picomc"),
    }
    if sys.platform in MAP:
        return MAP[sys.platform]()
    else:
        # This is probably better than nothing and should be fine on most
        # widely-used platforms other than the supported ones. Too bad in
        # case of something exotic. Minecraft doesn't run on those anyway.
        return expanduser("~/.picomc")


try:
    PLATFORM_MAP = {"darwin": "osx", "win32": "windows", "linux": "linux"}
    Env.platform = PLATFORM_MAP[sys.platform]
except KeyError:
    # This is probably not neccesary, as the game is not officialy supported
    # on other platforms and natives are not available. (Unless you compile
    # them and patch the corresponding version json)
    Env.platform = sys.platform
