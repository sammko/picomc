import logging
from contextlib import ExitStack

import click

import picomc.logging
from picomc.accounts import AccountManager, accounts_cli
from picomc.config import config_cli
from picomc.globals import APP_ROOT, _ctx_ptr, ctx
from picomc.instances import instance_cli
from picomc.utils import PersistentConfig, check_directories, get_default_java
from picomc.versions import VersionManager, version_cli

logger = logging.getLogger('picomc.cli')


@click.group()
@click.option('--debug/--no-debug', default=False)
@click.option(
    '-r', '--root', help="Application data directory.", default=APP_ROOT)
@click.pass_obj
def picomc_cli(es, debug, root):
    """picomc is a minimal CLI Minecraft launcher."""
    picomc.logging.initialize(debug)
    picomc.globals.APP_ROOT = root
    check_directories()

    logger.debug(
        "Using application directory: {}".format(picomc.globals.APP_ROOT))

    am = es.enter_context(AccountManager())
    ctx.am = am
    gconf = es.enter_context(
        PersistentConfig(
            'config.json', defaults=dict(java_path=get_default_java())))
    ctx.gconf = gconf
    ctx.vm = VersionManager()


def main():
    class Context:
        pass

    c = Context()
    _ctx_ptr.set(c)
    with ExitStack() as estack:
        picomc_cli(obj=estack)


picomc_cli.add_command(accounts_cli, name="account")
picomc_cli.add_command(version_cli, name="version")
picomc_cli.add_command(instance_cli, name="instance")
picomc_cli.add_command(config_cli, name="config")
