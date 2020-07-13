import click

from picomc import mod
from picomc.env import get_filepath


@click.group()
def mod_cli():
    pass


def list_loaders(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    print("list")
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
)
@click.pass_context
def loader_cli(ctx):
    ctx.ensure_object(dict)

    ctx.obj["VERSIONS_ROOT"] = get_filepath("versions")
    ctx.obj["LIBRARIES_ROOT"] = get_filepath("libraries")
    pass


for loader in mod.LOADERS:
    loader.register_cli(loader_cli)


def register_mod_cli(picomc_cli):
    picomc_cli.add_command(mod_cli, name="mod")
