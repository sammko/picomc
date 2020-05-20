import getpass
import os
from contextlib import ExitStack

import click
import picomc.logging
from picomc.account import (
    AccountError,
    AccountManager,
    OfflineAccount,
    OnlineAccount,
    register_account_cli,
)
from picomc.config import register_config_cli
from picomc.env import Env, get_default_root, get_filepath
from picomc.instances import Instance, register_instance_cli
from picomc.logging import logger
from picomc.utils import ConfigLoader, write_profiles_dummy
from picomc.version import VersionManager, register_version_cli

__version__ = "0.2.2"


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


@click.group()
@click.option("--debug/--no-debug", default=False)
@click.option(
    "-r", "--root", help="Application data directory.", default=get_default_root()
)
@click.version_option(version=__version__, prog_name="picomc")
def picomc_cli(debug, root):
    """picomc is a minimal CLI Minecraft launcher."""
    picomc.logging.initialize(debug)
    Env.debug = debug
    root_env = os.getenv("PICOMC_ROOT")
    if root_env is not None:
        root = root_env
    Env.app_root = os.path.abspath(root)
    check_directories()

    write_profiles_dummy()

    logger.debug("Using application directory: {}".format(Env.app_root))

    Env.am = Env.estack.enter_context(AccountManager())
    default_config = {
        "java.path": "java",
        "java.memory.min": "512M",
        "java.memory.max": "2G",
        "java.jvmargs": "-XX:+UnlockExperimentalVMOptions -XX:+UseG1GC -XX:G1NewSizePercent=20 -XX:G1ReservePercent=20 -XX:MaxGCPauseMillis=50 -XX:G1HeapRegionSize=32M",
    }
    Env.gconf = Env.estack.enter_context(
        ConfigLoader("config.json", defaults=default_config)
    )
    Env.vm = VersionManager()


register_account_cli(picomc_cli)
register_version_cli(picomc_cli)
register_instance_cli(picomc_cli)
register_config_cli(picomc_cli)


@picomc_cli.command()
@click.argument("version", default="latest")
def play(version):
    """Play Minecraft without having to deal with stuff"""
    try:
        account = Env.am.get_default()
    except AccountError:
        username = input("Choose your account name:\n> ")
        email = input(
            "\nIf you have a mojang account with a Minecraft license,\n"
            "enter your email. Leave blank if you want to play offline:\n> "
        )
        if email:
            account = OnlineAccount.new(username, email)
            password = getpass.getpass("\nPassword:\n> ")
            account.authenticate(password)
        else:
            account = OfflineAccount.new(username)
        Env.am.add(account)
    ready = Instance.exists("default")
    with Instance("default") as inst:
        if not ready:
            inst.populate("latest")
        inst.launch(account, version)


def main():
    with ExitStack() as estack:
        Env.estack = estack
        picomc_cli()
