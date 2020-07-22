import click

from picomc.cli.utils import pass_global_config


@click.group()
def config_cli():
    """Configure picomc."""
    pass


@config_cli.command()
@pass_global_config
def show(cfg):
    """Print the current config."""

    for k, v in cfg.bottom.items():
        if k not in cfg:
            print("[default] {}: {}".format(k, v))
    for k, v in cfg.items():
        print("{}: {}".format(k, v))


@config_cli.command("set")
@click.argument("key")
@click.argument("value")
@pass_global_config
def _set(cfg, key, value):
    """Set a global config value."""
    cfg[key] = value


@config_cli.command()
@click.argument("key")
@pass_global_config
def get(cfg, key):
    """Print a global config value."""
    try:
        print(cfg[key])
    except KeyError:
        print("No such item.")


@config_cli.command()
@click.argument("key")
@pass_global_config
def delete(cfg, key):
    """Delete a key from the global config."""
    try:
        del cfg[key]
    except KeyError:
        print("No such item.")


def register_config_cli(picomc_cli):
    picomc_cli.add_command(config_cli, name="config")
