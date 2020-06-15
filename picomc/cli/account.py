import click

from picomc.account import AccountError, OfflineAccount, OnlineAccount, RefreshError
from picomc.env import Env
from picomc.yggdrasil import AuthenticationError


def account_cmd(fn):
    return click.argument("account")(fn)


@click.group()
def account_cli():
    """Manage your accounts."""
    pass


@account_cli.command("list")
def _list():
    """List avaiable accounts."""
    alist = Env.am.list()
    if alist:
        print(
            "\n".join(
                "{}{}".format("* " if Env.am.is_default(u) else "  ", u) for u in alist
            )
        )
    else:
        print("No accounts.")


@account_cli.command()
@account_cmd
@click.argument("mojang_username", default="")
def create(account, mojang_username):
    """Create an account."""
    try:
        if mojang_username:
            acc = OnlineAccount.new(account, mojang_username)
        else:
            acc = OfflineAccount.new(account)
        Env.am.add(acc)
    except AccountError as e:
        print(e)


@account_cli.command()
@account_cmd
def authenticate(account):
    """Retrieve access token from Mojang servers using password."""
    import getpass

    try:
        a = Env.am.get(account)
        # add some output here
        p = getpass.getpass("Password: ")
        a.authenticate(p)
        Env.am.save(a)
    except AuthenticationError as e:
        print(e)


@account_cli.command()
@account_cmd
def refresh(account):
    """Refresh access token with Mojang servers."""
    try:
        a = Env.am.get(account)
        a.refresh()
    except (AccountError, RefreshError) as e:
        print(e)


@account_cli.command()
@account_cmd
def remove(account):
    """Remove the account."""
    try:
        Env.am.remove(account)
    except AccountError as e:
        print(e)


@account_cli.command()
@account_cmd
def setdefault(account):
    """Set the account as default."""
    try:
        default = Env.am.get(account)
        Env.am.set_default(default)
    except AccountError as e:
        print(e)


def register_account_cli(picomc_cli):
    picomc_cli.add_command(account_cli, name="account")
