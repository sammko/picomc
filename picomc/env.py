import os
import platform
import sys
from contextlib import ExitStack
from os.path import expanduser, join

from picomc.javainfo import get_java_info, get_java_version
from picomc.logging import logger
from picomc.utils import die


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


def get_appdata_uwp():
    """Use SHGetKnownFolderPath to get the real location of AppData after redirection
    for the current UWP python installation."""
    import ctypes
    from ctypes import windll, wintypes
    from uuid import UUID

    # https://docs.microsoft.com/en-us/windows/win32/api/guiddef/ns-guiddef-guid
    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", wintypes.BYTE * 8),
        ]

        def __init__(self, uuidstr):
            uuid = UUID(uuidstr)
            ctypes.Structure.__init__(self)
            (
                self.Data1,
                self.Data2,
                self.Data3,
                self.Data4[0],
                self.Data4[1],
                rest,
            ) = uuid.fields
            for i in range(2, 8):
                self.Data4[i] = rest >> (8 - i - 1) * 8 & 0xFF

    SHGetKnownFolderPath = windll.shell32.SHGetKnownFolderPath
    SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(GUID),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    RoamingAppData = "{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}"
    KF_FLAG_RETURN_FILTER_REDIRECTION_TARGET = 0x00040000

    result = ctypes.c_wchar_p()
    guid = GUID(RoamingAppData)
    flags = KF_FLAG_RETURN_FILTER_REDIRECTION_TARGET
    if SHGetKnownFolderPath(ctypes.byref(guid), flags, 0, ctypes.byref(result)):
        raise ctypes.WinError()
    return result.value


def get_appdata():
    # If the used Python installation comes from the Microsoft Store, it is
    # subject to path redirection for the AppData folder. The paths then passed
    # to java are invalid. Instead figure out the real location on disk and use
    # that. Another option would be to use a completely different location
    # for all files, not sure which solution is better.
    # https://docs.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-behind-the-scenes

    # HACK: This check is relatively fragile
    if "WindowsApps\\PythonSoftwareFoundation" in sys.base_exec_prefix:
        logger.warn(
            "Detected Microsoft Store Python distribution. It is recommended to install Python using the official installer or a package manager like Chocolatey."
        )
        appdata = get_appdata_uwp()
        logger.warn("Using redirected AppData directory: {}".format(appdata))
        return appdata
    else:
        return os.getenv("APPDATA")


def get_default_root():
    logger.debug("Resolving default application root")
    MAP = {
        "linux": lambda: expanduser("~/.local/share/picomc"),
        "win32": lambda: join(get_appdata(), ".picomc"),
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


def get_os_version(java_info):
    if not java_info:
        return None, None
    version = java_info.get("os.version").decode("ascii")
    return version


def get_os_arch():
    mach = platform.machine().lower()
    if mach == "amd64":  # Windows 64-bit
        return "x86_64"
    elif mach in ("i386", "i486", "i586", "i686"):  # Linux 32-bit
        return "x86"
    elif mach == "aarch64":  # Linux
        return "arm64"
    else:
        # Windows 32-bit (x86) and Linux 64-bit (x86_64) return the expected
        # values by default. Unsupported architectures are left untouched.
        return mach
