import click
from picomc import mod
from picomc.env import get_filepath


@click.group()
def mod_cli():
    pass


@mod_cli.group("loader")
def loader_cli():
    pass


@loader_cli.command("list")
def loader_list_cli():
    """List available mod loaders."""
    for loader in mod.LOADERS:
        print(loader._loader_name)


@loader_cli.group("install")
@click.pass_context
def loader_install_cli(ctx):
    ctx.ensure_object(dict)
    ctx.obj["VERSIONS_ROOT"] = get_filepath("versions")


for loader in mod.LOADERS:
    loader.register_cli(loader_install_cli)


def register_mod_cli(picomc_cli):
    picomc_cli.add_command(mod_cli, name="mod")
