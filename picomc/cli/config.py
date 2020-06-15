import click

from picomc.env import Env


@click.group()
def config_cli():
    """Configure picomc."""
    pass


@config_cli.command()
def show():
    """Print the current config."""

    for k, v in Env.gconf.bottom.items():
        if k not in Env.gconf:
            print("[default] {}: {}".format(k, v))
    for k, v in Env.gconf.items():
        print("{}: {}".format(k, v))


@config_cli.command("set")
@click.argument("key")
@click.argument("value")
def _set(key, value):
    Env.gconf[key] = value


@config_cli.command()
@click.argument("key")
def get(key):
    try:
        print(Env.gconf[key])
    except KeyError:
        print("No such item.")


@config_cli.command()
@click.argument("key")
def delete(key):
    try:
        del Env.gconf[key]
    except KeyError:
        print("No such item.")


def register_config_cli(picomc_cli):
    picomc_cli.add_command(config_cli, name="config")
