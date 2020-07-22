import os
import sys
from pathlib import Path

from picomc.logging import logger


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
        logger.warning(
            "Detected Microsoft Store Python distribution. It is recommended to install Python using the official installer or a package manager like Chocolatey."
        )
        appdata = get_appdata_uwp()
        logger.warning("Using redirected AppData directory: {}".format(appdata))
        return Path(appdata)
    else:
        return Path(os.getenv("APPDATA"))
