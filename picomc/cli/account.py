import click

from picomc.account import (
    AccountError,
    MicrosoftAccount,
    OfflineAccount,
    OnlineAccount,
    RefreshError,
)
from picomc.cli.utils import pass_account_manager
from picomc.logging import logger
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
        logger.info("No accounts.")


@account_cli.command()
@account_cmd
@click.argument("mojang_username", required=False)
@click.option("--ms", "--microsoft", "microsoft", is_flag=True, default=False)
@pass_account_manager
def create(am, account, mojang_username, microsoft):
    """Create an account."""
    try:
        if mojang_username:
            if microsoft:
                logger.error("Do not use --microsoft with mojang_username argument")
                return
            acc = OnlineAccount.new(am, account, mojang_username)
        elif microsoft:
            acc = MicrosoftAccount.new(am, account)
        else:
            acc = OfflineAccount.new(am, account)
        am.add(acc)
    except AccountError as e:
        logger.error("Could not create account: %s", e)


@account_cli.command()
@account_cmd
@pass_account_manager
def authenticate(am, account):
    """Retrieve access token from Mojang servers using password."""

    try:
        a = am.get(account)
    except AccountError:
        logger.error("AccountError", exc_info=True)
        return

    try:
        if isinstance(a, OfflineAccount):
            logger.error("Offline accounts cannot be authenticated")
        elif isinstance(a, OnlineAccount):
            import getpass

            p = getpass.getpass("Password: ")
            a.authenticate(p)
        elif isinstance(a, MicrosoftAccount):
            a.authenticate()
        else:
            logger.error("Unknown account type")
    except AuthenticationError as e:
        logger.error("Authentication failed: %s", e)


@account_cli.command()
@account_cmd
@pass_account_manager
def refresh(am, account):
    """Refresh access token with Mojang servers."""
    try:
        a = am.get(account)
        a.refresh()
    except (AccountError, RefreshError) as e:
        logger.error("Could not refresh account: %s", e)


@account_cli.command()
@account_cmd
@pass_account_manager
def remove(am, account):
    """Remove the account."""
    try:
        am.remove(account)
    except AccountError as e:
        logger.error("Could not remove account: %s", e)


@account_cli.command()
@account_cmd
@pass_account_manager
def setdefault(am, account):
    """Set the account as default."""
    try:
        default = am.get(account)
        am.set_default(default)
    except AccountError as e:
        logger.error("Could not set default account: %s", e)


def register_account_cli(picomc_cli):
    picomc_cli.add_command(account_cli, name="account")
