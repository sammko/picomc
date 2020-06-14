import os
import re
import shutil
import subprocess
import zipfile
from platform import architecture
from string import Template

import click
import picomc
from picomc.account import AccountError
from picomc.config import Config
from picomc.env import Env, get_filepath
from picomc.logging import logger
from picomc.utils import assert_java, join_classpath


class NativesExtractor:
    def __init__(self, instance, vobj):
        self.instance = instance
        self.vobj = vobj
        self.ndir = get_filepath("instances", instance.name, "natives")

    def __enter__(self):
        os.makedirs(self.ndir, exist_ok=True)
        dedup = set()
        for fullpath in self.vobj.lib_filenames(natives=True):
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

    def __exit__(self, ext_type, exc_value, traceback):
        logger.debug("Cleaning up natives.")
        shutil.rmtree(self.ndir)


def sanitize_name(name):
    return name.replace("..", "_").replace("/", "_")


def process_arguments(arguments_dict, java_info):
    def get_os_info():
        version = java_info.get("os.version", None)
        arch = java_info.get("os.arch", None)
        if not arch:
            arch = {"32": "x86"}.get(architecture()[0][:2], "?")
        return version, arch

    def match_rule(rule):
        # This launcher currently does not support any of the extended
        # features, which currently include at least:
        #   - is_demo_user
        #   - has_custom_resolution
        # It is not clear whether an `os` and `features` matcher may
        # be present simultaneously - assuming not.
        if "features" in rule:
            return False

        if "os" in rule:
            os_version, os_arch = get_os_info()

            osmatch = True
            if "name" in rule["os"]:
                osmatch = osmatch and rule["os"]["name"] == Env.platform
            if "arch" in rule["os"]:
                osmatch = osmatch and rule["os"]["arch"] == os_arch
            if "version" in rule["os"]:
                osmatch = osmatch and re.match(rule["os"]["version"], os_version)
            return osmatch

        logger.warn("Not matching unknown rule {}".format(rule.keys()))
        return False

    def subproc(obj):
        args = []
        for a in obj:
            if isinstance(a, str):
                args.append(a)
            else:
                if "rules" in a:
                    sat = False
                    for rule in a["rules"]:
                        m = match_rule(rule)
                        if m:
                            sat = rule["action"] == "allow"
                    if not sat:
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
    def __init__(self, name):
        self.name = sanitize_name(name)

    def __enter__(self):
        self.config = Config(
            get_filepath("instances", self.name, "config.json"), bottom=Env.gconf
        )
        Env.commit_manager.add(self.config)
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        pass

    def get_java(self):
        return self.config["java.path"]

    def populate(self, version):
        self.config["version"] = version

    def launch(self, account, version=None):
        vobj = Env.vm.get_version(version or self.config["version"])
        logger.info("Launching instance {}!".format(self.name))
        logger.info("Using minecraft version: {}".format(vobj.version_name))
        logger.info("Using account: {}".format(account))
        gamedir = get_filepath("instances", self.name, "minecraft")
        os.makedirs(gamedir, exist_ok=True)
        vobj.prepare_launch(gamedir)
        # Do this here so that configs are not needlessly overwritten after
        # the game quits
        Env.commit_manager.commit_all_dirty()
        with NativesExtractor(self, vobj):
            self._exec_mc(account, vobj, gamedir)

    def _exec_mc(self, account, v, gamedir):
        java = [self.get_java()]
        java_info = assert_java(java[0])

        java.append("-Xms{}".format(self.config["java.memory.min"]))
        java.append("-Xmx{}".format(self.config["java.memory.max"]))
        java += self.config["java.jvmargs"].split()
        libs = list(v.lib_filenames())
        libs.append(v.jarfile)
        classpath = join_classpath(*libs)

        version_type, user_type = (
            ("picomc", "mojang") if account.online else ("picomc/offline", "offline")
        )

        natives = get_filepath("instances", self.name, "natives")

        mc = v.vspec.mainClass

        if hasattr(v.vspec, "minecraftArguments"):
            mcargs = v.vspec.minecraftArguments.split()
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

        account.refresh()

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
                assets_root=get_filepath("assets"),
                assets_index_name=v.vspec.assetIndex["id"],
                game_assets=v.get_virtual_asset_path(),
            )
            smcargs.append(res)

        fargs = java + sjvmargs + [mc] + smcargs
        logger.debug("Launching: " + " ".join(fargs))
        subprocess.run(fargs, cwd=gamedir)

    @staticmethod
    def exists(name):
        name = sanitize_name(name)
        return os.path.exists(get_filepath("instances", name, "config.json"))

    @staticmethod
    def remove(name):
        shutil.rmtree(get_filepath("instances", name))


def instance_list():
    import os

    yield from (
        name for name in os.listdir(get_filepath("instances")) if Instance.exists(name)
    )


g_iname = ""


@click.group()
@click.argument("instance_name")
def instance_cli(instance_name):
    """Manage your instances."""
    instance_name = sanitize_name(instance_name)
    global g_iname
    g_iname = instance_name


@click.command()
@click.argument("instance_name")
@click.argument("version", default="latest")
def create_instance(instance_name, version):
    """Create a new instance."""
    if Instance.exists(instance_name):
        logger.error("An instance with that name already exists.")
        return
    with Instance(instance_name) as inst:
        inst.populate(version)


@click.command()
def list_instances():
    """Show a list of instances."""
    print("\n".join(instance_list()))


@instance_cli.command()
def remove():
    if Instance.exists(g_iname):
        Instance.remove(g_iname)
    else:
        logger.error("No such instance exists.")


@instance_cli.command()
@click.option("--account", default=None)
@click.option("--version-override", default=None)
def launch(account, version_override):
    """Launch the instance."""
    if account is None:
        account = Env.am.get_default()
    else:
        account = Env.am.get(account)
    if not Instance.exists(g_iname):
        logger.error("No such instance exists.")
        return
    with Instance(g_iname) as inst:
        try:
            inst.launch(account, version_override)
        except AccountError as e:
            logger.error("Not launching due to account error: {}".format(e))


@instance_cli.command()
def dir():
    """Print root directory of instance."""
    if not g_iname:
        print(get_filepath("instances"))
    else:
        # Careful, if configurable instance dirs are added, this breaks.
        print(get_filepath("instances", g_iname))


def register_instance_cli(picomc_cli):
    picomc_cli.add_command(instance_cli, name="instance")
    picomc_cli.add_command(create_instance)
    picomc_cli.add_command(list_instances)
