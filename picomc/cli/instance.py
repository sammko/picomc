import click

from picomc.account import AccountError
from picomc.env import Env
from picomc.instance import Instance
from picomc.logging import logger
from picomc.utils import get_filepath, sanitize_name


def instance_list():
    import os

    yield from (
        name for name in os.listdir(get_filepath("instances")) if Instance.exists(name)
    )


g_iname = ""


@click.group()
@click.argument("instance_name")
def instance_cli(instance_name):
    """Manage your instances."""
    instance_name = sanitize_name(instance_name)
    global g_iname
    g_iname = instance_name


@click.command()
@click.argument("instance_name")
@click.argument("version", default="latest")
def create_instance(instance_name, version):
    """Create a new instance."""
    if Instance.exists(instance_name):
        logger.error("An instance with that name already exists.")
        return
    with Instance(instance_name) as inst:
        inst.populate(version)


@click.command()
def list_instances():
    """Show a list of instances."""
    print("\n".join(instance_list()))


@instance_cli.command()
def remove():
    if Instance.exists(g_iname):
        Instance.remove(g_iname)
    else:
        logger.error("No such instance exists.")


@instance_cli.command()
@click.option("--account", default=None)
@click.option("--version-override", default=None)
def launch(account, version_override):
    """Launch the instance."""
    if account is None:
        account = Env.am.get_default()
    else:
        account = Env.am.get(account)
    if not Instance.exists(g_iname):
        logger.error("No such instance exists.")
        return
    with Instance(g_iname) as inst:
        try:
            inst.launch(account, version_override)
        except AccountError as e:
            logger.error("Not launching due to account error: {}".format(e))


@instance_cli.command()
def dir():
    """Print root directory of instance."""
    if not g_iname:
        print(get_filepath("instances"))
    else:
        # Careful, if configurable instance dirs are added, this breaks.
        print(get_filepath("instances", g_iname))


def register_instance_cli(picomc_cli):
    picomc_cli.add_command(instance_cli, name="instance")
    picomc_cli.add_command(create_instance)
    picomc_cli.add_command(list_instances)
