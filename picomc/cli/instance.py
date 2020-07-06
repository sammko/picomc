import functools

import click
from picomc.account import AccountError
from picomc.env import Env, get_filepath
from picomc.instance import Instance
from picomc.logging import logger
from picomc.utils import die, sanitize_name


def instance_list():
    import os

    yield from (
        name for name in os.listdir(get_filepath("instances")) if Instance.exists(name)
    )


def instance_cmd(fn):
    @click.argument("instance_name")
    @functools.wraps(fn)
    def inner(*args, instance_name, **kwargs):
        return fn(*args, instance_name=sanitize_name(instance_name), **kwargs)

    return inner


@click.group()
def instance_cli():
    """Manage your instances."""
    pass


@instance_cli.command()
@instance_cmd
@click.argument("version", default="latest")
def create(instance_name, version):
    """Create a new instance."""
    if Instance.exists(instance_name):
        logger.error("An instance with that name already exists.")
        return
    with Instance(instance_name) as inst:
        inst.populate(version)


@instance_cli.command()
def list():
    """Show a list of instances."""
    print("\n".join(instance_list()))


@instance_cli.command()
@instance_cmd
def delete(instance_name):
    """Delete the instance (from disk)."""
    if Instance.exists(instance_name):
        Instance.delete(instance_name)
    else:
        logger.error("No such instance exists.")


@instance_cli.command()
@instance_cmd
@click.option("--verify", is_flag=True, default=False)
@click.option("--account", default=None)
@click.option("--version-override", default=None)
def launch(instance_name, account, version_override, verify):
    """Launch the instance."""
    if account is None:
        account = Env.am.get_default()
    else:
        account = Env.am.get(account)
    if not Instance.exists(instance_name):
        logger.error("No such instance exists.")
        return
    with Instance(instance_name) as inst:
        try:
            inst.launch(account, version_override, verify_hashes=verify)
        except AccountError as e:
            logger.error("Not launching due to account error: {}".format(e))


@instance_cli.command("natives")
@instance_cmd
def extract_natives(instance_name):
    """Extract natives and leave them on disk"""
    if not Instance.exists(instance_name):
        die("No such instance exists.")
    with Instance(instance_name) as inst:
        inst.extract_natives()


@instance_cli.command("dir")
@instance_cmd
def _dir(instance_name):
    """Print root directory of instance."""
    if not instance_name:
        print(get_filepath("instances"))
    else:
        # Careful, if configurable instance dirs are added, this breaks.
        print(get_filepath("instances", instance_name))


@instance_cli.command("rename")
@instance_cmd
@click.argument("new_name")
def rename(instance_name, new_name):
    new_name = sanitize_name(new_name)
    if Instance.exists(instance_name):
        if Instance.exists(new_name):
            die("Instance with target name already exists.")
        Instance.rename(instance_name, new_name)
    else:
        die("No such instance exists.")


@instance_cli.group("config")
@instance_cmd
@click.pass_context
def config_cli(ctx, instance_name):
    """Configure an instance."""
    if Instance.exists(instance_name):
        ctx.obj = Env.estack.enter_context(Instance(instance_name)).config
    else:
        die("No such instance exists.")


@config_cli.command("show")
@click.pass_obj
def config_show(config):
    """Print the current instance config."""

    for k, v in config.items():
        print("{}: {}".format(k, v))


@config_cli.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_obj
def config_set(config, key, value):
    """Set an instance config value."""
    config[key] = value


@config_cli.command("get")
@click.argument("key")
@click.pass_obj
def config_get(config, key):
    """Print an instance config value."""
    try:
        print(config[key])
    except KeyError:
        print("No such item.")


@config_cli.command("delete")
@click.argument("key")
@click.pass_obj
def config_delete(config, key):
    """Delete a key from the instance config."""
    try:
        del config[key]
    except KeyError:
        print("No such item.")


def register_instance_cli(picomc_cli):
    picomc_cli.add_command(instance_cli, name="instance")
