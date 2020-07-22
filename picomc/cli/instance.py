import functools

import click

from picomc.account import AccountError
from picomc.cli.utils import pass_account_manager, pass_instance_manager, pass_launcher
from picomc.logging import logger
from picomc.utils import Directory, die, sanitize_name


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
@pass_instance_manager
def create(im, instance_name, version):
    """Create a new instance."""
    if im.exists(instance_name):
        logger.error("An instance with that name already exists.")
        return
    im.create(instance_name, version)


@instance_cli.command()
@pass_instance_manager
def list(im):
    """Show a list of instances."""
    print("\n".join(im.list()))


@instance_cli.command()
@instance_cmd
@pass_instance_manager
def delete(im, instance_name):
    """Delete the instance (from disk)."""
    if im.exists(instance_name):
        im.delete(instance_name)
    else:
        logger.error("No such instance exists.")


@instance_cli.command()
@instance_cmd
@click.option("--verify", is_flag=True, default=False)
@click.option("--account", default=None)
@click.option("--version-override", default=None)
@pass_instance_manager
@pass_account_manager
def launch(am, im, instance_name, account, version_override, verify):
    """Launch the instance."""
    if account is None:
        account = am.get_default()
    else:
        account = am.get(account)
    if not im.exists(instance_name):
        logger.error("No such instance exists.")
        return
    inst = im.get(instance_name)
    try:
        inst.launch(account, version_override, verify_hashes=verify)
    except AccountError as e:
        logger.error("Not launching due to account error: {}".format(e))


@instance_cli.command("natives")
@instance_cmd
@pass_instance_manager
def extract_natives(im, instance_name):
    """Extract natives and leave them on disk"""
    if not im.exists(instance_name):
        die("No such instance exists.")
    inst = im.get(instance_name)
    inst.extract_natives()


@instance_cli.command("dir")
@click.argument("instance_name", required=False)
@pass_instance_manager
@pass_launcher
def _dir(launcher, im, instance_name):
    """Print root directory of instance."""
    if not instance_name:
        # TODO
        print(launcher.get_path(Directory.INSTANCES))
    else:
        instance_name = sanitize_name(instance_name)
        print(im.get_root(instance_name))


@instance_cli.command("rename")
@instance_cmd
@click.argument("new_name")
@pass_instance_manager
def rename(im, instance_name, new_name):
    new_name = sanitize_name(new_name)
    if im.exists(instance_name):
        if im.exists(new_name):
            die("Instance with target name already exists.")
        im.rename(instance_name, new_name)
    else:
        die("No such instance exists.")


@instance_cli.group("config")
@instance_cmd
@pass_instance_manager
@click.pass_context
def config_cli(ctx, im, instance_name):
    """Configure an instance."""
    if im.exists(instance_name):
        ctx.obj = im.get(instance_name).config
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
