from contextlib import ExitStack

import click
import picomc.logging
from picomc.account import AccountManager, register_account_cli
from picomc.config import register_config_cli
from picomc.globals import APP_ROOT, _ctx_ptr, ctx
from picomc.instances import register_instance_cli
from picomc.logging import logger
from picomc.utils import ConfigLoader, check_directories, write_profiles_dummy
from picomc.version import VersionManager, register_version_cli


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

    write_profiles_dummy()

    logger.debug(
        "Using application directory: {}".format(picomc.globals.APP_ROOT))

    am = es.enter_context(AccountManager())
    ctx.am = am
    default_config = {
        'java.path': 'java',
        'java.memory.min': '128M',
        'java.memory.max': '1G',
        'java.jvmargs': ''
    }
    gconf = es.enter_context(
        ConfigLoader('config.json', defaults=default_config))
    ctx.gconf = gconf
    ctx.vm = VersionManager()


def main():
    class Context:
        pass

    c = Context()
    _ctx_ptr.set(c)
    with ExitStack() as estack:
        picomc_cli(obj=estack)


register_account_cli(picomc_cli)
register_version_cli(picomc_cli)
register_instance_cli(picomc_cli)
register_config_cli(picomc_cli)
