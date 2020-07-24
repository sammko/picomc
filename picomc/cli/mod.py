import click

from picomc import mod


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
def loader_cli():
    """Manage mod loaders.

    Loaders are customized Minecraft
    versions which can load other mods, e.g. Forge or Fabric.
    Installing a loader creates a new version which can be used by instances."""
    pass


for loader in mod.LOADERS:
    loader.register_cli(loader_cli)


@mod_cli.group("pack")
def pack_cli():
    """Install mod packs."""
    pass


for pack in mod.PACKS:
    pack.register_cli(pack_cli)


def register_mod_cli(picomc_cli):
    picomc_cli.add_command(mod_cli, name="mod")
