import os
import sys
from contextlib import ExitStack
from os.path import expanduser, join

from picomc.javainfo import get_java_info, get_java_version
from picomc.logging import logger
from picomc.utils import die, file_sha1


# This is not the best design, but passing these around is too much of a hassle.
# I considered singletons for the Managers, but I would still have to keep
# this for the other stuff. ¯\_(ツ)_/¯
# Better than the weirdo proxies I had before, not sure what I was thinking then.
class Env:
    am = None
    vm = None
    commit_manager = None
    estack: ExitStack
    gconf: dict
    app_root: str
    platform: str
    debug: bool


def get_filepath(*f):
    root = os.path.normpath(Env.app_root)
    res = os.path.normpath(os.path.join(root, *f))
    assert os.path.commonpath([root, res]) == root
    return res


def get_default_java():
    # This is probably the most friendly thing we can do short of detecting
    # java installations in various places depending on platform.
    # Having gained some experience, java is usually found in the PATH on
    # all three supported platforms, so this is no problem at all.
    return "java"


def get_default_config():
    return {
        "java.path": "java",
        "java.memory.min": "512M",
        "java.memory.max": "2G",
        "java.jvmargs": "-XX:+UnlockExperimentalVMOptions -XX:+UseG1GC -XX:G1NewSizePercent=20 -XX:G1ReservePercent=20 -XX:MaxGCPauseMillis=50 -XX:G1HeapRegionSize=32M",
    }


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


def write_profiles_dummy():
    # This file makes the forge installer happy.
    fname = get_filepath("launcher_profiles.json")
    with open(fname, "w") as fd:
        fd.write(r'{"profiles":{}}')


def file_verify_relative(path, sha1):
    abspath = get_filepath(path)
    return os.path.isfile(abspath) and file_sha1(abspath) == sha1


def check_directories():
    """Create directory structure for the application."""
    dirs = [
        "",
        "instances",
        "versions",
        "assets",
        "assets/indexes",
        "assets/objects",
        "assets/virtual",
        "libraries",
    ]
    for d in dirs:
        path = get_filepath(*d.split("/"))
        try:
            os.makedirs(path)
            logger.debug("Created dir: {}".format(path))
        except FileExistsError:
            pass


def assert_java(java):
    try:
        jinfo = get_java_info(java)
        jver = get_java_version(java)
        badjv = False
        if jinfo:
            badjv = not jinfo["java.version"].decode("ascii").startswith("1.8.0")
            bitness = jinfo.get("sun.arch.data.model", None).decode("ascii")
            if bitness and bitness != "64":
                logger.warn(
                    "You are not using 64-bit java. Things will probably not work."
                )
        else:
            badjv = "1.8.0_" not in jver

        logger.info("Using java version: {}".format(jver))

        if badjv:
            logger.warn(
                "Minecraft uses java 1.8.0 by default."
                " You may experience issues, especially with older versions of Minecraft."
            )

        return jinfo

    except FileNotFoundError:
        die(
            "Could not execute java at: {}. Have you installed it? Is it in yout PATH?".format(
                java
            )
        )


try:
    PLATFORM_MAP = {"darwin": "osx", "win32": "windows", "linux": "linux"}
    Env.platform = PLATFORM_MAP[sys.platform]
except KeyError:
    # This is probably not neccesary, as the game is not officialy supported
    # on other platforms and natives are not available. (Unless you compile
    # them and patch the corresponding version json)
    Env.platform = sys.platform
