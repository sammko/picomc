import click

from picomc.account import AccountError, OfflineAccount, OnlineAccount, RefreshError
from picomc.env import Env
from picomc.yggdrasil import AuthenticationError

g_aname = None


@click.group()
@click.argument("account_name")
def account_cli(account_name):
    """Manage your accounts."""
    global g_aname
    g_aname = account_name


@click.command()
def list_accounts():
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


@click.command()
@click.argument("account_name")
@click.argument("mojang_username", default="")
def create_account(account_name, mojang_username):
    """Create an account."""
    try:
        if mojang_username:
            acc = OnlineAccount.new(account_name, mojang_username)
        else:
            acc = OfflineAccount.new(account_name)
        Env.am.add(acc)
    except AccountError as e:
        print(e)


@account_cli.command()
def authenticate():
    """Retrieve access token from Mojang servers using password."""
    import getpass

    try:
        a = Env.am.get(g_aname)
        # add some output here
        p = getpass.getpass("Password: ")
        a.authenticate(p)
        Env.am.save(a)
    except AuthenticationError as e:
        print(e)


@account_cli.command()
def refresh():
    """Refresh access token with Mojang servers."""
    try:
        a = Env.am.get(g_aname)
        a.refresh()
    except (AccountError, RefreshError) as e:
        print(e)


@account_cli.command()
def remove():
    """Remove the account."""
    try:
        Env.am.remove(g_aname)
    except AccountError as e:
        print(e)


@account_cli.command()
def setdefault():
    """Set the account as default."""
    try:
        default = Env.am.get(g_aname)
        Env.am.set_default(default)
    except AccountError as e:
        print(e)


def register_account_cli(picomc_cli):
    picomc_cli.add_command(account_cli, name="account")
    picomc_cli.add_command(create_account)
    picomc_cli.add_command(list_accounts)
