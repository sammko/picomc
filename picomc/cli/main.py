import os
from functools import partial
from pathlib import Path

import click

from picomc import logging
from picomc.launcher import Launcher
from picomc.logging import logger


def print_version(printer):
    import platform

    from picomc import __version__

    printer("picomc, version {}".format(__version__))
    printer("Python {}".format(platform.python_version()))


def click_print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    print_version(click.echo)
    ctx.exit()


@click.group()
@click.option("--debug/--no-debug", default=None)
@click.option("-r", "--root", help="Application data directory.", default=None)
@click.option(
    "--version",
    is_flag=True,
    callback=click_print_version,
    expose_value=False,
    is_eager=True,
)
@click.pass_context
def picomc_cli(ctx: click.Context, debug, root):
    """picomc is a minimal CLI Minecraft launcher."""
    logging.initialize(debug)

    if debug:
        print_version(logger.debug)

    final_root = os.getenv("PICOMC_ROOT")
    if root is not None:
        final_root = root

    if final_root is not None:
        final_root = Path(final_root).resolve()

    launcher_cm = Launcher.new(root=final_root, debug=debug)
    launcher = launcher_cm.__enter__()
    ctx.call_on_close(partial(launcher_cm.__exit__, None, None, None))

    ctx.obj = launcher
