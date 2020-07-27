import os
import shlex
import shutil
import subprocess
import zipfile
from operator import attrgetter
from pathlib import Path
from string import Template
from tempfile import mkdtemp

import requests

import picomc
from picomc import logging
from picomc.javainfo import assert_java
from picomc.logging import logger
from picomc.rules import match_ruleset
from picomc.utils import Directory, join_classpath, sanitize_name


class InstanceError(Exception):
    pass


class InstanceNotFoundError(InstanceError):
    pass


class NativesExtractor:
    def __init__(self, libraries_root, instance, natives):
        self.libraries_root = libraries_root
        self.instance = instance
        self.natives = natives
        self.ndir = mkdtemp(prefix="natives-", dir=instance.get_relpath())

    def get_natives_path(self):
        return self.ndir

    def extract(self):
        dedup = set()
        for library in self.natives:
            fullpath = library.get_abspath(self.libraries_root)
            if fullpath in dedup:
                logger.debug(
                    "Skipping duplicate natives archive: " "{}".format(fullpath)
                )
                continue
            dedup.add(fullpath)
            logger.debug("Extracting natives archive: {}".format(fullpath))
            with zipfile.ZipFile(fullpath) as zf:
                # TODO take exclude into account
                zf.extractall(path=self.ndir)

    def __enter__(self):
        self.extract()
        return self.ndir

    def __exit__(self, ext_type, exc_value, traceback):
        logger.debug("Cleaning up natives.")
        shutil.rmtree(self.ndir)


def process_arguments(arguments_dict, java_info):
    def subproc(obj):
        args = []
        for a in obj:
            if isinstance(a, str):
                args.append(a)
            else:
                if "rules" in a and not match_ruleset(a["rules"], java_info):
                    continue
                if isinstance(a["value"], list):
                    args.extend(a["value"])
                elif isinstance(a["value"], str):
                    args.append(a["value"])
                else:
                    logger.error("Unknown type of value field.")
        return args

    return (subproc(arguments_dict["game"]), subproc(arguments_dict.get("jvm")))


class Instance:
    def __init__(self, launcher, root, name):
        self.instance_manager = launcher.instance_manager
        self.launcher = launcher

        self.name = sanitize_name(name)
        self.libraries_root = self.launcher.get_path(Directory.LIBRARIES)
        self.assets_root = self.launcher.get_path(Directory.ASSETS)
        self.directory = root
        self.config = self.launcher.config_manager.get_instance_config(
            Path("instances", Path(self.name), "config.json")
        )

    def get_relpath(self, rel=""):
        return self.directory / rel

    def get_minecraft_dir(self):
        return self.get_relpath("minecraft")

    def get_java(self):
        return self.config["java.path"]

    def set_version(self, version):
        self.config["version"] = version

    def launch(self, account, version=None, verify_hashes=False):
        vobj = self.launcher.version_manager.get_version(
            version or self.config["version"]
        )
        logger.info("Launching instance: {}".format(self.name))
        if version or vobj.version_name == self.config["version"]:
            logger.info("Using version: {}".format(vobj.version_name))
        else:
            logger.info(
                "Using version: {} -> {}".format(
                    self.config["version"], vobj.version_name
                )
            )
        logger.info("Using account: {}".format(account))
        gamedir = self.get_minecraft_dir()
        os.makedirs(gamedir, exist_ok=True)

        java = self.get_java()
        java_info = assert_java(java)

        libraries = vobj.get_libraries(java_info)
        vobj.prepare_launch(gamedir, java_info, verify_hashes)
        # Do this here so that configs are not needlessly overwritten after
        # the game quits
        self.launcher.config_manager.commit_all_dirty()
        with NativesExtractor(
            self.libraries_root, self, filter(attrgetter("is_native"), libraries)
        ) as natives_dir:
            self._exec_mc(
                account,
                vobj,
                java,
                java_info,
                gamedir,
                filter(attrgetter("is_classpath"), libraries),
                natives_dir,
                verify_hashes,
            )

    def extract_natives(self):
        vobj = self.launcher.version_manager.get_version(self.config["version"])
        java_info = assert_java(self.get_java())
        vobj.download_libraries(java_info, verify_hashes=True)
        libs = vobj.get_libraries(java_info)
        ne = NativesExtractor(
            self.libraries_root, self, filter(attrgetter("is_native"), libs)
        )
        ne.extract()
        logger.info("Extracted natives to {}".format(ne.get_natives_path()))

    def _exec_mc(
        self, account, v, java, java_info, gamedir, libraries, natives, verify_hashes
    ):
        libs = [lib.get_abspath(self.libraries_root) for lib in libraries]
        libs.append(v.jarfile)
        classpath = join_classpath(*libs)

        version_type, user_type = (
            ("picomc", "mojang") if account.online else ("picomc/offline", "offline")
        )

        mc = v.vspec.mainClass

        if hasattr(v.vspec, "minecraftArguments"):
            mcargs = shlex.split(v.vspec.minecraftArguments)
            sjvmargs = ["-Djava.library.path={}".format(natives), "-cp", classpath]
        elif hasattr(v.vspec, "arguments"):
            mcargs, jvmargs = process_arguments(v.vspec.arguments, java_info)
            sjvmargs = []
            for a in jvmargs:
                tmpl = Template(a)
                res = tmpl.substitute(
                    natives_directory=natives,
                    launcher_name="picomc",
                    launcher_version=picomc.__version__,
                    classpath=classpath,
                )
                sjvmargs.append(res)

        try:
            account.refresh()
        except requests.exceptions.ConnectionError:
            logger.warning(
                "Failed to refresh account due to a connectivity error. Continuing."
            )

        smcargs = []
        for a in mcargs:
            tmpl = Template(a)
            res = tmpl.substitute(
                auth_player_name=account.gname,
                auth_uuid=account.uuid,
                auth_access_token=account.access_token,
                # Only used in old versions.
                auth_session="token:{}:{}".format(account.access_token, account.uuid),
                user_type=user_type,
                user_properties={},
                version_type=version_type,
                version_name=v.version_name,
                game_directory=gamedir,
                assets_root=self.assets_root,
                assets_index_name=v.vspec.assets,
                game_assets=v.get_virtual_asset_path(),
            )
            smcargs.append(res)

        my_jvm_args = [
            "-Xms{}".format(self.config["java.memory.min"]),
            "-Xmx{}".format(self.config["java.memory.max"]),
        ]

        if verify_hashes:
            my_jvm_args.append("-Dpicomc.verify=true")

        my_jvm_args += shlex.split(self.config["java.jvmargs"])

        fargs = [java] + sjvmargs + my_jvm_args + [mc] + smcargs
        if logging.debug:
            logger.debug("Launching: " + " ".join(fargs))
        else:
            logger.info("Launching the game")
        subprocess.run(fargs, cwd=gamedir)


class InstanceManager:
    def __init__(self, launcher):
        self.launcher = launcher
        self.instances_root = launcher.get_path(Directory.INSTANCES)

    def get_root(self, name):
        return self.instances_root / name

    def get(self, name):
        if not self.exists(name):
            raise InstanceNotFoundError(name)
        return Instance(self.launcher, self.get_root(name), name)

    def exists(self, name):
        return os.path.exists(self.get_root(name) / "config.json")

    def list(self):
        return (name for name in os.listdir(self.instances_root) if self.exists(name))

    def create(self, name, version):
        iroot = self.get_root(name)
        os.mkdir(iroot)
        inst = Instance(self.launcher, iroot, name)
        inst.set_version(version)
        inst.config.save()
        return inst

    def delete(self, name):
        shutil.rmtree(self.get_root(name))

    def rename(self, old, new):
        oldpath = self.get_root(old)
        newpath = self.get_root(new)
        assert not os.path.exists(newpath)
        assert os.path.exists(oldpath)
        shutil.move(oldpath, newpath)
