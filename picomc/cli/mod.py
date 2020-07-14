from pathlib import Path

import click

from picomc import mod
from picomc.env import get_filepath


@click.group()
def mod_cli():
    """Helpers to install modded Minecraft."""
    pass


def list_loaders(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    for loader in mod.LOADERS:
        print(loader._loader_name)
    ctx.exit()


@mod_cli.group("loader")
@click.option(
    "--list",
    "-l",
    is_eager=True,
    is_flag=True,
    expose_value=False,
    callback=list_loaders,
    help="List available mod loaders",
)
@click.pass_context
def loader_cli(ctx):
    """Manage mod loaders.

    Loaders are customized Minecraft
    versions which can load other mods, e.g. Forge or Fabric.
    Installing a loader creates a new version which can be used by instances."""
    ctx.ensure_object(dict)

    ctx.obj["VERSIONS_ROOT"] = Path(get_filepath("versions"))
    ctx.obj["LIBRARIES_ROOT"] = Path(get_filepath("libraries"))
    pass


for loader in mod.LOADERS:
    loader.register_cli(loader_cli)


def register_mod_cli(picomc_cli):
    picomc_cli.add_command(mod_cli, name="mod")
