import platform
import sys


class OsInfo:
    platform: str
    arch: str

    def __init__(self):
        self.platform = self.get_platform()
        self.arch = self.get_arch()

    @staticmethod
    def get_platform():
        return {"darwin": "osx", "win32": "windows"}.get(sys.platform, sys.platform)

    @staticmethod
    def get_arch():
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

    @staticmethod
    def get_os_version(java_info):
        if not java_info:
            return None, None
        version = java_info.get("os.version")
        return version


osinfo = OsInfo()
