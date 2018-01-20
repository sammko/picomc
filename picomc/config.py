import click
from picomc.globals import gconf


@click.group()
def config_cli():
    """Configure picomc."""
    pass


@config_cli.command()
def show():
    """Print the current config."""
    for k, v in gconf.items():
        print("{}: {}".format(k, v))


@config_cli.command()
@click.argument('key')
@click.argument('value')
def set(key, value):
    gconf[key] = value


@config_cli.command()
@click.argument('key')
def get(key):
    try:
        print(gconf[key])
    except KeyError:
        print("No such attribute.")


@config_cli.command()
@click.argument('key')
def delete(key):
    delattr(gconf, key)


def register_config_cli(picomc_cli):
    picomc_cli.add_command(config_cli, name='config')
