import click

from picomc.account import AccountError, OfflineAccount, OnlineAccount, RefreshError
from picomc.cli.utils import pass_account_manager
from picomc.yggdrasil import AuthenticationError


def account_cmd(fn):
    return click.argument("account")(fn)


@click.group()
def account_cli():
    """Manage your accounts."""
    pass


@account_cli.command("list")
@pass_account_manager
def _list(am):
    """List avaiable accounts."""
    alist = am.list()
    if alist:
        lines = ("{}{}".format("* " if am.is_default(u) else "  ", u) for u in alist)
        print("\n".join(lines))
    else:
        print("No accounts.")


@account_cli.command()
@account_cmd
@click.argument("mojang_username", default="")
@pass_account_manager
def create(am, account, mojang_username):
    """Create an account."""
    try:
        if mojang_username:
            acc = OnlineAccount.new(account, mojang_username)
        else:
            acc = OfflineAccount.new(account)
        am.add(acc)
    except AccountError as e:
        print(e)


@account_cli.command()
@account_cmd
@pass_account_manager
def authenticate(am, account):
    """Retrieve access token from Mojang servers using password."""
    import getpass

    try:
        a = am.get(account)
        p = getpass.getpass("Password: ")
        a.authenticate(p)
    except AuthenticationError as e:
        print(e)


@account_cli.command()
@account_cmd
@pass_account_manager
def refresh(am, account):
    """Refresh access token with Mojang servers."""
    try:
        a = am.get(account)
        a.refresh()
    except (AccountError, RefreshError) as e:
        print(e)


@account_cli.command()
@account_cmd
@pass_account_manager
def remove(am, account):
    """Remove the account."""
    try:
        am.remove(account)
    except AccountError as e:
        print(e)


@account_cli.command()
@account_cmd
@pass_account_manager
def setdefault(am, account):
    """Set the account as default."""
    try:
        default = am.get(account)
        am.set_default(default)
    except AccountError as e:
        print(e)


def register_account_cli(picomc_cli):
    picomc_cli.add_command(account_cli, name="account")
