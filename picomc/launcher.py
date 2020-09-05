import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path, PurePath

from picomc.account import AccountManager
from picomc.config import Config, ConfigManager
from picomc.instance import InstanceManager
from picomc.logging import logger
from picomc.utils import Directory, cached_property
from picomc.version import VersionManager
from picomc.windows import get_appdata


def get_default_root():
    logger.debug("Resolving default application root")
    platforms = {
        "linux": lambda: Path("~/.local/share/picomc").expanduser(),
        "win32": lambda: get_appdata() / ".picomc",
        "darwin": lambda: Path("~/Library/Application Support/picomc").expanduser(),
    }
    if sys.platform in platforms:
        return platforms[sys.platform]()
    else:
        # This is probably better than nothing and should be fine on most
        # widely-used platforms other than the supported ones. Too bad in
        # case of something exotic. Minecraft doesn't run on those anyway.
        return Path("~/.picomc").expanduser()


DIRECTORY_MAP = {
    Directory.ASSETS: PurePath("assets"),
    Directory.ASSET_INDEXES: PurePath("assets", "indexes"),
    Directory.ASSET_OBJECTS: PurePath("assets", "objects"),
    Directory.ASSET_VIRTUAL: PurePath("assets", "virtual"),
    Directory.INSTANCES: PurePath("instances"),
    Directory.LIBRARIES: PurePath("libraries"),
    Directory.VERSIONS: PurePath("versions"),
}


class Launcher:
    root: Path
    exit_stack: ExitStack
    debug: bool

    @cached_property
    def config_manager(self) -> ConfigManager:
        return self.exit_stack.enter_context(ConfigManager(self.root))

    @cached_property
    def account_manager(self) -> AccountManager:
        return AccountManager(self)

    @cached_property
    def version_manager(self) -> VersionManager:
        return VersionManager(self)

    @cached_property
    def instance_manager(self) -> InstanceManager:
        return InstanceManager(self)

    @cached_property
    def global_config(self) -> Config:
        return self.config_manager.global_config

    @classmethod
    @contextmanager
    def new(cls, *args, **kwargs):
        """Create a Launcher instance with the application root at the given
        location. This is a context manager and a Launcher instance is returned."""
        with ExitStack() as es:
            yield cls(es, *args, **kwargs)

    def __init__(self, exit_stack: ExitStack, root: Path = None, debug=False):
        """Create a Launcher instance reusing an existing ExitStack."""
        self.exit_stack = exit_stack
        self.debug = debug
        if root is None:
            root = get_default_root()
        self.root = root
        logger.debug("Using application directory: {}".format(self.root))
        self.ensure_filesystem()

    def get_path(self, *pathsegments) -> Path:
        """Constructs a path relative to the Launcher root. `pathsegments` is
        specified similarly to `pathlib.PurePath`. Additionally, if the first
        element of `pathsegments` is a `picomc.utils.Directory`, it is resolved."""
        it = iter(pathsegments)
        try:
            d = next(it)
            if isinstance(d, Directory):
                d = DIRECTORY_MAP[d]
            return self.root / d / PurePath(*it)
        except StopIteration:
            return self.root

    def write_profiles_dummy(self):
        """Writes a minimal launcher_profiles.json which is expected to exist
        by installers and tooling surrounding the vanilla launcher."""
        # This file makes the forge installer happy.
        fname = self.get_path("launcher_profiles.json")
        with open(fname, "w") as fd:
            fd.write(r'{"profiles":{}}')

    def ensure_filesystem(self):
        """Create directory structure for the application."""
        for d in DIRECTORY_MAP:
            path = self.get_path(d)
            try:
                path.mkdir(parents=True)
            except FileExistsError:
                pass
            else:
                logger.debug("Created dir: {}".format(path))
        self.write_profiles_dummy()
