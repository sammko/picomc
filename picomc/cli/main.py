import getpass
import os

import click

import picomc
import picomc.logging
from picomc.account import AccountError, AccountManager, OfflineAccount, OnlineAccount
from picomc.config import CommitManager, Config
from picomc.env import Env, get_default_config, get_default_root
from picomc.instance import Instance
from picomc.logging import logger
from picomc.utils import check_directories, write_profiles_dummy
from picomc.version import VersionManager


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    from picomc import __version__

    click.echo("picomc, version {}".format(__version__))
    ctx.exit()


@click.group()
@click.option("--debug/--no-debug", default=None)
@click.option(
    "-r", "--root", help="Application data directory.", default=get_default_root()
)
@click.option(
    "--version", is_flag=True, callback=print_version, expose_value=False, is_eager=True
)
def picomc_cli(debug, root):
    """picomc is a minimal CLI Minecraft launcher."""
    picomc.logging.initialize(debug)
    Env.debug = debug
    Env.commit_manager = CommitManager()

    Env.estack.callback(lambda: Env.commit_manager.commit_all_dirty())
    root_env = os.getenv("PICOMC_ROOT")
    if root_env is not None:
        root = root_env
    Env.app_root = os.path.abspath(root)
    check_directories()

    write_profiles_dummy()

    logger.debug("Using application directory: {}".format(Env.app_root))

    Env.gconf = Config("config.json", bottom=get_default_config())
    Env.commit_manager.add(Env.gconf)

    Env.am = Env.estack.enter_context(AccountManager())
    Env.vm = VersionManager()


@picomc_cli.command()
@click.argument("version", default=False)
@click.option("-a", "--account", "account_name")
def play(version, account_name):
    """Play Minecraft without having to deal with stuff"""
    if account_name:
        account = Env.am.get(account_name)
    else:
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
