import click

from picomc import mod
from picomc.cli.utils import pass_launcher
from picomc.utils import Directory


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
@pass_launcher
@click.pass_context
def loader_cli(ctx, launcher):
    """Manage mod loaders.

    Loaders are customized Minecraft
    versions which can load other mods, e.g. Forge or Fabric.
    Installing a loader creates a new version which can be used by instances."""
    ctx.ensure_object(dict)

    ctx.obj["VERSIONS_ROOT"] = launcher.get_path(Directory.VERSIONS)
    ctx.obj["LIBRARIES_ROOT"] = launcher.get_path(Directory.LIBRARIES)


for loader in mod.LOADERS:
    loader.register_cli(loader_cli)


def register_mod_cli(picomc_cli):
    picomc_cli.add_command(mod_cli, name="mod")
